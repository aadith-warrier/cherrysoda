def graph_arithmetic(cfg: dict):
    from src.verify.graph_math import GraphArithmeticVerifier
    return GraphArithmeticVerifier(check_grounding=cfg.get("check_grounding", True)).verify_graph


VERIFIER_FACTORIES = {
    "gsm8k": graph_arithmetic,
    "svamp": graph_arithmetic,

}


def make_verify_fn(dataset: str, cfg: dict = None):
    cfg = cfg or {}
    if dataset not in VERIFIER_FACTORIES:
        raise ValueError(f"No verifier registered for dataset '{dataset}'. Registered: {sorted(VERIFIER_FACTORIES)}. "
                         "Add one in src/verify/registry.py (and a graph builder in src/graph/registry.py).")
    return VERIFIER_FACTORIES[dataset](cfg)
