import argparse
import copy
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.loaders import load_dataset_unified  # noqa: E402
from src.eval.scoring import score_record  # noqa: E402
from src.models.model_registry import get_model_wrapper  # noqa: E402

# Alternative prompt: reasoning requested first, no trailing "Solution:" cue.
REASON_FIRST_TEMPLATE = (
    "Solve the following grade school math problem. Think step by step and show each calculation "
    "explicitly (e.g., \"5 + 3 = 8\") before giving the answer.\n"
    "After your reasoning, write the final answer on its own line in the form \"The answer is: <number>\".\n\n"
    "Problem: {question}\n"
)

VARIANTS = {
    "dream": [
        ("A default (entropy)", {}, None),
        ("B low_confidence", {"remasking_strategy": "low_confidence"}, None),
        ("C entropy + suppress_endoftext", {"suppress_endoftext": True}, None),
        ("D README sampling t=0.2 p=0.95", {"temperature": 0.2, "top_p": 0.95}, None),
        ("E reason-first prompt", {}, REASON_FIRST_TEMPLATE),
    ],
    "llada": [
        ("A default", {}, None),
        ("B defer_eos_eot", {"defer_eos_eot": True}, None),
        ("E reason-first prompt", {}, REASON_FIRST_TEMPLATE),
    ],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset", default="configs/dataset/gsm8k.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    with open(args.model) as f:
        model_cfg = yaml.safe_load(f)
    if args.device:
        model_cfg["device"] = args.device
    base_gen = copy.deepcopy(model_cfg["generation"])

    with open(args.dataset) as f:
        ds_cfg = yaml.safe_load(f)
    examples = load_dataset_unified(args.dataset, sample_size=args.n)
    raw_questions = None
    if ds_cfg["loader"] in ("gsm8k", "svamp"):
        # Recover each raw question so the alternative template can be applied.
        head, tail = ds_cfg["prompt_template"].split("{question}")
        raw_questions = [e["prompt"][len(head):len(e["prompt"]) - len(tail)] for e in examples]

    model = get_model_wrapper(model_cfg)
    print(f"Loaded {model_cfg['name']} ({model_cfg['hf_repo_id']}) on {model_cfg['device']}")

    rows = []
    for name, overrides, template in VARIANTS[model_cfg["wrapper"]]:
        if template is not None and raw_questions is None:
            continue
        model.config["generation"] = {**base_gen, **overrides}
        gen = model.config["generation"]
        try:
            import torch
            torch.manual_seed(args.seed)
        except ImportError:
            pass
        lens, correct, at_limit, pattern = [], 0, 0, 0
        first_text = None
        for i, ex in enumerate(examples):
            prompt = template.format(question=raw_questions[i]) if template else ex["prompt"]
            r = model.generate(
                prompt=prompt,
                max_new_tokens=gen["max_new_tokens"],
                num_denoising_steps=gen["num_denoising_steps"],
                remasking_strategy=gen["remasking_strategy"],
                block_length=gen.get("block_length"),
            )
            sc = score_record({"dataset": ex["metadata"]["dataset"], "generation": r.generated_text,
                               "reference_answer": ex["reference_answer"]})
            lens.append(r.raw_metadata.get("answer_num_tokens") or 0)
            correct += sc["correct"]
            pattern += sc["extraction"] == "pattern"
            at_limit += bool(r.raw_metadata.get("hit_length_limit"))
            if first_text is None:
                first_text = r.generated_text
        rows.append((name, correct, len(examples), sum(lens) / len(lens), min(lens), at_limit, pattern))
        print(f"\n--- {name}: first generation ---\n{first_text}\n")

    print(f"\n{'variant':<34} {'acc':>7} {'mean_tok':>8} {'min_tok':>7} {'at_256':>6} {'pattern':>7}")
    for name, c, n, mean_len, min_len, lim, pat in rows:
        print(f"{name:<34} {c:>3}/{n:<3} {mean_len:>8.0f} {min_len:>7} {lim:>6} {pat:>7}")


if __name__ == "__main__":
    main()
