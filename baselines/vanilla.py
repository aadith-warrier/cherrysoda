import inspect

from src.models.base import GenerationResult

# Decoding options only some wrappers take (LLaDA's free-order settings used by the graph runs);
# they are passed only to wrappers whose generate() accepts them.
OPTIONAL_GENERATION_KEYS = ("temperature", "logits_eos_inf", "confidence_eos_eot_inf")


def run(model, example: dict, gen_config: dict) -> GenerationResult:
    accepted = inspect.signature(model.generate).parameters
    extra = {k: gen_config[k] for k in OPTIONAL_GENERATION_KEYS if k in gen_config and k in accepted}
    return model.generate(
        prompt=example["prompt"],
        max_new_tokens=gen_config["max_new_tokens"],
        num_denoising_steps=gen_config["num_denoising_steps"],
        remasking_strategy=gen_config["remasking_strategy"],
        return_intermediate_states=False,
        eligibility_fn=None,
        block_length=gen_config.get("block_length"),
        **extra,
    )
