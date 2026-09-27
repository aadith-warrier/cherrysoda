import re

_NUM = r"-?\d[\d,]*(?:\.\d+)?"
_NUMERIC_PATTERNS = [
    re.compile(r"answer\s+is\s*[:：]?\s*\**\s*\$?\s*(" + _NUM + ")", re.IGNORECASE),
    re.compile(r"\\boxed\{\s*\$?\s*(" + _NUM + ")"),
    re.compile(r"####\s*\$?\s*(" + _NUM + ")"),
]
_NUM_ANY = re.compile(_NUM)

_LABEL_PATTERN = re.compile(r"answer\s+is\s*[:：]?\s*\**\s*\"?(true|false|unknown)\b", re.IGNORECASE)
_LABEL_ANY = re.compile(r"\b(true|false|unknown)\b", re.IGNORECASE)
_LABELS = {"true": "True", "false": "False", "unknown": "Unknown"}

ANSWER_TYPE_BY_DATASET = {"gsm8k": "numeric", "svamp": "numeric", "proofwriter": "label"}


def _to_float(s: str):
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def extract_numeric(text: str):
    best = None
    for pat in _NUMERIC_PATTERNS:
        for m in pat.finditer(text):
            if best is None or m.start() > best.start():
                best = m
    if best is not None:
        v = _to_float(best.group(1))
        if v is not None:
            return v, "pattern"
    nums = _NUM_ANY.findall(text)
    for s in reversed(nums):
        v = _to_float(s)
        if v is not None:
            return v, "fallback"
    return None, "none"


def extract_label(text: str):
    matches = list(_LABEL_PATTERN.finditer(text))
    if matches:
        return _LABELS[matches[-1].group(1).lower()], "pattern"
    matches = list(_LABEL_ANY.finditer(text))
    if matches:
        return _LABELS[matches[-1].group(1).lower()], "fallback"
    return None, "none"


def score_record(record: dict) -> dict:
    answer_type = record.get("answer_type") or ANSWER_TYPE_BY_DATASET[record["dataset"]]
    text = record.get("generation") or ""
    voted = record.get("voted_answer")
    if answer_type == "numeric":
        if voted is not None:
            pred, method = float(voted), "vote"
        else:
            pred, method = extract_numeric(text)
        ref = _to_float(str(record["reference_answer"]))
        correct = pred is not None and ref is not None and abs(pred - ref) <= 1e-4 * max(1.0, abs(ref))
    elif answer_type == "label":
        if voted is not None:
            pred, method = str(voted), "vote"
        else:
            pred, method = extract_label(text)
        correct = pred is not None and pred == str(record["reference_answer"])
    else:
        raise ValueError(f"Unknown answer_type {answer_type!r}")
    return {"predicted": pred, "extraction": method, "correct": bool(correct)}


def summarize(records: list) -> dict:
    n = len(records)
    if n == 0:
        return {"num_examples": 0}
    scored = [score_record(r) for r in records]

    def avg(key):
        vals = [r[key] for r in records if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    out = {
        "num_examples": n,
        "accuracy": sum(s["correct"] for s in scored) / n,
        "num_correct": sum(s["correct"] for s in scored),
        "extraction_pattern": sum(s["extraction"] == "pattern" for s in scored),
        "extraction_vote": sum(s["extraction"] == "vote" for s in scored),
        "extraction_fallback": sum(s["extraction"] == "fallback" for s in scored),
        "extraction_none": sum(s["extraction"] == "none" for s in scored),
        "empty_generations": sum(1 for r in records if not (r.get("generation") or "").strip()),
        "hit_length_limit": sum(1 for r in records if r.get("hit_length_limit")),
        "avg_forward_passes": avg("num_forward_passes"),
        "avg_wall_time_sec": avg("wall_time_sec"),
        "avg_remasked_tokens": avg("num_remasked_tokens"),
        "avg_answer_tokens": avg("answer_num_tokens"),
    }
    if records[0].get("dataset") == "proofwriter" or records[0].get("answer_type") == "label":
        per_label = {}
        for r, s in zip(records, scored):
            lab = str(r["reference_answer"])
            d = per_label.setdefault(lab, {"n": 0, "correct": 0})
            d["n"] += 1
            d["correct"] += s["correct"]
        out["accuracy_by_label"] = {k: v["correct"] / v["n"] for k, v in sorted(per_label.items())}
        preds = {}
        for s in scored:
            preds[str(s["predicted"])] = preds.get(str(s["predicted"]), 0) + 1
        out["predicted_label_counts"] = preds
    return out
