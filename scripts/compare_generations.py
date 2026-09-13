
import argparse
import json
 
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file1")
    parser.add_argument("file2")
    args = parser.parse_args()
 
    with open(args.file1) as f:
        records1 = [json.loads(line) for line in f]
    with open(args.file2) as f:
        records2 = [json.loads(line) for line in f]
 
    if len(records1) != len(records2):
        print(f"MISMATCH: file1 has {len(records1)} lines, file2 has {len(records2)} lines")
        return
 
    mismatches = 0
    for i, (r1, r2) in enumerate(zip(records1, records2)):
        if r1["generation"] != r2["generation"]:
            mismatches += 1
            if mismatches <= 3:  # show first few mismatches as examples
                print(f"--- Mismatch at line {i} ({r1['example_id']}) ---")
                print(f"Run1: {r1['generation'][:200]!r}")
                print(f"Run2: {r2['generation'][:200]!r}")
                print()
 
    total = len(records1)
    print(f"\n{mismatches}/{total} generations differ between the two runs.")
    if mismatches == 0:
        print("Fully deterministic -- seed is working correctly.")
    else:
        print(f"NOT fully deterministic ({mismatches/total:.1%} of examples differ).")
 
 
if __name__ == "__main__":
    main()
 