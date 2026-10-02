"""Run step verifiers over model generations and report how flags relate to answer correctness.

    python scripts/verify_generations.py --generations logs/vanilla_proofwriter_d3_llada/generations.jsonl --verifiers symbolic nli

For ProofWriter answers (no graph builder yet): each line is a step, checked against the theory.
Maths runs with saved graphs go through scripts/verify_graphs.py instead. Writes
<run dir>/verdicts_<verifier>.jsonl and prints:
  reasoning consistency rate   share of answers with no flagged step (proposal, Sec. 5)
  flag -> wrong answer         precision / recall of "some step is flagged" as a detector of a wrong final answer
When both symbolic and nli run on ProofWriter, the NLI verdicts are also scored against the symbolic
ones (as silver labels) on the steps both could judge.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.verify.base import INVALID, UNVERIFIABLE, StepInput, graph_step_inputs
from src.verify.calibration import binary_metrics, per_class_metrics


def step_inputs(record: dict) -> list:
    if record.get("dataset") in ("gsm8k", "svamp"):
        from src.graph.registry import build_graph
        return graph_step_inputs(build_graph(record), use_all_earlier=True)
    from src.graph.segment import segment_generation
    steps, prev = [], []
    for k, seg in enumerate(segment_generation(record["generation"]), start=1):
        if seg.is_header:
            continue
        steps.append(StepInput(seg.text, list(prev), record["prompt"], str(k)))
        prev.append(seg.text)
    return steps


def build(name: str, args):
    if name == "arithmetic":
        from src.verify.arithmetic import ArithmeticVerifier
        return ArithmeticVerifier(check_grounding=not args.no_grounding)
    if name == "symbolic":
        from src.verify.logic import SymbolicLogicVerifier
        return SymbolicLogicVerifier()
    if name == "nli":
        from src.verify.nli import HFNLIBackend, NLIVerifier
        return NLIVerifier(HFNLIBackend(args.nli_model), temperature=args.temperature, flag_threshold=args.threshold)
    raise ValueError(name)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--generations", required=True)
    ap.add_argument("--verifiers", nargs="+", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-grounding", action="store_true", help="arithmetic verifier: only check the arithmetic")
    ap.add_argument("--nli-model", default="MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli")
    ap.add_argument("--temperature", type=float, default=1.0, help="from eval_verifiers.py calibration")
    ap.add_argument("--threshold", type=float, default=0.5)
    args = ap.parse_args()

    with open(args.generations) as f:
        records = [json.loads(l) for l in f if l.strip()][: args.limit]
    dataset = records[0].get("dataset")
    names = args.verifiers or (["arithmetic"] if dataset in ("gsm8k", "svamp") else ["symbolic"])
    inputs = [step_inputs(r) for r in records]
    correct = [bool(r["correct"]) for r in records]
    out_dir = os.path.dirname(args.generations)

    all_verdicts = {}
    for name in names:
        v = build(name, args)
        verdicts = []
        for steps in inputs:
            verdicts.append(v.verify_batch(steps) if hasattr(v, "verify_batch") else [v.verify(s) for s in steps])
        all_verdicts[name] = verdicts

        path = os.path.join(out_dir, f"verdicts_{name}.jsonl")
        with open(path, "w") as f:
            for r, ok, steps, vs in zip(records, correct, inputs, verdicts):
                f.write(json.dumps({"example_id": r["example_id"], "correct": ok, "steps": [
                    {"step_id": s.step_id, "text": s.text, "status": d.status, "error_type": d.error_type,
                     "p_invalid": d.p_invalid, "checks": [(c.name, c.passed, c.detail) for c in d.checks]}
                    for s, d in zip(steps, vs)]}) + "\n")

        flat = [d for vs in verdicts for d in vs]
        flagged = [any(d.status == INVALID for d in vs) for vs in verdicts]
        det = binary_metrics([not c for c in correct], flagged)
        print(f"== {name}  ({len(records)} answers, {len(flat)} steps)  -> {path}")
        print(f"  steps judged {sum(d.status != UNVERIFIABLE for d in flat) / max(1, len(flat)):.3f}   "
              f"steps flagged {sum(d.status == INVALID for d in flat) / max(1, len(flat)):.3f}")
        print(f"  reasoning consistency rate {1 - sum(flagged) / len(flagged):.3f}   "
              f"(correct answers {sum(1 for c, fl in zip(correct, flagged) if c and not fl) / max(1, sum(correct)):.3f}, "
              f"wrong answers {sum(1 for c, fl in zip(correct, flagged) if not c and not fl) / max(1, len(correct) - sum(correct)):.3f})")
        print(f"  flag -> wrong answer: precision {det['precision']:.3f}  recall {det['recall']:.3f}  F1 {det['f1']:.3f}")
        errs = {}
        for d in flat:
            if d.status == INVALID:
                errs[d.error_type] = errs.get(d.error_type, 0) + 1
        print(f"  error types {errs}")

    if "symbolic" in all_verdicts and "nli" in all_verdicts:
        silver, pred = [], []
        for vs_s, vs_n in zip(all_verdicts["symbolic"], all_verdicts["nli"]):
            for s, n in zip(vs_s, vs_n):
                if s.status != UNVERIFIABLE and n.status != UNVERIFIABLE:
                    silver.append("invalid" if s.status == INVALID else "valid")
                    pred.append("invalid" if n.status == INVALID else "valid")
        m = per_class_metrics(silver, pred, ["valid", "invalid"])
        print(f"== nli vs symbolic silver labels on {len(silver)} model-written steps")
        print(json.dumps(m, indent=2))


if __name__ == "__main__":
    main()
