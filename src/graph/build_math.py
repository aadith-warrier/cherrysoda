import re
from collections import Counter

from src.graph.extract import find_numbers, find_word_numbers, normalize_math, parse_equations, values_match
from src.graph.schema import PROBLEM_NODE_ID, DependencyEdge, ReasoningGraph, ReasoningNode
from src.graph.segment import segment_generation
from src.graph.stats import fmt_value

PROBLEM_RE = re.compile(r"(?:Problem|Question):\s*(.*?)\s*(?:Solution:|Let's think step by step|Answer:|$)", re.S)
STEP_REF_RE = re.compile(r"\bstep\s+(\d+)\b", re.I)
PREV_REF_RE = re.compile(r"\b(?:from above|previous(?:ly)?|the result above)\b", re.I)

CAPITALIZED_RE = re.compile(r"\b[A-Z][a-z]+\b")
UNIT_NOUN_RE = re.compile(r"\d%?\s+([a-z]{3,})\b")
ENTITY_STOPWORDS = {
    "the", "so", "then", "therefore", "since", "first", "second", "third", "next", "finally",
    "total", "in", "she", "he", "they", "it", "we", "this", "that", "each", "and", "of", "per",
    "times", "is", "are", "to", "for", "with", "from", "was", "has", "have", "more", "less",
    "calculate", "determine", "find", "step", "answer", "solution", "problem", "let",
}


def _entities(text: str) -> set:
    words = CAPITALIZED_RE.findall(text)[1:] if text[:1].isupper() else CAPITALIZED_RE.findall(text)
    ents = {w.lower() for w in words} | {w.lower() for w in UNIT_NOUN_RE.findall(text)}
    return ents - ENTITY_STOPWORDS


_UNIT_WORDS_RE = re.compile(r"\s*/?\s*([A-Za-z]+)(?:\s+([A-Za-z]+))?(?:\s+([A-Za-z]+))?")
_UNIT_STOPWORDS = {
    "of", "per", "each", "the", "a", "an", "and", "for", "to", "in", "at", "is", "are", "was", "were", "on",
    "with", "from", "by", "as", "so", "that", "this", "it", "or", "than", "every", "more", "less", "then",
}
_CONTAINER_WORDS = {
    "pair", "piece", "pack", "box", "bag", "set", "cup", "unit", "bunch", "packet", "bottle", "can", "jar",
    "slice", "batch", "group", "row", "kind", "type", "carton", "crate", "bucket",
}
# Small fractions such as 2/3 or 1 / 4 are constants ("two-thirds"), not quantities from earlier steps.
_FRACTION_LITERAL_RE = re.compile(r"(?<![\d.])(\d)\s*/\s*(\d{1,2})(?![\d.])")


def _singular(w: str) -> str:
    w = w.lower()
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def _unit_of(text: str, end: int):
    """(head noun, container) right after a number: "3 pairs of pants" -> ("pant", "pair"), "6 hours" -> ("hour", None)."""
    m = _UNIT_WORDS_RE.match(text, end)
    if not m:
        return None
    words = [w for w in m.groups() if w]
    first = _singular(words[0])
    if first in _UNIT_STOPWORDS:
        return None
    if first in _CONTAINER_WORDS and len(words) >= 3 and words[1].lower() == "of":
        return (_singular(words[2]), first)
    return (first, None)


def _units_compatible(a, b) -> bool:
    if a is None or b is None or a[0] == b[0]:
        return True
    return a[0] == b[1] or b[0] == a[1]  # "12 cups" is compatible with "12 cups of feed"


def _with_units(text: str, mentions: list) -> list:
    for m in mentions:
        m.unit = _unit_of(text, m.end)
    return mentions


def _fraction_spans(text: str) -> list:
    return [(m.start(), m.end()) for m in _FRACTION_LITERAL_RE.finditer(text) if int(m.group(1)) < int(m.group(2)) <= 12]


def _extract_problem(prompt, warnings: list) -> str:
    """The question being answered: the last one in the prompt, since few-shot prompts contain worked examples first."""
    if isinstance(prompt, list):
        prompt = [m for m in prompt if m["role"] == "user"][-1]["content"]
    matches = PROBLEM_RE.findall(prompt)
    if matches:
        return matches[-1].strip()
    warnings.append("problem text not found in prompt; using the whole prompt")
    return prompt.strip()


def build_math_graph(record: dict) -> ReasoningGraph:
    """Build a dependency graph for a GSM8K/SVAMP answer.

    Edges always point from an earlier step to a later one, so the graph is a DAG.
    Value flow: a step that uses a number links from the most recent earlier step
    that provided it (an equation result, or a number stated in an equation-free
    claim), falling back to the problem node if the number is a given.
    """
    warnings = []
    generation = record["generation"]

    problem_text = _extract_problem(record["prompt"], warnings)
    problem_mentions = _with_units(problem_text, find_numbers(problem_text) + find_word_numbers(problem_text))
    nodes = [ReasoningNode(
        node_id=PROBLEM_NODE_ID, text=problem_text, char_start=-1, char_end=-1, kind="problem",
        values_produced=[m.value for m in problem_mentions],
    )]
    provided = [problem_mentions]
    used = [[]]

    for idx, seg in enumerate(segment_generation(generation), start=1):
        node = ReasoningNode(
            node_id=str(idx), text=seg.text, char_start=seg.start, char_end=seg.end,
            kind="header" if seg.is_header else "claim", list_marker=seg.list_marker,
        )
        step_provided, step_used = [], []
        if not seg.is_header:
            math_text = normalize_math(seg.text)
            fractions = _fraction_spans(math_text)
            mentions = [m for m in _with_units(math_text, find_numbers(math_text))
                        if not any(s <= m.start < e for s, e in fractions)]
            equations, results, eq_warnings = parse_equations(math_text)
            warnings.extend(f"step {idx}: {w}" for w in eq_warnings)
            if equations:
                node.kind = "calc"
                node.equations = equations
                result_mentions = [r for r, _ in results]
                # An assignment like "Total hours = 45" restates a known value, so it also uses it.
                assignment_starts = {r.start for r, is_assignment in results if is_assignment}
                result_starts = {r.start for r in result_mentions} - assignment_starts
                step_provided = result_mentions
                step_used = [
                    m for m in mentions
                    if m.start not in result_starts
                    and not any(r.start < m.start and _mention_matches(m, r) for r in result_mentions)
                ]
            else:
                step_provided = mentions
                step_used = mentions
        node.values_used = [m.value for m in step_used]
        node.values_produced = [m.value for m in step_provided]
        nodes.append(node)
        provided.append(step_provided)
        used.append(step_used)

    if len(nodes) == 1:
        warnings.append("no reasoning steps found in generation")

    edges = {}

    def add_edge(src: int, dst: int, reason: str, evidence: str):
        key = (nodes[src].node_id, nodes[dst].node_id)
        if key in edges:
            # One edge per step pair; only same-reason evidence is merged (a value_flow edge's
            # evidence stays a list of numbers even if the step also names its source in words).
            if edges[key].reason == reason and evidence and evidence not in edges[key].evidence.split(","):
                edges[key].evidence += f",{evidence}"
            return
        edges[key] = DependencyEdge(key[0], key[1], reason, evidence)

    for j in range(1, len(nodes)):
        for mention in used[j]:
            srcs = _find_providers(mention, provided, j, limit=1)
            if srcs:
                add_edge(srcs[0], j, "value_flow", fmt_value(mention.value))
        # "180 + 180 + 15": a value repeated within one equation adds different quantities,
        # so each occurrence links to a different earlier step.
        for eq in nodes[j].equations:
            repeats = Counter(fmt_value(v) for v in eq.operands)
            for key, count in repeats.items():
                mention = next((m for m in used[j] if fmt_value(m.value) == key), None)
                if count > 1 and mention is not None:
                    for src in _find_providers(mention, provided, j, limit=count):
                        add_edge(src, j, "value_flow", key)

    for j in range(1, len(nodes)):
        if nodes[j].kind == "header":
            continue
        for m in STEP_REF_RE.finditer(nodes[j].text):
            target = int(m.group(1))
            for i in range(j - 1, 0, -1):
                if nodes[i].list_marker == target and nodes[i].kind != "header":
                    add_edge(i, j, "explicit_ref", m.group(0))
                    break
        if PREV_REF_RE.search(nodes[j].text):
            for i in range(j - 1, 0, -1):
                if nodes[i].kind != "header":
                    add_edge(i, j, "explicit_ref", PREV_REF_RE.search(nodes[j].text).group(0))
                    break

    has_incoming = {e.dst for e in edges.values()}
    for j in range(1, len(nodes)):
        if nodes[j].kind == "header" or nodes[j].node_id in has_incoming:
            continue
        ents_j = _entities(nodes[j].text)
        for i in range(j - 1, 0, -1):
            if nodes[i].kind == "header":
                continue
            shared = ents_j & _entities(nodes[i].text)
            if shared:
                add_edge(i, j, "shared_entity", sorted(shared)[0])
                break

    return ReasoningGraph(
        example_id=record["example_id"],
        dataset=record.get("dataset", ""),
        nodes=nodes,
        edges=list(edges.values()),
        parse_warnings=warnings,
    )


def _mention_matches(a, b) -> bool:
    return any(values_match(x, y) for x in a.candidates() for y in b.candidates())


def _find_providers(mention, provided: list, j: int, limit: int) -> list:
    """Up to `limit` earlier steps that produced this value (most recent first), skipping ones whose
    unit contradicts it ("3 pairs of shorts" can't supply "3 pairs of pants"); the problem is the fallback."""
    found = []
    for i in range(j - 1, 0, -1):
        if any(_mention_matches(mention, p) and _units_compatible(mention.unit, p.unit) for p in provided[i]):
            found.append(i)
            if len(found) == limit:
                return found
    if any(_mention_matches(mention, p) for p in provided[0]):
        found.append(0)
    return found
