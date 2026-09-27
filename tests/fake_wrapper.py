from src.models.base import BaseDLMWrapper, GenerationResult


class FakeTokenizer:
    def decode(self, ids, skip_special_tokens=True):
        return "".join(chr(i) for i in ids)


class FakeWrapper(BaseDLMWrapper):
    crash_after = None

    def load(self):
        self.calls = 0
        self.tokenizer = FakeTokenizer()
        self.stop_token_ids = {0}

    def generate(self, prompt, max_new_tokens, num_denoising_steps, remasking_strategy="low_confidence",
                 return_intermediate_states=False, eligibility_fn=None, block_length=None,
                 step_observer=None):
        self.calls += 1
        if FakeWrapper.crash_after and self.calls > FakeWrapper.crash_after:
            raise RuntimeError("simulated crash")
        assert remasking_strategy == self.config["generation"]["remasking_strategy"]
        if step_observer is not None:  # early guesses say 9, later ones say 7
            for step in range(num_denoising_steps):
                guess = "The answer is: 9" if step < num_denoising_steps // 3 else "The answer is: 7"
                step_observer(step, [ord(c) for c in guess] + [0, 65])
        text = "3 + 4 = 7\nThe answer is: 7" if self.calls % 2 else ""
        return GenerationResult(prompt=prompt, generated_text=text, num_forward_passes=num_denoising_steps,
                                wall_time_sec=0.01, num_denoising_steps_used=num_denoising_steps,
                                raw_metadata={"answer_num_tokens": 9, "hit_length_limit": False})

    def get_token_confidences(self, logits):
        return []
