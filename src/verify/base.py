"""Shared types for step verifiers.

A verifier looks at one reasoning step at a time: the step's text, the texts it depends on
(its parents in whatever dependency graph is in use), and the task context (the maths problem
or the ProofWriter theory). Verifiers are pure functions of that input, so they work on gold
reference graphs, on graphs built from model outputs, and on partially denoised text alike;
nothing here depends on how the graph was built.
"""
from dataclasses import asdict, dataclass, field
from typing import Optional, Protocol

VALID = "valid"
INVALID = "invalid"
UNVERIFIABLE = "unverifiable"  # nothing checkable in the step (or it is still masked)

# Masked positions as they appear in decoded text, so a half-denoised step is never judged.
MASK_MARKERS = ("<|mdm_mask|>", "[MASK]", "<mask>", "<|mask|>")


@dataclass
class StepInput:
    text: str
    premises: list = field(default_factory=list)  # texts of the steps this one depends on
    context: str = ""  # problem statement / theory
    step_id: str = ""


@dataclass
class Check:
    name: str  # e.g. "arithmetic", "grounding", "conclusion", "premise"
    passed: Optional[bool]  # None: the check could not be run
    detail: str = ""


@dataclass
class Verdict:
    status: str  # VALID | INVALID | UNVERIFIABLE
    p_invalid: float  # score in [0, 1]; deterministic verifiers give 0/1 (or a fixed weight for soft checks)
    verifier: str
    error_type: str = ""  # "arithmetic", "ungrounded_operand", "contradiction", "unsupported", ...
    checks: list = field(default_factory=list)
    probs: Optional[dict] = None  # NLI class probabilities for the step, when available

    @property
    def flagged(self) -> bool:
        return self.status == INVALID

    def to_dict(self) -> dict:
        return asdict(self)


class StepVerifier(Protocol):
    name: str

    def verify(self, step: StepInput) -> Verdict: ...


def has_mask(text: str) -> bool:
    return any(m in text for m in MASK_MARKERS)


def unverifiable(verifier: str, detail: str = "") -> Verdict:
    return Verdict(UNVERIFIABLE, 0.0, verifier, checks=[Check("parse", None, detail)] if detail else [])


class CascadeVerifier:
    """Try verifiers in order and keep the first verdict that is not UNVERIFIABLE.

    Typical use: an exact verifier first (sympy arithmetic, symbolic logic) and the NLI
    verifier as the fallback for steps the exact one cannot parse.
    """

    def __init__(self, verifiers: list):
        self.verifiers = verifiers
        self.name = "+".join(v.name for v in verifiers)

    def verify(self, step: StepInput) -> Verdict:
        verdict = None
        for v in self.verifiers:
            verdict = v.verify(step)
            if verdict.status != UNVERIFIABLE:
                return verdict
        return verdict if verdict is not None else unverifiable(self.name)


SKIP_KINDS = ("problem", "header")


def graph_step_inputs(graph, use_all_earlier: bool = False) -> list:
    """StepInputs for every reasoning step of a graph.

    `graph` only needs `.nodes` (with node_id, text, kind) and `.edges` (with src, dst), so a
    ReasoningGraph from src.graph works, as does any reference graph with the same shape.
    Premises are the step's parents; with `use_all_earlier` they are all earlier steps instead,
    which is more forgiving when the graph misses an edge.
    """
    problem = next((n for n in graph.nodes if n.kind == "problem"), None)
    context = problem.text if problem is not None else ""
    by_id = {n.node_id: n for n in graph.nodes}
    order = [n.node_id for n in graph.nodes]
    parents = {}
    for e in graph.edges:
        parents.setdefault(e.dst, []).append(e.src)

    inputs = []
    for i, n in enumerate(graph.nodes):
        if n.kind in SKIP_KINDS:
            continue
        if use_all_earlier:
            src_ids = [m for m in order[:i] if by_id[m].kind not in SKIP_KINDS]
        else:
            src_ids = sorted(set(parents.get(n.node_id, [])), key=order.index)
        premises = [by_id[s].text for s in src_ids if by_id[s].kind != "problem"]
        inputs.append(StepInput(text=n.text, premises=premises, context=context, step_id=n.node_id))
    return inputs


def verify_graph(graph, verifier, use_all_earlier: bool = False) -> dict:
    """{node_id: Verdict} for every reasoning step in the graph."""
    return {s.step_id: verifier.verify(s) for s in graph_step_inputs(graph, use_all_earlier)}
