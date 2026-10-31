def graph_arithmetic(cfg: dict):
    from src.verify.graph_math import GraphArithmeticVerifier
    return GraphArithmeticVerifier(check_grounding=cfg.get("check_grounding", True)).verify_graph


ANSWER_LABEL_RE = None


def answer_label(text: str):
    """The last True / False / Unknown stated in an answer line, or None."""
    import re
    global ANSWER_LABEL_RE
    if ANSWER_LABEL_RE is None:
        ANSWER_LABEL_RE = re.compile(r"\b(true|false|unknown)\b", re.I)
    found = ANSWER_LABEL_RE.findall(text)
    return found[-1].capitalize() if found else None


def hypothesis_support(graph, verdicts: dict):
    """(hypothesis atom or None, proved, disproved) from the trace's own verified, asserted steps."""
    from src.graph.build_logic import _problem_parts
    from src.verify.base import VALID
    from src.verify.causal import sentences, split_causal
    from src.verify.logic import parse_atom, parse_theory

    theory, hyp = _problem_parts(graph.nodes[0].text, [])
    th = parse_theory(theory)
    h = parse_atom(hyp, th.verbs) if hyp else None
    if h is None:
        return None, False, False
    pos_t, neg_t = h.text(), h.negated().text()
    proves = disproves = False
    for n in graph.nodes:
        if n.kind not in ("fact", "inference"):
            continue
        v = verdicts.get(n.node_id)
        if v is None or v.status != VALID:
            continue
        if any(split_causal(x).cue == "if" for x in sentences(n.text)):
            continue
        proves |= pos_t in n.values_produced
        disproves |= neg_t in n.values_produced
    return h, proves, disproves


def answer_support_verdicts(graph, verdicts: dict) -> dict:
    """Open-world check of the answer lines against the trace's own verified steps (never the gold label):
    True needs a verified step that asserts the hypothesis, False one that asserts its negation, and Unknown is
    contradicted by either. Asserted means a `fact` or `inference` step marked valid that is not a hypothetical
    "if ... then" application. Returns {answer node id: INVALID verdict} for answer lines that fail; the label is
    kept in the check's detail so the remask loop can forbid it."""
    from src.verify.base import INVALID, Check, Verdict

    h, proves, disproves = hypothesis_support(graph, verdicts)
    if h is None:
        return {}
    out = {}
    for n in graph.nodes:
        if n.kind != "answer":
            continue
        label = answer_label(n.text)
        why = None
        if label == "True" and not proves:
            why = "True, but no verified step derives the hypothesis"
        elif label == "False" and not disproves:
            why = "False, but no verified step derives its negation"
        elif label == "Unknown" and (proves or disproves):
            why = "Unknown, but a verified step settles the hypothesis"
        if why:
            out[n.node_id] = Verdict(INVALID, 1.0, "answer_support", error_type="unsupported_answer",
                                     checks=[Check("answer_support", False, label)])
    return out


def graph_logic(cfg: dict):
    """ProofWriter: the symbolic verifier on every graph step, with all earlier steps as premises (as in
    scripts/verify_generations.py). Steps whose kind is in skip_kinds are left out: by default `meta`, the lines
    that only restate the hypothesis (e.g. the bullet under a "Hypothesis:" header). The verifier reads those as
    claims and flags them whenever the hypothesis is unprovable, which was 15% of its flags on LLaDA, and they
    feed nothing downstream."""
    from src.verify.base import graph_step_inputs
    from src.verify.logic import SymbolicLogicVerifier
    verifier = SymbolicLogicVerifier()
    skip = set(cfg.get("skip_kinds", ["meta"]))

    check_answer = bool(cfg.get("check_answer", False))

    def verify_graph(graph) -> dict:
        kind = {n.node_id: n.kind for n in graph.nodes}
        verdicts = {s.step_id: verifier.verify(s) for s in graph_step_inputs(graph, use_all_earlier=True)
                    if kind.get(s.step_id) not in skip}
        if check_answer:
            verdicts.update(answer_support_verdicts(graph, verdicts))
        return verdicts
    return verify_graph


VERIFIER_FACTORIES = {
    "gsm8k": graph_arithmetic,
    "svamp": graph_arithmetic,
    "proofwriter": graph_logic,
    "proofwriter_depth3": graph_logic,   # the dataset config's name; examples carry "proofwriter"
}


def make_verify_fn(dataset: str, cfg: dict = None):
    cfg = cfg or {}
    if dataset not in VERIFIER_FACTORIES:
        raise ValueError(f"No verifier registered for dataset '{dataset}'. Registered: {sorted(VERIFIER_FACTORIES)}. "
                         "Add one in src/verify/registry.py (and a graph builder in src/graph/registry.py).")
    return VERIFIER_FACTORIES[dataset](cfg)
