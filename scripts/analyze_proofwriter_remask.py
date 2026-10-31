"""Why did remasking not move ProofWriter accuracy? Breaks a remask run's records down.

    python -m scripts.analyze_proofwriter_remask logs/graph_remask_proofwriter_d3_llada [logs/full_remask_...]

For each run:
  1. wrong drafts by (gold label -> predicted label) and whether the verifier flagged any step;
  2. among remasked examples: was the answer line inside the first round's affected subgraph, did the
     predicted label change, and how (fixed / broken / wrong -> other wrong / unchanged);
  3. flag precision by gold label.
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.graph.registry import build_graph  # noqa: E402


def final_pred(r):
    return r.get("predicted_answer", r.get("predicted"))  # run_graph_method saves "predicted_answer"


def load(run_dir):
    with open(os.path.join(run_dir, "generations.jsonl")) as f:
        return [json.loads(line) for line in f]


def answer_in_first_round(r):
    if not r.get("rounds"):
        return None
    g = build_graph({"example_id": r["example_id"], "dataset": "proofwriter", "prompt": r["prompt"],
                     "generation": r["draft_generation"]})
    answers = [n.node_id for n in g.nodes if n.kind == "answer"]
    return bool(answers) and answers[-1] in set(r["rounds"][0]["affected"])


def report(run_dir):
    rs = load(run_dir)
    n = len(rs)
    wrong = [r for r in rs if not r["draft_correct"]]
    print(f"\n=== {os.path.basename(run_dir.rstrip('/'))}  (n={n}, draft {sum(r['draft_correct'] for r in rs)}/{n} right, "
          f"final {sum(r['correct'] for r in rs)}/{n})")

    print("\n1. Wrong drafts: gold -> predicted, flagged / not flagged")
    conf = Counter((r["reference_answer"], str(r["draft_predicted"]), r["flags_before"] > 0) for r in wrong)  # None = no answer
    pairs = sorted({(g, p) for g, p, _ in conf})
    for g, p in pairs:
        print(f"   {g:>7} -> {str(p):<8} flagged {conf[(g, p, True)]:>3}   not flagged {conf[(g, p, False)]:>3}")
    nf = sum(r["flags_before"] == 0 for r in wrong)
    print(f"   total wrong {len(wrong)}: flagged {len(wrong) - nf}, never flagged {nf} (out of reach of any remasking)")

    touched = [r for r in rs if r.get("rounds")]
    print(f"\n2. Remasked examples: {len(touched)}")
    if touched:
        ans_in = [answer_in_first_round(r) for r in touched]
        changed = [r for r in touched if r["draft_predicted"] != final_pred(r)]
        kinds = Counter(
            "fixed" if (not r["draft_correct"] and r["correct"]) else
            "broken" if (r["draft_correct"] and not r["correct"]) else
            "wrong -> other wrong" if r["draft_predicted"] != final_pred(r) else
            "label unchanged" for r in touched)
        identical = sum(not any(x["changed"] for x in r["rounds"]) for r in touched)
        print(f"   answer line inside round-1 A(B): {sum(bool(a) for a in ans_in)}/{len(touched)}")
        print(f"   tokens came back identical: {identical}/{len(touched)}")
        print(f"   predicted label changed: {len(changed)}/{len(touched)}  -> {dict(kinds)}")
        wt = [r for r in touched if not r["draft_correct"]]
        print(f"   wrong drafts remasked: {len(wt)}; label changed in {sum(r['draft_predicted'] != final_pred(r) for r in wt)}, "
              f"fixed {sum(r['correct'] for r in wt)}")

    print("\n3. Flag precision by gold label (share of flagged drafts that were wrong)")
    for lab in ("True", "False", "Unknown"):
        sub = [r for r in rs if r["reference_answer"] == lab]
        fl = [r for r in sub if r["flags_before"] > 0]
        w = [r for r in sub if not r["draft_correct"]]
        print(f"   {lab:>7}: n={len(sub):>3} draft acc {sum(r['draft_correct'] for r in sub) / max(1, len(sub)):.0%}  "
              f"flagged {len(fl):>3} (wrong {sum(not r['draft_correct'] for r in fl)})  "
              f"wrong never flagged {sum(r['flags_before'] == 0 for r in w)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for d in sys.argv[1:]:
        report(d)