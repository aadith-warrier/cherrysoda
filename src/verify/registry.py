def graph_arithmetic(cfg: dict):
    from src.verify.graph_math import GraphArithmeticVerifier
    return GraphArithmeticVerifier(check_grounding=cfg.get("check_grounding", True)).verify_graph


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

    def verify_graph(graph) -> dict:
        kind = {n.node_id: n.kind for n in graph.nodes}
        return {s.step_id: verifier.verify(s) for s in graph_step_inputs(graph, use_all_earlier=True)
                if kind.get(s.step_id) not in skip}
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
