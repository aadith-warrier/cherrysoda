import argparse
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from baselines.vanilla import run as run_generate
from data.loaders import load_dataset_unified
from src.models.model_registry import get_model_wrapper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="a run config (model, dataset, generation)")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--device")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    model_cfg = yaml.safe_load(open(cfg["model_config"]))
    if args.device:
        model_cfg["device"] = args.device
    gen_cfg = {**model_cfg["generation"], **cfg.get("generation", {}), "temperature": 0.0}
    examples = load_dataset_unified(cfg["dataset_config"], sample_size=args.n)
    model = get_model_wrapper(model_cfg)
    eos_last = bool(gen_cfg.get("confidence_eos_eot_inf", False))

    ok = True
    for ex in examples:
        draft = run_generate(model, ex, gen_cfg)
        ids = draft.token_ids
        full = model.refine(ex["prompt"], ids, list(range(len(ids))), temperature=0.0, allow_end_from=0,
                            confidence_eos_eot_inf=eos_last)
        same = sum(a == b for a, b in zip(ids, full.token_ids)) / len(ids)
        first_diff = next((i for i, (a, b) in enumerate(zip(ids, full.token_ids)) if a != b), None)
        print(f"{ex['example_id']}: refine(all) vs generate: {same:.1%} tokens equal, first difference at position "
              f"{first_diff}, text equal {full.generated_text == draft.generated_text}, "
              f"NFE {full.num_forward_passes} vs {draft.num_forward_passes}")
        if same < 0.99:
            print("   NOTE: refine(all) does not reproduce generate(). Expected for LLaDA (must be 100%); for Dream it "
                  "should be close to 100% once the numerics match. Report this line.")

        a, b = len(ids) // 4, len(ids) // 2
        mid = list(range(a, b))
        part = model.refine(ex["prompt"], ids, mid, temperature=0.0, allow_end_from=None)
        outside_ok = all(x == y for i, (x, y) in enumerate(zip(ids, part.token_ids)) if not a <= i < b)
        no_mask = part.raw_metadata.get("leftover_masks", 0) == 0
        print(f"   slice [{a},{b}): outside untouched {outside_ok}, no [MASK] left {no_mask}, NFE {part.num_forward_passes}")
        ok &= outside_ok and no_mask

        left_to_right = lambda remaining, conf: remaining[:2]
        sel = model.refine(ex["prompt"], ids, mid, temperature=0.0, select_fn=left_to_right)
        exp = (len(mid) + 1) // 2
        print(f"   select_fn (2 tokens/pass, left to right): NFE {sel.num_forward_passes} (expected {exp})")
        ok &= sel.num_forward_passes == exp and sel.raw_metadata.get("leftover_masks", 0) == 0
    print("OK" if ok else "PROBLEM: see lines above")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()