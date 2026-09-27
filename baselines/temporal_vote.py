from src.eval.scoring import ANSWER_TYPE_BY_DATASET, extract_label, extract_numeric
from src.methods.correction import TemporalVote
from src.models.base import GenerationResult, truncate_at_stop


def _pattern_only(extract):
    def fn(text):
        value, method = extract(text)
        return value if method == "pattern" else None
    return fn


def run(model, example: dict, gen_config: dict) -> GenerationResult:
    answer_type = example["metadata"].get("answer_type") or ANSWER_TYPE_BY_DATASET[example["metadata"]["dataset"]]
    extract = extract_numeric if answer_type == "numeric" else extract_label
    vote = TemporalVote(
        _pattern_only(extract),
        total_steps=gen_config["num_denoising_steps"],
        weighting=gen_config.get("vote_weighting", "exp"),
        alpha=gen_config.get("vote_alpha", 5.0),
    )
    stop_ids = getattr(model, "stop_token_ids", set())

    def observer(step, gen_token_ids):
        ids = truncate_at_stop(gen_token_ids, stop_ids)
        vote.add(step, model.tokenizer.decode(ids, skip_special_tokens=True))

    result = model.generate(
        prompt=example["prompt"],
        max_new_tokens=gen_config["max_new_tokens"],
        num_denoising_steps=gen_config["num_denoising_steps"],
        remasking_strategy=gen_config["remasking_strategy"],
        return_intermediate_states=False,
        block_length=gen_config.get("block_length"),
        step_observer=observer,
    )
    result.raw_metadata = dict(result.raw_metadata or {})
    result.raw_metadata["voted_answer"] = vote.result()
    result.raw_metadata["vote_top"] = vote.top(3)
    result.raw_metadata["num_votes"] = vote.num_votes
    return result
