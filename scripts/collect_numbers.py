#!/usr/bin/env python
"""Prints every number the paper still needs, from the run folders in logs/.
Run from the repo root:  python scripts/collect_numbers.py --logs logs > numbers_report.txt
Then send numbers_report.txt. It only reads files, it never runs a model."""
import argparse, glob, itertools, json, os, sys

sys.path.insert(0, os.getcwd())
from scripts.compare_runs import compare, load_run          # baselines vs base model
from scripts.run_graph_method import mcnemar_exact, paired_bootstrap_ci

DS = {"gsm8k": "gsm8k", "svamp": "svamp", "proofwriter": "proofwriter_d3"}
MODELS = ["llada", "dream"]


def pct(x):
    return "-" if x is None else f"{100 * x:.1f}"


def part1_baselines(logs):
    print("\n=== 1. BASE MODEL AND EXISTING METHODS (vs vanilla) ===")
    print("dataset model method n base% meth% delta [lo,hi] fixed/broken p nfe")
    for d, suf in DS.items():
        for m in MODELS:
            base = os.path.join(logs, f"vanilla_{suf}_{m}")
            if not os.path.isfile(os.path.join(base, "generations.jsonl")):
                print(d, m, "vanilla MISSING"); continue
            b = load_run(base)
            for kind in ["vote", "dapd", "remedi_rl", "proseco"]:
                if kind in ("remedi_rl", "proseco"):
                    if m == "dream": continue
                    run = os.path.join(logs, f"{kind}_{suf}")
                else:
                    run = os.path.join(logs, f"{kind}_{suf}_{m}")
                if not os.path.isfile(os.path.join(run, "generations.jsonl")):
                    print(d, m, kind, "MISSING"); continue
                r = compare(b, load_run(run))
                print(d, m, kind, r["n"], pct(r["base_acc"]), pct(r["method_acc"]),
                      f"{100*r['diff']:+.1f} [{100*r['ci_low']:+.1f},{100*r['ci_high']:+.1f}]",
                      f"{r['fixed']}/{r['broken']}", f"{r['p_mcnemar']:.3g}",
                      f"{r['method_nfe']:.0f}" if r["method_nfe"] else "-")


def corr_runs(logs):
    out = []
    for f in sorted(glob.glob(os.path.join(logs, "*", "metrics.json"))):
        try:
            m = json.load(open(f))
        except Exception:
            continue
        if m.get("method") not in ("remask", "scheduled") or "draft_accuracy" not in m:
            continue
        name = os.path.basename(os.path.dirname(f))
        ds = next((k for k in DS if k in name), None)
        md = "dream" if "dream" in name else "llada"
        out.append((name, ds, md, m, os.path.dirname(f)))
    return out


def part2_correction(runs):
    print("\n=== 2. OUR VARIANTS (from each run's metrics.json) ===")
    keys = ["draft_accuracy", "accuracy", "delta_accuracy", "delta_ci95", "fixed", "broken", "mcnemar_p",
            "mean_nfe_total", "mean_nfe_overhead", "mean_tokens_regenerated", "mean_remask_ratio_per_round",
            "mean_remask_ratio_cumulative", "mean_affected_subgraph_ratio", "reasoning_consistency_before",
            "reasoning_consistency_after", "flagged_draft_wrong", "flagged_draft_right", "flag_precision_draft_wrong",
            "wrong_drafts_not_flagged", "unchanged_after_remask", "frac_examples_remasked", "mean_rounds_when_remasked"]
    for name, ds, md, m, _ in runs:
        print(f"\n[{name}] dataset={ds} model={md} method={m.get('method')} mode={m.get('mode')} n={m['num_examples']}")
        for k in keys:
            if k in m:
                v = m[k]
                print(f"  {k} = {round(v, 4) if isinstance(v, float) else v}")


def part3_pairs(runs):
    print("\n=== 3. PAIRWISE COMPARISONS (same problems only) ===")
    groups = {}
    for name, ds, md, m, d in runs:
        gp = os.path.join(d, "generations.jsonl")
        if os.path.isfile(gp):
            groups.setdefault((ds, md, m["num_examples"]), []).append((name, gp))
    for (ds, md, n), items in groups.items():
        recs = {}
        for name, gp in items:
            rs = [json.loads(l) for l in open(gp) if l.strip()]
            recs[name] = {r["example_id"]: bool(r["correct"]) for r in rs}
        for a, b in itertools.combinations(sorted(recs), 2):
            ids = sorted(set(recs[a]) & set(recs[b]))
            if len(ids) < 20: continue
            xa, xb = [recs[a][i] for i in ids], [recs[b][i] for i in ids]
            ao = sum(x and not y for x, y in zip(xa, xb)); bo = sum(y and not x for x, y in zip(xa, xb))
            lo, hi = paired_bootstrap_ci(xb, xa)
            print(f"{ds} {md} n={len(ids)}  {a} vs {b}: gap {100*(sum(xa)-sum(xb))/len(ids):+.1f} "
                  f"[{100*lo:+.1f},{100*hi:+.1f}] only-A {ao} only-B {bo} p={mcnemar_exact(ao, bo):.3g}")


def part4_errors(logs_root):
    print("\n=== 4. ERROR ANALYSIS (Appendix E, RQ1) ===")
    for ds in ("gsm8k", "svamp"):
        for md in MODELS:
            f = os.path.join(logs_root, "results", "error_analysis", f"vanilla_{ds}_{md}.json")
            if not os.path.isfile(f):
                print(ds, md, "MISSING"); continue
            e = json.load(open(f)); b = e["wrong_breakdown"]; w = e["num_wrong"]
            print(ds, md, f"wrong={w} arith_slip={100*b['arith_slip']/w:.1f}% no_slip={100*b['no_slip']/w:.1f}% "
                  f"unchecked={100*b['unchecked']/w:.1f}% max_gain_pts={100*b['arith_slip']/e['num_examples']:.1f}")


def part5_proofwriter(runs):
    print("\n=== 5. PROOFWRITER BY DEPTH AND LABEL (our runs, draft vs final) ===")
    for name, ds, md, m, d in runs:
        if ds != "proofwriter" or m.get("method") != "remask": continue
        gp = os.path.join(d, "generations.jsonl")
        if not os.path.isfile(gp): continue
        rs = [json.loads(l) for l in open(gp) if l.strip()]
        by = {}
        for r in rs:
            by.setdefault(str(r.get("reference_answer")), []).append(r)
        for lab, g in sorted(by.items()):
            dc = sum(bool(r["draft_correct"]) for r in g); fc = sum(bool(r["correct"]) for r in g)
            print(f"{name} label={lab} n={len(g)} draft={100*dc/len(g):.1f}% final={100*fc/len(g):.1f}% delta={100*(fc-dc)/len(g):+.1f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs")
    a = ap.parse_args()
    runs = corr_runs(a.logs)
    part1_baselines(a.logs)
    part2_correction(runs)
    part3_pairs(runs)
    part4_errors(os.path.dirname(os.path.abspath(a.logs)) if os.path.basename(a.logs) == "logs" else ".")
    part5_proofwriter(runs)
