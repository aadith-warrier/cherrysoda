"""Does the label-ban gain come from the diffusion model or from the answer-support rule alone? (CPU only)

    python -m scripts.answer_rule_baseline logs/graph_ans_proofwriter_d3_llada_n300 [--split 150]

Reads a graph+check+ban run. For each problem it re-derives, from the draft alone, what the answer-support check
says, and builds a model-free baseline: when the check rejects the draft's answer, relabel it by the rule
(True if a verified step derives the hypothesis, False if one derives its negation, otherwise Unknown); otherwise
keep the draft's label. No refinement, no model calls.

It also splits the ban run's outcomes by how much choice the model had: one label banned (the model picked one of
the two remaining labels) or two banned (the third label was forced).
Reported for the design half (first --split questions) and the held-out half separately.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.compare_runs import mcnemar_exact_p  # noqa: E402
from src.graph.registry import build_graph  # noqa: E402
from src.verify.registry import answer_support_verdicts, hypothesis_support, make_verify_fn  # noqa: E402


def final_pred(r):
    return r.get("predicted_answer", r.get("predicted"))


def rule_label(r, step_verify):
    g = build_graph({"example_id": r["example_id"], "dataset": "proofwriter", "prompt": r["prompt"],
                     "generation": r["draft_generation"]})
    v = step_verify(g)
    if not answer_support_verdicts(g, v):
        return r["draft_predicted"], False
    _, proves, disproves = hypothesis_support(g, v)
    return ("True" if proves else "False" if disproves else "Unknown"), True


def pair(a, b):
    """a, b: lists of bools on the same problems -> (a only right, b only right, p)."""
    ao = sum(1 for x, y in zip(a, b) if x and not y)
    bo = sum(1 for x, y in zip(a, b) if y and not x)
    return ao, bo, mcnemar_exact_p(ao, bo)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--split", type=int, default=150)
    args = ap.parse_args()
    with open(os.path.join(args.run_dir, "generations.jsonl")) as f:
        rs = sorted((json.loads(line) for line in f), key=lambda r: r["example_id"])
    step_verify = make_verify_fn("proofwriter_depth3")          # step verdicts only; the rule is applied here
    for r in rs:
        r["_rule"], r["_rule_flag"] = rule_label(r, step_verify)
        r["_rule_ok"] = r["_rule"] == r["reference_answer"]
        r["_banned"] = sorted({b for x in r.get("rounds") or [] for b in x.get("banned_labels") or []})

    print(f"{os.path.basename(args.run_dir.rstrip('/'))}: model-free rule relabel vs label ban")
    for half, sub in (("design", rs[:args.split]), ("held-out", rs[args.split:]), ("all", rs)):
        if not sub:
            continue
        n = len(sub)
        d = [bool(r["draft_correct"]) for r in sub]
        ban = [bool(r["correct"]) for r in sub]
        rule = [r["_rule_ok"] for r in sub]
        rf, rb, rp = pair(rule, d)
        bf, bb, bp = pair(ban, d)
        x, y, xp = pair(ban, rule)
        print(f"\n  {half} (n = {n}): draft {100 * sum(d) / n:.1f}%")
        print(f"    rule relabel, no model : {100 * sum(rule) / n:.1f}%  fixed {rf} / broken {rb}  p {rp:.3f}"
              f"  ({sum(r['_rule_flag'] for r in sub)} answers relabelled)")
        print(f"    label ban (diffusion)  : {100 * sum(ban) / n:.1f}%  fixed {bf} / broken {bb}  p {bp:.3f}")
        print(f"    ban vs rule            : ban only right {x}, rule only right {y}, p {xp:.3f}")
        for k, name in ((1, "one label banned (model chose)"), (2, "two labels banned (label forced)")):
            g = [r for r in sub if len(r["_banned"]) == k]
            fx = sum(1 for r in g if not r["draft_correct"] and r["correct"])
            br = sum(1 for r in g if r["draft_correct"] and not r["correct"])
            print(f"    {name:34}: {len(g):3} problems, fixed {fx}, broken {br}")
        same = sum(1 for r in sub if r["_banned"] and final_pred(r) == r["_rule"])
        print(f"    ban run's final label equals the rule's label in {same} of {sum(1 for r in sub if r['_banned'])} banned problems")


if __name__ == "__main__":
    main()
