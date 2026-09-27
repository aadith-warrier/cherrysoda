import argparse
import json
import os
import sys
 
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
from src.eval.scoring import score_record, summarize  # noqa: E402
 
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("generations", nargs="+", help="generations.jsonl file(s)")
    parser.add_argument("--show_errors", type=int, default=0, help="Print N wrong examples per file")
    args = parser.parse_args()
 
    rows = []
    for path in args.generations:
        with open(path) as f:
            records = [json.loads(line) for line in f if line.strip()]
        s = summarize(records)
        rows.append((path, s))
        with open(os.path.join(os.path.dirname(path), "scores.json"), "w") as f:
            json.dump(s, f, indent=2)
 
        if args.show_errors:
            shown = 0
            for r in records:
                sc = score_record(r)
                if not sc["correct"]:
                    print("=" * 80)
                    print(f"{r['example_id']}  ref={r['reference_answer']}  pred={sc['predicted']}  ({sc['extraction']})")
                    print(r["generation"][-600:])
                    shown += 1
                    if shown >= args.show_errors:
                        break
 
    print(f"\n{'run':<45} {'n':>5} {'acc':>7} {'fallbk':>6} {'none':>5} {'empty':>5} {'NFE':>6} {'sec':>6}")
    for path, s in rows:
        name = os.path.basename(os.path.dirname(path)) or path
        if not s.get("num_examples"):
            print(f"{name:<45}     0   (no generations yet: still running, or the run crashed)")
            continue
        print(f"{name:<45} {s['num_examples']:>5} {s['accuracy']:>7.2%} {s['extraction_fallback']:>6} "
              f"{s['extraction_none']:>5} {s['empty_generations']:>5} "
              f"{(s['avg_forward_passes'] or 0):>6.1f} {(s['avg_wall_time_sec'] or 0):>6.2f}")
        if "accuracy_by_label" in s:
            print(f"{'':<45} by label: " + ", ".join(f"{k} {v:.1%}" for k, v in s["accuracy_by_label"].items()))
 
 
if __name__ == "__main__":
    main()
