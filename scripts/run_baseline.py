import argparse
import importlib
import json
import os
import random
import sys
import time
import zlib
 
import yaml
 
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
from data.loaders import load_dataset_unified  # noqa: E402
from src.eval.scoring import score_record, summarize  # noqa: E402
from src.models.model_registry import get_model_wrapper  # noqa: E402
 
 
_HELD_LOCKS = []
 
 
def _release_locks():
    while _HELD_LOCKS:
        path = _HELD_LOCKS.pop()
        try:
            if open(path).read().strip() == str(os.getpid()):
                os.remove(path)
        except OSError:
            pass
 
 
def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)
 
 
def seed_everything(seed: int):
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass
 
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to a configs/run/*.yaml file")
    parser.add_argument("--device", default=None, help="Override the model config's device, e.g. cuda:2")
    parser.add_argument("--sample_size", default=None, help='Override run sample_size: "full", "prelim" or an integer')
    parser.add_argument("--run_id", default=None, help="Override run_id (log folder name)")
    parser.add_argument("--resume", action="store_true", help="Skip examples already in generations.jsonl")
    parser.add_argument("--seed", type=int, default=None, help="Override run seed (use with a new --run_id per seed)")
    parser.add_argument("--no_wandb", action="store_true")
    args = parser.parse_args()
 
    run_cfg = load_yaml(args.config)
    if args.run_id:
        run_cfg["run_id"] = args.run_id
    if args.sample_size is not None:
        run_cfg["sample_size"] = None if args.sample_size == "prelim" else (
            "full" if args.sample_size == "full" else int(args.sample_size))
    if args.seed is not None:
        run_cfg["seed"] = args.seed
    base_seed = run_cfg.get("seed", 42)
    seed_everything(base_seed)
 
    model_cfg = load_yaml(run_cfg["model_config"])
    if args.device:
        model_cfg["device"] = args.device
    model_cfg["generation"].update(run_cfg.get("generation_overrides") or {})
    gen_cfg = model_cfg["generation"]
    dataset_cfg_path = run_cfg["dataset_config"]
    dataset_cfg = load_yaml(dataset_cfg_path)
 
    run_id = run_cfg["run_id"]
    log_dir = os.path.join("logs", run_id)
    os.makedirs(log_dir, exist_ok=True)
    generations_path = os.path.join(log_dir, "generations.jsonl")
 
    lock_path = os.path.join(log_dir, ".lock")
    for _attempt in range(4):
        try: 
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                content = open(lock_path).read().strip()
                if not content:              # the other process created it but has not written its pid yet
                    time.sleep(0.5)
                    continue
                other_pid = int(content)
                os.kill(other_pid, 0)        # raises if that process is gone
                sys.exit(f"[{run_id}] Another process (pid {other_pid}) is already running this run. Not starting.")
            except (ValueError, ProcessLookupError, PermissionError, FileNotFoundError):
                try:
                    os.remove(lock_path)     # stale lock from a crashed run; retry once
                except FileNotFoundError:
                    pass
    else:
        sys.exit(f"[{run_id}] Could not acquire {lock_path}.")
    _HELD_LOCKS.append(lock_path) 
 
    if os.path.exists(generations_path) and not args.resume and os.path.getsize(generations_path) > 0:
        sys.exit(f"{generations_path} already exists. Use --resume to continue it, or a new --run_id.")
 
    with open(os.path.join(log_dir, "config_used.yaml"), "w") as f:
        yaml.dump({"run": run_cfg, "model": model_cfg, "dataset": dataset_cfg}, f, sort_keys=False)
 
    print(f"[{run_id}] Loading dataset: {dataset_cfg_path}")
    examples = load_dataset_unified(dataset_cfg_path, sample_size=run_cfg.get("sample_size"))
    print(f"[{run_id}] Loaded {len(examples)} examples")
 
    done_ids = set()
    if args.resume and os.path.exists(generations_path):
        with open(generations_path) as f:
            done_ids = {json.loads(line)["example_id"] for line in f if line.strip()}
        print(f"[{run_id}] Resuming: {len(done_ids)} already done")
    todo = [ex for ex in examples if ex["example_id"] not in done_ids]
 
    print(f"[{run_id}] Loading model: {model_cfg['name']} on {model_cfg.get('device')}")
    model = get_model_wrapper(model_cfg)
    baseline_module = importlib.import_module(f"baselines.{run_cfg['baseline']}")
 
    wandb_run = None
    if run_cfg.get("logging", {}).get("wandb_project") and not args.no_wandb:
        import wandb
        wandb_run = wandb.init(
            project=run_cfg["logging"]["wandb_project"],
            name=run_cfg["logging"].get("wandb_run_name") or run_id,
            config={"run": run_cfg, "model": model_cfg},
        )
 
    try:
        from tqdm import tqdm
    except ImportError:
        def tqdm(x, **_):
            return x
    running_correct = 0
    with open(generations_path, "a") as out_f:
        for i, example in enumerate(tqdm(todo, desc=run_id)):
            example_seed = (base_seed * 1_000_003 + zlib.crc32(example["example_id"].encode())) % (2**31)
            seed_everything(example_seed)
            result = baseline_module.run(model, example, gen_cfg)
            meta = result.raw_metadata or {}
            record = {
                "example_id": example["example_id"],
                "dataset": example["metadata"].get("dataset"),
                "answer_type": example["metadata"].get("answer_type"),
                "model": model_cfg["name"],
                "baseline": run_cfg["baseline"],
                "prompt": example["prompt"],
                "generation": result.generated_text,
                "reference_answer": example["reference_answer"],
                "num_forward_passes": result.num_forward_passes,
                "num_denoising_steps_used": result.num_denoising_steps_used,
                "num_remasked_tokens": result.num_remasked_tokens,
                "wall_time_sec": result.wall_time_sec,
                "answer_num_tokens": meta.get("answer_num_tokens"),
                "hit_length_limit": meta.get("hit_length_limit"),
                "raw_head": meta.get("raw_head"),
                "seed": example_seed,
                "voted_answer": meta.get("voted_answer"),
                "vote_top": meta.get("vote_top"),
                "num_votes": meta.get("num_votes"),
                "metadata": example["metadata"],
            }
            record.update(score_record(record))
            out_f.write(json.dumps(record) + "\n")
            out_f.flush()
            running_correct += record["correct"]
 
            if wandb_run:
                wandb_run.log({
                    "wall_time_sec": result.wall_time_sec,
                    "num_forward_passes": result.num_forward_passes,
                    "running_accuracy": running_correct / (i + 1),
                })
 
    with open(generations_path) as f:
        all_records = [json.loads(line) for line in f if line.strip()]
    summary = {"run_id": run_id, "model": model_cfg["name"], "dataset": dataset_cfg["name"],
               "baseline": run_cfg["baseline"], "generation": gen_cfg, **summarize(all_records)}
    with open(os.path.join(log_dir, "metrics.json"), "w") as f:
        json.dump(summary, f, indent=2)
 
    print(f"[{run_id}] Done. accuracy={summary['accuracy']:.2%}  "
          f"(format fallback {summary['extraction_fallback']}, no answer {summary['extraction_none']}, "
          f"empty {summary['empty_generations']})  avg NFE={summary['avg_forward_passes']:.1f}  "
          f"avg time={summary['avg_wall_time_sec']:.2f}s")
    print(f"[{run_id}] Generations: {generations_path}")
 
    if wandb_run:
        wandb_run.summary.update({k: v for k, v in summary.items() if isinstance(v, (int, float))})
        wandb_run.finish()
 
 
if __name__ == "__main__":
    try:
        main()
    finally:
        _release_locks()
 