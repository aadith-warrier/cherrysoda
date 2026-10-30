import inspect
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
DREAM_EPS = 1e-3


def _top_p_logits(logits, top_p):
    sorted_logits, sorted_idx = torch.sort(logits, descending=True)
    cum = torch.cumsum(torch.softmax(sorted_logits, dim=-1), dim=-1)
    remove = cum > top_p
    remove[..., 1:] = remove[..., :-1].clone()
    remove[..., 0] = False
    drop = torch.zeros_like(logits, dtype=torch.bool).scatter_(-1, sorted_idx, remove)
    return logits.masked_fill(drop, torch.finfo(logits.dtype).min)


def dream_sample_tokens(logits, temperature, top_p, alg):

    if temperature > 0:
        logits = logits / temperature
    if top_p is not None and top_p < 1:
        logits = _top_p_logits(logits, top_p)
    probs = torch.softmax(logits, dim=-1)
    if temperature > 0:
        try:
            x0 = torch.distributions.Categorical(probs=probs).sample()
            confidence = torch.gather(probs, -1, x0.unsqueeze(-1)).squeeze(-1)
        except Exception:
            confidence, x0 = probs.max(dim=-1)
    else:
        confidence, x0 = probs.max(dim=-1)
    if alg == "topk_margin":
        top2 = torch.sort(probs, dim=-1, descending=True)[0][:, :2]
        confidence = top2[:, 0] - top2[:, 1]
    elif alg == "entropy":
        confidence = torch.sum(probs * torch.log(probs + 1e-10), dim=-1)
    return confidence, x0


class DreamWrapper(BaseDLMWrapper):

    def load(self):
        repo_id = self.config["hf_repo_id"]
        dtype = getattr(torch, self.config.get("dtype", "bfloat16"))

        self.tokenizer = AutoTokenizer.from_pretrained(repo_id, trust_remote_code=True)
        self.model = self._load_model(repo_id, dtype).to(self.device).eval()

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

    @staticmethod
    def _load_model(repo_id, dtype):

        try:
            return AutoModel.from_pretrained(repo_id, torch_dtype=dtype, trust_remote_code=True)
        except TypeError as e:
            if "weights_only" not in str(e):
                raise
        from transformers import PreTrainedModel

        saved = PreTrainedModel.__dict__["from_pretrained"]
        base = saved.__func__

        def dropping_weights_only(cls, *args, **kwargs):
            kwargs.pop("weights_only", None)
            return base(cls, *args, **kwargs)

        PreTrainedModel.from_pretrained = classmethod(dropping_weights_only)
        try:
            return AutoModel.from_pretrained(repo_id, torch_dtype=dtype, trust_remote_code=True)
        finally:
            PreTrainedModel.from_pretrained = saved

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
        if temperature is None:
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
                if step is None or logits is None:
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
            num_forward_passes=num_denoising_steps,
            wall_time_sec=wall_time,
            num_denoising_steps_used=num_denoising_steps,
            num_remasked_tokens=0,
            intermediate_states=intermediate_states,
            token_ids=gen_token_ids,
            raw_metadata={
                "prompt_num_tokens": prompt_len,
                "answer_num_tokens": len(answer_ids),
                "answer_tokens": len(answer_ids),
                "hit_length_limit": len(answer_ids) == len(gen_token_ids),

                "raw_head": self.tokenizer.decode(gen_token_ids[:24]) if not answer_ids else None,
            },
        )

    @torch.no_grad()
    def _refine_native(self, prompt, prompt_ids, token_ids, positions, num_denoising_steps, temperature, top_p, alg,
                       allow_end_from, start_time):

        prompt_len, L = prompt_ids.shape[1], len(token_ids)
        n = len(positions)
        gen_params = self.config.get("generation", {})
        if n == 0:
            answer_ids = truncate_at_stop(list(token_ids), self.stop_token_ids)
            return GenerationResult(prompt=prompt, generated_text=self.tokenizer.decode(answer_ids, skip_special_tokens=True).strip(),
                                    num_forward_passes=0, wall_time_sec=time.time() - start_time,
                                    num_denoising_steps_used=0, num_remasked_tokens=0, token_ids=list(token_ids))
        steps = max(1, min(num_denoising_steps or n, n))
        keep = torch.ones(L, dtype=torch.bool, device=self.device)
        if n:
            keep[torch.tensor(positions, dtype=torch.long, device=self.device)] = False
        fixed = torch.tensor(token_ids, dtype=torch.long, device=self.device)
        end_ids = torch.tensor(sorted(self.stop_token_ids), dtype=torch.long, device=self.device)
        ban_rows = None
        if allow_end_from is not None and allow_end_from > 0:
            rows = torch.arange(min(allow_end_from, L), device=self.device)
            ban_rows = (prompt_len + rows[~keep[rows]])
        eot_id = self.endoftext_id if gen_params.get("suppress_endoftext", False) else None

        def tokens_hook(step, x, logits):
            if step is None:
                window = x[0, prompt_len:prompt_len + L]
                x[0, prompt_len:prompt_len + L] = torch.where(keep, fixed, window)
            return x

        def logits_hook(step, x, logits):
            low = torch.finfo(logits.dtype).min
            if ban_rows is not None and ban_rows.numel():
                logits[0][ban_rows[:, None], end_ids[None, :]] = low
            if eot_id is not None:
                logits[..., eot_id] = float("-inf")
            return logits

        output = self.model.diffusion_generate(
            prompt_ids,
            attention_mask=torch.ones_like(prompt_ids),
            max_new_tokens=L,
            steps=steps,
            output_history=False,
            return_dict_in_generate=True,
            temperature=temperature,
            top_p=top_p,
            alg=alg,
            alg_temp=gen_params.get("alg_temp", 0.0),
            generation_tokens_hook_func=tokens_hook,
            generation_logits_hook_func=logits_hook,
        )
        out_ids = output.sequences[0][prompt_len:].tolist()
        answer_ids = truncate_at_stop(out_ids, self.stop_token_ids)
        return GenerationResult(
            prompt=prompt,
            generated_text=self.tokenizer.decode(answer_ids, skip_special_tokens=True).strip(),
            num_forward_passes=steps,
            wall_time_sec=time.time() - start_time,
            num_denoising_steps_used=steps,
            num_remasked_tokens=n,
            token_ids=out_ids,
            raw_metadata={
                "answer_tokens": len(answer_ids),
                "hit_length_limit": len(answer_ids) == len(out_ids),
                "leftover_masks": sum(t == self.mask_token_id for t in out_ids),
            },
        )

    def _sample(self, logits, temperature, top_p, alg):

        if not hasattr(self, "_native_sample"):
            module = inspect.getmodule(type(self.model).diffusion_generate)
            self._native_sample = getattr(module, "sample_tokens", None)
        if self._native_sample is None:
            return dream_sample_tokens(logits, temperature, top_p, alg)
        return self._native_sample(logits, temperature, top_p=top_p, top_k=None,
                                   margin_confidence=(alg == "topk_margin"), neg_entropy=(alg == "entropy"))

    @torch.no_grad()
    def refine(
        self,
        prompt,
        token_ids,
        remask_positions,
        num_denoising_steps=None,
        temperature=None,
        allow_end_from=None,
        confidence_eos_eot_inf=True,
        select_fn=None,
        trace=None,
    ) -> GenerationResult:

        start_time = time.time()
        gen_params = self.config.get("generation", {})
        if temperature is None:
            temperature = gen_params.get("temperature", 0.0)
        temperature = temperature or 0.0
        top_p = gen_params.get("top_p") if temperature > 0 else None
        alg = DREAM_ALG[gen_params.get("remasking_strategy", "entropy")]

        prompt_ids = build_chat_input_ids(self.tokenizer, prompt, self.device)
        prompt_len = prompt_ids.shape[1]
        positions = sorted(set(int(p) for p in remask_positions))
        if any(p < 0 or p >= len(token_ids) for p in positions):
            raise ValueError("remask_positions out of range of token_ids")
        if select_fn is None:

            return self._refine_native(prompt, prompt_ids, token_ids, positions, num_denoising_steps, temperature,
                                       top_p, alg, allow_end_from, start_time)
        gen_ids = torch.tensor([token_ids], dtype=torch.long, device=self.device)
        pos_t = torch.tensor(positions, dtype=torch.long, device=self.device)
        gen_ids[0, pos_t] = self.mask_token_id
        input_ids = torch.cat([prompt_ids, gen_ids], dim=1)

        n = len(positions)
        steps = max(1, min(num_denoising_steps or n, n)) if n else 0


        grid = torch.linspace(1, DREAM_EPS, steps + 1, device=self.device) if n else None
        end_ids = sorted(self.stop_token_ids)
        num_forward_passes, i = 0, 0

        while True:
            still = input_ids[0, prompt_len + pos_t] == self.mask_token_id
            remaining = pos_t[still]
            m = remaining.numel()
            if m == 0:
                break
            if select_fn is None:
                k = m if i >= steps - 1 else int(torch.tensor(m, device=self.device) * (1 - grid[i + 1] / grid[i]))
                i += 1
                if k <= 0:
                    continue

            logits = self.model(input_ids=input_ids, attention_mask="full", position_ids=None).logits
            logits = torch.cat([logits[:, :1], logits[:, :-1]], dim=1)[0, prompt_len:][remaining]
            num_forward_passes += 1
            if allow_end_from is not None:
                banned = remaining < allow_end_from
                logits[:, end_ids] = torch.where(banned[:, None], torch.finfo(logits.dtype).min, logits[:, end_ids])
            conf, pred = self._sample(logits, temperature, top_p, alg)
            if select_fn is None:


                full_conf = torch.full((1, input_ids.shape[1]), -torch.inf, dtype=conf.dtype, device=self.device)
                full_conf[0, prompt_len + remaining] = conf
                chosen = torch.topk(full_conf, min(k, m)).indices[0]
                full_pred = torch.full((input_ids.shape[1],), self.mask_token_id, dtype=torch.long, device=self.device)
                full_pred[prompt_len + remaining] = pred
                input_ids[0, chosen] = full_pred[chosen]
                if trace is not None:
                    trace.append({"step": i - 1, "chosen": sorted((chosen - prompt_len).tolist()),
                                  "tokens": {int(c) - prompt_len: int(full_pred[c]) for c in chosen},
                                  "conf": dict(zip(remaining.tolist(), conf.float().tolist()))})
            else:
                rem_list, want = remaining.tolist(), set(select_fn(remaining.tolist(), conf.float().tolist()))
                idx = [j for j, p in enumerate(rem_list) if p in want] or [int(conf.argmax())]
                top = torch.tensor(idx, dtype=torch.long, device=self.device)
                input_ids[0, prompt_len + remaining[top]] = pred[top]

        out_ids = input_ids[0, prompt_len:].tolist()
        answer_ids = truncate_at_stop(out_ids, self.stop_token_ids)
        return GenerationResult(
            prompt=prompt,
            generated_text=self.tokenizer.decode(answer_ids, skip_special_tokens=True).strip(),
            num_forward_passes=num_forward_passes,
            wall_time_sec=time.time() - start_time,
            num_denoising_steps_used=num_forward_passes,
            num_remasked_tokens=n,
            token_ids=out_ids,
            raw_metadata={
                "answer_tokens": len(answer_ids),
                "hit_length_limit": len(answer_ids) == len(out_ids),
                "leftover_masks": sum(t == self.mask_token_id for t in out_ids),
            },
        )

    def get_token_confidences(self, logits) -> list:
        probs = torch.softmax(logits.float(), dim=-1)
        return probs.max(dim=-1).values.tolist()
