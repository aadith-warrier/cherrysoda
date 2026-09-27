import argparse
import collections
import json
import os
import re
import sys
 
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
from src.eval.arith_check import check_equations  # noqa: E402
from src.eval.scoring import score_record  # noqa: E402
 
LOOP_MIN_REPEATS = 3
 
 
def pct(a, b):
    return f"{a:>4} ({a / b:5.1%})" if b else f"{a:>4}"
 
 
def analyse_numeric(recs):
    wrong_cats = collections.Counter()
    ids = collections.defaultdict(list)
    n_wrong_eqs = collections.Counter()
    first_pos = collections.Counter()
    correct_with_slip = 0
    n_correct = 0
    for r in recs:
        sc = score_record(r)
        eqs = check_equations(r.get("generation") or "")
        bad = [i for i, e in enumerate(eqs) if not e["ok"]]
        if sc["correct"]:
            n_correct += 1
            if bad:
                correct_with_slip += 1
                ids["correct_with_slip"].append(r["example_id"])
            continue
        if sc["extraction"] == "none":
            cat = "no_answer"
        elif bad:
            cat = "arith_slip"
            n_wrong_eqs["1" if len(bad) == 1 else "2+"] += 1
            frac = bad[0] / max(1, len(eqs) - 1) if len(eqs) > 1 else 0.0
            first_pos["early" if frac < 1 / 3 else "middle" if frac < 2 / 3 else "late"] += 1
        elif eqs:
            cat = "no_slip"
        else:
            cat = "unchecked"
        wrong_cats[cat] += 1
        ids[cat].append(r["example_id"])
    n = len(recs)
    n_wrong = n - n_correct
    summary = {
        "num_examples": n, "num_correct": n_correct, "num_wrong": n_wrong,
        "wrong_breakdown": dict(wrong_cats),
        "arith_slip_num_wrong_calcs": dict(n_wrong_eqs),
        "arith_slip_first_error_position": dict(first_pos),
        "correct_but_contains_slip": correct_with_slip,
    }
    print(f"  answers: {n_correct}/{n} correct, {n_wrong} wrong")
    print(f"  why the {n_wrong} wrong answers are wrong:")
    for cat, label in [("arith_slip", "a written calculation is wrong (locally detectable)"),
                       ("no_slip", "calculations correct, answer wrong (setup/logic error)"),
                       ("unchecked", "no calculation could be checked"),
                       ("no_answer", "no final answer (cut off / format)")]:
        print(f"    {pct(wrong_cats[cat], n_wrong)}  {label}")
    s = wrong_cats["arith_slip"]
    if s:
        print(f"  among arithmetic-slip answers: exactly 1 wrong calculation {pct(n_wrong_eqs['1'], s)}; "
              f"2+ {pct(n_wrong_eqs['2+'], s)}")
        print(f"    first wrong calculation: early {first_pos['early']}, middle {first_pos['middle']}, "
              f"late {first_pos['late']}")
    print(f"  correct answers that still contain a wrong calculation: {pct(correct_with_slip, n_correct)}")
    return summary, ids
 
 
def _looping(text):
    sents = [s.strip().lower() for s in re.split(r"[.\n]", text) if len(s.strip()) > 15]
    counts = collections.Counter(sents)
    return bool(counts) and counts.most_common(1)[0][1] >= LOOP_MIN_REPEATS
 
 
def analyse_label(recs):
    ids = collections.defaultdict(list)
    confusion = collections.defaultdict(collections.Counter)
    by_depth = collections.defaultdict(lambda: [0, 0])
    by_depth_proved = collections.defaultdict(lambda: [0, 0])
    unknown_by_depth = collections.Counter()
    loops = loops_wrong = no_answer = 0
    n_correct = 0
    for r in recs:
        sc = score_record(r)
        gold = str(r["reference_answer"])
        pred = str(sc["predicted"]) if sc["predicted"] is not None else "none"
        confusion[gold][pred] += 1
        depth = (r.get("metadata") or {}).get("qdep")
        if depth is not None:
            by_depth[depth][0] += int(sc["correct"])
            by_depth[depth][1] += 1
            if gold != "Unknown":        # Unknown questions have no proof, so their depth is not a proof depth
                by_depth_proved[depth][0] += int(sc["correct"])
                by_depth_proved[depth][1] += 1
            else:
                unknown_by_depth[depth] += 1
        loop = _looping(r.get("generation") or "")
        loops += loop
        n_correct += sc["correct"]
        if sc["extraction"] == "none":
            no_answer += 1
            ids["no_answer"].append(r["example_id"])
        if loop:
            ids["looping"].append(r["example_id"])
            if not sc["correct"]:
                loops_wrong += 1
    n = len(recs)
    labels = ["True", "False", "Unknown"]
    preds = labels + ["none"]
    print(f"  answers: {n_correct}/{n} correct; no answer found: {pct(no_answer, n)}")
    print(f"  looping outputs (a sentence repeated {LOOP_MIN_REPEATS}+ times): {pct(loops, n)}, "
          f"of which wrong: {loops_wrong}")
    print("  gold \\ predicted " + " ".join(f"{p:>8}" for p in preds))
    for g in labels:
        print(f"  {g:<17} " + " ".join(f"{confusion[g][p]:>8}" for p in preds))
    if by_depth:
        print("  accuracy by proof depth: " + ", ".join(
            f"d{d}: {c}/{t} ({c / t:.0%})" for d, (c, t) in sorted(by_depth.items())))
        print("    Unknown-gold questions per depth: " + ", ".join(
            f"d{d}: {unknown_by_depth[d]}" for d in sorted(by_depth)))
        print("  accuracy by proof depth, True/False gold only: " + ", ".join(
            f"d{d}: {c}/{t} ({c / t:.0%})" for d, (c, t) in sorted(by_depth_proved.items())))
    summary = {
        "num_examples": n, "num_correct": n_correct, "no_answer": no_answer,
        "looping": loops, "looping_and_wrong": loops_wrong,
        "confusion": {g: dict(confusion[g]) for g in labels},
        "accuracy_by_depth": {str(d): c / t for d, (c, t) in sorted(by_depth.items())},
        "accuracy_by_depth_true_false_only": {str(d): c / t for d, (c, t) in sorted(by_depth_proved.items())},
        "unknown_gold_by_depth": {str(d): unknown_by_depth[d] for d in sorted(by_depth)},
    }
    return summary, ids
 
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", help="Run folders under logs/")
    parser.add_argument("--show", type=int, default=0, help="Print N example ids per category")
    parser.add_argument("--out_dir", default="results/error_analysis")
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
 
    for run in args.runs:
        path = os.path.join(run, "generations.jsonl")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            recs = [json.loads(line) for line in f if line.strip()]
        if not recs:
            continue
        name = os.path.basename(run.rstrip("/"))
        print("=" * 80 + f"\n{name}")
        if recs[0].get("dataset") == "proofwriter":
            summary, ids = analyse_label(recs)
        else:
            summary, ids = analyse_numeric(recs)
        if args.show:
            for cat, lst in ids.items():
                print(f"    e.g. {cat}: {lst[:args.show]}")
        summary["example_ids"] = {k: v[:50] for k, v in ids.items()}
        with open(os.path.join(args.out_dir, f"{name}.json"), "w") as f:
            json.dump(summary, f, indent=2)
    print(f"\nSaved per-run summaries to {args.out_dir}/")
 
 
if __name__ == "__main__":
    main()