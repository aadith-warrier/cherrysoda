import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from scripts.run_graph_method import summarize
from data.loaders import load_dataset_unified


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--upto", type=int)
    a = ap.parse_args()
    base = os.path.join(a.logs, a.run)
    cfg = json.load(open(os.path.join(base, "run_config.json")))
    method = cfg["method"]
    dirs = [base] + sorted(glob.glob(base + "_r*-*"))
    recs, seen = [], set()
    for d in dirs:
        g = os.path.join(d, "generations.jsonl")
        if os.path.exists(g):
            for l in open(g):
                if l.strip():
                    r = json.loads(l)
                    if r["example_id"] not in seen:
                        seen.add(r["example_id"])
                        recs.append(r)
    sample = cfg["config"].get("sample_size") or "full"
    order = {e["example_id"]: i for i, e in enumerate(load_dataset_unified(cfg["config"]["dataset_config"], sample_size=sample))}
    recs.sort(key=lambda r: order[r["example_id"]])
    k = 0
    while k < len(recs) and order[recs[k]["example_id"]] == k:
        k += 1
    if a.upto:
        k = min(k, a.upto)
    recs = recs[:k]
    out = os.path.join(a.logs, a.run + "_merged")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "generations.jsonl"), "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    mode = cfg["method_settings"].get("mode", "graph") if method == "remask" else "scheduled"
    m = summarize(recs, mode, method)
    if method == "scheduled":
        sched = [r["schedule"] for r in recs if not r["skipped_reason"]]
        mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
        m.update(mean_nfe_schedule=mean([x["nfe"] for x in sched]), mean_levels=mean([x["levels"] for x in sched]),
                 mean_tokens_per_pass=mean([x["tokens_per_pass"] for x in sched]), num_skipped=len(recs) - len(sched))
    json.dump(m, open(os.path.join(out, "metrics.json"), "w"), indent=2)
    json.dump(cfg, open(os.path.join(out, "run_config.json"), "w"), indent=2)
    print(f"{out}: {len(recs)} contiguous problems from {len([d for d in dirs if os.path.exists(os.path.join(d,'generations.jsonl'))])} dir(s); "
          f"{len(seen)} records seen")


if __name__ == "__main__":
    main()
