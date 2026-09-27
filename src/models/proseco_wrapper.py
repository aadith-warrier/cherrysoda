import importlib.util
import os
import time

import torch
from transformers import AutoModel, AutoTokenizer

from src.models.base import BaseDLMWrapper, GenerationResult

PROSECO_LLADA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                 "third_party", "proseco", "llada")


class ProSeCoWrapper(BaseDLMWrapper):

    def load(self):
        if not os.path.isfile(os.path.join(PROSECO_LLADA_DIR, "generate.py")):
            raise FileNotFoundError(f"{PROSECO_LLADA_DIR} not found. Run: bash scripts/setup_third_party.sh")
        spec = importlib.util.spec_from_file_location("proseco_official_generate",
                                                      os.path.join(PROSECO_LLADA_DIR, "generate.py"))
        module = importlib.util.module_from_spec(spec)              # official llada/generate.py, loaded by path
        spec.loader.exec_module(module)
        self._generate_fn = module.generate

        dtype = getattr(torch, self.config.get("dtype", "bfloat16"))
        self.model = AutoModel.from_pretrained(
            self.config["hf_repo_id"], trust_remote_code=True, torch_dtype=dtype)
        self.model.eval()
        self.model = self.model.to(self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(self.config["tokenizer_repo_id"], trust_remote_code=True)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        self.mask_token_id = self.config.get("mask_token_id", 126336)

    @torch.no_grad()
    def generate(self, prompt, max_new_tokens, num_denoising_steps, remasking_strategy="low_confidence",
                 return_intermediate_states=False, eligibility_fn=None, block_length=None):
        if eligibility_fn is not None or return_intermediate_states:
            raise NotImplementedError("ProSeCo runs the official sampler only.")
        gen = self.config["generation"]
        start = time.time()

        prompt_str = self.tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}], add_generation_prompt=True, tokenize=False)
        input_ids = torch.tensor(self.tokenizer(prompt_str)["input_ids"], dtype=torch.long,
                                 device=self.device).unsqueeze(0)

        generated, nfe, _ = self._generate_fn(
            self.model, input_ids,
            steps=num_denoising_steps,
            gen_length=max_new_tokens,
            block_length=block_length or gen["block_length"],
            temperature=gen.get("temperature", 0.0),
            remasking=remasking_strategy,
            mask_id=self.mask_token_id,
            threshold=None,
            max_corrector_steps_per_loop=gen["max_corrector_steps_per_loop"],
            apply_corrector_every_n_steps=gen["apply_corrector_every_n_steps"],
            early_eos_stopping=gen.get("early_eos_stopping", True),
            tokenizer=self.tokenizer,
            disable_pbar=True,
        )
        gen_ids = generated[0, input_ids.shape[1]:]
        text = self.tokenizer.decode(gen_ids, skip_special_tokens=True).strip()
        n_tokens = int((gen_ids != self.tokenizer.eos_token_id).sum().item())   # as in the official harness
        return GenerationResult(
            prompt=prompt,
            generated_text=text,
            num_forward_passes=int(nfe["total_nfe"]),
            wall_time_sec=time.time() - start,
            num_denoising_steps_used=int(nfe["predictor_nfe"]),
            num_remasked_tokens=0,
            raw_metadata={"answer_num_tokens": n_tokens, "hit_length_limit": n_tokens >= max_new_tokens,
                          "predictor_nfe": int(nfe["predictor_nfe"]), "corrector_nfe": int(nfe["corrector_nfe"])},
        )

    def get_token_confidences(self, logits) -> list:
        raise NotImplementedError
