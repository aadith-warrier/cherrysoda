import argparse
import json
import re


def extract_final_number(text: str):
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", required=True, help="Path to a generations.jsonl file")
    args = parser.parse_args()

    total = 0
    correct = 0
    unparseable = 0

    with open(args.generations) as f:
        for line in f:
            record = json.loads(line)
            total += 1

            predicted = extract_final_number(record["generation"])
            reference = normalize_reference(record["reference_answer"])

            if predicted is None or reference is None:
                unparseable += 1
                continue

            if abs(predicted - reference) < 1e-4:
                correct += 1

    accuracy = correct / total if total else 0.0
    print(f"File: {args.generations}")
    print(f"Total examples: {total}")
    print(f"Correct: {correct}")
    print(f"Unparseable (no number extracted): {unparseable}")
    print(f"Accuracy: {accuracy:.2%}")


if __name__ == "__main__":
    main()