"""Results of remask runs on the design half (first 150 ProofWriter questions, where the answer-support idea came
from) and the held-out half (questions 150-299, fresh drafts), reported separately.

    python -m scripts.split_report --runs logs/A logs/B ... [--names a b ...] [--split 150] [--out results/x.md]

Per run and half: draft and final accuracy, paired bootstrap 95% CI of the change, fixed / broken, exact McNemar p,
and for runs with the answer check how many answer lines were rejected and how often the label then changed.
Then every pair of runs head to head on each half (same drafts, so the comparison is paired).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.compare_runs import mcnemar_exact_p  # noqa: E402
from scripts.run_graph_method import paired_bootstrap_ci  # noqa: E402


def load(run_dir):
    with open(os.path.join(run_dir, "generations.jsonl")) as f:
        rs = [json.loads(line) for line in f]
    return {r["example_id"]: r for r in rs}


def final_pred(r):
    return r.get("predicted_answer", r.get("predicted"))


def halves(ids, split):
    ids = sorted(ids)
    return {"design": ids[:split], "held-out": ids[split:]}


def row(rs, ids):
    d = [bool(rs[i]["draft_correct"]) for i in ids]
    f = [bool(rs[i]["correct"]) for i in ids]
    fixed = sum(1 for a, b in zip(d, f) if not a and b)
    broken = sum(1 for a, b in zip(d, f) if a and not b)
    lo, hi = paired_bootstrap_ci(d, f)
    banned = [rs[i] for i in ids if any(x.get("banned_labels") for x in rs[i].get("rounds") or [])]
    changed = sum(1 for r in banned if r["draft_predicted"] != final_pred(r))
    return {"n": len(ids), "draft": sum(d) / len(ids), "final": sum(f) / len(ids), "lo": lo, "hi": hi,
            "fixed": fixed, "broken": broken, "p": mcnemar_exact_p(fixed, broken),
            "banned": len(banned), "banned_changed": changed,
            "banned_fixed": sum(1 for r in banned if not r["draft_correct"] and r["correct"]),
            "banned_broken": sum(1 for r in banned if r["draft_correct"] and not r["correct"])}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--names", nargs="+")
    ap.add_argument("--split", type=int, default=150, help="first N questions are the design half")
    ap.add_argument("--out", help="also write the tables to this .md file")
    args = ap.parse_args()
    names = args.names or [os.path.basename(r.rstrip("/")) for r in args.runs]
    runs = {}
    for name, d in zip(names, args.runs):
        if not os.path.exists(os.path.join(d, "generations.jsonl")):
            print(f"(skipping {name}: {d} has no generations.jsonl)")
            continue
        runs[name] = load(d)
    if not runs:
        sys.exit("no runs found")
    common = set.intersection(*(set(r) for r in runs.values()))
    parts = halves(common, args.split)
    lines = []
    for half, ids in parts.items():
        if not ids:
            continue
        lines += [f"\n### {half} ({ids[0]} .. {ids[-1]}, n = {len(ids)})\n",
                  "| method | draft | final | Δ [95% CI] | fixed / broken | McNemar p | answer bans: lines / label changed / fixed / broken |",
                  "|---|---|---|---|---|---|---|"]
        for name, rs in runs.items():
            s = row(rs, ids)
            bans = (f"{s['banned']} / {s['banned_changed']} / {s['banned_fixed']} / {s['banned_broken']}"
                    if s["banned"] else "-")
            lines.append(f"| {name} | {100 * s['draft']:.1f}% | {100 * s['final']:.1f}% | "
                         f"{100 * (s['final'] - s['draft']):+.1f} [{100 * s['lo']:+.1f}, {100 * s['hi']:+.1f}] | "
                         f"{s['fixed']} / {s['broken']} | {s['p']:.3f} | {bans} |")
        names_ = list(runs)
        if len(names_) > 1:
            lines += ["", "| A vs B | A only right | B only right | gap A-B | McNemar p |", "|---|---|---|---|---|"]
            for i, a in enumerate(names_):
                for b in names_[i + 1:]:
                    ao = sum(1 for k in ids if runs[a][k]["correct"] and not runs[b][k]["correct"])
                    bo = sum(1 for k in ids if runs[b][k]["correct"] and not runs[a][k]["correct"])
                    lines.append(f"| {a} vs {b} | {ao} | {bo} | {100 * (ao - bo) / len(ids):+.1f} | {mcnemar_exact_p(ao, bo):.3f} |")
    text = "\n".join(lines)
    print(text)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as f:
            f.write(text + "\n")
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
