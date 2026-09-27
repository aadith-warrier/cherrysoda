"""Mechanical checks of the trace-to-graph builder over saved generations.

Each check is independent of the builder's own logic where possible, so it can catch the builder's
mistakes: lost text, wrong spans, equations present in the text but not parsed, parsed values that
don't appear in the text, backward edges, and ambiguous number attribution.
"""
import argparse
import glob
import json
import re
from collections import Counter, defaultdict

from src.graph.extract import find_numbers, normalize_math, values_match
from src.graph.registry import build_graph
from src.graph.schema import PROBLEM_NODE_ID

# Loose, builder-independent pattern: something numeric, an "=", then a number.
EQUATION_HINT_RE = re.compile(r"\d[^=\n]*?=\s*[$(]?\s*-?\d")
MARKUP_RE = re.compile(r"\*\*|^#+|\\\[|\\\]|\\\(|\\\)|^\s*(?:\d+[.)]|[-*•])\s", re.M)
FORMAT_PATTERNS = {
    "brackets_around_numbers": re.compile(r"\(\s*\d[^()]*\)"),
    "negative_number": re.compile(r"(?:^|[=(\s])-\d"),
    "clock_time": re.compile(r"\b\d{1,2}:\d{2}\b"),
    "bare_fraction": re.compile(r"(?<![\d.])\d+/\d+(?![\d.])"),
    "number_word_in_step": re.compile(r"\b(?:twice|half|double|triple|thrice|dozen)\b", re.I),
}


def clean(s):
    return s.replace("**", "").strip().lstrip("#").strip()


def audit(records):
    issues = defaultdict(list)
    counts = Counter()
    for r in records:
        g = build_graph(r)
        gen = r["generation"]
        order = {n.node_id: i for i, n in enumerate(g.nodes)}
        covered = [False] * len(gen)
        counts["answers"] += 1
        for n in g.nodes:
            if n.kind == "problem":
                continue
            counts["nodes"] += 1
            if clean(gen[n.char_start:n.char_end]) != n.text:
                issues["span_mismatch"].append((r["example_id"], n.node_id, n.text[:60]))
            for i in range(n.char_start, n.char_end):
                covered[i] = True
            if n.kind == "header":
                continue
            math = normalize_math(n.text)
            nums = [m.value for m in find_numbers(math)]
            # The number right after each "=" must be a parsed result or operand (chains like
            # "a * b = c * d = e" are one equation whose middle values are operands).
            parsed = [v for eq in n.equations for v in eq.operands + ([eq.result] if eq.result is not None else [])]
            parsed += [m.value for eq in n.equations for m in find_numbers(eq.rhs)]
            for m in re.finditer(r"=", math):
                after = find_numbers(math, m.end(), min(len(math), m.end() + 12))
                if after and not any(values_match(after[0].value, v) for v in parsed):
                    issues["equation_in_text_not_parsed"].append((r["example_id"], n.node_id, math[:120]))
                    break
            for eq in n.equations:
                counts["equations"] += 1
                for v in eq.operands + ([eq.result] if eq.result is not None else []):
                    if not any(values_match(v, x) or values_match(v / 100, x) or values_match(v, x / 100) for x in nums):
                        issues["parsed_value_not_in_text"].append((r["example_id"], n.node_id, v, eq.raw[:80]))
                if eq.result is not None and len(eq.operands) >= 2 and len(eq.operators) != len(eq.operands) - 1:
                    issues["operator_operand_mismatch"].append((r["example_id"], n.node_id, eq.raw[:80]))
            for name, pat in FORMAT_PATTERNS.items():
                if pat.search(math):
                    counts[f"format:{name}"] += 1
        # Text outside every node span, ignoring whitespace and pure markup.
        lost = "".join(c if not cov else " " for c, cov in zip(gen, covered))
        lost = MARKUP_RE.sub(" ", lost)
        lost_words = [w for w in lost.split() if any(ch.isalnum() for ch in w)]
        if lost_words:
            issues["text_not_in_any_step"].append((r["example_id"], " ".join(lost_words)[:100]))
        for e in g.edges:
            counts["edges"] += 1
            if order[e.src] >= order[e.dst]:
                issues["backward_edge"].append((r["example_id"], e.src, e.dst))
            if e.reason == "value_flow":
                dst_vals = g.node(e.dst).values_used
                for ev in e.evidence.split(","):
                    if not any(values_match(float(ev), v) or values_match(float(ev), v / 100) or values_match(float(ev) / 100, v)
                               for v in dst_vals):
                        issues["edge_value_not_used_by_target"].append((r["example_id"], e.src, e.dst, ev))
        # Ambiguity: a used value produced by 2+ earlier steps (builder picks the most recent).
        producers = defaultdict(list)
        for n in g.nodes:
            if n.kind in ("calc", "claim"):
                for v in n.values_used:
                    earlier = [m.node_id for m in g.nodes[1: order[n.node_id]]
                               if m.kind in ("calc", "claim") and any(values_match(v, p) for p in m.values_produced)]
                    if len(earlier) >= 2:
                        producers[(n.node_id, v)] = earlier
        counts["ambiguous_attributions"] += len(producers)
        counts["used_values"] += sum(len(n.values_used) for n in g.nodes if n.kind in ("calc", "claim"))
    return issues, counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--glob", default="logs/study_*/*/generations.jsonl")
    parser.add_argument("--examples", type=int, default=6)
    args = parser.parse_args()
    records, seen = [], set()
    for path in sorted(glob.glob(args.glob)):
        if path.endswith("steps32/generations.jsonl"):
            continue  # collapsed 8-tokens-per-round outputs, not real reasoning text
        for line in open(path):
            r = json.loads(line)
            key = (r["example_id"], r["generation"])
            if key not in seen:
                seen.add(key)
                records.append(r)
    issues, counts = audit(records)
    print(f"{counts['answers']} unique answers, {counts['nodes']} steps, {counts['equations']} equations, {counts['edges']} edges")
    print(f"ambiguous attributions: {counts['ambiguous_attributions']} of {counts['used_values']} used values")
    for k in sorted(k for k in counts if k.startswith("format:")):
        print(f"steps containing {k[7:]}: {counts[k]}")
    print()
    for name in ("span_mismatch", "text_not_in_any_step", "equation_in_text_not_parsed", "parsed_value_not_in_text",
                 "operator_operand_mismatch", "backward_edge", "edge_value_not_used_by_target"):
        items = issues.get(name, [])
        print(f"== {name}: {len(items)}")
        for it in items[: args.examples]:
            print("    ", it)


if __name__ == "__main__":
    main()
