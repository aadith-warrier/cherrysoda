import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
import zlib

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.loaders import load_dataset_unified
from scripts.score_accuracy import extract_final_number, normalize_reference
from src.eval.scoring import ANSWER_TYPE_BY_DATASET, extract_label, extract_numeric, score_record
from src.methods.graph_remask import GraphRemasker, RemaskConfig
from src.methods.scheduler import ScheduleConfig, ScheduledDecoder
from src.models.base import GenerationResult, truncate_at_stop
from src.verify.registry import make_verify_fn


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def make_scorer(dataset_name, answer_type=None):
    """(text, reference) -> (predicted answer, correct). Numeric tasks use the graph scripts' last-number rule
    (as in run_study.py); label tasks (ProofWriter) use src.eval.scoring."""
    answer_type = answer_type or ANSWER_TYPE_BY_DATASET[dataset_name]
    if answer_type == "numeric":
        def score(text, reference):
            pred, ref = extract_final_number(text), normalize_reference(reference)
            return pred, pred is not None and ref is not None and abs(pred - ref) < 1e-4
    else:
        def score(text, reference):
            r = score_record({"dataset": dataset_name, "answer_type": answer_type, "generation": text,
                              "reference_answer": reference})
            return r["predicted"], r["correct"]
    return score



def make_format_check(dataset_name, answer_type=None):
    """text -> did the output state its answer in the requested form ('The answer is ...')? The scorer falls back to
    the last number, so this is reported separately (paper Sec. 3.7: outputs that do not follow the answer format)."""
    answer_type = answer_type or ANSWER_TYPE_BY_DATASET[dataset_name]
    extract = extract_numeric if answer_type == "numeric" else extract_label
    return lambda text: extract(text)[1] == "pattern"


def mcnemar_exact(fixed: int, broken: int) -> float:
    """Two-sided exact McNemar p-value: are the discordant pairs split evenly between the two methods?"""
    n = fixed + broken
    if n == 0:
        return 1.0
    k = min(fixed, broken)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2**n)


def paired_bootstrap_ci(draft_ok, final_ok, n_boot=2000, seed=0):
    rng = random.Random(seed)
    diffs = [int(f) - int(d) for d, f in zip(draft_ok, final_ok)]
    n = len(diffs)
    if n == 0:
        return (0.0, 0.0)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    return (means[int(0.025 * n_boot)], means[int(0.975 * n_boot) - 1])


def _ratio(a, b):
    return a / b if b else 0.0


def _sum_counts(dicts):
    out = {}
    for d in dicts:
        for k, v in d.items():
            out[k] = out.get(k, 0) + v
    return out


def _by_graph_size(records):
    """Accuracy by problem size (number of reasoning steps in the draft's graph), in three roughly equal bins:
    RQ4 asks how the effect varies with reasoning complexity."""
    sizes = sorted(r.get("graph_steps", 0) for r in records)
    if len(sizes) < 3:
        return {}
    lo, hi = sizes[len(sizes) // 3], sizes[2 * len(sizes) // 3]
    bins = {f"<= {lo} steps": lambda g: g <= lo, f"{lo + 1}-{hi} steps": lambda g: lo < g <= hi,
            f"> {hi} steps": lambda g: g > hi}
    out = {}
    for name, keep in bins.items():
        rs = [r for r in records if keep(r.get("graph_steps", 0))]
        if rs:
            out[name] = {"n": len(rs), "draft_accuracy": sum(r["draft_correct"] for r in rs) / len(rs),
                         "accuracy": sum(r["correct"] for r in rs) / len(rs),
                         "fixed": sum(r["fixed"] for r in rs), "broken": sum(r["broken"] for r in rs)}
    return out


def summarize(records, mode_name="graph", method="remask"):
    n = len(records)
    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
    d_ok, f_ok = [r["draft_correct"] for r in records], [r["correct"] for r in records]
    fixed, broken = sum(r["fixed"] for r in records), sum(r["broken"] for r in records)
    touched = [r for r in records if r["rounds"]]
    lo, hi = paired_bootstrap_ci(d_ok, f_ok)
    return {
        "num_examples": n,
        "method": method,
        "mode": mode_name,
        "draft_accuracy": mean(d_ok),
        "accuracy": mean(f_ok),
        "delta_accuracy": mean(f_ok) - mean(d_ok),
        "delta_ci95": [lo, hi],
        "fixed": fixed,
        "broken": broken,
        "mcnemar_p": mcnemar_exact(fixed, broken),
        "reasoning_consistency_before": mean([r["flags_before"] == 0 for r in records]),
        "reasoning_consistency_after": mean([r["flags_after"] == 0 for r in records]),
        "frac_examples_remasked": len(touched) / n if n else 0.0,
        "mean_rounds_when_remasked": mean([len(r["rounds"]) for r in touched]),
        "mean_nfe_draft": mean([r["nfe_draft"] for r in records]),
        "mean_nfe_total": mean([r["num_forward_passes"] for r in records]),
        "mean_nfe_overhead": mean([r["num_forward_passes"] - r["nfe_draft"] for r in records]),
        "mean_remask_ratio_per_round": mean([x["remask_ratio"] for r in touched for x in r["rounds"]]),
        "mean_remask_ratio_cumulative": mean([sum(x["remask_ratio"] for x in r["rounds"]) for r in touched]),
        "mean_affected_subgraph_ratio": mean([x["affected_ratio"] for r in touched for x in r["rounds"]]),
        "flagged_draft_wrong": sum(r["flags_before"] > 0 and not r["draft_correct"] for r in records),
        "flagged_draft_right": sum(r["flags_before"] > 0 and r["draft_correct"] for r in records),
        "unchanged_after_remask": sum(bool(r["rounds"]) and not any(x["changed"] for x in r["rounds"]) for r in records),
        "no_answer_rate": mean([r["predicted_answer"] is None for r in records]),
        "hit_length_limit_rate": mean([r.get("hit_length_limit", False) for r in records]),
        "mean_sec_per_problem": mean([r["wall_time_sec"] for r in records]),

        "format_rate_draft": mean([r.get("draft_format_ok", True) for r in records]),
        "format_rate": mean([r.get("format_ok", True) for r in records]),
        "accuracy_among_formatted_draft": mean([r["draft_correct"] for r in records if r.get("draft_format_ok", True)]),
        "accuracy_among_formatted": mean([r["correct"] for r in records if r.get("format_ok", True)]),

        "mean_graph_steps": mean([r.get("graph_steps", 0) for r in records]),
        "graph_parse_clean_rate": mean([r.get("parse_warnings", 0) == 0 and r.get("graph_steps", 0) > 0 for r in records]),
        "flag_type_counts": _sum_counts([r.get("flag_types", {}) for r in records]),
        "flag_precision_draft_wrong": _ratio(sum(r["flags_before"] > 0 and not r["draft_correct"] for r in records),
                                             sum(r["flags_before"] > 0 for r in records)),
        "wrong_drafts_not_flagged": sum(r["flags_before"] == 0 and not r["draft_correct"] for r in records),
        "wrong_drafts_flagged_still_wrong": sum(r["flags_before"] > 0 and not r["draft_correct"] and not r["correct"]
                                                for r in records),

        "mean_tokens_draft": mean([r.get("tokens_draft", 0) for r in records]),
        "mean_tokens_final": mean([r.get("tokens_final", 0) for r in records]),
        "mean_tokens_regenerated": mean([r.get("tokens_regenerated", 0) for r in records]),
        "mean_sec_generate": mean([r.get("sec_generate", 0.0) for r in records]),
        "mean_sec_refine": mean([r.get("sec_refine", 0.0) for r in records]),
        "mean_sec_parse_verify": mean([r.get("sec_parse_verify", 0.0) for r in records]),
        "mean_sec_total": mean([r.get("sec_generate", 0.0) + r.get("sec_refine", 0.0) + r.get("sec_parse_verify", 0.0)
                                for r in records]),
        "by_graph_size": _by_graph_size(records),
    }


def write_summary(path, run_id, m, settings):
    ci = m["delta_ci95"]
    lines = [
        f"# {run_id}", "",
        f"{settings}, n = {m['num_examples']}", "",
        f"| | draft | after {'scheduling' if m['method'] == 'scheduled' else 'remasking'} |", "|---|---|---|",
        f"| accuracy | {m['draft_accuracy']:.1%} | {m['accuracy']:.1%} ({m['delta_accuracy']:+.1%}, 95% CI "
        f"[{ci[0]:+.1%}, {ci[1]:+.1%}]) |",
        f"| reasoning consistency (no flagged step) | {m['reasoning_consistency_before']:.1%} | "
        f"{m['reasoning_consistency_after']:.1%} |",
        f"| mean NFE | {m['mean_nfe_draft']:.0f} | {m['mean_nfe_total']:.0f} (+{m['mean_nfe_overhead']:.0f}) |",
        "", f"fixed {m['fixed']}, broken {m['broken']} (exact McNemar p = {m['mcnemar_p']:.3f})", "",
        f"- examples with a flagged step: {m['flagged_draft_wrong']} wrong, {m['flagged_draft_right']} right drafts",
        f"- no answer {m['no_answer_rate']:.1%}, hit token limit {m['hit_length_limit_rate']:.1%}, "
        f"{m['mean_sec_per_problem']:.1f} s/problem",
    ]
    lines += [
        f"- answer format ('The answer is'): draft {m['format_rate_draft']:.1%}, final {m['format_rate']:.1%}; accuracy among "
        f"formatted {m['accuracy_among_formatted_draft']:.1%} -> {m['accuracy_among_formatted']:.1%}",
        f"- verifier in situ: graphs parsed cleanly {m['graph_parse_clean_rate']:.1%}, {m['mean_graph_steps']:.1f} steps "
        f"per answer; a flag means a wrong draft {m['flag_precision_draft_wrong']:.1%} of the time; "
        f"{m['wrong_drafts_not_flagged']} wrong drafts never flagged, {m['wrong_drafts_flagged_still_wrong']} flagged "
        f"but still wrong; flags by type {m['flag_type_counts']}",
        f"- tokens: draft {m['mean_tokens_draft']:.0f}, final {m['mean_tokens_final']:.0f}, re-denoised "
        f"{m['mean_tokens_regenerated']:.0f} per problem",
        f"- time per problem: draft {m['mean_sec_generate']:.1f} s + refine {m['mean_sec_refine']:.1f} s + "
        f"parse/verify {m['mean_sec_parse_verify']:.2f} s = {m['mean_sec_total']:.1f} s"
        + (f"; peak GPU memory {m['peak_gpu_gib']:.1f} GiB" if m.get("peak_gpu_gib") else ""),
    ]
    for name, b in m["by_graph_size"].items():
        lines.append(f"- {name} (n={b['n']}): {b['draft_accuracy']:.0%} -> {b['accuracy']:.0%} "
                     f"(fixed {b['fixed']}, broken {b['broken']})")
    if m["method"] == "remask":
        lines += [
            f"- remasked: {m['frac_examples_remasked']:.1%} of examples, {m['mean_rounds_when_remasked']:.2f} rounds on average;"
            f" {m['unchanged_after_remask']} came back identical",
            f"- remask ratio |M|/L: {m['mean_remask_ratio_per_round']:.1%} per round, "
            f"{m['mean_remask_ratio_cumulative']:.1%} cumulative",
            f"- affected-subgraph ratio |A(B)|/|V|: {m['mean_affected_subgraph_ratio']:.1%}",
        ]
    if m["method"] == "scheduled":
        lines += [
            f"- scheduled pass: {m['mean_nfe_schedule']:.0f} NFE ({m['mean_tokens_per_pass']:.2f} tokens per pass, "
            f"{m['mean_levels']:.1f} dependency levels); {m['num_skipped']} examples left as drafted",
        ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")



class DraftCache:
    """Drafts are deterministic (greedy), so each is generated once per (model, decoding, dataset) and reused."""

    def __init__(self, directory, key_obj):
        os.makedirs(directory, exist_ok=True)
        key = hashlib.sha1(json.dumps(key_obj, sort_keys=True, default=str).encode()).hexdigest()[:12]
        self.path = os.path.join(directory, f"drafts_{key}.jsonl")
        self.items = {}
        if os.path.exists(self.path):
            with open(self.path) as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        self.items[d["example_id"]] = d

    def get(self, example_id):
        d = self.items.get(example_id)
        if d is None:
            return None
        return GenerationResult(prompt=None, generated_text=d["generated_text"], num_forward_passes=d["nfe"],
                                wall_time_sec=d["wall"], num_denoising_steps_used=d["nfe"], token_ids=d["token_ids"],
                                raw_metadata=d.get("meta", {}))

    def put(self, example_id, res):
        d = {"example_id": example_id, "generated_text": res.generated_text, "nfe": res.num_forward_passes,
             "wall": res.wall_time_sec, "token_ids": res.token_ids, "meta": res.raw_metadata}
        self.items[example_id] = d
        with open(self.path, "a") as f:
            f.write(json.dumps(d) + "\n")



def seed_everything(seed):
    random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--limit", type=int, help="only the first N problems (writes to <run_id>_limit<N>)")
    ap.add_argument("--device")
    ap.add_argument("--seed", type=int, help="override the run seed (writes to <run_id>_seed<N>); for Dream, report the mean over seeds")
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    if args.seed is not None:
        cfg["seed"] = args.seed
        cfg["run_id"] = f"{cfg['run_id']}_seed{args.seed}"
    method = cfg.get("method", "remask")
    if method not in ("remask", "scheduled"):
        raise ValueError(f"method must be 'remask' or 'scheduled', got {method!r}")
    model_cfg = load_yaml(cfg["model_config"])
    dataset_cfg = load_yaml(cfg["dataset_config"])
    if args.device:
        model_cfg["device"] = args.device
    gen_cfg = {**model_cfg["generation"], **cfg.get("generation", {})}
    remask_cfg = RemaskConfig(**cfg.get("remask", {}))
    sched_cfg = ScheduleConfig(**cfg.get("schedule", {}))
    method_cfg = remask_cfg if method == "remask" else sched_cfg
    sample = args.limit or cfg.get("sample_size")
    run_id = cfg["run_id"] + (f"_limit{args.limit}" if args.limit else "")
    out_dir = os.path.join("logs", run_id)
    os.makedirs(out_dir, exist_ok=True)

    examples = load_dataset_unified(cfg["dataset_config"], sample_size=sample)
    run_config = {"config": cfg, "generation": gen_cfg, "method": method, "method_settings": method_cfg.__dict__,
                  "n": len(examples)}
    cfg_path, gen_path = os.path.join(out_dir, "run_config.json"), os.path.join(out_dir, "generations.jsonl")
    if os.path.exists(cfg_path) and json.load(open(cfg_path)) != json.loads(json.dumps(run_config)):
        raise ValueError(f"{out_dir} holds results for different settings; use a new run_id or delete it")
    json.dump(run_config, open(cfg_path, "w"), indent=2)
    records = [json.loads(l) for l in open(gen_path) if l.strip()] if os.path.exists(gen_path) else []
    if [r["example_id"] for r in records] != [e["example_id"] for e in examples[: len(records)]]:
        raise ValueError(f"{gen_path} does not match the first {len(records)} problems; delete it to start over")

    from src.models.model_registry import get_model_wrapper
    print(f"Loading {model_cfg['name']} on {model_cfg.get('device')}  |  {method} on {dataset_cfg['name']}", flush=True)
    model = get_model_wrapper(model_cfg)
    verify_fn = make_verify_fn(dataset_cfg["name"], cfg.get("verifier", {}))
    method_obj = GraphRemasker(model, verify_fn, remask_cfg) if method == "remask" \
        else ScheduledDecoder(model, verify_fn, sched_cfg)
    score = make_scorer(dataset_cfg["name"], dataset_cfg.get("answer_type"))
    fmt_ok = make_format_check(dataset_cfg["name"], dataset_cfg.get("answer_type"))
    cache = DraftCache(cfg.get("draft_cache", "logs/draft_cache"),
                       {"model": model_cfg["name"], "repo": model_cfg.get("hf_repo_id"), "gen": gen_cfg,
                        "dataset": cfg["dataset_config"],

                        **({"seed": cfg.get("seed", 42)} if (gen_cfg.get("temperature") or 0) > 0 else {})})

    t_start = time.time()
    with open(gen_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
        for i, ex in enumerate(examples, start=1):
            if i <= len(records):
                continue
            draft = cache.get(ex["example_id"])
            if draft is None:
                from baselines.vanilla import run as run_generate

                seed_everything((cfg.get("seed", 42) * 1_000_003 + zlib.crc32(ex["example_id"].encode())) % (2**31))
                draft = run_generate(model, ex, gen_cfg)
                cache.put(ex["example_id"], draft)
            res = method_obj.run(ex, gen_cfg, draft=draft)

            d_pred, d_ok = score(res.draft_text, ex["reference_answer"])
            f_pred, f_ok = score(res.final_text, ex["reference_answer"])
            rec = {
                "example_id": ex["example_id"], "prompt": ex["prompt"], "dataset": ex["metadata"].get("dataset"),
                "reference_answer": ex["reference_answer"], "method": method,
                "draft_generation": res.draft_text, "generation": res.final_text,
                "draft_predicted": d_pred, "predicted_answer": f_pred,
                "draft_correct": d_ok, "correct": f_ok, "fixed": (not d_ok) and f_ok, "broken": d_ok and not f_ok,
                "flags_before": res.flags_before, "flags_after": res.flags_after,
                "nfe_draft": res.nfe_draft, "num_forward_passes": res.nfe_total, "wall_time_sec": res.wall_time_sec,
                "hit_length_limit": len(truncate_at_stop(res.final_token_ids, model.stop_token_ids)) == len(res.final_token_ids),
                "skipped_reason": res.skipped_reason,
                "graph_steps": res.n_steps, "parse_warnings": res.parse_warnings, "flag_types": res.flag_types,
                "tokens_draft": res.tokens_draft, "tokens_final": res.tokens_final,
                "tokens_regenerated": res.tokens_regenerated,
                "sec_generate": res.sec_generate, "sec_refine": res.sec_refine, "sec_parse_verify": res.sec_parse_verify,
                "draft_format_ok": fmt_ok(res.draft_text), "format_ok": fmt_ok(res.final_text),
            }
            if method == "remask":
                rec["rounds"] = [x.__dict__ for x in res.rounds]
            else:
                rec["rounds"] = []
                rec["schedule"] = {"nfe": res.nfe_schedule, "levels": res.n_levels, "steps": res.n_steps,
                                   "tokens_per_pass": res.tokens_per_pass}
            f.write(json.dumps(rec) + "\n")
            f.flush()
            records.append(rec)
            tag = "FIXED" if rec["fixed"] else "BROKE" if rec["broken"] else "ok   " if f_ok else "bad  "
            extra = f"rounds {len(rec['rounds'])}" if method == "remask" else f"passes {res.nfe_schedule}"
            print(f"[{run_id}] {i}/{len(examples)} {tag} flags {res.flags_before}->{res.flags_after} "
                  f"{extra} nfe {res.nfe_total} | acc {sum(r['draft_correct'] for r in records)}"
                  f"->{sum(r['correct'] for r in records)}/{len(records)}", flush=True)

    m = summarize(records, getattr(remask_cfg, "mode", "graph") if method == "remask" else "scheduled", method)
    if method == "scheduled":
        sched = [r["schedule"] for r in records if not r["skipped_reason"]]
        mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
        m.update(mean_nfe_schedule=mean([x["nfe"] for x in sched]), mean_levels=mean([x["levels"] for x in sched]),
                 mean_tokens_per_pass=mean([x["tokens_per_pass"] for x in sched]),
                 num_skipped=len(records) - len(sched))
    try:
        import torch
        if torch.cuda.is_available():
            m["peak_gpu_gib"] = torch.cuda.max_memory_allocated() / 2**30
    except ImportError:
        pass
    m["total_minutes"] = (time.time() - t_start) / 60
    json.dump(m, open(os.path.join(out_dir, "metrics.json"), "w"), indent=2)
    settings = (f"{model_cfg['name']}, method `remask`, mode `{remask_cfg.mode}`, max_rounds {remask_cfg.max_rounds}, "
                f"temperature {remask_cfg.temperature}") if method == "remask" else \
        f"{model_cfg['name']}, method `scheduled`, {sched_cfg.tokens_per_unit} token(s) per active step per pass"
    write_summary(os.path.join(out_dir, "summary.md"), run_id, m, settings)
    print(open(os.path.join(out_dir, "summary.md")).read())


if __name__ == "__main__":
    main()
