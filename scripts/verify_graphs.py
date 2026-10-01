"""Run the graph arithmetic verifier over a saved run (generations.jsonl + graphs.jsonl); nothing is regenerated.

    python -m scripts.verify_graphs --dir outputs/analysis_paper_noblock_250

Writes <dir>/verdicts_arith.jsonl, one line per answer: {example_id, correct, verdicts: {node_id: verdict}}
(the input for Phase 5), and prints per-step and per-answer numbers:
  reasoning consistency rate   answers with no flagged step (proposal, Sec. 5)
  flag -> wrong answer         how well "some step is flagged" picks out wrong final answers
Arithmetic-only and arithmetic + grounding are reported separately.
"""
import argparse
import json
from collections import Counter

from src.graph.schema import ReasoningGraph
from src.verify.base import INVALID, UNVERIFIABLE
from src.verify.calibration import binary_metrics
from src.verify.graph_math import GraphArithmeticVerifier


def report(name, correct, verdicts):
    steps = [v for vs in verdicts for v in vs.values()]
    flagged = [any(v.status == INVALID for v in vs.values()) for vs in verdicts]
    m = binary_metrics([not c for c in correct], flagged)
    n_right = sum(correct)
    print(f"== {name}")
    print(f"  steps: {len(steps)}   judged {sum(v.status != UNVERIFIABLE for v in steps) / len(steps):.3f}   "
          f"flagged {sum(v.status == INVALID for v in steps) / len(steps):.3f}   "
          f"{dict(Counter(v.error_type for v in steps if v.status == INVALID))}")
    print(f"  reasoning consistency rate {1 - sum(flagged) / len(flagged):.3f}   "
          f"(right answers {sum(c and not f for c, f in zip(correct, flagged)) / n_right:.3f}, "
          f"wrong answers {sum(not c and not f for c, f in zip(correct, flagged)) / (len(correct) - n_right):.3f})")
    print(f"  flag -> wrong answer: caught {m['tp']}/{m['tp'] + m['fn']}  precision {m['precision']:.3f}  "
          f"recall {m['recall']:.3f}  F1 {m['f1']:.3f}  (right answers flagged {m['fp']}/{m['fp'] + m['tn']})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    args = ap.parse_args()

    gens = [json.loads(l) for l in open(f"{args.dir}/generations.jsonl")]
    graphs = [ReasoningGraph.from_dict(json.loads(l)) for l in open(f"{args.dir}/graphs.jsonl")]
    correct = [bool(r["correct"]) for r in gens]

    arith_only = [GraphArithmeticVerifier(check_grounding=False).verify_graph(g) for g in graphs]
    full = [GraphArithmeticVerifier().verify_graph(g) for g in graphs]
    report("arithmetic", correct, arith_only)
    report("arithmetic + grounding", correct, full)

    path = f"{args.dir}/verdicts_arith.jsonl"
    with open(path, "w") as f:
        for r, g, vs in zip(gens, graphs, full):
            f.write(json.dumps({"example_id": g.example_id, "correct": bool(r["correct"]),
                                "verdicts": {k: v.to_dict() for k, v in vs.items()}}) + "\n")
    print(f"verdicts: {path}")


if __name__ == "__main__":
    main()
