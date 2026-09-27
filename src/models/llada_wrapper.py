import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.models.base import BaseDLMWrapper, DenoisingStepRecord, GenerationResult

# Follows the official sampler: https://github.com/ML-GSAI/LLaDA/blob/main/generate.py
EOS_TOKEN_ID = 126081  # <|endoftext|>, also used as padding after the answer
EOT_TOKEN_ID = 126348  # <|eot_id|>


def num_transfer_tokens(n_masked: int, steps: int) -> list:
    """How many tokens to unmask in each of `steps` rounds; the remainder goes to the first rounds."""
    base, remainder = divmod(n_masked, steps)
    return [base + 1 if i < remainder else base for i in range(steps)]


def add_gumbel_noise(logits, temperature: float):
    # Float64 on purpose: the LLaDA authors found low-precision Gumbel noise hurts generation quality.
    if temperature == 0:
        return logits
    logits = logits.to(torch.float64)
    noise = torch.rand_like(logits, dtype=torch.float64)
    return logits.exp() / (-torch.log(noise)) ** temperature


def token_confidence(logits, x0, remasking_strategy: str, confidence_eos_eot_inf: bool = False):
    """Confidence used to rank which predicted tokens to commit this round.

    With confidence_eos_eot_inf, end-of-text predictions get probability 0, so they are
    committed only after all content (LLaDA paper, Appendix B.4).
    """
    if remasking_strategy == "low_confidence":
        if confidence_eos_eot_inf:
            logits = logits.clone()
            logits[..., [EOS_TOKEN_ID, EOT_TOKEN_ID]] = -torch.inf
        probs = torch.softmax(logits, dim=-1)
        return torch.gather(probs, -1, x0.unsqueeze(-1)).squeeze(-1)
    if remasking_strategy == "random":
        return torch.rand(x0.shape, device=x0.device)
    raise ValueError(f"Unknown remasking_strategy '{remasking_strategy}'")


class LLaDAWrapper(BaseDLMWrapper):

    def load(self):
        repo_id = self.config["hf_repo_id"]
        dtype = getattr(torch, self.config.get("dtype", "bfloat16"))

        self.tokenizer = AutoTokenizer.from_pretrained(repo_id, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            repo_id, trust_remote_code=True, dtype=dtype
        ).to(self.device).eval()

        self.mask_token_id = self.config.get("mask_token_id", 126336)
        self.use_chat_template = self.config.get("use_chat_template", True)

    def encode_prompt(self, prompt):
        """`prompt` is a string (one user turn) or a list of chat messages (e.g. few-shot turns)."""
        if self.use_chat_template:
            messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]
            text = self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
            return self.tokenizer(text, add_special_tokens=False, return_tensors="pt").input_ids
        if isinstance(prompt, list):
            raise ValueError("Chat-message prompts require use_chat_template: true")
        return self.tokenizer(prompt, return_tensors="pt").input_ids

    @torch.no_grad()
    def generate(
        self,
        prompt,
        max_new_tokens,
        num_denoising_steps,
        remasking_strategy="low_confidence",
        return_intermediate_states=False,
        eligibility_fn=None,
        block_length=None,
        temperature=0.0,
        logits_eos_inf=False,
        confidence_eos_eot_inf=False,
    ) -> GenerationResult:
        start_time = time.time()
        gen_length = max_new_tokens
        block_length = block_length or gen_length
        if gen_length % block_length != 0:
            raise ValueError(f"max_new_tokens ({gen_length}) must be divisible by block_length ({block_length})")
        num_blocks = gen_length // block_length
        if num_denoising_steps % num_blocks != 0:
            raise ValueError(
                f"num_denoising_steps ({num_denoising_steps}) must be divisible by the number of blocks ({num_blocks})"
            )
        steps_per_block = num_denoising_steps // num_blocks

        prompt_ids = self.encode_prompt(prompt).to(self.device)
        prompt_len = prompt_ids.shape[1]
        x = torch.cat(
            [prompt_ids, torch.full((1, gen_length), self.mask_token_id, dtype=torch.long, device=self.device)],
            dim=1,
        )

        intermediate_states = [] if return_intermediate_states else None
        num_forward_passes = 0
        step_index = 0

        for block in range(num_blocks):
            block_start = prompt_len + block * block_length
            block_end = block_start + block_length
            n_masked = int((x[0, block_start:block_end] == self.mask_token_id).sum())
            schedule = num_transfer_tokens(n_masked, steps_per_block)

            for k in schedule:
                mask_index = x[0] == self.mask_token_id
                candidates = mask_index.clone()
                candidates[:block_start] = False
                candidates[block_end:] = False

                logits = self.model(x).logits[0]
                num_forward_passes += 1
                if logits_eos_inf:
                    logits[..., EOS_TOKEN_ID] = -torch.inf

                x0 = torch.argmax(add_gumbel_noise(logits, temperature), dim=-1)
                confidence = token_confidence(logits, x0, remasking_strategy, confidence_eos_eot_inf)

                if eligibility_fn is not None:
                    candidate_rel = (candidates[prompt_len:]).nonzero(as_tuple=True)[0].tolist()
                    eligible = set(eligibility_fn(step_index, candidate_rel, None, None))
                    for p in candidate_rel:
                        if p not in eligible:
                            candidates[prompt_len + p] = False

                confidence = torch.where(candidates, confidence.to(torch.float32), torch.tensor(-float("inf"), device=x.device))
                k = min(k, int(candidates.sum()))
                if k > 0:
                    commit = torch.topk(confidence, k=k).indices
                    x[0, commit] = x0[commit]
                else:
                    commit = torch.empty(0, dtype=torch.long, device=x.device)

                if return_intermediate_states:
                    gen_conf = torch.softmax(logits[prompt_len:].float(), dim=-1).max(dim=-1).values
                    committed = set((commit - prompt_len).tolist())
                    intermediate_states.append(DenoisingStepRecord(
                        step_index=step_index,
                        token_ids=x[0].tolist(),
                        confidences=gen_conf.tolist(),
                        newly_unmasked_positions=sorted(committed),
                        still_masked_positions=[
                            p for p in (x[0, prompt_len:] == self.mask_token_id).nonzero(as_tuple=True)[0].tolist()
                        ],
                    ))
                step_index += 1

        gen_ids = x[0, prompt_len:]
        is_end = (gen_ids == EOS_TOKEN_ID) | (gen_ids == EOT_TOKEN_ID)
        generated_text = self.tokenizer.decode(gen_ids, skip_special_tokens=True)

        return GenerationResult(
            prompt=prompt,
            generated_text=generated_text,
            num_forward_passes=num_forward_passes,
            wall_time_sec=time.time() - start_time,
            num_denoising_steps_used=step_index,
            intermediate_states=intermediate_states,
            raw_metadata={
                "answer_tokens": int((~is_end).sum()),
                # Content in the very last slot means the answer may have been cut off by the length limit.
                "hit_length_limit": not bool(is_end[-1]),
                "leftover_masks": int((gen_ids == self.mask_token_id).sum()),
            },
        )
