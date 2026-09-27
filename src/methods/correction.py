import math


class TemporalVote:

    def __init__(self, extract_fn, total_steps: int, weighting: str = "exp", alpha: float = 5.0):
        if weighting not in ("exp", "linear", "fixed"):
            raise ValueError(f"Unknown weighting {weighting!r}")
        self.extract_fn = extract_fn          # text -> answer or None
        self.total_steps = max(1, total_steps)
        self.weighting = weighting
        self.alpha = alpha
        self.scores = {}
        self.num_votes = 0

    def weight(self, step: int) -> float:
        frac = step / self.total_steps
        if self.weighting == "exp":
            return math.exp(self.alpha * frac)
        if self.weighting == "linear":
            return (step + 1) / self.total_steps
        return 1.0

    @staticmethod
    def _key(answer):
        return round(answer, 6) if isinstance(answer, float) else answer

    def add(self, step: int, text: str):
        answer = self.extract_fn(text)
        if answer is None:
            return
        k = self._key(answer)
        self.scores[k] = self.scores.get(k, 0.0) + self.weight(step)
        self.num_votes += 1

    def result(self):
        if not self.scores:
            return None
        return max(self.scores.items(), key=lambda kv: kv[1])[0]

    def top(self, n: int = 3) -> list:
        return [[a, round(w, 3)] for a, w in sorted(self.scores.items(), key=lambda kv: -kv[1])[:n]]
