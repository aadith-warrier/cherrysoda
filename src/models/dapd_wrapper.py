import os
import time
 
import torch
from transformers import AutoModel, AutoTokenizer
 
from src.models.base import BaseDLMWrapper, GenerationResult, load_package_from_dir
 
DAPD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "third_party", "DAPD")
LLADA1_MASK_TOKEN_ID = 126336   # fallback used by the official wrapper
 
 
class DAPDWrapper(BaseDLMWrapper):
 
    def load(self):
        if not os.path.isdir(os.path.join(DAPD_DIR, "dapd")):
            raise FileNotFoundError(f"{DAPD_DIR} not found. Run: bash scripts/setup_third_party.sh")
        # Load the official `dapd` package by path. Adding the DAPD repo root to sys.path
        # would let its own top-level `baselines/` folder shadow ours.
        self._dapd = load_package_from_dir("dapd", os.path.join(DAPD_DIR, "dapd"))
        self.base = self.config["base"]
        if self.base not in ("llada", "dream"):
            raise ValueError(f"base must be 'llada' or 'dream', got {self.base!r}")
 
        # The official Dream code allocates with device='cuda' (dapd/dream_core.py, line 248),
        # i.e. the *current* GPU. Their scripts run with one visible GPU; we make the model's
        # GPU the current one so that 'cuda' means the same device. No change to their code.
        if str(self.device).startswith("cuda") and torch.cuda.is_available():
            torch.cuda.set_device(torch.device(self.device))
 
        repo_id = self.config["hf_repo_id"]
        self.tokenizer = AutoTokenizer.from_pretrained(repo_id, trust_remote_code=True)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        self.model = AutoModel.from_pretrained(
            repo_id, trust_remote_code=True, torch_dtype=torch.bfloat16).to(self.device).eval()
        mask_id = getattr(self.tokenizer, "mask_token_id", None)
        self.mask_id = int(mask_id) if mask_id is not None else LLADA1_MASK_TOKEN_ID
 
    @torch.no_grad()
    def generate(self, prompt, max_new_tokens, num_denoising_steps, remasking_strategy="low_confidence",
                 return_intermediate_states=False, eligibility_fn=None, block_length=None):
        if eligibility_fn is not None or return_intermediate_states:
            raise NotImplementedError("DAPD runs the official sampler only.")
        g = self.config["generation"]
        start = time.time()
 
        text = self.tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True)
        context = self.tokenizer.encode(text, return_tensors="pt", add_special_tokens=False).to(self.device)
        block = int(block_length or 0)
        blockwise = 0 < block < max_new_tokens
 
        if self.base == "llada":
            kwargs = dict(model=self.model, prompt=context, attention_mask=torch.ones_like(context),
                          gen_length=max_new_tokens, tau_min=g["tau_min"], tau_max=g["tau_max"],
                          layer_ratio=g["layer_ratio"], mask_id=self.mask_id, alg=g["dapd_alg"],
                          collect_step_history=False, verbose=False)
            if blockwise:
                output, stats = self._dapd.generate_dapd_with_blocks(
                    **kwargs, block_length=block, attention_scope="global")
            else:
                output, stats = self._dapd.generate_dapd(**kwargs)
        else:
            kwargs = dict(model=self.model, tokenizer=self.tokenizer, input_ids=context,
                          layer_ratio=g["layer_ratio"], tau_min=g["tau_min"], tau_max=g["tau_max"],
                          dapd_alg=g["dapd_alg"])
            if blockwise:
                output, stats = self._dapd.dream_generate_dapd_with_blocks(
                    **kwargs, gen_length=max_new_tokens, block_length=block)
            else:
                output, stats = self._dapd.dream_generate_dapd(**kwargs, max_new_tokens=max_new_tokens)
 
        gen_ids = output[0, context.shape[1]:]
        text_out = self.tokenizer.decode(gen_ids, skip_special_tokens=True).strip()
        n_tokens = int((gen_ids != self.tokenizer.eos_token_id).sum().item())
        nfe = int(stats.get("total_forward_passes") or stats.get("total_steps") or 0)
        return GenerationResult(
            prompt=prompt,
            generated_text=text_out,
            num_forward_passes=nfe,
            wall_time_sec=time.time() - start,
            num_denoising_steps_used=int(stats.get("total_steps") or 0),
            num_remasked_tokens=0,
            raw_metadata={"answer_num_tokens": n_tokens, "hit_length_limit": n_tokens >= max_new_tokens},
        )
 
    def get_token_confidences(self, logits) -> list:
        raise NotImplementedError
 