
import argparse
import json
 
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", required=True)
    parser.add_argument("--n", type=int, default=5)
    args = parser.parse_args()
 
    with open(args.generations) as f:
        for i, line in enumerate(f):
            if i >= args.n:
                break
            record = json.loads(line)
            print("=" * 80)
            print(f"example_id: {record['example_id']}")
            print(f"reference_answer: {record['reference_answer']}")
            print("-" * 80)
            print("RAW GENERATION:")
            print(repr(record["generation"]))  
            print()
 
 
if __name__ == "__main__":
    main()
 