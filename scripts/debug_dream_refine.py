import argparse
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.loaders import load_dataset_unified
from src.models.model_registry import get_model_wrapper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--index", type=int, default=1, help="0-based problem index (gsm8k_00001 -> 1)")
    ap.add_argument("--device")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    model_cfg = yaml.safe_load(open(cfg["model_config"]))
    if args.device:
        model_cfg["device"] = args.device
    gen = {**model_cfg["generation"], **cfg.get("generation", {})}
    ex = load_dataset_unified(cfg["dataset_config"], sample_size=args.index + 1)[args.index]
    model = get_model_wrapper(model_cfg)

    native = model.generate(ex["prompt"], gen["max_new_tokens"], gen["num_denoising_steps"],
                            remasking_strategy=gen["remasking_strategy"], return_intermediate_states=True,
                            block_length=None, temperature=0.0)
    trace = []
    mine = model.refine(ex["prompt"], native.token_ids, list(range(len(native.token_ids))), temperature=0.0,
                        allow_end_from=0, trace=trace)
    history = {r.step_index: r for r in native.intermediate_states}
    print(f"{ex['example_id']}: native commits per step recorded for {len(history)} steps; refine ran {len(trace)} passes; "
          f"tokens equal {sum(a == b for a, b in zip(native.token_ids, mine.token_ids)) / len(mine.token_ids):.1%}")

    for t in trace:
        rec = history.get(t["step"])
        if rec is None:
            print(f"step {t['step']}: refine committed {t['chosen']} but the native history has no such step")
            return
        native_set, mine_set = set(rec.newly_unmasked_positions), set(t["chosen"])
        if native_set != mine_set:
            only_n, only_m = sorted(native_set - mine_set), sorted(mine_set - native_set)
            print(f"FIRST COMMIT-SET DIFFERENCE at step {t['step']} (committing {len(native_set)} native / "
                  f"{len(mine_set)} refine tokens)")
            print(f"  only native : {only_n}")
            print(f"  only refine : {only_m}")
            shown = sorted(set(only_n + only_m))[:8]
            print("  refine's confidence (neg. entropy) for these positions, and the cutoff:")
            ranked = sorted(t["conf"].values(), reverse=True)
            k = len(mine_set)
            for p in shown:
                print(f"    pos {p}: {t['conf'].get(p)}")
            print(f"    k-th and (k+1)-th best: {ranked[k - 1]} / {ranked[k] if k < len(ranked) else None}")
            return
        for p in sorted(native_set):
            if rec.token_ids[p] != t["tokens"][p]:
                print(f"commit sets agree up to step {t['step']}, but the token at position {p} differs: "
                      f"native {rec.token_ids[p]} vs refine {t['tokens'][p]}  -> logits differ (forward-pass inputs "
                      f"or numerics), not the ordering")
                return
    print("commit sets and tokens agree at every step: the difference is not in the denoising loop "
          "(compare how generated_text / token_ids are read out)")


if __name__ == "__main__":
    main()
