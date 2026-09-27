import importlib

# Imported lazily so a machine without one model's dependencies can still run the other.
REGISTRY = {
    "llada": ("src.models.llada_wrapper", "LLaDAWrapper"),
    "dream": ("src.models.dream_wrapper", "DreamWrapper"),
    "remedi": ("src.models.remedi_wrapper", "RemeDiWrapper"),
    "proseco": ("src.models.proseco_wrapper", "ProSeCoWrapper"),
    "dapd": ("src.models.dapd_wrapper", "DAPDWrapper"),
}


def get_model_wrapper(model_config: dict):
    wrapper_key = model_config["wrapper"]
    if wrapper_key not in REGISTRY:
        raise ValueError(f"Unknown wrapper '{wrapper_key}'. Registered wrappers: {list(REGISTRY.keys())}")
    module_name, cls_name = REGISTRY[wrapper_key]
    wrapper_cls = getattr(importlib.import_module(module_name), cls_name)
    model = wrapper_cls(model_config)
    model.load()
    return model
