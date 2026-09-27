from src.graph.schema import PROBLEM_NODE_ID, ReasoningGraph


def fmt_value(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def unsourced_values(graph: ReasoningGraph) -> list:
    """(node_id, value) for numbers a step uses that no earlier step or the problem provided."""
    out = []
    for n in graph.nodes:
        if n.kind not in ("calc", "claim"):
            continue
        evidence = set()
        for e in graph.edges:
            if e.dst == n.node_id:
                evidence.update(e.evidence.split(","))
        out.extend((n.node_id, v) for v in n.values_used if fmt_value(v) not in evidence)
    return out


def graph_stats(graph: ReasoningGraph) -> dict:
    steps = [n for n in graph.nodes if n.kind in ("calc", "claim")]
    has_incoming = {e.dst for e in graph.edges}
    return {
        "graph_steps": len(steps),
        "graph_equations": sum(len(n.equations) for n in steps),
        "graph_edges": len(graph.edges),
        "graph_isolated_calcs": sum(1 for n in steps if n.kind == "calc" and n.node_id not in has_incoming),
        "graph_unsourced_numbers": len(unsourced_values(graph)),
        "graph_warnings": len(graph.parse_warnings),
    }


def render_graph_text(graph: ReasoningGraph, width: int = 90) -> str:
    """One line per step: `id [kind] text   uses: value <- source`."""
    lines = []
    for n in graph.nodes:
        if n.node_id == PROBLEM_NODE_ID:
            continue
        ins = [
            f"{e.evidence} <- {'problem' if e.src == PROBLEM_NODE_ID else 'step ' + e.src}"
            + ("" if e.reason == "value_flow" else f" [{e.reason}]")
            for e in graph.edges if e.dst == n.node_id
        ]
        text = " ".join(n.text.split())
        text = text if len(text) <= width else text[: width - 1] + "…"
        lines.append(f"  {n.node_id:>2} [{n.kind:6}] {text}" + ("   uses: " + "; ".join(ins) if ins else ""))
    for w in graph.parse_warnings:
        lines.append(f"  warning: {w}")
    return "\n".join(lines)
