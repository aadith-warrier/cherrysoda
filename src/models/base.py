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
    generated_text: str
    num_forward_passes: int
    wall_time_sec: float
    num_denoising_steps_used: int
    intermediate_states: Optional[list] = field(default=None) 
    raw_metadata: dict = field(default_factory=dict) 


class BaseDLMWrapper(ABC):
    def __init__(self, model_config: dict):
        self.config = model_config
        self.name = model_config["name"]
        self.device = model_config.get("device", "cuda:0")

    @abstractmethod
    def load(self):
        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        prompt,  # a string (one user turn) or a list of chat messages
        max_new_tokens: int,
        num_denoising_steps: int,
        remasking_strategy: str = "low_confidence",
        return_intermediate_states: bool = False,
        eligibility_fn: Optional[callable] = None,
        block_length: Optional[int] = None,
        temperature: float = 0.0,
        logits_eos_inf: bool = False,
        confidence_eos_eot_inf: bool = False,
    ) -> GenerationResult:
        raise NotImplementedError
