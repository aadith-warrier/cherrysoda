import argparse
import csv
import glob
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.eval.scoring import score_record  # noqa: E402

DATASET_TO_RUN_SUFFIX = {"gsm8k": "gsm8k", "svamp": "svamp", "proofwriter": "proofwriter_d3"}


def load_run(run_dir: str) -> dict:
    path = os.path.join(run_dir, "generations.jsonl")
    recs = {}
    if not os.path.exists(path):
        return recs
    with open(path) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                r["_correct"] = score_record(r)["correct"]
                recs[r["example_id"]] = r
    return recs


def family(model_name: str) -> str:
    return "dream" if "dream" in (model_name or "").lower() else "llada"


def mcnemar_exact_p(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def bootstrap_ci(base: list, meth: list, n_boot: int = 2000, seed: int = 0):
    rng = random.Random(seed)
    n = len(base)
    diffs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(meth[i] - base[i] for i in idx) / n)
    diffs.sort()
    return diffs[int(0.025 * n_boot)], diffs[int(0.975 * n_boot) - 1]


def avg(recs, key):
    vals = [r.get(key) for r in recs if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def compare(base_recs: dict, meth_recs: dict) -> dict:
    ids = sorted(set(base_recs) & set(meth_recs))
    if not ids:
        return {"n": 0}
    b = [int(base_recs[i]["_correct"]) for i in ids]
    m = [int(meth_recs[i]["_correct"]) for i in ids]
    fixed = sum(1 for x, y in zip(b, m) if x == 0 and y == 1)
    broken = sum(1 for x, y in zip(b, m) if x == 1 and y == 0)
    lo, hi = bootstrap_ci(b, m)
    return {
        "n": len(ids),
        "base_acc": sum(b) / len(ids),
        "method_acc": sum(m) / len(ids),
        "diff": (sum(m) - sum(b)) / len(ids),
        "ci_low": lo,
        "ci_high": hi,
        "fixed": fixed,
        "broken": broken,
        "p_mcnemar": mcnemar_exact_p(fixed, broken),
        "base_nfe": avg([base_recs[i] for i in ids], "num_forward_passes"),
        "method_nfe": avg([meth_recs[i] for i in ids], "num_forward_passes"),
        "base_sec": avg([base_recs[i] for i in ids], "wall_time_sec"),
        "method_sec": avg([meth_recs[i] for i in ids], "wall_time_sec"),
    }


def auto_pairs(logs_dir: str):
    pairs = []
    runs = sorted(d for d in glob.glob(os.path.join(logs_dir, "*")) if os.path.isfile(os.path.join(d, "generations.jsonl")))
    for d in runs:
        name = os.path.basename(d)
        if name.startswith(("vanilla_", "smoke_", "pytest_")):
            continue
        recs = load_run(d)
        if not recs:
            continue
        first = next(iter(recs.values()))
        suffix = DATASET_TO_RUN_SUFFIX.get(first.get("dataset"))
        if suffix is None:
            continue
        base = os.path.join(logs_dir, f"vanilla_{suffix}_{family(first.get('model'))}")
        if os.path.isdir(base):
            pairs.append((base, d))
        if name.startswith("proseco_") and not name.startswith(("proseco_nocorr", "proseco_sampler")):
            off = os.path.join(logs_dir, name.replace("proseco_", "proseco_nocorr_", 1))
            if os.path.isdir(off):
                pairs.append((off, d))
        if name == "check_proseco" and os.path.isdir(os.path.join(logs_dir, "check_proseco_off")):
            pairs.append((os.path.join(logs_dir, "check_proseco_off"), d))
    return pairs


def fmt(x, spec):
    return "-" if x is None else format(x, spec)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="Pair every run in --logs_dir with its vanilla run")
    parser.add_argument("--logs_dir", default="logs")
    parser.add_argument("--base", help="Baseline run folder (with --runs)")
    parser.add_argument("--runs", nargs="*", default=[], help="Method run folders")
    parser.add_argument("--out", default="results/compare_runs.csv")
    args = parser.parse_args()

    if args.auto:
        pairs = auto_pairs(args.logs_dir)
    elif args.base and args.runs:
        pairs = [(args.base, r) for r in args.runs]
    else:
        parser.error("use --auto, or --base with --runs")
    if not pairs:
        sys.exit("No run pairs found.")

    cache = {}
    rows = []
    for base_dir, meth_dir in pairs:
        for d in (base_dir, meth_dir):
            if d not in cache:
                cache[d] = load_run(d)
        res = compare(cache[base_dir], cache[meth_dir])
        rows.append({"method": os.path.basename(meth_dir.rstrip("/")),
                     "baseline": os.path.basename(base_dir.rstrip("/")), **res})

    hdr = (f"{'method':<34} {'vs':<26} {'n':>5} {'base':>6} {'meth':>6} {'diff':>6} "
           f"{'95% CI':>14} {'fixed':>5} {'broke':>5} {'p':>6} {'NFE b/m':>11} {'sec b/m':>11}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        if not r.get("n"):
            print(f"{r['method']:<34} {r['baseline']:<26}     0   (no shared examples)")
            continue
        sig = "*" if r["p_mcnemar"] < 0.05 else " "
        print(f"{r['method']:<34} {r['baseline']:<26} {r['n']:>5} {r['base_acc']:>6.1%} {r['method_acc']:>6.1%} "
              f"{r['diff']*100:>+5.1f} [{r['ci_low']*100:+5.1f},{r['ci_high']*100:+5.1f}] "
              f"{r['fixed']:>5} {r['broken']:>5} {r['p_mcnemar']:>5.3f}{sig} "
              f"{fmt(r['base_nfe'], '5.0f')}/{fmt(r['method_nfe'], '<5.0f')} "
              f"{fmt(r['base_sec'], '5.1f')}/{fmt(r['method_sec'], '<5.1f')}")
    print("\n* = significant at p < 0.05 (McNemar, paired). diff and CI are in accuracy points.")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    keys = ["method", "baseline", "n", "base_acc", "method_acc", "diff", "ci_low", "ci_high",
            "fixed", "broken", "p_mcnemar", "base_nfe", "method_nfe", "base_sec", "method_sec"]
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
