import argparse
import importlib
import json
import os
import time

import yaml
from tqdm import tqdm

from src.models.model_registry import get_model_wrapper
from data.loaders import load_dataset_unified


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def get_baseline_module(baseline_name: str):
    return importlib.import_module(f"baselines.{baseline_name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to a configs/run/*.yaml file")
    args = parser.parse_args()

    run_cfg = load_yaml(args.config)
    model_cfg = load_yaml(run_cfg["model_config"])
    dataset_cfg_path = run_cfg["dataset_config"]

    run_id = run_cfg["run_id"]
    log_dir = os.path.join("logs", run_id)
    os.makedirs(log_dir, exist_ok=True)

    with open(os.path.join(log_dir, "config_used.yaml"), "w") as f:
        yaml.dump({"run": run_cfg, "model": model_cfg}, f)

    print(f"[{run_id}] Loading model: {model_cfg['name']} on {model_cfg.get('device')}")
    model = get_model_wrapper(model_cfg)

    print(f"[{run_id}] Loading dataset: {dataset_cfg_path}")
    examples = load_dataset_unified(dataset_cfg_path, sample_size=run_cfg.get("sample_size"))
    print(f"[{run_id}] Loaded {len(examples)} examples")

    baseline_module = get_baseline_module(run_cfg["baseline"])

    wandb_run = None
    if run_cfg.get("logging", {}).get("wandb_project"):
        import wandb
        wandb_run = wandb.init(
            project=run_cfg["logging"]["wandb_project"],
            name=run_cfg["logging"].get("wandb_run_name") or run_id,
            config={"run": run_cfg, "model": model_cfg},
        )

    generations_path = os.path.join(log_dir, "generations.jsonl")
    results = []

    with open(generations_path, "w") as out_f:
        for example in tqdm(examples, desc=run_id):
            start = time.time()
            result = baseline_module.run(model, example, model_cfg["generation"])
            elapsed = time.time() - start

            record = {
                "example_id": example["example_id"],
                "prompt": example["prompt"],
                "generation": result.generated_text,
                "reference_answer": example["reference_answer"],
                "num_forward_passes": result.num_forward_passes,
                "wall_time_sec": result.wall_time_sec,
                "num_denoising_steps_used": result.num_denoising_steps_used,
                "model": model_cfg["name"],
                "baseline": run_cfg["baseline"],
                "dataset": example["metadata"].get("dataset"),
            }
            out_f.write(json.dumps(record) + "\n")
            results.append(record)

            if wandb_run:
                wandb_run.log({
                    "wall_time_sec": result.wall_time_sec,
                    "num_forward_passes": result.num_forward_passes,
                })

    avg_time = sum(r["wall_time_sec"] for r in results) / len(results)
    avg_passes = sum(r["num_forward_passes"] for r in results) / len(results)
    summary = {
        "run_id": run_id,
        "num_examples": len(results),
        "avg_wall_time_sec": avg_time,
        "avg_forward_passes": avg_passes,
    }
    with open(os.path.join(log_dir, "metrics.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"[{run_id}] Done. Avg time/example: {avg_time:.2f}s, avg forward passes: {avg_passes:.1f}")
    print(f"[{run_id}] Generations saved to: {generations_path}")

    if wandb_run:
        wandb_run.finish()


if __name__ == "__main__":
    main()
