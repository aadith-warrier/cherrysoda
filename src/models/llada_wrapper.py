import time
import torch
from transformers import AutoModel, AutoTokenizer

from src.models.base import BaseDLMWrapper, GenerationResult, DenoisingStepRecord


class LLaDAWrapper(BaseDLMWrapper):

    def load(self):
        repo_id = self.config["hf_repo_id"]
        dtype = getattr(torch, self.config.get("dtype", "bfloat16"))

        self.tokenizer = AutoTokenizer.from_pretrained(repo_id, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(
            repo_id, torch_dtype=dtype, trust_remote_code=True
        ).to(self.device).eval()

        self.mask_token_id = getattr(self.tokenizer, "mask_token_id", None)
        if self.mask_token_id is None:
            raise ValueError(
                "Could not find mask_token_id on tokenizer — check LLaDA's tokenizer config; "
                "this is required for masked-diffusion generation."
            )

    @torch.no_grad()
    def generate(
        self,
        prompt,
        max_new_tokens,
        num_denoising_steps,
        remasking_strategy="low_confidence",
        return_intermediate_states=False,
        eligibility_fn=None,
    ) -> GenerationResult:
        start_time = time.time()

        prompt_ids = self.tokenizer(prompt, return_tensors="pt").input_ids.to(self.device)
        gen_ids = torch.full((1, max_new_tokens), self.mask_token_id, dtype=torch.long, device=self.device)
        input_ids = torch.cat([prompt_ids, gen_ids], dim=1)
        prompt_len = prompt_ids.shape[1]

        intermediate_states = [] if return_intermediate_states else None
        num_forward_passes = 0

        tokens_per_step = max(1, max_new_tokens // num_denoising_steps)

        for step in range(num_denoising_steps):
            masked_positions = (input_ids[0, prompt_len:] == self.mask_token_id).nonzero(as_tuple=True)[0]
            if len(masked_positions) == 0:
                break

            logits = self.model(input_ids).logits
            num_forward_passes += 1

            confidences = self.get_token_confidences(logits[0, prompt_len:])

            if eligibility_fn is not None:
                eligible = eligibility_fn(step, masked_positions.tolist(), None, None)
                eligible_set = set(eligible)
                candidate_positions = [p for p in masked_positions.tolist() if p in eligible_set]
            else:
                candidate_positions = masked_positions.tolist()

            if not candidate_positions:
                continue

            ranked = sorted(candidate_positions, key=lambda p: confidences[p], reverse=True)
            commit_positions = ranked[:tokens_per_step]

            predicted_ids = logits[0, prompt_len:].argmax(dim=-1)
            for p in commit_positions:
                input_ids[0, prompt_len + p] = predicted_ids[p]

            if return_intermediate_states:
                intermediate_states.append(DenoisingStepRecord(
                    step_index=step,
                    token_ids=input_ids[0].tolist(),
                    confidences=confidences,
                    newly_unmasked_positions=commit_positions,
                    still_masked_positions=[p for p in candidate_positions if p not in commit_positions],
                ))

        generated_text = self.tokenizer.decode(input_ids[0, prompt_len:], skip_special_tokens=True)
        wall_time = time.time() - start_time

        return GenerationResult(
            prompt=prompt,
            generated_text=generated_text,
            num_forward_passes=num_forward_passes,
            wall_time_sec=wall_time,
            num_denoising_steps_used=step + 1,
            intermediate_states=intermediate_states,
        )

    def get_token_confidences(self, logits) -> list:
        probs = torch.softmax(logits, dim=-1)
        max_probs = probs.max(dim=-1).values
        return max_probs.tolist()
