import argparse
import importlib
import json
import os
import time

import torch
import yaml

from data.loaders import load_dataset_unified
from scripts.score_accuracy import extract_final_number, normalize_reference
from src.graph.registry import build_graph
from src.graph.stats import fmt_value, graph_stats
from src.models.model_registry import get_model_wrapper


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def load_resumable(out_dir, examples, run_config):
    """Records from an interrupted run of this exact configuration, so it can continue where it stopped."""
    cfg_path = os.path.join(out_dir, "run_config.json")
    gen_path = os.path.join(out_dir, "generations.jsonl")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            saved = json.load(f)
        if saved != run_config:
            raise ValueError(f"{out_dir} holds results for different settings:\n{saved}\nvs\n{run_config}")
    with open(cfg_path, "w") as f:
        json.dump(run_config, f, indent=2)
    if not os.path.exists(gen_path):
        return []
    with open(gen_path) as f:
        records = [json.loads(l) for l in f if l.strip()]
    expected = [ex["example_id"] for ex in examples[: len(records)]]
    if [r["example_id"] for r in records] != expected:
        raise ValueError(f"{gen_path} does not match the first {len(records)} problems; delete it to start over")
    for r in records:
        r.update(graph_stats(build_graph(r)))  # graph code may have changed since they were written
    return records


def run_variant(model, baseline, examples, gen_cfg, out_dir, name, dataset_path):
    os.makedirs(out_dir, exist_ok=True)
    torch.cuda.reset_peak_memory_stats()
    records = load_resumable(out_dir, examples, {"generation": gen_cfg, "dataset_config": dataset_path})
    if records:
        print(f"[{name}] resuming after {len(records)} finished problems", flush=True)
    t_start = time.time()
    with open(os.path.join(out_dir, "generations.jsonl"), "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
        for i, ex in enumerate(examples, start=1):
            if i <= len(records):
                continue
            result = baseline.run(model, ex, gen_cfg)
            pred = extract_final_number(result.generated_text)
            ref = normalize_reference(ex["reference_answer"])
            record = {
                "example_id": ex["example_id"],
                "prompt": ex["prompt"],
                "generation": result.generated_text,
                "reference_answer": ex["reference_answer"],
                "predicted_answer": pred,
                "correct": pred is not None and ref is not None and abs(pred - ref) < 1e-4,
                "num_forward_passes": result.num_forward_passes,
                "wall_time_sec": result.wall_time_sec,
                "dataset": ex["metadata"].get("dataset"),
                **result.raw_metadata,
            }
            record.update(graph_stats(build_graph(record)))
            f.write(json.dumps(record) + "\n")
            f.flush()
            records.append(record)
            n_correct = sum(r["correct"] for r in records)
            print(
                f"[{name}] {i}/{len(examples)} {'OK ' if record['correct'] else 'BAD'} "
                f"pred={fmt_value(pred) if pred is not None else '-'} ref={ex['reference_answer']} "
                f"{result.wall_time_sec:.1f}s tokens={record['answer_tokens']} "
                f"limit={'Y' if record['hit_length_limit'] else 'n'} | running acc {n_correct}/{i}",
                flush=True,
            )

    n = len(records)
    mean = lambda key: sum(r[key] for r in records) / n
    metrics = {
        "variant": name,
        "generation": gen_cfg,
        "num_examples": n,
        "accuracy": mean("correct"),
        "no_answer_rate": sum(r["predicted_answer"] is None for r in records) / n,
        "hit_length_limit_rate": mean("hit_length_limit"),
        "mean_answer_tokens": mean("answer_tokens"),
        "mean_sec_per_problem": mean("wall_time_sec"),
        "mean_forward_passes": mean("num_forward_passes"),
        "leftover_masks_total": sum(r["leftover_masks"] for r in records),
        "peak_gpu_gib": torch.cuda.max_memory_allocated() / 2**30,
        "mean_graph_steps": mean("graph_steps"),
        "mean_graph_equations": mean("graph_equations"),
        "mean_graph_unsourced_numbers": mean("graph_unsourced_numbers"),
        "total_minutes": (time.time() - t_start) / 60,
    }
    with open(os.path.join(out_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    return metrics


def write_summary(study_cfg, out_root):
    rows = []
    for v in study_cfg["variants"]:
        path = os.path.join(out_root, v["name"], "metrics.json")
        if os.path.exists(path):
            with open(path) as f:
                rows.append(json.load(f))
    lines = [
        f"# {study_cfg['study_id']}",
        "",
        f"{study_cfg['sample_size']} problems from `{study_cfg['dataset_config']}`, model `{study_cfg['model_config']}`.",
        "",
        "| variant | length | steps | block | tok/round | accuracy | no answer | hit limit | answer tokens | s/problem "
        "| graph steps | equations | unsourced | extras |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in rows:
        g = m["generation"]
        length, steps = g["max_new_tokens"], g["num_denoising_steps"]
        block = g.get("block_length") or length
        extras = [k for k in ("logits_eos_inf", "confidence_eos_eot_inf") if g.get(k)]
        if m.get("dataset_config", study_cfg["dataset_config"]) != study_cfg["dataset_config"]:
            extras.append(os.path.basename(m["dataset_config"]))
        lines.append(
            f"| {m['variant']} | {length} | {steps} | {'off' if block == length else block} | {length / steps:g} "
            f"| {m['accuracy']:.0%} | {m['no_answer_rate']:.0%} | {m['hit_length_limit_rate']:.0%} "
            f"| {m['mean_answer_tokens']:.0f} | {m['mean_sec_per_problem']:.1f} | {m['mean_graph_steps']:.1f} "
            f"| {m['mean_graph_equations']:.1f} | {m['mean_graph_unsourced_numbers']:.2f} | {', '.join(extras) or '-'} |"
        )
    with open(os.path.join(out_root, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to a configs/study/*.yaml file")
    parser.add_argument("--variants", help="Comma-separated subset of variant names to run")
    args = parser.parse_args()

    study_cfg = load_yaml(args.config)
    model_cfg = load_yaml(study_cfg["model_config"])
    out_root = os.path.join("logs", study_cfg["study_id"])
    os.makedirs(out_root, exist_ok=True)

    variants = study_cfg["variants"]
    if args.variants:
        wanted = set(args.variants.split(","))
        unknown = wanted - {v["name"] for v in variants}
        if unknown:
            raise ValueError(f"Unknown variants: {sorted(unknown)}")
        variants = [v for v in variants if v["name"] in wanted]

    pending = [v for v in variants if not os.path.exists(os.path.join(out_root, v["name"], "metrics.json"))]
    for v in variants:
        if v not in pending:
            print(f"[{v['name']}] already done, skipping", flush=True)
    if not pending:
        write_summary(study_cfg, out_root)
        return

    datasets = {}
    for v in pending:
        path = v.get("dataset_config", study_cfg["dataset_config"])
        if path not in datasets:
            datasets[path] = load_dataset_unified(path, sample_size=study_cfg["sample_size"])
    baseline = importlib.import_module(f"baselines.{study_cfg['baseline']}")
    print(f"Loading {model_cfg['name']} ({model_cfg.get('dtype')}) on {model_cfg.get('device')}", flush=True)
    model = get_model_wrapper(model_cfg)

    for v in pending:
        gen_cfg = {**model_cfg["generation"], **study_cfg.get("base_generation", {}), **v["generation"]}
        dataset_path = v.get("dataset_config", study_cfg["dataset_config"])
        print(f"\n=== {v['name']}: {v['generation']} on {dataset_path} ===", flush=True)
        m = run_variant(
            model, baseline, datasets[dataset_path], gen_cfg, os.path.join(out_root, v["name"]), v["name"], dataset_path
        )
        m["dataset_config"] = dataset_path
        with open(os.path.join(out_root, v["name"], "metrics.json"), "w") as f:
            json.dump(m, f, indent=2)
        print(
            f"[{v['name']}] DONE accuracy {m['accuracy']:.0%}, no answer {m['no_answer_rate']:.0%}, "
            f"hit limit {m['hit_length_limit_rate']:.0%}, {m['mean_sec_per_problem']:.1f}s/problem, "
            f"{m['total_minutes']:.1f} min",
            flush=True,
        )
        write_summary(study_cfg, out_root)

    print(f"\nSummary: {os.path.join(out_root, 'summary.md')}", flush=True)


if __name__ == "__main__":
    main()
