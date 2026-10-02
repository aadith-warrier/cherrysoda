"""Metrics for verifiers: per-class P/R/F1, false-positive rate, and calibration (ECE, temperature scaling)."""
import numpy as np

from src.verify.nli import softmax


def binary_metrics(y_true: list, y_flag: list) -> dict:
    """y_true / y_flag: 1 = step is invalid / step was flagged."""
    t, f = np.asarray(y_true, bool), np.asarray(y_flag, bool)
    tp, fp = int((t & f).sum()), int((~t & f).sum())
    fn, tn = int((t & ~f).sum()), int((~t & ~f).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {
        "n": len(t), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": prec, "recall": rec, "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "accuracy": (tp + tn) / len(t) if len(t) else 0.0,
    }


def per_class_metrics(y_true: list, y_pred: list, labels: list) -> dict:
    out = {}
    for lab in labels:
        m = binary_metrics([y == lab for y in y_true], [p == lab for p in y_pred])
        out[lab] = {k: m[k] for k in ("precision", "recall", "f1", "false_positive_rate")} | {"support": m["tp"] + m["fn"]}
    out["macro_f1"] = float(np.mean([out[l]["f1"] for l in labels]))
    out["confusion"] = {t: {p: sum(1 for a, b in zip(y_true, y_pred) if a == t and b == p) for p in labels} for t in labels}
    return out


def auroc(y_true: list, scores: list) -> float:
    """Probability a random invalid step scores higher than a random valid one (ties count half)."""
    t, s = np.asarray(y_true, bool), np.asarray(scores, float)
    pos, neg = s[t], s[~t]
    if not len(pos) or not len(neg):
        return float("nan")
    greater = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(greater / (len(pos) * len(neg)))


def ece(confidence: list, correct: list, n_bins: int = 10) -> tuple:
    """Expected calibration error and the reliability table [(lo, hi, n, mean conf, accuracy)]."""
    c, k = np.asarray(confidence, float), np.asarray(correct, float)
    edges = np.linspace(0, 1, n_bins + 1)
    total, table = 0.0, []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (c > lo) & (c <= hi) if lo > 0 else (c >= lo) & (c <= hi)
        if m.sum() == 0:
            continue
        gap = abs(c[m].mean() - k[m].mean())
        total += m.sum() / len(c) * gap
        table.append((float(lo), float(hi), int(m.sum()), float(c[m].mean()), float(k[m].mean())))
    return float(total), table


def binary_calibration(y_true: list, p_invalid: list, n_bins: int = 10) -> dict:
    """Calibration of p_invalid as a probability that the step is invalid."""
    p, t = np.asarray(p_invalid, float), np.asarray(y_true, float)
    e, table = ece(p, t, n_bins)
    return {"ece": e, "brier": float(((p - t) ** 2).mean()), "reliability": table}


def multiclass_calibration(logits: np.ndarray, y: list, temperature: float = 1.0, n_bins: int = 10) -> dict:
    probs = softmax(logits, temperature)
    pred = probs.argmax(1)
    e, table = ece(probs.max(1), pred == np.asarray(y), n_bins)
    nll = float(-np.log(probs[np.arange(len(y)), y] + 1e-12).mean())
    return {"ece": e, "nll": nll, "accuracy": float((pred == np.asarray(y)).mean()), "reliability": table}


def fit_temperature(logits: np.ndarray, y: list) -> float:
    """Temperature minimising NLL (Guo et al., 2017), by golden-section search over log T."""
    y = np.asarray(y)

    def nll(log_t):
        p = softmax(logits, float(np.exp(log_t)))
        return -np.log(p[np.arange(len(y)), y] + 1e-12).mean()

    a, b = np.log(0.05), np.log(20.0)
    g = (np.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    for _ in range(80):
        if nll(c) < nll(d):
            b = d
        else:
            a = c
        c, d = b - g * (b - a), a + g * (b - a)
    return float(np.exp((a + b) / 2))


def best_threshold(y_true: list, p_invalid: list, max_fpr: float = None) -> float:
    """Flag threshold maximising F1 (optionally subject to a false-positive-rate cap)."""
    best, best_t = -1.0, 0.5
    for thr in np.unique(np.round(p_invalid, 4)):
        m = binary_metrics(y_true, [p >= thr for p in p_invalid])
        if max_fpr is not None and m["false_positive_rate"] > max_fpr:
            continue
        if m["f1"] > best:
            best, best_t = m["f1"], float(thr)
    return best_t
