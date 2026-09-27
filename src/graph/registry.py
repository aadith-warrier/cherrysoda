from src.graph.build_math import build_math_graph
from src.graph.schema import ReasoningGraph

GRAPH_BUILDER_REGISTRY = {
    "gsm8k": build_math_graph,
    "svamp": build_math_graph,
}


def build_graph(record: dict) -> ReasoningGraph:
    """Build the reasoning graph for one generations.jsonl record, dispatching on its dataset."""
    dataset = record.get("dataset")
    if dataset not in GRAPH_BUILDER_REGISTRY:
        raise ValueError(
            f"No graph builder for dataset '{dataset}'. Registered: {list(GRAPH_BUILDER_REGISTRY.keys())}"
        )
    return GRAPH_BUILDER_REGISTRY[dataset](record)
