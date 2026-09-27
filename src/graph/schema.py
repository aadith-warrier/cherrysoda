from dataclasses import asdict, dataclass, field
from typing import Optional

import networkx as nx

PROBLEM_NODE_ID = "P"


@dataclass
class Equation:
    raw: str
    operands: list  # numbers in the left-hand expression
    operators: list
    result: Optional[float]  # the right-hand side when it is a single stated number, else None
    lhs: str = ""  # canonical expressions, e.g. "8 * (0.6 * 5)"; "" when that side has no arithmetic
    rhs: str = ""


@dataclass
class ReasoningNode:
    node_id: str
    text: str
    # Span in the raw generation string; (-1, -1) for the problem node, which lives in the prompt.
    char_start: int
    char_end: int
    kind: str  # "problem" | "calc" | "claim" | "header"
    list_marker: Optional[int] = None
    equations: list = field(default_factory=list)
    values_used: list = field(default_factory=list)
    values_produced: list = field(default_factory=list)


@dataclass
class DependencyEdge:
    src: str
    dst: str
    reason: str  # "value_flow" | "explicit_ref" | "shared_entity"
    evidence: str = ""


@dataclass
class ReasoningGraph:
    example_id: str
    dataset: str
    nodes: list
    edges: list
    parse_warnings: list = field(default_factory=list)

    def node(self, node_id: str) -> ReasoningNode:
        return next(n for n in self.nodes if n.node_id == node_id)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ReasoningGraph":
        nodes = []
        for n in d["nodes"]:
            n = dict(n)
            n["equations"] = [Equation(**e) for e in n.get("equations", [])]
            nodes.append(ReasoningNode(**n))
        return cls(
            example_id=d["example_id"],
            dataset=d["dataset"],
            nodes=nodes,
            edges=[DependencyEdge(**e) for e in d["edges"]],
            parse_warnings=list(d.get("parse_warnings", [])),
        )

    def to_networkx(self) -> nx.DiGraph:
        g = nx.DiGraph()
        for n in self.nodes:
            g.add_node(n.node_id, **asdict(n))
        for e in self.edges:
            g.add_edge(e.src, e.dst, reason=e.reason, evidence=e.evidence)
        return g
