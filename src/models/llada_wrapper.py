import random
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

LLADA_STOP_TOKENS = ("<|eot_id|>", "<|endoftext|>")
LLADA_EOS_ID = 126081
LLADA_EOT_ID = 126348


def get_num_transfer_tokens(num_masked: int, steps: int) -> list:
    base, remainder = divmod(num_masked, steps)
    return [base + (1 if i < remainder else 0) for i in range(steps)]


def add_gumbel_noise(logits, temperature: float):

    if temperature == 0:
        return logits
    logits = logits.to(torch.float64)
    noise = torch.rand_like(logits, dtype=torch.float64)
    return logits.exp() / (-torch.log(noise)) ** temperature


class LLaDAWrapper(BaseDLMWrapper):

    def load(self):
        repo_id = self.config["hf_repo_id"]
        dtype = getattr(torch, self.config.get("dtype", "bfloat16"))

        self.tokenizer = AutoTokenizer.from_pretrained(repo_id, trust_remote_code=True)

        self.model = AutoModel.from_pretrained(
            repo_id, trust_remote_code=True, torch_dtype=dtype
        ).to(self.device).eval()

        self.mask_token_id = self.config.get("mask_token_id", 126336)
        self.use_chat_template = self.config.get("use_chat_template", True)

        stop_ids = set()
        for tok in LLADA_STOP_TOKENS:
            tid = self.tokenizer.convert_tokens_to_ids(tok)
            if tid is not None and tid != self.tokenizer.unk_token_id:
                stop_ids.add(tid)
        if self.tokenizer.eos_token_id is not None:
            stop_ids.add(self.tokenizer.eos_token_id)
        self.stop_token_ids = stop_ids

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
        step_observer=None,
        temperature=0.0,
        logits_eos_inf=False,
        confidence_eos_eot_inf=False,
    ) -> GenerationResult:

        if remasking_strategy not in ("low_confidence", "random"):
            raise ValueError(
                f"LLaDA supports remasking_strategy 'low_confidence' or 'random', got '{remasking_strategy}'."
            )

        start_time = time.time()

        block_length = block_length or self.config.get("generation", {}).get("block_length") or max_new_tokens
        if max_new_tokens % block_length != 0:
            raise ValueError(f"max_new_tokens ({max_new_tokens}) must be divisible by block_length ({block_length}).")
        num_blocks = max_new_tokens // block_length
        if num_denoising_steps % num_blocks != 0:
            raise ValueError(
                f"num_denoising_steps ({num_denoising_steps}) must be divisible by the number of blocks ({num_blocks})."
            )
        steps_per_block = num_denoising_steps // num_blocks
        defer_eos_eot = bool(self.config.get("generation", {}).get("defer_eos_eot", False))

        if self.use_chat_template:
            prompt_ids = build_chat_input_ids(self.tokenizer, prompt, self.device)
        elif isinstance(prompt, list):
            raise ValueError("Chat-message prompts require use_chat_template: true")
        else:
            prompt_ids = self.tokenizer(prompt, return_tensors="pt").input_ids.to(self.device)
        prompt_len = prompt_ids.shape[1]
        gen_ids = torch.full((1, max_new_tokens), self.mask_token_id, dtype=torch.long, device=self.device)
        input_ids = torch.cat([prompt_ids, gen_ids], dim=1)

        intermediate_states = [] if return_intermediate_states else None
        num_forward_passes = 0
        global_step = 0
        forward_count = [0]

        def forward_block(bs, be):
            all_logits = self.model(input_ids).logits[0]
            if logits_eos_inf:
                all_logits[..., LLADA_EOS_ID] = -torch.inf
            if step_observer is not None:
                gen = input_ids[0, prompt_len:]
                guess = torch.where(gen == self.mask_token_id, all_logits[prompt_len:].argmax(dim=-1), gen)
                step_observer(forward_count[0], guess.tolist())
            forward_count[0] += 1
            block_logits = all_logits[bs:be]
            if temperature == 0 and not confidence_eos_eot_inf:
                probs = torch.softmax(block_logits.to(torch.float64), dim=-1)
                conf, pred = probs.max(dim=-1)
            else:
                pred = torch.argmax(add_gumbel_noise(block_logits, temperature), dim=-1)
                scored = block_logits
                if confidence_eos_eot_inf:
                    scored = block_logits.clone()
                    scored[..., [LLADA_EOS_ID, LLADA_EOT_ID]] = -torch.inf
                conf = torch.gather(torch.softmax(scored, dim=-1), -1, pred.unsqueeze(-1)).squeeze(-1).float()
            if defer_eos_eot:
                is_end = (pred == LLADA_EOS_ID) | (pred == LLADA_EOT_ID)
                conf = conf.masked_fill(is_end, float("-inf"))
            return conf, pred

        for block_idx in range(num_blocks):
            bs = prompt_len + block_idx * block_length
            be = bs + block_length
            n_masked = int((input_ids[0, bs:be] == self.mask_token_id).sum())
            schedule = get_num_transfer_tokens(n_masked, steps_per_block)

            for k in schedule:
                masked = (input_ids[0, bs:be] == self.mask_token_id).nonzero(as_tuple=True)[0].tolist()
                if not masked:
                    break
                if k == 0:
                    continue

                conf, pred = forward_block(bs, be)
                num_forward_passes += 1

                candidates = masked
                if eligibility_fn is not None:
                    eligible = set(eligibility_fn(global_step, candidates, None, None))
                    candidates = [p for p in candidates if p in eligible]
                    if not candidates:
                        global_step += 1
                        continue

                if remasking_strategy == "low_confidence":
                    ranked = sorted(candidates, key=lambda p: conf[p].item(), reverse=True)
                else:
                    ranked = random.sample(candidates, len(candidates))
                commit = ranked[:min(k, len(ranked))]
                for p in commit:
                    input_ids[0, bs + p] = pred[p]

                if return_intermediate_states:
                    committed = set(commit)
                    intermediate_states.append(DenoisingStepRecord(
                        step_index=global_step,
                        token_ids=input_ids[0, prompt_len:].tolist(),
                        confidences=conf.tolist(),
                        newly_unmasked_positions=[bs - prompt_len + p for p in commit],
                        still_masked_positions=[bs - prompt_len + p for p in masked if p not in committed],
                    ))
                global_step += 1



            leftover = (input_ids[0, bs:be] == self.mask_token_id).nonzero(as_tuple=True)[0].tolist()
            if leftover:
                conf, pred = forward_block(bs, be)
                num_forward_passes += 1
                for p in leftover:
                    input_ids[0, bs + p] = pred[p]
                global_step += 1

        gen_token_ids = input_ids[0, prompt_len:].tolist()
        answer_ids = truncate_at_stop(gen_token_ids, self.stop_token_ids)
        generated_text = self.tokenizer.decode(answer_ids, skip_special_tokens=True).strip()
        wall_time = time.time() - start_time

        return GenerationResult(
            prompt=prompt,
            generated_text=generated_text,
            num_forward_passes=num_forward_passes,
            wall_time_sec=wall_time,
            num_denoising_steps_used=global_step,
            num_remasked_tokens=0,
            intermediate_states=intermediate_states,
            token_ids=gen_token_ids,
            raw_metadata={
                "prompt_num_tokens": prompt_len,
                "answer_num_tokens": len(answer_ids),
                "hit_length_limit": len(answer_ids) == len(gen_token_ids),

                "answer_tokens": len(answer_ids),
                "leftover_masks": sum(t == self.mask_token_id for t in gen_token_ids),
            },
        )

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
        ban=None,
    ) -> GenerationResult:
        """ban: optional {response position: [token ids]} that may not be predicted there (the remask loop uses it
        to forbid an answer label the verifier rejected)."""
        start_time = time.time()
        temperature = 0.0 if temperature is None else temperature
        if self.use_chat_template:
            prompt_ids = build_chat_input_ids(self.tokenizer, prompt, self.device)
        elif isinstance(prompt, list):
            raise ValueError("Chat-message prompts require use_chat_template: true")
        else:
            prompt_ids = self.tokenizer(prompt, return_tensors="pt").input_ids.to(self.device)
        prompt_len = prompt_ids.shape[1]

        positions = sorted(set(int(p) for p in remask_positions))
        if any(p < 0 or p >= len(token_ids) for p in positions):
            raise ValueError("remask_positions out of range of token_ids")
        gen_ids = torch.tensor([token_ids], dtype=torch.long, device=self.device)
        pos_t = torch.tensor(positions, dtype=torch.long, device=self.device)
        gen_ids[0, pos_t] = self.mask_token_id
        input_ids = torch.cat([prompt_ids, gen_ids], dim=1)

        n = len(positions)
        steps = max(1, min(num_denoising_steps or n, n)) if n else 0
        schedule = get_num_transfer_tokens(n, steps) if n else []
        if select_fn is not None:
            schedule = [1] * n
        end_ids = [LLADA_EOS_ID, LLADA_EOT_ID]
        num_forward_passes = 0

        for k in schedule:
            still = input_ids[0, prompt_len + pos_t] == self.mask_token_id
            remaining = pos_t[still]
            if remaining.numel() == 0:
                break
            logits = self.model(input_ids).logits[0, prompt_len:][remaining]
            num_forward_passes += 1
            if allow_end_from is not None:
                banned = remaining < allow_end_from
                logits[:, end_ids] = torch.where(banned[:, None], -torch.inf, logits[:, end_ids])
            if ban:
                for row, p in enumerate(remaining.tolist()):
                    if p in ban:
                        logits[row, list(ban[p])] = -torch.inf
            pred = torch.argmax(add_gumbel_noise(logits, temperature), dim=-1)
            scored = logits.float()
            if confidence_eos_eot_inf:
                scored = scored.clone()
                scored[:, end_ids] = -torch.inf
            conf = torch.gather(torch.softmax(scored, dim=-1), -1, pred.unsqueeze(-1)).squeeze(-1)
            if select_fn is None:
                top = torch.topk(conf, min(k, remaining.numel())).indices
            else:
                rem_list, want = remaining.tolist(), set(select_fn(remaining.tolist(), conf.tolist()))
                idx = [i for i, p in enumerate(rem_list) if p in want] or [int(conf.argmax())]
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
