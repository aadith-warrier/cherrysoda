"""Use a baseline run's saved answers as our method's drafts, so both start from the identical base-model outputs.

    python -m scripts.drafts_from_baseline --config configs/run/<our run>.yaml --baseline logs/vanilla_proofwriter_d3_llada

Each saved answer is re-tokenised, followed by the model's end-of-turn token and padded with <|endoftext|> to the
generation length (as a real generation ends), and written to the draft cache named in the run config under the
key the runner looks up, so `scripts.run_graph_method` skips drafting and only corrects. Prints how many answers
round-trip exactly (decode(encode(text)) == text) and how many hit the length limit.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.run_graph_method import DraftCache, load_yaml  # noqa: E402
from src.models.base import GenerationResult  # noqa: E402

END_TOKENS = {"dream": ("<|im_end|>", "<|endoftext|>"), "llada": ("<|eot_id|>", "<|endoftext|>")}


def cache_key(cfg, model_cfg):
    """Exactly as scripts/run_graph_method.py builds it."""
    gen_cfg = {**model_cfg["generation"], **cfg.get("generation", {})}
    key = {"model": model_cfg["name"], "repo": model_cfg.get("hf_repo_id"), "gen": gen_cfg,
           "dataset": cfg["dataset_config"],
           **({"seed": cfg.get("seed", 42)} if (gen_cfg.get("temperature") or 0) > 0 else {})}
    return key, gen_cfg


def to_token_ids(tok, text, length, end_id, pad_id):
    try:
        ids = tok.encode(text, add_special_tokens=False)
    except TypeError:
        ids = tok.encode(text)
    hit = len(ids) >= length
    ids = list(ids[:length])
    if len(ids) < length:
        ids += [end_id] + [pad_id] * (length - len(ids) - 1)
    return ids, hit


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--baseline", required=True, help="baseline run folder with generations.jsonl")
    args = ap.parse_args()
    cfg = load_yaml(args.config)
    model_cfg = load_yaml(cfg["model_config"])
    key, gen_cfg = cache_key(cfg, model_cfg)
    family = "dream" if "dream" in model_cfg["name"] else "llada"

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_cfg.get("tokenizer_repo_id") or model_cfg["hf_repo_id"], trust_remote_code=True)
    end_id, pad_id = (tok.convert_tokens_to_ids(t) for t in END_TOKENS[family])
    L = int(gen_cfg["max_new_tokens"])

    cache = DraftCache(cfg["draft_cache"], key)
    with open(os.path.join(args.baseline, "generations.jsonl")) as f:
        recs = [json.loads(l) for l in f if l.strip()]
    exact = hits = 0
    for r in recs:
        text = r["generation"] or ""
        ids, hit = to_token_ids(tok, text, L, end_id, pad_id)
        hits += hit
        exact += tok.decode([i for i in ids if i not in (end_id, pad_id)], skip_special_tokens=True).strip() == text.strip()
        cache.put(r["example_id"], GenerationResult(
            prompt=None, generated_text=text, num_forward_passes=int(r.get("num_forward_passes") or gen_cfg["num_denoising_steps"]),
            wall_time_sec=float(r.get("wall_time_sec") or 0.0), num_denoising_steps_used=int(r.get("num_denoising_steps_used") or 0),
            token_ids=ids, raw_metadata={"source": args.baseline}))
    print(f"{len(recs)} drafts from {args.baseline} -> {cache.path}")
    print(f"  re-tokenised exactly: {exact}/{len(recs)}; at the length limit: {hits}; baseline accuracy "
          f"{100 * sum(bool(r['correct']) for r in recs) / len(recs):.1f}%")


if __name__ == "__main__":
    main()
