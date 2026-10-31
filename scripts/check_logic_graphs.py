"""Does a flagged step reach the final answer through the ProofWriter graph?

    python -m scripts.check_logic_graphs --generations logs/vanilla_proofwriter_d3_llada/generations.jsonl

For every answer with at least one step flagged by the symbolic verifier, takes the flagged steps and
all their descendants (A(B) without the stop-at-valid rule) and reports how often the final answer
line falls inside it (overall and on wrong answers), plus the mean share of steps that would be
remasked. Without edges no flagged step could ever reach an answer line, which the verifier itself
cannot judge.
"""
import argparse
import json

import networkx as nx

from src.graph.registry import build_graph
from src.verify.base import INVALID, graph_step_inputs
from src.verify.logic import SymbolicLogicVerifier


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--generations", required=True)
    args = ap.parse_args()
    verifier = SymbolicLogicVerifier()
    n = reach = wrong = wrong_reach = 0
    ratios = []
    with open(args.generations) as f:
        for line in f:
            record = json.loads(line)
            g = build_graph(record)
            G = g.to_networkx()
            flagged = {s.step_id for s in graph_step_inputs(g, use_all_earlier=True) if verifier.verify(s).status == INVALID}
            answers = [x.node_id for x in g.nodes if x.kind == "answer"]
            if not flagged or not answers:
                continue
            affected = set(flagged).union(*(nx.descendants(G, b) for b in flagged))
            hit = answers[-1] in affected
            n += 1
            reach += hit
            if not record["correct"]:
                wrong += 1
                wrong_reach += hit
            steps = [x for x in g.nodes if x.kind not in ("problem", "header")]
            ratios.append(len(affected) / len(steps))
    print(f"answers with a flagged step: {n}")
    print(f"flagged step reaches the final answer: {reach / max(1, n):.1%}  (wrong answers: {wrong_reach / max(1, wrong):.1%} of {wrong})")
    print(f"mean affected-subgraph ratio |A(B)|/|steps|: {sum(ratios) / max(1, len(ratios)):.2f}")


if __name__ == "__main__":
    main()
