"""NLI verifier (Phase 4.2): semantic check of causal (if / since / because / so) reasoning steps
with an off-the-shelf NLI model.

Each sentence of a step is split at its causal cue (src.verify.causal) into stated reasons and a
conclusion, and checked with three kinds of NLI pairs:

  grounding    each stated reason, one clause at a time, against the relevant context + parent steps
  conditional  each stated rule ("if A then B", "A things are B") against the relevant context
  inference    is the conclusion licensed? Off-the-shelf NLI models do not apply rules: "The mouse is
               big. If the mouse is big then the mouse is nice." => "The mouse is nice" comes out
               neutral. So modus ponens is decomposed into what NLI does well, for each candidate rule
               (the stated ones, else the context rules most relevant to the conclusion), with its
               variable bound to each entity the step mentions:
                   consequent  rule's "then" part  => conclusion
                   antecedent  known facts          => each "if" clause
               p(entailment) = p(consequent) * min p(antecedent); the best rule/binding is kept, next to
               a direct check (stated facts => conclusion) for restated facts.

The step takes the distribution of its weakest check: entailment -> VALID; contradiction or neutral
-> INVALID ("contradiction" / "unsupported"); p_invalid = 1 - p(entailment). Pair logits are
temperature-scaled; temperature and flag threshold are fitted on reference data by
scripts/eval_verifiers.py (src.verify.calibration).
"""
import re
from typing import Optional

import numpy as np

from src.verify.base import INVALID, VALID, Check, StepInput, Verdict, has_mask, unverifiable
from src.verify.causal import clean, sentences, split_causal

LABELS = ("entailment", "neutral", "contradiction")
DEFAULT_MODEL = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"

META_SENTENCE = re.compile(r"\b(?:hypothesis|the answer|true, false|let's|step by step|we need to|to determine)\b", re.I)
_STOP = {
    "the", "a", "an", "is", "are", "and", "or", "if", "then", "it", "they", "so", "since", "because", "of",
    "to", "in", "that", "this", "all", "things", "people", "someone", "something", "not", "be", "we", "can",
    "therefore", "thus", "also", "does", "do", "has", "have", "was", "were", "which", "means",
}


def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = np.asarray(logits, dtype=np.float64) / temperature
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


class HFNLIBackend:
    """Sequence-pair classifier from the HF hub; logits are returned in LABELS order."""

    def __init__(self, model_name: str = DEFAULT_MODEL, device: Optional[str] = None, batch_size: int = 16, max_length: int = 512):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = device
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(device).eval()
        self.batch_size = batch_size
        self.max_length = max_length
        id2label = {int(i): l.lower() for i, l in self.model.config.id2label.items()}
        self.order = [next(i for i, l in id2label.items() if l.startswith(name[:5])) for name in LABELS]

    def logits(self, pairs: list) -> np.ndarray:
        out = []
        for i in range(0, len(pairs), self.batch_size):
            batch = pairs[i:i + self.batch_size]
            enc = self.tokenizer([p for p, _ in batch], [h for _, h in batch], truncation="only_first",
                                 max_length=self.max_length, padding=True, return_tensors="pt").to(self.device)
            with self.torch.no_grad():
                out.append(self.model(**enc).logits.float().cpu().numpy()[:, self.order])
        return np.concatenate(out) if out else np.zeros((0, 3))


def _content_words(text: str) -> set:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOP and len(w) > 1}


def relevant_context(context: str, query: str, k: int) -> str:
    """The k context sentences sharing the most content words with the query, in original order."""
    sents = [s for s in re.split(r"(?<=[.!?])\s+", context.strip()) if s]
    if k <= 0 or len(sents) <= k:
        return " ".join(sents)
    q = _content_words(query)
    scored = sorted(range(len(sents)), key=lambda i: -len(q & _content_words(sents[i])))[:k]
    return " ".join(sents[i] for i in sorted(scored))


RULE_CLAUSE = re.compile(r"(?:if\s+.+?\s+then\s+.+|(?:all\s+)?[a-z]+(?:\s*,\s*[a-z]+)*\s+(?:things|people|ones)\s+are\s+.+)", re.I)
_RULE_SPAN = re.compile(r"\bif\s+.+?\s+then\s+[^,;]+?(?=,\s|;|$|\s+and\s+(?!not\b)[A-Z]|\s+and\s+(?:the|all)\s)|"
                        r"\b(?:all\s+)?[a-z]+(?:\s*,\s*[a-z]+)*\s+(?:things|people|ones)\s+are\s+(?:not\s+)?[a-z]+", re.I)


def reason_clauses(reasons: str) -> list:
    """Split stated reasons into single claims, keeping rules whole:
    "Anne is white, and white things are nice" -> ["Anne is white", "white things are nice"]."""
    if not reasons:
        return []
    rules = []

    def keep(m):
        rules.append(m.group().strip())
        return f" \x00{len(rules) - 1}\x00 "

    masked = _RULE_SPAN.sub(keep, reasons)
    parts = [p.strip(" ,.") for p in re.split(r"\s*,\s*and\s+|\s+and\s+|\s*,\s*", masked)]
    out = []
    for p in parts:
        m = re.fullmatch(r"\x00(\d+)\x00", p)
        if m:
            out.append(rules[int(m.group(1))])
        elif len(p.split()) >= 2:
            out.append(re.sub(r"\x00(\d+)\x00", lambda k: rules[int(k.group(1))], p))
    return out


_SUBJECT = re.compile(r"^(.+?)\s+(?:is|are|does|do|was|were|[a-z]+s)\b")
_VAR_WORDS = re.compile(r"\b(?:something|someone|somebody|they|it|them)\b", re.I)
_GENERIC_RULE = re.compile(r"^(?:all\s+)?([a-z]+(?:\s*,\s*[a-z]+)*)\s+(?:things|people|ones)\s+are\s+(not\s+)?([a-z]+)$", re.I)


def subject_of(claim: str) -> str:
    m = _SUBJECT.match(claim.strip())
    return m.group(1) if m else ""


def instantiate_rule(rule: str, entity: str) -> str:
    """Bind a rule's variable to an entity, since NLI models rarely apply rules over "someone":
    "If someone eats the dog then they need the dog" -> "If the bear eats the dog then the bear need the dog";
    "Round, young things are white" -> "If Anne is round and Anne is young then Anne is white"."""
    r = rule.strip().rstrip(".")
    if not entity:
        return r
    m = _GENERIC_RULE.match(r)
    if m:
        attrs = [a for a in re.split(r"\s*,\s*", m.group(1).lower()) if a]
        conds = " and ".join(f"{entity} is {a}" for a in attrs)
        return f"If {conds} then {entity} is {'not ' if m.group(2) else ''}{m.group(3)}"
    if not re.match(r"^if\b", r, re.I) or not _VAR_WORDS.search(r):
        return r
    out = _VAR_WORDS.sub(entity, r)
    return re.sub(rf"({re.escape(entity)}) are\b", r"\1 is", out)


def _instantiated(texts: list, entity: str) -> list:
    return [instantiate_rule(t, entity) if RULE_CLAUSE.fullmatch(t.strip().rstrip(".")) else t for t in texts]


def _relevant_rules(body: str, query: str, k: int) -> list:
    rules = [x for x in re.split(r"(?<=[.!?])\s+", body.strip()) if RULE_CLAUSE.fullmatch(x.strip().rstrip("."))]
    q = _content_words(query)
    return sorted(rules, key=lambda x: -len(q & _content_words(x)))[:k]


def _conclusion(step_text: str) -> str:
    """What a parent step established: the conclusion of its last sentence."""
    sents = [x for x in sentences(step_text) if not META_SENTENCE.search(x)]
    return (split_causal(sents[-1]).conclusion + ".") if sents else ""


def _context_body(context: str) -> str:
    """The theory / problem part of a prompt (drops instructions and the hypothesis)."""
    m = re.search(r"Theory:\s*(.*?)\s*(?:Hypothesis:|$)", context, re.S)
    if m:
        return m.group(1)
    m = re.search(r"(?:Problem|Question):\s*(.*?)\s*(?:Solution:|Answer:|Let's think|$)", context, re.S)
    return m.group(1) if m else context


_IF_THEN = re.compile(r"^if\s+(.+?),?\s+then\s+(.+)$", re.I)


def _entities_in(texts: list) -> list:
    out = []
    for t in texts:
        for part in reason_clauses(t) or [t]:
            e = subject_of(part)
            if e and e.lower() not in ("it", "they", "something", "someone", "this", "that", "there") and e not in out:
                out.append(e)
    return out


class NLIVerifier:
    name = "nli"

    def __init__(self, backend=None, temperature: float = 1.0, flag_threshold: float = 0.5, top_k_context: int = 6,
                 check_premises: bool = True, max_parents: int = 3, top_k_rules: int = 3, max_bindings: int = 3):
        self.backend = backend if backend is not None else HFNLIBackend()
        self.temperature = temperature
        self.flag_threshold = flag_threshold
        self.top_k_context = top_k_context
        self.check_premises = check_premises
        self.max_parents = max_parents
        self.top_k_rules = top_k_rules
        self.max_bindings = max_bindings

    # -- checks -----------------------------------------------------------------
    def checks_for(self, step: StepInput) -> list:
        """[(name, hypothesis, spec)]; spec is a (premise, hypothesis) pair, or for "inference" a dict
        {"direct": pair, "rules": [(rule text, consequent pair, [antecedent pairs])]}."""
        body = _context_body(step.context)
        parent_facts = [_conclusion(p) for p in step.premises[-self.max_parents:]]
        out, earlier_facts, earlier_rules = [], [], []
        for sent in sentences(step.text):
            if META_SENTENCE.search(sent):
                continue
            split = split_causal(sent)
            concl = split.conclusion
            if split.cue == "if" or (not split.premise and RULE_CLAUSE.fullmatch(concl)):
                rule = clean(sent).rstrip(".") if split.cue == "if" else concl
                out.append(("conditional", rule, (relevant_context(body, rule, self.top_k_context), rule)))
                earlier_rules.append(rule)
                continue
            clauses = reason_clauses(split.premise or "")
            stated_rules = [c for c in clauses if RULE_CLAUSE.fullmatch(c)]
            stated_facts = [c for c in clauses if not RULE_CLAUSE.fullmatch(c)]
            if self.check_premises:
                for c in stated_facts:
                    out.append(("grounding", c, (_join(parent_facts + [relevant_context(body, c, self.top_k_context)]), c)))
                for r in stated_rules:
                    out.append(("conditional", r, (relevant_context(body, r, self.top_k_context), r)))
            if len(concl.split()) < 2:
                continue
            facts = parent_facts + earlier_facts + stated_facts
            direct = _join(facts) if facts else relevant_context(body, concl, self.top_k_context)
            rules = stated_rules + earlier_rules or _relevant_rules(body, concl, self.top_k_rules)
            known = _join(facts + [relevant_context(body, concl, self.top_k_context)])
            bindings = _entities_in([concl] + stated_facts + earlier_facts + parent_facts)[: self.max_bindings]
            mp = []
            for r in rules:
                for e in (bindings if _VAR_WORDS.search(r) or _GENERIC_RULE.match(r.strip().rstrip(".")) else [None]):
                    inst = instantiate_rule(r, e) if e else r.strip().rstrip(".")
                    m = _IF_THEN.match(inst)
                    if not m:
                        continue
                    ants = [a for a in reason_clauses(m.group(1)) if len(a.split()) >= 2]
                    mp.append((inst, (m.group(2).strip() + ".", concl), [(known, a) for a in ants]))
            out.append(("inference", concl, {"direct": (direct, concl), "rules": mp}))
            earlier_facts.append(concl)
        return [c for c in out if c[1] and len(c[1].split()) >= 2]

    # -- verification -------------------------------------------------------------
    def verify(self, step: StepInput) -> Verdict:
        return self.verify_batch([step])[0]

    def verify_batch(self, steps: list) -> list:
        flat, plans = [], []

        def add(pair):
            flat.append(pair)
            return len(flat) - 1

        for s in steps:
            plan = []
            for name, hyp, spec in ([] if has_mask(s.text) else self.checks_for(s)):
                if name != "inference":
                    plan.append((name, hyp, add(spec)))
                else:
                    plan.append((name, hyp, {"direct": add(spec["direct"]),
                                             "rules": [(r, add(c), [add(a) for a in ants]) for r, c, ants in spec["rules"]]}))
            plans.append(plan)
        probs_all = softmax(self.backend.logits(flat), self.temperature) if flat else np.zeros((0, 3))

        verdicts = []
        for s, plan in zip(steps, plans):
            if not plan:
                verdicts.append(unverifiable(self.name, "masked step" if has_mask(s.text) else "no checkable sentence"))
                continue
            checks, dists = [], []
            for name, hyp, ref in plan:
                if name == "inference":
                    dist, how = _inference_dist(probs_all, ref)
                else:
                    dist, how = probs_all[ref], ""
                dists.append(dist)
                checks.append(Check(name, bool(dist[0] >= 1 - self.flag_threshold),
                                    f"{hyp!r}: " + ", ".join(f"{l[:5]}={v:.2f}" for l, v in zip(LABELS, dist)) + how))
            worst = int(np.argmin([d[0] for d in dists]))
            verdicts.append(self._verdict(dists[worst], checks))
        return verdicts

    def _verdict(self, probs, checks) -> Verdict:
        p_invalid = float(1 - probs[0])
        info = {l: float(v) for l, v in zip(LABELS, probs)}
        info["logits"] = [float(x) for x in np.log(np.clip(probs, 1e-6, 1))]  # log-probs: re-scalable by a temperature
        if p_invalid < self.flag_threshold:
            return Verdict(VALID, p_invalid, self.name, checks=checks, probs=info)
        err = "contradiction" if probs[2] >= probs[1] else "unsupported"
        return Verdict(INVALID, p_invalid, self.name, err, checks, probs=info)


def _join(texts: list) -> str:
    return " ".join(t.strip().rstrip(".") + "." for t in texts if t and t.strip())


def _inference_dist(probs, ref) -> tuple:
    """Class distribution for "is the conclusion licensed": the more decisive of the direct check and
    the best modus-ponens decomposition."""
    best, how = probs[ref["direct"]], " (direct)"
    for rule, c, ants in ref["rules"]:
        pc = probs[c]
        applies = min((probs[a][0] for a in ants), default=1.0)
        ent, contra = pc[0] * applies, pc[2] * applies
        dist = np.array([ent, max(0.0, 1 - ent - contra), contra])
        if max(dist[0], dist[2]) > max(best[0], best[2]):
            best, how = dist, f" (via {rule!r})"
    return best, how
