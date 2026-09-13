import time
import torch
from transformers import AutoModel, AutoTokenizer

from src.models.base import BaseDLMWrapper, GenerationResult, DenoisingStepRecord


class DreamWrapper(BaseDLMWrapper):

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
                "tokenizer.mask_token_id is None for this Dream checkpoint. "
                "Check the model's tokenizer_config.json / generation_config.json — "
                "some Dream mirrors ship this broken. You may need to hardcode the "
                "mask id for this specific checkpoint (check Dream's official repo)."
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
        block_length=None,
    ) -> GenerationResult:
        if eligibility_fn is not None:
            raise NotImplementedError(
                "Dependency-aware scheduling (eligibility_fn) is not yet supported "
                "for Dream — its denoising loop is internal to diffusion_generate(). "
                "See the module docstring in this file for what needs to happen "
                "before this works. Use LLaDA for scheduling experiments until this "
                "is resolved."
            )

        start_time = time.time()

        messages = [{"role": "user", "content": prompt}]
        inputs = self.tokenizer.apply_chat_template(
            messages, return_tensors="pt", return_dict=True, add_generation_prompt=True
        )
        input_ids = inputs.input_ids.to(self.device)
        attention_mask = inputs.attention_mask.to(self.device)

        gen_params = self.config.get("generation", {})
        output = self.model.diffusion_generate(
            input_ids,
            attention_mask=attention_mask,
            max_new_tokens=max_new_tokens,
            steps=num_denoising_steps,
            output_history=return_intermediate_states,
            return_dict_in_generate=True,
            temperature=gen_params.get("temperature", 0.2),
            top_p=gen_params.get("top_p", 0.95),
            alg="entropy",
            alg_temp=gen_params.get("alg_temp", 0.0),
        )

        prompt_len = input_ids.shape[1]
        generated_ids = output.sequences[0][prompt_len:]
        generated_text = self.tokenizer.decode(generated_ids.tolist()).split(
            self.tokenizer.eos_token
        )[0]

        intermediate_states = None
        if return_intermediate_states and hasattr(output, "history") and output.history is not None:
            intermediate_states = []
            for step_idx, step_sequence in enumerate(output.history):
                seq = step_sequence[0][prompt_len:]
                masked_positions = (seq == self.mask_token_id).nonzero(as_tuple=True)[0].tolist()
                unmasked_positions = [
                    i for i in range(len(seq)) if i not in masked_positions
                ]
                intermediate_states.append(DenoisingStepRecord(
                    step_index=step_idx,
                    token_ids=seq.tolist(),
                    confidences=[],
                    newly_unmasked_positions=unmasked_positions,
                    still_masked_positions=masked_positions,
                ))

        wall_time = time.time() - start_time

        return GenerationResult(
            prompt=prompt,
            generated_text=generated_text,
            num_forward_passes=num_denoising_steps,
            wall_time_sec=wall_time,
            num_denoising_steps_used=num_denoising_steps,
            intermediate_states=intermediate_states,
        )

    def get_token_confidences(self, logits) -> list:
        probs = torch.softmax(logits, dim=-1)
        max_probs = probs.max(dim=-1).values
        return max_probs.tolist()