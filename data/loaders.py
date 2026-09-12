import yaml
from datasets import load_dataset


def _load_config(dataset_config_path: str) -> dict:
    with open(dataset_config_path) as f:
        return yaml.safe_load(f)


def load_gsm8k(dataset_config_path: str, sample_size: int = None) -> list:
    cfg = _load_config(dataset_config_path)
    ds = load_dataset(cfg["hf_repo_id"], cfg["hf_subset"], split=cfg["split"])
    if sample_size:
        ds = ds.select(range(min(sample_size, len(ds))))

    examples = []
    for i, row in enumerate(ds):
        reference_answer = row["answer"].split("####")[-1].strip()
        examples.append({
            "example_id": f"gsm8k_{i:05d}",
            "prompt": cfg["prompt_template"].format(question=row["question"]),
            "reference_answer": reference_answer,
            "reference_solution": row["answer"],
            "metadata": {"dataset": "gsm8k"},
        })
    return examples


def load_svamp(dataset_config_path: str, sample_size: int = None) -> list:
    import json

    cfg = _load_config(dataset_config_path)
    with open(cfg["raw_json_path"]) as f:
        rows = json.load(f)

    if sample_size:
        rows = rows[:sample_size]

    examples = []
    for i, row in enumerate(rows):
        question_text = f"{row.get('Body', '')} {row.get('Question', '')}".strip()
        reference_answer = str(row.get("Answer", ""))
        examples.append({
            "example_id": f"svamp_{i:05d}",
            "prompt": cfg["prompt_template"].format(question=question_text),
            "reference_answer": reference_answer,
            "reference_solution": "",  
            "metadata": {"dataset": "svamp"},
        })
    return examples


def load_proofwriter(dataset_config_path: str, sample_size: int = None) -> list:
    import json
    import glob

    cfg = _load_config(dataset_config_path)
    target_depth = cfg.get("depth")
    raw_dir = cfg["raw_data_path"]

    candidate_files = glob.glob(f"{raw_dir}/**/*depth-{target_depth}*.jsonl", recursive=True)
    if not candidate_files:
        raise FileNotFoundError(
            f"No ProofWriter files found matching depth {target_depth} under {raw_dir}. "
            f"Download it manually from https://allenai.org/data/proofwriter, unzip into "
            f"{raw_dir}, then fix the glob pattern in this function to match the real layout."
        )

    rows = []
    for fp in candidate_files:
        with open(fp) as f:
            for line in f:
                rows.append(json.loads(line))

    if sample_size:
        rows = rows[:sample_size]

    examples = []
    for i, row in enumerate(rows):
        theory = row.get("theory", row.get("triples_rules", ""))
        hypothesis = row.get("question", row.get("hypothesis", ""))
        reference_answer = str(row.get("answer", row.get("label", "")))

        examples.append({
            "example_id": f"proofwriter_d{target_depth}_{i:05d}",
            "prompt": cfg["prompt_template"].format(theory=theory, hypothesis=hypothesis),
            "reference_answer": reference_answer,
            "reference_solution": row.get("proof", ""),
            "metadata": {"dataset": "proofwriter", "depth": target_depth},
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
        effective_sample_size = None
    elif sample_size is not None:
        effective_sample_size = sample_size
    else:
        effective_sample_size = cfg.get("prelim_sample_size")

    return LOADER_REGISTRY[loader_key](dataset_config_path, effective_sample_size)