"""Is the first commit different because of the forward pass or because of the confidence computation?

    CUDA_VISIBLE_DEVICES=1 python -m scripts.probe_dream_logits --config configs/run/graph_remask_gsm8k_dream.yaml \
        --device cuda:0 --index 0

At the first denoising step the whole response is still [MASK], so native diffusion_generate and refine() feed the model
the same input. This script grabs the logits native sees (through its logits hook), computes the logits refine() sees,
and ranks the positions by confidence under both.
"""
import argparse
import os
import sys

import torch
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.loaders import load_dataset_unified  # noqa: E402
from src.models.base import build_chat_input_ids  # noqa: E402
from src.models.dream_wrapper import DREAM_ALG, dream_sample_tokens  # noqa: E402
from src.models.model_registry import get_model_wrapper  # noqa: E402


@torch.no_grad()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--device")
    ap.add_argument("--step", type=int, default=0, help="denoising step to probe (0 = all masked, same input for both)")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    model_cfg = yaml.safe_load(open(cfg["model_config"]))
    if args.device:
        model_cfg["device"] = args.device
    gen = {**model_cfg["generation"], **cfg.get("generation", {})}
    ex = load_dataset_unified(cfg["dataset_config"], sample_size=args.index + 1)[args.index]
    w = get_model_wrapper(model_cfg)
    L, steps = gen["max_new_tokens"], gen["num_denoising_steps"]

    ids = build_chat_input_ids(w.tokenizer, ex["prompt"], w.device)
    P = ids.shape[1]
    seen = {}

    def hook(step, x, logits):
        if step == args.step:
            seen["x"], seen["logits"] = x.clone(), logits.clone()
        if step == args.step + 1:
            seen["x_next"] = x.clone()
        if step is not None and args.step <= step <= args.step + 4:
            seen.setdefault("xs", {})[step] = x.clone()
        return logits

    w.model.diffusion_generate(ids, attention_mask=torch.ones_like(ids), max_new_tokens=L, steps=steps,
                               output_history=False, return_dict_in_generate=True, temperature=0.0, top_p=None,
                               alg=DREAM_ALG[gen["remasking_strategy"]], alg_temp=gen.get("alg_temp", 0.0),
                               generation_logits_hook_func=hook)
    x = seen["x"]
    xs = seen.get("xs", {})
    for st in sorted(xs):
        if st + 1 in xs:
            a_, b_ = xs[st][0, P:], xs[st + 1][0, P:]
            newly = ((a_ == w.mask_token_id) & (b_ != w.mask_token_id)).nonzero().flatten().tolist()
            print(f"  step {st}: {int((a_ == w.mask_token_id).sum())} masked, native committed "
                  f"{[(p, int(b_[p])) for p in newly]}  (response positions 0-3 now: {b_[:4].tolist()})")
    if "x_next" in seen:    # x at the start of the next step shows what native committed in this one
        was = x[0, P:] == w.mask_token_id
        now = seen["x_next"][0, P:] == w.mask_token_id
        print(f"native committed at step {args.step}: {(was & ~now).nonzero().flatten().tolist()}")
    native = seen["logits"]
    mine = w.model(input_ids=x, attention_mask="full", position_ids=None).logits
    mine = torch.cat([mine[:, :1], mine[:, :-1]], dim=1)

    print(f"{ex['example_id']}: probing step {args.step}; {int((x[0] == w.mask_token_id).sum())} masked positions")
    print(f"logits dtype {native.dtype}; max |native - mine| over the response: "
          f"{(native[0, P:].float() - mine[0, P:].float()).abs().max().item():.4g}")

    masked = (x[0, P:] == w.mask_token_id).nonzero().flatten()
    import inspect
    mod = inspect.getmodule(type(w.model).diffusion_generate)
    alg = DREAM_ALG[gen["remasking_strategy"]]
    nat = getattr(mod, "sample_tokens", None)
    if nat is not None:
        conf, _ = nat(native[0, P:][masked], 0.0, top_p=None, top_k=None, margin_confidence=(alg == "topk_margin"),
                      neg_entropy=(alg == "entropy"))
        top = torch.topk(conf.float(), 5)
        print("top-5 by confidence from Dream's own sample_tokens: "
              + ", ".join(f"{int(masked[i])}:{v:.4f}" for v, i in zip(top.values.tolist(), top.indices.tolist())))
        # replay Dream's selection by hand: confidence over the whole sequence, top-k with k = int(m*(1-s/t))
        full = torch.full_like(x, -torch.inf, dtype=native.dtype)
        full[x == w.mask_token_id] = conf
        mrows = int((x[0] == w.mask_token_id).sum())
        t_, s_ = torch.linspace(1, 1e-3, steps + 1, device=x.device)[[args.step, args.step + 1]]
        k = int(torch.tensor(float(mrows), device=x.device) * (1 - s_ / t_))
        idx = torch.topk(full, max(k, 1)).indices[0] - P
        print(f"hand replay of Dream's selection at this step: k={k}, picks response positions {idx.tolist()}")
        x0 = nat(native[0, P:][masked], 0.0, top_p=None, top_k=None, neg_entropy=True)[1]
        for i in torch.topk(conf.float(), 3).indices.tolist():
            print(f"  position {int(masked[i])}: predicted token {int(x0[i])} "
                  f"{w.tokenizer.decode([int(x0[i])])!r}{'  <-- this IS the [MASK] token' if int(x0[i]) == w.mask_token_id else ''}")
        print(f"  [MASK] token id = {w.mask_token_id}; dtype of the confidence vector: {full.dtype}")
        gc = w.model.generation_config
        print(f"model.generation_config: temperature={getattr(gc, 'temperature', None)} top_p={getattr(gc, 'top_p', None)} "
              f"top_k={getattr(gc, 'top_k', None)} alg={getattr(gc, 'alg', None)} alg_temp={getattr(gc, 'alg_temp', None)}")
        for tp, tk in {(None, None), (getattr(gc, "top_p", None), getattr(gc, "top_k", None))}:
            c2, _ = nat(native[0, P:][masked], 0.0, top_p=tp, top_k=tk, neg_entropy=True)
            f2 = torch.full_like(x, -torch.inf, dtype=native.dtype)
            f2[x == w.mask_token_id] = c2
            print(f"  with top_p={tp} top_k={tk}: Dream's top-k would pick "
                  f"{(torch.topk(f2, max(k, 1)).indices[0] - P).tolist()}")
        print("---- Dream's sample_tokens source ----")
        print(inspect.getsource(nat))
    else:
        print("could not locate sample_tokens in", getattr(mod, "__name__", mod))
    for name, lg in (("native logits", native), ("refine logits", mine)):
        conf, _ = dream_sample_tokens(lg[0, P:][masked], 0.0, None, alg)
        top = torch.topk(conf.float(), 5)
        print(f"top-5 by confidence from {name}: "
              + ", ".join(f"{int(masked[i])}:{v:.4f}" for v, i in zip(top.values.tolist(), top.indices.tolist())))


if __name__ == "__main__":
    main()