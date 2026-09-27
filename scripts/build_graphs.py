import argparse
import json
import os
import re
from collections import Counter

from src.graph.registry import build_graph
from src.graph.stats import graph_stats, render_graph_text


def extract_final_number(text: str):
    # As in the LLaDA authors' OpenCompass scorer: ignore anything after the model starts a new "Question:".
    text = text.split("Question:")[0]
    numbers = re.findall(r"-?\d[\d,]*\.?\d*", text)
    if not numbers:
        return None
    last = numbers[-1].replace(",", "")
    try:
        return float(last)
    except ValueError:
        return None


def normalize_reference(ref: str):
    try:
        return float(str(ref).replace(",", "").strip())
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser(description="Build reasoning graphs for every answer in a generations.jsonl file.")
    parser.add_argument("--generations", required=True, help="Path to a generations.jsonl file")
    parser.add_argument("--show", type=int, default=0, help="Print the first N graphs as text")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.generations)
    graphs_path = os.path.join(out_dir, "graphs.jsonl")
    rows, reasons = [], Counter()
    with open(args.generations) as f_in, open(graphs_path, "w") as f_out:
        for i, line in enumerate(f_in):
            record = json.loads(line)
            graph = build_graph(record)
            stats = graph_stats(graph)
            pred = extract_final_number(record["generation"])
            ref = normalize_reference(record["reference_answer"])
            correct = pred is not None and ref is not None and abs(pred - ref) < 1e-4
            f_out.write(json.dumps({**graph.to_dict(), "correct": correct, "stats": stats}) + "\n")
            rows.append({**stats, "correct": correct})
            reasons.update(e.reason for e in graph.edges)
            if i < args.show:
                print("=" * 90)
                print(f"{record['example_id']}  {'CORRECT' if correct else 'WRONG'} (model {pred}, reference {ref})")
                print(render_graph_text(graph))

    n = len(rows)
    mean = lambda k: sum(r[k] for r in rows) / n
    summary = {
        "num_answers": n,
        "accuracy": mean("correct"),
        "mean_steps": mean("graph_steps"),
        "mean_equations": mean("graph_equations"),
        "mean_edges": mean("graph_edges"),
        "edge_reasons": dict(reasons),
        "answers_without_steps": sum(r["graph_steps"] == 0 for r in rows) / n,
        "mean_isolated_calcs": mean("graph_isolated_calcs"),
        "mean_unsourced_numbers": mean("graph_unsourced_numbers"),
        "answers_with_warnings": sum(r["graph_warnings"] > 0 for r in rows) / n,
    }
    with open(os.path.join(out_dir, "graph_stats.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("=" * 90)
    print(json.dumps(summary, indent=2))
    print(f"Graphs: {graphs_path}")


if __name__ == "__main__":
    main()
