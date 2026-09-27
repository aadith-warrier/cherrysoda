import importlib.util
import os
import sys
import time
 
import torch
from transformers import AutoTokenizer
 
from src.models.base import BaseDLMWrapper, GenerationResult
 
REMEDI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                          "third_party", "RemeDi")
 
 
class RemeDiWrapper(BaseDLMWrapper):
 
    def load(self):
        if not os.path.isdir(os.path.join(REMEDI_DIR, "remedi")):
            raise FileNotFoundError(f"{REMEDI_DIR} not found. Run: bash scripts/setup_third_party.sh")
        if REMEDI_DIR not in sys.path:
            sys.path.append(REMEDI_DIR)   # appended (not prepended) so nothing there can shadow our modules
        spec = importlib.util.spec_from_file_location("remedi_official_inference",
                                                      os.path.join(REMEDI_DIR, "inference.py"))
        remedi_inference = importlib.util.module_from_spec(spec)   # official inference.py, loaded by path
        spec.loader.exec_module(remedi_inference)
        from remedi import RemeDiUPMModelLM
        from remedi.modelling_remedi_bitowel import DynamicCache as RemeDiCache
        remedi_inference.DynamicCache = RemeDiCache                 # the compatibility patch (see module docstring)
        self._generate_fn = remedi_inference.generate_block_diffusion
 
        repo_id = self.config["hf_repo_id"]
        dtype = getattr(torch, self.config.get("dtype", "bfloat16"))
        tok_repo = self.config.get("tokenizer_repo_id", "GSAI-ML/LLaDA-8B-Instruct")
        self.tokenizer = AutoTokenizer.from_pretrained(tok_repo, trust_remote_code=True)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = RemeDiUPMModelLM.from_pretrained(repo_id, torch_dtype=dtype)
        self.model.eval().requires_grad_(False).to(self.device)
 
        self._forward_calls = 0
 
        def _count(module, args, kwargs):
            self._forward_calls += 1
        self.model.register_forward_pre_hook(_count, with_kwargs=True)
 
    @torch.no_grad()
    def generate(self, prompt, max_new_tokens, num_denoising_steps, remasking_strategy="low_confidence",
                 return_intermediate_states=False, eligibility_fn=None, block_length=None):
        if eligibility_fn is not None or return_intermediate_states:
            raise NotImplementedError("RemeDi runs the official sampler only.")
        block_length = block_length or self.config["generation"]["block_length"]
        if max_new_tokens % block_length:
            raise ValueError("max_new_tokens must be divisible by block_length")
        num_blocks = max_new_tokens // block_length
        if num_denoising_steps % num_blocks:
            raise ValueError("num_denoising_steps must be divisible by the number of blocks")
        steps_per_block = num_denoising_steps // num_blocks
 
        start = time.time()
        self._forward_calls = 0
        conv = {"role": "user", "content": prompt}
        responses = self._generate_fn(
            self.model, conv, self.tokenizer, self.device,
            num_generations=1,
            steps=steps_per_block,
            max_length=max_new_tokens,
            block_size=block_length,
        )
        text = responses[0].strip()
        n_tokens = len(self.tokenizer(text, add_special_tokens=False)["input_ids"])
        return GenerationResult(
            prompt=prompt,
            generated_text=text,
            num_forward_passes=self._forward_calls,   # prompt prefill + block steps + per-block cache updates
            wall_time_sec=time.time() - start,
            num_denoising_steps_used=num_denoising_steps,
            num_remasked_tokens=0,                    # the official sampler does not report remasks
            raw_metadata={"answer_num_tokens": n_tokens, "hit_length_limit": n_tokens >= max_new_tokens},
        )
 
    def get_token_confidences(self, logits) -> list:
        raise NotImplementedError
 