from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DenoisingStepRecord:
    step_index: int
    token_ids: list
    confidences: list
    newly_unmasked_positions: list
    still_masked_positions: list


@dataclass
class GenerationResult:
    prompt: str
    generated_text: str               # decoded answer, truncated at the first end-of-turn / EOS token
    num_forward_passes: int           # NFE actually spent
    wall_time_sec: float
    num_denoising_steps_used: int
    num_remasked_tokens: int = 0      # tokens reverted to [MASK] after being committed (0 for vanilla)
    intermediate_states: Optional[list] = field(default=None)
    raw_metadata: dict = field(default_factory=dict)


def build_chat_input_ids(tokenizer, prompt: str, device):
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    return tokenizer(text, add_special_tokens=False, return_tensors="pt").input_ids.to(device)


def load_package_from_dir(name: str, package_dir: str):
    import importlib.util
    import os
    import sys
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(package_dir, "__init__.py"), submodule_search_locations=[package_dir])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[name]
        raise
    return module


def truncate_at_stop(token_ids: list, stop_ids: set) -> list:
    for i, t in enumerate(token_ids):
        if t in stop_ids:
            return token_ids[:i]
    return token_ids


class BaseDLMWrapper(ABC):
    def __init__(self, model_config: dict):
        self.config = model_config
        self.name = model_config["name"]
        self.device = model_config.get("device", "cuda:0")
        self.supports_intermediate_states = model_config.get("supports_intermediate_states", False)

    @abstractmethod
    def load(self):
        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_new_tokens: int,
        num_denoising_steps: int,
        remasking_strategy: str = "low_confidence",
        return_intermediate_states: bool = False,
        eligibility_fn: Optional[callable] = None,
        block_length: Optional[int] = None,
    ) -> GenerationResult:
        raise NotImplementedError

    @abstractmethod
    def get_token_confidences(self, logits) -> list:
        raise NotImplementedError

    def unload(self):
        pass
