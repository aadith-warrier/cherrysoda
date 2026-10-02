import time

import torch
from transformers import AutoModel, AutoTokenizer

from src.models.base import (
    BaseDLMWrapper,
    DenoisingStepRecord,
    GenerationResult,
    build_chat_input_ids,
    truncate_at_stop,
)

DREAM_ALG = {
    "low_confidence": "maskgit_plus",
    "entropy": "entropy",
    "margin": "topk_margin",
    "random": "origin",
}
DREAM_STOP_TOKENS = ("<|im_end|>", "<|endoftext|>")


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
                "Check the model's tokenizer_config.json / generation_config.json."
            )

        stop_ids = set()
        for tok in DREAM_STOP_TOKENS:
            tid = self.tokenizer.convert_tokens_to_ids(tok)
            if tid is not None and tid != self.tokenizer.unk_token_id:
                stop_ids.add(tid)
        for tid in (self.tokenizer.eos_token_id, self.tokenizer.pad_token_id):
            if tid is not None and tid != self.mask_token_id:
                stop_ids.add(tid)
        self.stop_token_ids = stop_ids
        self.endoftext_id = self.tokenizer.convert_tokens_to_ids("<|endoftext|>")

    @torch.no_grad()
    def generate(
        self,
        prompt,
        max_new_tokens,
        num_denoising_steps,
        remasking_strategy="entropy",
        return_intermediate_states=False,
        eligibility_fn=None,
        block_length=None,
        step_observer=None,
        temperature=None,
        logits_eos_inf=False,
        confidence_eos_eot_inf=False,
    ) -> GenerationResult:
        if logits_eos_inf or confidence_eos_eot_inf:
            raise NotImplementedError("End-of-text controls are only implemented for LLaDA.")
        if eligibility_fn is not None:
            raise NotImplementedError(
                "eligibility_fn is not supported for Dream (the loop is inside diffusion_generate). "
                "Use LLaDA for scheduling experiments."
            )
        if block_length not in (None, max_new_tokens):
            raise ValueError(
                f"Dream v0 does not support semi-autoregressive blocks; set block_length: null (got {block_length})."
            )
        if remasking_strategy not in DREAM_ALG:
            raise ValueError(f"Unknown remasking_strategy '{remasking_strategy}' for Dream. Options: {list(DREAM_ALG)}")

        start_time = time.time()

        input_ids = build_chat_input_ids(self.tokenizer, prompt, self.device)
        attention_mask = torch.ones_like(input_ids)
        prompt_len = input_ids.shape[1]

        gen_params = self.config.get("generation", {})
        if temperature is None:  # default: the model config's sampling temperature
            temperature = gen_params.get("temperature", 0.0)
        temperature = temperature or 0.0
        top_p = gen_params.get("top_p") if temperature > 0 else None

        hooks = {}
        if gen_params.get("suppress_endoftext", False):
            eot_id = self.endoftext_id

            def _ban_endoftext(step, x, logits):
                logits[..., eot_id] = float("-inf")
                return logits

            hooks["generation_logits_hook_func"] = _ban_endoftext

        mask_id = self.mask_token_id
        if step_observer is not None:
            def _tokens_hook(step, x, logits):
                if step is None or logits is None:  # initial call before the first step
                    return x
                gen = x[0, prompt_len:]
                guess = torch.where(gen == mask_id, logits[0, prompt_len:].argmax(dim=-1), gen)
                step_observer(step, guess.tolist())
                return x

            hooks["generation_tokens_hook_func"] = _tokens_hook

        output = self.model.diffusion_generate(
            input_ids,
            attention_mask=attention_mask,
            max_new_tokens=max_new_tokens,
            steps=num_denoising_steps,
            output_history=return_intermediate_states,
            return_dict_in_generate=True,
            temperature=temperature,
            top_p=top_p,
            alg=DREAM_ALG[remasking_strategy],
            alg_temp=gen_params.get("alg_temp", 0.0),
            **hooks,
        )

        gen_token_ids = output.sequences[0][prompt_len:].tolist()
        answer_ids = truncate_at_stop(gen_token_ids, self.stop_token_ids)
        generated_text = self.tokenizer.decode(answer_ids, skip_special_tokens=True).strip()

        intermediate_states = None
        if return_intermediate_states and getattr(output, "history", None) is not None:
            intermediate_states = []
            prev_masked = set(range(max_new_tokens))
            for step_idx, step_sequence in enumerate(output.history):
                seq = step_sequence[0][prompt_len:]
                masked = set((seq == self.mask_token_id).nonzero(as_tuple=True)[0].tolist())
                intermediate_states.append(DenoisingStepRecord(
                    step_index=step_idx,
                    token_ids=seq.tolist(),
                    confidences=[],
                    newly_unmasked_positions=sorted(prev_masked - masked),
                    still_masked_positions=sorted(masked),
                ))
                prev_masked = masked

        wall_time = time.time() - start_time

        return GenerationResult(
            prompt=prompt,
            generated_text=generated_text,
            num_forward_passes=num_denoising_steps,  # diffusion_generate runs exactly `steps` forward passes
            wall_time_sec=wall_time,
            num_denoising_steps_used=num_denoising_steps,
            num_remasked_tokens=0,
            intermediate_states=intermediate_states,
            raw_metadata={
                "prompt_num_tokens": prompt_len,
                "answer_num_tokens": len(answer_ids),
                "hit_length_limit": len(answer_ids) == len(gen_token_ids),
                # First tokens undecoded: lets you diagnose empty outputs without rerunning.
                "raw_head": self.tokenizer.decode(gen_token_ids[:24]) if not answer_ids else None,
            },
        )

    def get_token_confidences(self, logits) -> list:
        probs = torch.softmax(logits.float(), dim=-1)
        return probs.max(dim=-1).values.tolist()
