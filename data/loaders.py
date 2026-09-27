import glob
import json
import os
import random

import yaml


def _load_config(dataset_config_path: str) -> dict:
    with open(dataset_config_path) as f:
        return yaml.safe_load(f)


def _format_number(x) -> str:
    v = float(str(x).replace(",", "").strip())
    return str(int(v)) if v == int(v) else repr(v)


def load_gsm8k(dataset_config_path: str, sample_size: int = None) -> list:
    from datasets import load_dataset

    cfg = _load_config(dataset_config_path)
    ds = load_dataset(cfg["hf_repo_id"], cfg["hf_subset"], split=cfg["split"])
    if sample_size:
        ds = ds.select(range(min(sample_size, len(ds))))

    examples = []
    for i, row in enumerate(ds):
        reference_answer = _format_number(row["answer"].split("####")[-1])
        examples.append({
            "example_id": f"gsm8k_{i:05d}",
            "prompt": cfg["prompt_template"].format(question=row["question"].strip()),
            "reference_answer": reference_answer,
            "reference_solution": row["answer"],
            "metadata": {"dataset": "gsm8k", "answer_type": "numeric"},
        })
    return examples


def load_svamp(dataset_config_path: str, sample_size: int = None) -> list:
    cfg = _load_config(dataset_config_path)
    with open(cfg["raw_json_path"]) as f:
        rows = json.load(f)

    if sample_size:
        rows = rows[:sample_size]

    examples = []
    for i, row in enumerate(rows):
        # Standard SVAMP formatting: Body followed by Question. About a third of
        # Bodies have no final period ("...on each pack"), so add one.
        body = row["Body"].strip()
        if body and body[-1] not in ".?!":
            body += "."
        question_text = f"{body} {row['Question'].strip()}"
        examples.append({
            "example_id": f"svamp_{i:05d}",
            "prompt": cfg["prompt_template"].format(question=question_text),
            "reference_answer": _format_number(row["Answer"]),
            "reference_solution": row.get("Equation", ""),
            "metadata": {"dataset": "svamp", "answer_type": "numeric",
                         "svamp_id": row.get("ID"), "type": row.get("Type")},
        })
    return examples


def _normalize_pw_answer(ans) -> str:
    if isinstance(ans, bool):
        return "True" if ans else "False"
    s = str(ans).strip().lower()
    mapping = {"true": "True", "false": "False", "unknown": "Unknown"}
    if s not in mapping:
        raise ValueError(f"Unexpected ProofWriter answer value: {ans!r}")
    return mapping[s]


def _iter_pw_questions(row: dict):
    qs = row.get("questions", [])
    if isinstance(qs, dict):          # original AllenAI release: {"Q1": {...}, "Q2": {...}}
        items = qs.items()
    else:                             # some mirrors store a list with an "id" field
        items = ((q.get("id", f"Q{j + 1}"), q) for j, q in enumerate(qs))
    for qid, q in items:
        yield qid, q


def load_proofwriter(dataset_config_path: str, sample_size: int = None) -> list:
    cfg = _load_config(dataset_config_path)
    depth = cfg["depth"]
    world = cfg.get("world", "OWA")
    split = cfg.get("split", "test")
    raw_dir = cfg["raw_data_path"]

    pattern = os.path.join(raw_dir, "**", world, f"depth-{depth}", f"meta-{split}.jsonl")
    files = sorted(glob.glob(pattern, recursive=True))
    if not files:
        raise FileNotFoundError(
            f"No file matching {pattern}. Download the ProofWriter zip from "
            f"https://allenai.org/data/proofwriter (see scripts/download_data.sh) and unzip it into {raw_dir}."
        )
    if len(files) > 1:
        raise RuntimeError(f"Expected one ProofWriter file, found {len(files)}: {files}")

    flat = []
    with open(files[0]) as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            for qid, q in _iter_pw_questions(row):
                flat.append({
                    "uid": f"{row['id']}_{qid}",
                    "theory": row["theory"],
                    "hypothesis": q["question"],
                    "answer": _normalize_pw_answer(q["answer"]),
                    "qdep": q.get("QDep"),
                    "strategy": q.get("strategy"),
                    "proof": q.get("proofs", ""),
                })

    # Label-balanced, seeded order: shuffle each label's pool, then interleave
    # True/False/Unknown round-robin. Any prefix is (near-)balanced, and a
    # smaller sample is always a prefix of a larger one.
    rng = random.Random(cfg.get("sample_seed", 1234))
    labels = ["True", "False", "Unknown"]
    pools = {lab: [x for x in flat if x["answer"] == lab] for lab in labels}
    for lab in labels:
        rng.shuffle(pools[lab])
    ordered = []
    for i in range(max(len(p) for p in pools.values())):
        for lab in labels:
            if i < len(pools[lab]):
                ordered.append(pools[lab][i])
    if sample_size:
        ordered = ordered[:sample_size]

    examples = []
    for i, x in enumerate(ordered):
        examples.append({
            "example_id": f"proofwriter_d{depth}_{i:05d}",
            "prompt": cfg["prompt_template"].format(theory=x["theory"], hypothesis=x["hypothesis"]),
            "reference_answer": x["answer"],
            "reference_solution": x["proof"],
            "metadata": {"dataset": "proofwriter", "answer_type": "label", "depth": depth, "world": world,
                         "source_uid": x["uid"], "qdep": x["qdep"], "strategy": x["strategy"]},
        })
    return examples


LOADER_REGISTRY = {
    "gsm8k": load_gsm8k,
    "svamp": load_svamp,
    "proofwriter": load_proofwriter,
}


def load_dataset_unified(dataset_config_path: str, sample_size=None) -> list:
    cfg = _load_config(dataset_config_path)
    loader_key = cfg["loader"]
    if loader_key not in LOADER_REGISTRY:
        raise ValueError(f"Unknown loader '{loader_key}'. Registered: {list(LOADER_REGISTRY.keys())}")

    if sample_size == "full":
        effective_sample_size = cfg.get("full_sample_size")
    elif sample_size is not None:
        effective_sample_size = int(sample_size)
    else:
        effective_sample_size = cfg.get("prelim_sample_size")

    return LOADER_REGISTRY[loader_key](dataset_config_path, effective_sample_size)
