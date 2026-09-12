from src.models.base import GenerationResult


def run(model, example: dict, gen_config: dict) -> GenerationResult:
    result = model.generate(
        prompt=example["prompt"],
        max_new_tokens=gen_config["max_new_tokens"],
        num_denoising_steps=gen_config["num_denoising_steps"],
        remasking_strategy=gen_config.get("remasking_strategy", "low_confidence"),
        return_intermediate_states=False,
        eligibility_fn=None,
        block_length=gen_config.get("block_length"),
    )
    return result