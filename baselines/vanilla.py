"""
Vanilla baseline: standard confidence-based DLM sampling, no correction,
no dependency-aware scheduling. This is your floor — every other baseline
and your final method should be reported relative to this.
"""

from src.models.base import GenerationResult


def run(model, example: dict, gen_config: dict) -> GenerationResult:
    """
    model: an already-loaded BaseDLMWrapper instance
    example: one row from data/loaders.py's unified schema
    gen_config: the `generation` block from the model's yaml config
    """
    result = model.generate(
        prompt=example["prompt"],
        max_new_tokens=gen_config["max_new_tokens"],
        num_denoising_steps=gen_config["num_denoising_steps"],
        remasking_strategy=gen_config.get("remasking_strategy", "low_confidence"),
        return_intermediate_states=False,
        eligibility_fn=None,   # vanilla = no scheduling constraint
    )
    return result
