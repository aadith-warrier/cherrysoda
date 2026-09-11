import argparse
import time

import yaml

from src.models.model_registry import get_model_wrapper
from data.loaders import load_dataset_unified


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()

    with open(args.model) as f:
        model_cfg = yaml.safe_load(f)

    print(f"Loading model {model_cfg['name']}...")
    t0 = time.time()
    model = get_model_wrapper(model_cfg)
    print(f"Model load time: {time.time() - t0:.1f}s")

    examples = load_dataset_unified(args.dataset, sample_size=1)
    example = examples[0]
    print(f"\nExample prompt:\n{example['prompt']}\n")

    gen_cfg = model_cfg["generation"]

    print("--- Generation WITHOUT intermediate state capture ---")
    t0 = time.time()
    result = model.generate(
        prompt=example["prompt"],
        max_new_tokens=gen_cfg["max_new_tokens"],
        num_denoising_steps=gen_cfg["num_denoising_steps"],
        return_intermediate_states=False,
    )
    print(f"Wall time: {time.time() - t0:.2f}s")
    print(f"Forward passes: {result.num_forward_passes}")
    print(f"Generated text:\n{result.generated_text}\n")

    print("--- Generation WITH intermediate state capture (checks Track D dependency) ---")
    t0 = time.time()
    result2 = model.generate(
        prompt=example["prompt"],
        max_new_tokens=gen_cfg["max_new_tokens"],
        num_denoising_steps=gen_cfg["num_denoising_steps"],
        return_intermediate_states=True,
    )
    print(f"Wall time: {time.time() - t0:.2f}s")
    if result2.intermediate_states:
        print(f"Captured {len(result2.intermediate_states)} intermediate steps. "
              f"CONFIRMED: intermediate state extraction works.")
        print(f"Example step record: step_index={result2.intermediate_states[0].step_index}, "
              f"num confidences={len(result2.intermediate_states[0].confidences)}")
    else:
        print("WARNING: intermediate_states is empty/None. "
              "This BLOCKS Track D — fix before proceeding to Week 2.")

    print("\n--- Sizing guidance ---")
    per_example_time = result.wall_time_sec
    for n in [20, 50, 100, 300]:
        print(f"  {n} examples x 1 baseline ≈ {per_example_time * n / 60:.1f} min")
    print(f"  Full prelim (100 examples x 3 datasets x 4 baselines) "
          f"≈ {per_example_time * 100 * 3 * 4 / 3600:.1f} hours on ONE GPU "
          f"(divide by 3 if parallelized across your 3 GPUs)")


if __name__ == "__main__":
    main()
