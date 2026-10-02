"""Evaluate step verifiers on labelled cases built from gold reasoning graphs (src.verify.reference).

    python scripts/eval_verifiers.py --task math                       # sympy arithmetic verifier, GSM8K + SVAMP
    python scripts/eval_verifiers.py --task logic --verifiers symbolic nli cascade
    python scripts/eval_verifiers.py --task logic --verifiers nli --nli-model MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli

Writes results/verifiers/<task>_<verifier>.json (metrics) and _cases.jsonl (per-case predictions).
For the NLI verifier the cases are split by source problem into a calibration half and a test half:
temperature and flag threshold are fitted on the first, all reported numbers come from the second.
"""
import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.verify.base import INVALID, UNVERIFIABLE, CascadeVerifier
from src.verify.calibration import (auroc, best_threshold, binary_calibration, binary_metrics, fit_temperature,
                                    multiclass_calibration, per_class_metrics)
from src.verify.nli import LABELS

PW_META = "data/raw/proofwriter/proofwriter-dataset-V2020.12.3/OWA/depth-{depth}/meta-{split}.jsonl"


def load_cases(args) -> list:
    from src.verify import reference
    if args.task == "math":
        from datasets import load_dataset
        rows = load_dataset("openai/gsm8k", "main", split="test")
        rows = [rows[i] for i in range(min(args.n or len(rows), len(rows)))]
        cases = reference.gsm8k_cases(rows, seed=args.seed)
        with open("data/raw/SVAMP/SVAMP.json") as f:
            cases += reference.svamp_cases(json.load(f), seed=args.seed)
        return cases
    cases, _ = reference.proofwriter_cases(PW_META.format(depth=args.depth, split=args.split), max_steps=args.n or 500, seed=args.seed)
    return cases


def source_of(case) -> str:
    return case.case_id.rsplit("_s", 1)[0]


def in_calibration_half(case) -> bool:
    return int(hashlib.md5(source_of(case).encode()).hexdigest(), 16) % 2 == 0


def build_verifier(name: str, args):
    if name == "arithmetic":
        from src.verify.arithmetic import ArithmeticVerifier
        return ArithmeticVerifier()
    if name == "arithmetic_nogrounding":
        from src.verify.arithmetic import ArithmeticVerifier
        v = ArithmeticVerifier(check_grounding=False)
        v.name = name
        return v
    if name == "symbolic":
        from src.verify.logic import SymbolicLogicVerifier
        return SymbolicLogicVerifier()
    if name in ("nli", "cascade"):
        from src.verify.nli import HFNLIBackend, NLIVerifier
        if not hasattr(args, "_nli_backend"):
            args._nli_backend = HFNLIBackend(args.nli_model, batch_size=args.batch_size)
        nli = NLIVerifier(args._nli_backend, top_k_context=args.top_k)
        if name == "nli":
            return nli
        from src.verify.logic import SymbolicLogicVerifier
        return CascadeVerifier([SymbolicLogicVerifier(), nli])
    raise ValueError(name)


def run(verifier, cases, batch_size=64) -> list:
    if hasattr(verifier, "verify_batch"):
        out = []
        for i in range(0, len(cases), batch_size):
            out.extend(verifier.verify_batch([c.step for c in cases[i:i + batch_size]]))
            print(f"\r  {len(out)}/{len(cases)}", end="", file=sys.stderr, flush=True)
        print(file=sys.stderr)
        return out
    return [verifier.verify(c.step) for c in cases]


def summarize(cases, verdicts) -> dict:
    y = [c.invalid for c in cases]
    flag = [v.status == INVALID for v in verdicts]
    res = {"binary": binary_metrics(y, flag),
           "coverage": sum(v.status != UNVERIFIABLE for v in verdicts) / len(verdicts),
           "coverage_on_valid": _mean([v.status != UNVERIFIABLE for c, v in zip(cases, verdicts) if not c.invalid]),
           "auroc": auroc(y, [v.p_invalid for v in verdicts])}
    by_err = defaultdict(list)
    for c, v in zip(cases, verdicts):
        by_err[c.error_type or "valid"].append(v)
    res["detection_rate_by_error"] = {e: _mean([v.status == INVALID for v in vs]) for e, vs in sorted(by_err.items())}
    res["detection_rate_by_error"]["valid (false positive rate)"] = res["detection_rate_by_error"].pop("valid", 0.0)
    res["predicted_error_types"] = {e: dict(Counter(v.error_type or v.status for v in vs)) for e, vs in sorted(by_err.items())}
    by_ds = defaultdict(lambda: ([], []))
    for c, v in zip(cases, verdicts):
        by_ds[c.dataset][0].append(c.invalid)
        by_ds[c.dataset][1].append(v.status == INVALID)
    if len(by_ds) > 1:
        res["binary_by_dataset"] = {d: binary_metrics(*yv) for d, yv in by_ds.items()}
    return res


def nli_analysis(cases, verdicts) -> dict:
    """3-class metrics and calibration for verdicts that carry NLI logits; temperature/threshold fitted on the calibration half."""
    idx = [i for i, v in enumerate(verdicts) if v.probs and "logits" in v.probs]
    cal = [i for i in idx if in_calibration_half(cases[i])]
    test = [i for i in idx if not in_calibration_half(cases[i])]
    lab = {l: k for k, l in enumerate(LABELS)}

    def arrays(ix):
        return np.array([verdicts[i].probs["logits"] for i in ix]), [lab[cases[i].nli_label] for i in ix], [cases[i].invalid for i in ix]

    if len(cal) < 20 or len(test) < 20:
        return {"n_nli_verdicts": len(idx), "note": "too few steps reached the NLI verifier to calibrate"}
    lg_cal, y_cal, b_cal = arrays(cal)
    lg_test, y_test, b_test = arrays(test)
    temp = fit_temperature(lg_cal, y_cal)
    from src.verify.nli import softmax
    p_inv_cal = list(1 - softmax(lg_cal, temp)[:, 0])
    thr = best_threshold(b_cal, p_inv_cal)
    thr_fpr = best_threshold(b_cal, p_inv_cal, max_fpr=0.05)

    out = {"n_calibration": len(cal), "n_test": len(test), "temperature": temp,
           "threshold_best_f1": thr, "threshold_fpr_le_5pct": thr_fpr}
    for name, t in (("uncalibrated", 1.0), ("temperature_scaled", temp)):
        probs = softmax(lg_test, t)
        pred = [LABELS[k] for k in probs.argmax(1)]
        p_inv = 1 - probs[:, 0]
        out[name] = {
            "three_class": per_class_metrics([LABELS[k] for k in y_test], pred, list(LABELS)),
            "three_class_calibration": multiclass_calibration(lg_test, y_test, t),
            "binary_at_0.5": binary_metrics(b_test, list(p_inv >= 0.5)),
            "binary_calibration": binary_calibration(b_test, list(p_inv)),
            "auroc": auroc(b_test, list(p_inv)),
        }
    probs = softmax(lg_test, temp)
    out["binary_at_fitted_threshold"] = binary_metrics(b_test, list(1 - probs[:, 0] >= thr))
    out["binary_at_fpr5_threshold"] = binary_metrics(b_test, list(1 - probs[:, 0] >= thr_fpr))
    return out


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def eval_math_graphs(args):
    """Gold GSM8K solutions parsed by the team's graph builder, clean and with one injected error each."""
    import networkx as nx
    from datasets import load_dataset
    from src.verify.graph_math import GraphArithmeticVerifier
    from src.verify.reference import gsm8k_graph_cases

    rows = load_dataset("openai/gsm8k", "main", split="test")
    rows = [rows[i] for i in range(min(args.n or len(rows), len(rows)))]
    cases = gsm8k_graph_cases(rows, seed=args.seed)
    clean = [c for c in cases if not c.error_type]
    pert = [c for c in cases if c.error_type and c.target]
    print(f"{len(clean)} gold graphs, {len(pert)} with an injected error")
    os.makedirs(args.out, exist_ok=True)
    for grounding in (False, True):
        name = "graph_arithmetic" + ("" if grounding else "_nogrounding")
        v = GraphArithmeticVerifier(check_grounding=grounding)
        steps = flagged_steps = judged = graphs_flagged = 0
        for c in clean:
            vs = v.verify_graph(c.graph)
            steps += len(vs)
            judged += sum(x.status != UNVERIFIABLE for x in vs.values())
            flagged_steps += sum(x.status == INVALID for x in vs.values())
            graphs_flagged += any(x.status == INVALID for x in vs.values())
        by_err = defaultdict(lambda: Counter())
        for c in pert:
            vs = v.verify_graph(c.graph)
            flagged = {k for k, x in vs.items() if x.status == INVALID}
            below = nx.descendants(c.gold.to_networkx(), c.target)  # the perturbation may cut the edges it should follow
            t = by_err[c.error_type]
            t["n"] += 1
            t["detected"] += c.target in flagged
            t["exact"] += flagged == {c.target}
            t["first_flag_is_error"] += bool(flagged) and min(flagged, key=int) == c.target
            t["extra_downstream"] += len(flagged & below)
            t["extra_unrelated"] += len(flagged - below - {c.target})
        res = {"verifier": name, "n_gold_graphs": len(clean), "gold_step_fpr": flagged_steps / max(1, steps),
               "gold_judged_step_fpr": flagged_steps / max(1, judged), "gold_graph_fpr": graphs_flagged / len(clean),
               "gold_steps_judged": judged / max(1, steps), "perturbed": {}}
        print(f"== {name}\n  gold graphs: steps judged {res['gold_steps_judged']:.3f}  step FPR {res['gold_step_fpr']:.4f}  "
              f"graphs with a flag {res['gold_graph_fpr']:.3f}")
        tot = Counter()
        for e, t in sorted(by_err.items()):
            tot.update(t)
            res["perturbed"][e] = {k: t[k] / t["n"] for k in t if k != "n"} | {"n": t["n"]}
        res["perturbed"]["all"] = {k: tot[k] / tot["n"] for k in tot if k != "n"} | {"n": tot["n"]}
        for e, r in res["perturbed"].items():
            print(f"  {e:14} n={r['n']:4}  detected {r['detected']:.3f}  exact localisation {r['exact']:.3f}  "
                  f"first flag = error {r['first_flag_is_error']:.3f}  extra flags/graph: downstream {r['extra_downstream']:.3f} "
                  f"unrelated {r['extra_unrelated']:.3f}")
        with open(os.path.join(args.out, f"math_graph_{name}_n{len(clean)}.json"), "w") as f:
            json.dump(res, f, indent=2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", choices=["math", "math-graph", "logic"], required=True)
    ap.add_argument("--verifiers", nargs="+", default=None)
    ap.add_argument("--n", type=int, default=None, help="math: GSM8K problems; logic: gold proof steps (default 500)")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--split", default="test")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--nli-model", default="MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--top-k", type=int, default=6)
    ap.add_argument("--out", default="results/verifiers")
    args = ap.parse_args()
    if args.task == "math-graph":
        return eval_math_graphs(args)
    verifiers = args.verifiers or (["arithmetic", "arithmetic_nogrounding"] if args.task == "math" else ["symbolic"])

    cases = load_cases(args)
    print(f"{len(cases)} cases ({sum(c.invalid for c in cases)} invalid): {dict(Counter(c.error_type or 'valid' for c in cases))}")
    os.makedirs(args.out, exist_ok=True)
    for name in verifiers:
        verifier = build_verifier(name, args)
        print(f"== {name}")
        verdicts = run(verifier, cases)
        res = {"task": args.task, "verifier": name, "n_cases": len(cases), **summarize(cases, verdicts)}
        if name in ("nli", "cascade"):
            res["nli_model"] = args.nli_model
            res["nli"] = nli_analysis(cases, verdicts)
        tag = f"{args.task}_{name}" + ("" if name not in ("nli", "cascade") else "_" + args.nli_model.split("/")[-1])
        with open(os.path.join(args.out, f"{tag}.json"), "w") as f:
            json.dump(res, f, indent=2)
        with open(os.path.join(args.out, f"{tag}_cases.jsonl"), "w") as f:
            for c, v in zip(cases, verdicts):
                f.write(json.dumps({"case_id": c.case_id, "dataset": c.dataset, "error_type": c.error_type, "text": c.step.text,
                                    "status": v.status, "p_invalid": v.p_invalid, "pred_error": v.error_type,
                                    "checks": [(k.name, k.passed, k.detail) for k in v.checks]}) + "\n")
        b = res["binary"]
        print(f"  coverage {res['coverage']:.3f}  P {b['precision']:.3f}  R {b['recall']:.3f}  F1 {b['f1']:.3f}  "
              f"FPR {b['false_positive_rate']:.3f}  AUROC {res['auroc']:.3f}")
        print("  detection rate:", {k: round(v, 3) for k, v in res["detection_rate_by_error"].items()})
        if "nli" in res and "note" not in res["nli"]:
            n = res["nli"]
            for k in ("uncalibrated", "temperature_scaled"):
                print(f"  [{k}] macro-F1 {n[k]['three_class']['macro_f1']:.3f}  3-class ECE {n[k]['three_class_calibration']['ece']:.3f}  "
                      f"binary ECE {n[k]['binary_calibration']['ece']:.3f}  Brier {n[k]['binary_calibration']['brier']:.3f}")
            print(f"  T={n['temperature']:.2f}  threshold={n['threshold_best_f1']:.3f}  -> test F1 {n['binary_at_fitted_threshold']['f1']:.3f} "
                  f"FPR {n['binary_at_fitted_threshold']['false_positive_rate']:.3f}")


if __name__ == "__main__":
    main()
