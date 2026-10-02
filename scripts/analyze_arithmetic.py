"""How many wrong answers are arithmetic slips the deterministic verifier catches, and how many would be fixed
by correcting the arithmetic alone.

"Fixable" simulates ideal arithmetic-only repair: every false equation gets its correct value, the corrected
value is carried along the graph's value-flow edges to the steps that use it, their equations are recomputed,
and the corrected final answer is compared with the reference. It is an upper bound for correction that only
repairs arithmetic (it assumes the model would redo downstream steps consistently).
"""
import argparse
import json

from scripts.score_accuracy import extract_final_number, normalize_reference
from src.graph.extract import equation_holds, evaluate_expression, values_match
from src.graph.schema import ReasoningGraph
from src.graph.stats import fmt_value


def repaired_answer(g: ReasoningGraph, predicted):
    """Final answer after correcting every false equation and propagating the fixes downstream."""
    fixes = {}  # node_id -> {old value: corrected value}
    incoming = {}
    for e in g.edges:
        if e.reason == "value_flow":
            incoming.setdefault(e.dst, []).append(e)

    for n in g.nodes[1:]:
        if n.kind not in ("calc", "claim"):
            continue
        upstream = {}
        for e in incoming.get(n.node_id, []):
            for v in e.evidence.split(","):
                for old, new in fixes.get(e.src, {}).items():
                    if fmt_value(old) == v:
                        upstream[old] = new

        def sub(v):
            return next((new for old, new in upstream.items() if values_match(old, v)), v)

        node_fixes = {}
        if n.kind == "claim":
            node_fixes = {v: sub(v) for v in n.values_produced if not values_match(sub(v), v)}
        prev_rhs, prev_value = None, None
        for eq in n.equations:
            if not eq.rhs:
                continue
            if eq.lhs and eq.lhs == prev_rhs and prev_value is not None:
                value = prev_value  # chain "a = b = c": b's true value is a's
            elif eq.lhs:
                value = evaluate_expression(eq.lhs, replace=sub)
            else:
                value = evaluate_expression(eq.rhs, replace=sub)
            if value is not None and eq.result is not None and not values_match(value, eq.result):
                if equation_holds(eq) is not False and not upstream:
                    value = eq.result  # rounding the verifier accepts, with nothing upstream changed
                if not values_match(value, eq.result):
                    node_fixes[eq.result] = value
            prev_rhs, prev_value = eq.rhs, value
        if node_fixes:
            fixes[n.node_id] = node_fixes

    if predicted is None:
        return None
    for n in reversed(g.nodes[1:]):
        for old, new in fixes.get(n.node_id, {}).items():
            if values_match(old, predicted):
                return new
    # "Claire will eat 14 dozens of eggs in 4 weeks": the scorer reads the last number (4), but the stated
    # answer is 14; if the final statement's own answer was corrected, that correction is the repaired answer.
    last = next((n for n in reversed(g.nodes[1:]) if n.kind in ("calc", "claim")), None)
    if last is not None and fixes.get(last.node_id):
        return next(iter(fixes[last.node_id].values()))
    return predicted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="Folder with generations.jsonl and graphs.jsonl")
    parser.add_argument("--list", action="store_true", help="Print every flagged answer")
    args = parser.parse_args()

    gens = [json.loads(l) for l in open(f"{args.dir}/generations.jsonl")]
    graphs = [ReasoningGraph.from_dict(json.loads(l)) for l in open(f"{args.dir}/graphs.jsonl")]
    rows = []
    for r, g in zip(gens, graphs):
        pred = extract_final_number(r["generation"])
        ref = normalize_reference(r["reference_answer"])
        correct = pred is not None and ref is not None and abs(pred - ref) < 1e-4
        false_eqs = [e for n in g.nodes for e in n.equations if equation_holds(e) is False]
        checkable = sum(equation_holds(e) is not None for n in g.nodes for e in n.equations)
        repaired = repaired_answer(g, pred) if false_eqs else pred
        fixed = repaired is not None and ref is not None and abs(repaired - ref) < 1e-4
        rows.append(dict(id=r["example_id"], correct=correct, flagged=bool(false_eqs), fixed=fixed and not correct,
                         pred=pred, ref=ref, repaired=repaired, false_eqs=[e.raw for e in false_eqs], checkable=checkable))

    n = len(rows)
    wrong = [x for x in rows if not x["correct"]]
    right = [x for x in rows if x["correct"]]
    wf = [x for x in wrong if x["flagged"]]
    rf = [x for x in right if x["flagged"]]
    fixed = [x for x in wf if x["fixed"]]
    print(f"answers: {n}   accuracy: {len(right)}/{n} = {len(right) / n:.0%}   error rate: {len(wrong) / n:.0%}")
    print(f"equations checked by the verifier: {sum(x['checkable'] for x in rows)}")
    print(f"wrong answers with a false equation (caught): {len(wf)}/{len(wrong)} = {len(wf) / max(1, len(wrong)):.0%}")
    print(f"right answers with a false equation (false alarms or harmless slips): {len(rf)}/{len(right)}")
    print(f"flagged answers that are actually wrong (precision): {len(wf)}/{len(wf) + len(rf)}")
    print(f"fixable by arithmetic-only repair: {len(fixed)}/{len(wrong)} wrong answers = {len(fixed) / max(1, len(wrong)):.0%}"
          f"  ->  accuracy {len(right)}/{n} would become {len(right) + len(fixed)}/{n}")
    if args.list:
        print()
        for x in wf + rf:
            tag = "right" if x["correct"] else ("WRONG, fixable" if x["fixed"] else "WRONG, not fixable")
            print(f"{x['id']} [{tag}] model {fmt_value(x['pred']) if x['pred'] is not None else '-'} ref {fmt_value(x['ref'])}"
                  f" repaired {fmt_value(x['repaired']) if x['repaired'] is not None else '-'} | {x['false_eqs'][:3]}")
        print("\nwrong and not flagged:", [(x["id"], x["pred"], x["ref"]) for x in wrong if not x["flagged"]])


if __name__ == "__main__":
    main()
