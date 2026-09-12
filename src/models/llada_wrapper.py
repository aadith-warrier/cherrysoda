import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
 
from src.models.base import BaseDLMWrapper, GenerationResult, DenoisingStepRecord
 
 
class LLaDAWrapper(BaseDLMWrapper):
 
    def load(self):
        repo_id = self.config["hf_repo_id"]
        dtype = getattr(torch, self.config.get("dtype", "bfloat16"))
 
        self.tokenizer = AutoTokenizer.from_pretrained(repo_id, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            repo_id, trust_remote_code=True, torch_dtype=dtype
        ).to(self.device).eval()

        self.mask_token_id = self.config.get("mask_token_id", 126336)
 
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
    ) -> GenerationResult:

        start_time = time.time()
 
        block_length = block_length or self.config.get("block_length") or max_new_tokens
        if max_new_tokens % block_length != 0:
            raise ValueError(
                f"max_new_tokens ({max_new_tokens}) must be divisible by block_length ({block_length})."
            )
        num_blocks = max_new_tokens // block_length
        steps_per_block = max(1, num_denoising_steps // num_blocks)
 
        prompt_ids = self.tokenizer(prompt, return_tensors="pt").input_ids.to(self.device)
        gen_ids = torch.full((1, max_new_tokens), self.mask_token_id, dtype=torch.long, device=self.device)
        input_ids = torch.cat([prompt_ids, gen_ids], dim=1)
        prompt_len = prompt_ids.shape[1]
 
        intermediate_states = [] if return_intermediate_states else None
        num_forward_passes = 0
        global_step = 0
 
        for block_idx in range(num_blocks):
            block_start = prompt_len + block_idx * block_length
            block_end = prompt_len + (block_idx + 1) * block_length
 
            for _ in range(steps_per_block):
                block_masked = (input_ids[0, block_start:block_end] == self.mask_token_id).nonzero(as_tuple=True)[0]
                if len(block_masked) == 0:
                    break  
 
                logits = self.model(input_ids).logits
                num_forward_passes += 1
 
                block_logits = logits[0, block_start:block_end]
                confidences = self.get_token_confidences(block_logits)
 
                eos_id = getattr(self.tokenizer, "eos_token_id", None)
                predicted_ids = block_logits.argmax(dim=-1)
                if eos_id is not None:
                    for pos in block_masked.tolist():
                        if predicted_ids[pos].item() == eos_id:
                            confidences[pos] = -1.0  
 
                candidate_positions = block_masked.tolist()
                if eligibility_fn is not None:
                    eligible = eligibility_fn(global_step, candidate_positions, None, None)
                    eligible_set = set(eligible)
                    candidate_positions = [p for p in candidate_positions if p in eligible_set]
                    if not candidate_positions:
                        global_step += 1
                        continue
 
                tokens_this_step = max(1, len(block_masked) // steps_per_block)
                ranked = sorted(candidate_positions, key=lambda p: confidences[p], reverse=True)
                commit_positions = ranked[:tokens_this_step]
 
                for p in commit_positions:
                    input_ids[0, block_start + p] = predicted_ids[p]
 
                if return_intermediate_states:
                    intermediate_states.append(DenoisingStepRecord(
                        step_index=global_step,
                        token_ids=input_ids[0].tolist(),
                        confidences=confidences,
                        newly_unmasked_positions=[block_start - prompt_len + p for p in commit_positions],
                        still_masked_positions=[block_start - prompt_len + p for p in candidate_positions if p not in commit_positions],
                    ))
                global_step += 1
 
        generated_text = self.tokenizer.decode(input_ids[0, prompt_len:], skip_special_tokens=True)
        wall_time = time.time() - start_time
 
        return GenerationResult(
            prompt=prompt,
            generated_text=generated_text,
            num_forward_passes=num_forward_passes,
            wall_time_sec=wall_time,
            num_denoising_steps_used=global_step,
            intermediate_states=intermediate_states,
        )
 
    def get_token_confidences(self, logits) -> list:
        probs = torch.softmax(logits, dim=-1)
        max_probs = probs.max(dim=-1).values
        return max_probs.tolist()
 