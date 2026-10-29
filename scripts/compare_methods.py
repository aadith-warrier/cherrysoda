import argparse
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.run_graph_method import mcnemar_exact, paired_bootstrap_ci


def load_run(path):
    recs = [json.loads(l) for l in open(os.path.join(path, "generations.jsonl")) if l.strip()]
    return recs, json.load(open(os.path.join(path, "metrics.json")))


def compare(run_dirs, names=None):
    names = names or [os.path.basename(os.path.normpath(d)) for d in run_dirs]
    runs = {n: load_run(d) for n, d in zip(names, run_dirs)}
    ids = [r["example_id"] for r in next(iter(runs.values()))[0]]
    for n, (recs, _) in runs.items():
        if [r["example_id"] for r in recs] != ids:
            raise ValueError(f"run '{n}' is not on the same problems (in the same order) as '{names[0]}'")

    drafts = {n: [r["draft_generation"] for r in recs] for n, (recs, _) in runs.items()}
    same_draft = all(d == drafts[names[0]] for d in drafts.values())

    rows = []
    for n, (recs, m) in runs.items():
        mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
        rows.append({
            "name": n, "method": m["method"], "mode": m["mode"], "n": len(recs),
            "draft_acc": m["draft_accuracy"], "acc": m["accuracy"], "delta": m["delta_accuracy"],
            "ci": m["delta_ci95"], "fixed": m["fixed"], "broken": m["broken"], "p_vs_draft": m["mcnemar_p"],
            "nfe": m["mean_nfe_total"], "nfe_over": m["mean_nfe_overhead"],
            "tokens_regen": m.get("mean_tokens_regenerated", 0.0),
            "remask_ratio": m.get("mean_remask_ratio_cumulative", 0.0) if m["method"] == "remask" else 1.0,
            "consistency": m["reasoning_consistency_after"], "sec": m.get("mean_sec_total", m["mean_sec_per_problem"]),
            "tokens_per_pass": m.get("mean_tokens_per_pass"),
        })
    pairs = []
    for a, b in itertools.combinations(names, 2):
        ra, rb = runs[a][0], runs[b][0]
        a_only = sum(x["correct"] and not y["correct"] for x, y in zip(ra, rb))
        b_only = sum(y["correct"] and not x["correct"] for x, y in zip(ra, rb))
        lo, hi = paired_bootstrap_ci([y["correct"] for y in rb], [x["correct"] for x in ra])
        pairs.append({"a": a, "b": b, "a_only": a_only, "b_only": b_only, "p": mcnemar_exact(a_only, b_only),
                      "gap": (sum(x["correct"] for x in ra) - sum(y["correct"] for y in rb)) / len(ra), "ci": [lo, hi]})
    return {"rows": rows, "pairs": pairs, "same_draft": same_draft}


def render_md(res):
    L = ["| method | acc (draft) | Δ vs draft [95% CI] | fixed / broken | NFE (+overhead) | tokens re-denoised | "
         "remask ratio | consistent after | s/problem |", "|---|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        L.append(f"| {r['name']} | {r['acc']:.1%} ({r['draft_acc']:.1%}) | {r['delta']:+.1%} [{r['ci'][0]:+.1%}, "
                 f"{r['ci'][1]:+.1%}] | {r['fixed']} / {r['broken']} | {r['nfe']:.0f} (+{r['nfe_over']:.0f}) | "
                 f"{r['tokens_regen']:.0f} | {r['remask_ratio']:.1%} | {r['consistency']:.1%} | {r['sec']:.1f} |")
    L += ["", "| A vs B | A only right | B only right | gap A-B [95% CI] | exact McNemar p |", "|---|---|---|---|---|"]
    for p in res["pairs"]:
        L.append(f"| {p['a']} vs {p['b']} | {p['a_only']} | {p['b_only']} | {p['gap']:+.1%} [{p['ci'][0]:+.1%}, "
                 f"{p['ci'][1]:+.1%}] | {p['p']:.3f} |")
    if not res["same_draft"]:
        L += ["", "WARNING: the runs do not share the same drafts, so 'vs draft' is not comparable between rows."]
    return "\n".join(L) + "\n"


def render_tex(res):
    esc = lambda s: s.replace("_", r"\_")
    L = [r"\begin{tabular}{lrrrrr}", r"\toprule",
         r"Method & Acc.\ (\%) & $\Delta$ vs draft & Fixed/Broken & NFE & Remask ratio \\", r"\midrule"]
    for r in res["rows"]:
        L.append(f"{esc(r['name'])} & {100 * r['acc']:.1f} & {100 * r['delta']:+.1f} & {r['fixed']}/{r['broken']} & "
                 f"{r['nfe']:.0f} & {100 * r['remask_ratio']:.1f}\\% \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--names", nargs="+")
    ap.add_argument("--out", default="results/compare")
    args = ap.parse_args()
    res = compare(args.runs, args.names)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    open(args.out + ".md", "w").write(render_md(res))
    open(args.out + ".tex", "w").write(render_tex(res))
    print(render_md(res))
    print(f"wrote {args.out}.md and {args.out}.tex")


if __name__ == "__main__":
    main()
