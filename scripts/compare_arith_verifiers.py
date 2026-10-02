"""Compare the arithmetic checkers on saved graphs, equation by equation and answer by answer.

    python -m scripts.compare_arith_verifiers --dir outputs/analysis_paper_noblock_250

  equation_holds        src/graph/extract.py      (float check of the graph's parsed equations)
  sympy_equation_holds  src/verify/graph_math.py  (same parsed equations, exact rationals)
  check_equations       src/eval/arith_check.py   (line-level text checker, no graph)
  graph verifier        src/verify/graph_math.py  (sympy + text fallback for equations the graph missed)

Prints the agreement and every disagreement, so each one can be traced to a checker bug or a parse difference.
"""
import argparse
import json
from collections import Counter

from src.eval.arith_check import check_equations
from src.graph.extract import equation_holds
from src.graph.schema import ReasoningGraph
from src.verify.base import INVALID
from src.verify.graph_math import GraphArithmeticVerifier, sympy_equation_holds


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="folder with generations.jsonl and graphs.jsonl")
    args = ap.parse_args()

    gens = [json.loads(l) for l in open(f"{args.dir}/generations.jsonl")]
    graphs = [ReasoningGraph.from_dict(json.loads(l)) for l in open(f"{args.dir}/graphs.jsonl")]
    verifier = GraphArithmeticVerifier(check_grounding=False)

    eq_table, eq_diff = Counter(), []
    ans = {"equation_holds": [], "sympy": [], "check_equations": [], "graph_verifier": []}
    correct = []
    for r, g in zip(gens, graphs):
        flags = {k: False for k in ans}
        for n in g.nodes:
            for eq in n.equations:
                a, b = equation_holds(eq), sympy_equation_holds(eq)
                eq_table[(a, b)] += 1
                if a != b:
                    eq_diff.append((g.example_id, n.node_id, eq.raw, eq.lhs, eq.rhs, a, b))
                flags["equation_holds"] |= a is False
                flags["sympy"] |= b is False
        flags["check_equations"] = any(not e["ok"] for e in check_equations(r["generation"]))
        flags["graph_verifier"] = any(v.status == INVALID for v in verifier.verify_graph(g).values())
        for k in ans:
            ans[k].append(flags[k])
        correct.append(bool(r["correct"]))

    total = sum(eq_table.values())
    print(f"{len(gens)} answers, {total} parsed equations")
    print("equation_holds vs sympy_equation_holds (rows: equation_holds):")
    for a in (True, False, None):
        print(f"  {str(a):5}  " + "  ".join(f"sympy={str(b):5}: {eq_table[(a, b)]:4}" for b in (True, False, None)))
    print(f"  agreement {sum(v for (a, b), v in eq_table.items() if a == b) / max(1, total):.4f}")
    for d in eq_diff:
        print("   differ:", d)

    wrong = [not c for c in correct]
    print("\nanswer-level: flagged / catches wrong answers / flags right answers")
    for k in ("equation_holds", "sympy", "check_equations", "graph_verifier"):
        f = ans[k]
        tp = sum(x and w for x, w in zip(f, wrong))
        fp = sum(x and not w for x, w in zip(f, wrong))
        print(f"  {k:16} flagged {sum(f):3}   wrong caught {tp:3}/{sum(wrong)}   right flagged {fp:3}/{len(f) - sum(wrong)}"
              f"   precision {tp / max(1, tp + fp):.3f}")
    for k in ("check_equations", "graph_verifier"):
        only_k = [g.example_id for g, x, y in zip(graphs, ans[k], ans["sympy"]) if x and not y]
        only_s = [g.example_id for g, x, y in zip(graphs, ans[k], ans["sympy"]) if y and not x]
        print(f"\n  flagged by {k} but not sympy ({len(only_k)}): {only_k}")
        print(f"  flagged by sympy but not {k} ({len(only_s)}): {only_s}")


if __name__ == "__main__":
    main()
