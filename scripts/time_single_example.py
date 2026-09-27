import argparse
import os
import sys
import time

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.loaders import load_dataset_unified  # noqa: E402
from src.models.model_registry import get_model_wrapper  # noqa: E402

FULL_SIZES = {"gsm8k": 1319, "svamp": 1000, "proofwriter_depth3": 600}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--device", default=None)
    parser.add_argument("--n", type=int, default=3, help="Examples to time (the first is a warm-up)")
    args = parser.parse_args()

    with open(args.model) as f:
        model_cfg = yaml.safe_load(f)
    if args.device:
        model_cfg["device"] = args.device
    gen = model_cfg["generation"]

    t0 = time.time()
    model = get_model_wrapper(model_cfg)
    print(f"Model load time: {time.time() - t0:.1f}s")

    examples = load_dataset_unified(args.dataset, sample_size=args.n)
    times = []
    for i, ex in enumerate(examples):
        r = model.generate(
            prompt=ex["prompt"],
            max_new_tokens=gen["max_new_tokens"],
            num_denoising_steps=gen["num_denoising_steps"],
            remasking_strategy=gen["remasking_strategy"],
            block_length=gen.get("block_length"),
        )
        times.append(r.wall_time_sec)
        print(f"[{i}] {r.wall_time_sec:.2f}s  NFE={r.num_forward_passes}  "
              f"answer_tokens={r.raw_metadata.get('answer_num_tokens')}  ref={ex['reference_answer']}")
        if i == 0:
            print(f"Prompt:\n{ex['prompt']}\nGeneration:\n{r.generated_text}\n")

    per_ex = sum(times[1:]) / max(1, len(times) - 1) if len(times) > 1 else times[0]
    print(f"\nPer example (excluding warm-up): {per_ex:.2f}s")
    total = 0.0
    for name, n in FULL_SIZES.items():
        h = per_ex * n / 3600
        total += h
        print(f"  {name:<20} {n:>5} examples ≈ {h:.1f} GPU-h")
    print(f"  all three datasets, one model x one method ≈ {total:.1f} GPU-h")


if __name__ == "__main__":
    main()
