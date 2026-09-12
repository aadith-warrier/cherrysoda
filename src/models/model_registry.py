
from src.models.llada_wrapper import LLaDAWrapper
from src.models.dream_wrapper import DreamWrapper

REGISTRY = {
    "llada": LLaDAWrapper,
    "dream": DreamWrapper,
}


def get_model_wrapper(model_config: dict):
    wrapper_key = model_config["wrapper"]
    if wrapper_key not in REGISTRY:
        raise ValueError(
            f"Unknown wrapper '{wrapper_key}'. Registered wrappers: {list(REGISTRY.keys())}"
        )
    wrapper_cls = REGISTRY[wrapper_key]
    model = wrapper_cls(model_config)
    model.load()
    return model
