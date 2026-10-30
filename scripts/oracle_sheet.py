"""Make the annotation sheet for the perfect-localization oracle.

  python -m scripts.oracle_sheet --run graph_scheduled_gsm8k_llada_n1319 --n 60 --out oracle_sheet_llada.md --seed 0

Takes wrong drafts (draft_correct == false) from a finished run, parses each into the same steps the method uses,
and writes a Markdown sheet with the problem, the reference answer and the numbered steps. Whoever labels it fills in
oracle_labels.json as {"example_id": ["5", "9"], ...}, listing the FIRST wrong step and any step that is wrong on its
own. Step ids are the numbers shown in the sheet. Then run
  python -m scripts.run_graph_method --config configs/run/full/graph_remask_gsm8k_llada_n1319.yaml --oracle-labels oracle_labels.json"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from src.graph.registry import build_graph  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="oracle_sheet.md")
    a = ap.parse_args()
    recs = [json.loads(l) for l in open(os.path.join(a.logs, a.run, "generations.jsonl")) if l.strip()]
    wrong = [r for r in recs if not r["draft_correct"]]
    random.Random(a.seed).shuffle(wrong)
    wrong = sorted(wrong[: a.n], key=lambda r: r["example_id"])
    with open(a.out, "w") as f:
        f.write(f"# Oracle labelling sheet ({len(wrong)} wrong drafts)\n\nList the wrong step ids in oracle_labels.json.\n\n")
        for r in wrong:
            g = build_graph({"example_id": r["example_id"], "dataset": r.get("dataset"), "prompt": r["prompt"],
                             "generation": r["draft_generation"]})
            f.write(f"## {r['example_id']}  (reference answer: {r['reference_answer']}, draft answer: {r['draft_predicted']})\n\n")
            for n in g.nodes:
                if n.kind == "problem":
                    f.write(f"Problem: {n.text}\n\n")
                else:
                    f.write(f"- [{n.node_id}] ({n.kind}) {n.text.strip()}\n")
            f.write("\n")
    json.dump({r["example_id"]: [] for r in wrong}, open("oracle_labels.json", "w"), indent=1)
    print(f"wrote {a.out} and an empty oracle_labels.json with {len(wrong)} problems")


if __name__ == "__main__":
    main()
