"""Symbolic verifier for ProofWriter-style reasoning (deterministic half of Phase 4 for logic).

ProofWriter theories are written in a small template language ("Bob is big.", "The cat does not
chase the dog.", "If something is red and not big then it is young.", "Round, young things are
white."), so the theory can be parsed exactly and closed under its rules. A reasoning step is
then checked against that closure:

  conclusion   every fact the step concludes must be provable; its negation being provable is a
               contradiction, neither being provable makes it unsupported
  premise      every fact the step gives as a reason must be provable too (catches misread facts)
  rule         every rule the step cites must be a rule of the theory (or an instance of one)
  unknown      "we have no information that X" / "cannot prove X" is wrong when X or not-X is provable

The closure follows ProofWriter's open-world semantics: a negated condition holds only when the
negated fact is itself provable. Steps with nothing the parser recognises are UNVERIFIABLE, which
is where the NLI verifier takes over in a CascadeVerifier.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from src.verify.base import INVALID, VALID, Check, StepInput, Verdict, has_mask, unverifiable
from src.verify.causal import clean, sentences, split_causal

VAR = "?x"
_VARIABLE_WORDS = {"something", "someone", "it", "they", "them", "things", "people", "ones", "somebody"}
_PRONOUNS = {"it", "they", "them", "he", "she", "him", "her"}
_COPULA = r"(?:is|are|was|were)"
# ProofWriter's relation verbs (Tafjord et al., 2021); theories using others are picked up from their facts.
PROOFWRITER_VERBS = {"chase", "eat", "like", "need", "see", "visit"}


@dataclass(frozen=True)
class Atom:
    subj: str
    rel: str  # "is" for attributes, else the verb lemma ("chase", "like")
    obj: str
    neg: bool = False

    def negated(self) -> "Atom":
        return Atom(self.subj, self.rel, self.obj, not self.neg)

    def key(self) -> tuple:
        return (self.subj, self.rel, self.obj)

    def text(self) -> str:
        subj = self.subj if self.subj[:1].isupper() or self.subj == VAR else f"the {self.subj}"
        if self.rel == "is":
            return f"{subj} is {'not ' if self.neg else ''}{self.obj}"
        obj = self.obj if self.obj[:1].isupper() or self.obj == VAR else f"the {self.obj}"
        return f"{subj} {'does not ' + self.rel if self.neg else self.rel + 's'} {obj}"

    def bind(self, value: str) -> "Atom":
        return Atom(value if self.subj == VAR else self.subj, self.rel, value if self.obj == VAR else self.obj, self.neg)

    @property
    def has_var(self) -> bool:
        return VAR in (self.subj, self.obj)


@dataclass(frozen=True)
class Rule:
    conds: frozenset
    concl: Atom

    def canonical(self) -> tuple:
        return (self.conds, self.concl)


@dataclass
class Theory:
    facts: set = field(default_factory=set)
    rules: list = field(default_factory=list)
    entities: set = field(default_factory=set)
    attributes: set = field(default_factory=set)
    verbs: set = field(default_factory=set)
    unparsed: list = field(default_factory=list)
    _closure: Optional[set] = None

    def closure(self) -> set:
        """All provable literals (open world: a negated condition needs a provable negative fact)."""
        if self._closure is None:
            known = set(self.facts)
            changed = True
            while changed:
                changed = False
                for r in self.rules:
                    for value in (self.entities if any(c.has_var for c in r.conds) or r.concl.has_var else [None]):
                        conds = [c.bind(value) if value else c for c in r.conds]
                        if all(c in known for c in conds):
                            new = r.concl.bind(value) if value else r.concl
                            if new not in known:
                                known.add(new)
                                changed = True
            self._closure = known
        return self._closure

    def status(self, atom: Atom) -> str:
        """"proved", "disproved" or "unknown"."""
        c = self.closure()
        if atom in c:
            return "proved"
        if atom.negated() in c:
            return "disproved"
        return "unknown"

    def has_rule(self, rule: Rule) -> bool:
        canon = rule.canonical()
        if any(r.canonical() == canon for r in self.rules):
            return True
        # "if Fiona is green and young then she is round": an instance of a rule with the variable bound
        for r in self.rules:
            for value in self.entities:
                if frozenset(c.bind(value) for c in r.conds) == rule.conds and r.concl.bind(value) == rule.concl:
                    return True
        return False


# ---------------------------------------------------------------- parsing

def _norm_entity(s: str) -> str:
    s = s.strip()
    if s.lower() in _VARIABLE_WORDS:
        return VAR
    s = re.sub(r"^the\s+", "", s, flags=re.I)
    return s if s[:1].isupper() and " " not in s else s.lower()


def _lemma(verb: str) -> str:
    v = verb.lower()
    if v.endswith("es") and v[:-2] in ("chas", "se"):  # chases, sees are regular "+s"
        return v[:-1]
    return v[:-1] if v.endswith("s") and not v.endswith("ss") else v


# Case-sensitive on purpose: a capitalised word is a name ("Bob"), "the x" / "the bald eagle" is an animal.
_ENTITY = r"(?:[Tt]he\s+[a-z]+(?:\s+[a-z]+)?|[A-Z][a-z]+|(?i:something|someone|somebody|it|they|them|he|she|him|her))"
_FACT_IS = re.compile(rf"^(?P<s>{_ENTITY})\s+{_COPULA}\s+(?P<neg>not\s+)?(?P<a>[a-z]+)$")
_FACT_REL_NEG = re.compile(rf"^(?P<s>{_ENTITY})\s+(?:does|do|did)\s+not\s+(?P<v>[a-z]+)\s+(?P<o>{_ENTITY})$")
_FACT_REL = re.compile(rf"^(?P<s>{_ENTITY})\s+(?P<v>[a-z]+)\s+(?P<o>{_ENTITY})$")
_RULE_IF = re.compile(r"^if\s+(?P<c>.+?)(?:,?\s+then\s+|,\s*)(?P<d>.+)$", re.I)
# "Round, young things are white." (ProofWriter never joins these conditions with "and")
_RULE_GENERIC = re.compile(r"^(?:all\s+)?(?P<attrs>[a-z]+(?:\s*,\s*[a-z]+)*)\s+(?:things|people|ones|animals)"
                           r"\s+are\s+(?P<neg>not\s+)?(?P<a>[a-z]+)$", re.I)


def parse_atom(text: str, verbs: Optional[set] = None, subject: Optional[str] = None) -> Optional[Atom]:
    """One literal. `subject` fills an elided subject ("... is rough and not red": "not red")."""
    t = text.strip().rstrip(".").strip()
    t = re.sub(r"\s+", " ", t)
    m = _FACT_IS.match(t)
    if m:
        return Atom(_norm_entity(m.group("s")), "is", m.group("a").lower(), bool(m.group("neg")))
    m = _FACT_REL_NEG.match(t)
    if m:
        return Atom(_norm_entity(m.group("s")), _lemma(m.group("v")), _norm_entity(m.group("o")), True)
    m = _FACT_REL.match(t)
    if m and m.group("v").lower() not in ("is", "are", "was", "were", "does", "do") and (verbs is None or _lemma(m.group("v")) in verbs):
        return Atom(_norm_entity(m.group("s")), _lemma(m.group("v")), _norm_entity(m.group("o")), False)
    if subject is not None:  # elided subject: "not red", "young", "chases the cat"
        m = re.match(r"^(?:is\s+|are\s+)?(not\s+)?([a-z]+)$", t, re.I)
        if m:
            return Atom(subject, "is", m.group(2).lower(), bool(m.group(1)))
        m = re.match(r"^(?:(?:does|do) not\s+)?([a-z]+)\s+(" + _ENTITY + r")$", t)
        if m and (verbs is None or _lemma(m.group(1)) in verbs):
            return Atom(subject, _lemma(m.group(1)), _norm_entity(m.group(2)), t.lower().startswith(("does not", "do not")))
    return None


def _conjuncts(text: str) -> list:
    return [p for p in re.split(r"\s*,\s*and\s+|\s+and\s+|\s*,\s*", text.strip()) if p]


def parse_conjunction(text: str, verbs: Optional[set] = None) -> Optional[list]:
    atoms, subject = [], None
    for part in _conjuncts(text):
        a = parse_atom(part, verbs, subject)
        if a is None:
            return None
        atoms.append(a)
        subject = a.subj
    return atoms or None


def parse_rule(text: str, verbs: Optional[set] = None) -> Optional[Rule]:
    t = re.sub(r"\s+", " ", text.strip().rstrip("."))
    m = _RULE_IF.match(t)
    if m:
        conds = parse_conjunction(m.group("c"), verbs)
        concl = parse_conjunction(m.group("d"), verbs)
        if conds and concl and len(concl) == 1:
            return Rule(frozenset(conds), concl[0])
        return None
    m = _RULE_GENERIC.match(t)
    if m:
        attrs = [a for a in re.split(r"\s*,\s*|\s+and\s+", m.group("attrs").lower()) if a and a != "all"]
        conds = frozenset(Atom(VAR, "is", a) for a in attrs)
        return Rule(conds, Atom(VAR, "is", m.group("a").lower(), bool(m.group("neg"))))
    return None


def parse_theory(text: str) -> Theory:
    th = Theory(verbs=set(PROOFWRITER_VERBS))
    raw = [s for s in re.split(r"(?<=\.)\s+", text.strip()) if s.strip()]
    # Relation verbs first, so "The cat likes the dog" is not confused with other shapes.
    for s in raw:
        m = _FACT_REL_NEG.match(s.rstrip(".")) or _FACT_REL.match(s.rstrip("."))
        if m and not s.lower().startswith("if ") and m.group("v").lower() not in ("is", "are", "does", "do"):
            th.verbs.add(_lemma(m.group("v")))
        for m in re.finditer(r"\b(?:does|do) not ([a-z]+)\b|\b(?:it|they|something|someone)\s+([a-z]+s)\s+the\b", s):
            th.verbs.add(_lemma(m.group(1) or m.group(2)))
    th.verbs -= {"is", "are", "doe", "do", "the", "not", "a", "an", "and", "then", "if"}
    for s in raw:
        rule = parse_rule(s, th.verbs) if (s.lower().startswith("if ") or " things are " in s or " people are " in s) else None
        if rule is not None:
            th.rules.append(rule)
            continue
        atom = parse_atom(s, th.verbs)
        if atom is not None and not atom.has_var:
            th.facts.add(atom)
            continue
        th.unparsed.append(s)
    for a in list(th.facts) + [c for r in th.rules for c in list(r.conds) + [r.concl]]:
        for e in (a.subj, a.obj if a.rel != "is" else None):
            if e and e != VAR:
                th.entities.add(e)
        if a.rel == "is":
            th.attributes.add(a.obj)
    return th


# ---------------------------------------------------------------- reading model steps

_HEDGE = re.compile(
    r"(?:no information|not (?:enough|sufficient) information|(?:can ?not|unable to|do not|does not) "
    r"(?:be )?(?:definitively |directly |explicitly )?(?:prove|proved|determine|confirm|conclude|infer|know|tell|say|state)|"
    r"not (?:explicitly )?(?:stated|mentioned|given|known|proved|provable|proven|determined|certain)|no (?:rule|fact|evidence)|"
    r"(?:do|does) not (?:provide|give|contain) (?:any )?(?:information|evidence)|"
    r"none of the (?:given )?(?:facts|rules|statements)|there is no (?:direct )?(?:implication|information|indication))", re.I)
# A question the step sets itself ("we need to determine if Harry is big") claims nothing.
_QUESTION = re.compile(r"(?:need|have|want) to (?:determine|check|find out|see|verify|figure out|know)|"
                       r"\b(?:let's|let us) (?:check|see|determine)|\?\s*$", re.I)
_SKIP = re.compile(r"\b(?:hypothesis|the answer|true, false|is true|is false|is unknown)\b", re.I)
_QUOTED = re.compile(r"[\"“]([^\"”]+)[\"”]")


class _Reader:
    """Pull literals and rules out of free-form model text, restricted to the theory's vocabulary."""

    def __init__(self, theory: Theory):
        self.th = theory
        ents = sorted((e for e in theory.entities), key=len, reverse=True)
        self.ent_re = re.compile(r"\b(?:the\s+)?(" + "|".join(re.escape(e) for e in ents) + r")\b", re.I) if ents else None
        attrs = "|".join(sorted(theory.attributes, key=len, reverse=True)) or "(?!)"
        verbs = "|".join(sorted(theory.verbs, key=len, reverse=True)) or "(?!)"
        ent = r"(?:the\s+)?(?:" + ("|".join(re.escape(e) for e in ents) if ents else "(?!)") + r"|it|they|he|she|them|him|her|something|someone)"
        self.is_re = re.compile(rf"\b(?P<s>{ent})\s+(?:is|are|was|were)\s+(?:also\s+)?(?P<neg>not\s+)?(?:also\s+)?(?P<a>{attrs})\b", re.I)
        self.rel_re = re.compile(rf"\b(?P<s>{ent})\s+(?:(?P<neg>does not|do not|did not)\s+)?(?P<v>(?:{verbs})(?:e?s)?)\s+(?P<o>{ent})\b", re.I)
        self.attrs, self.verbs = attrs, verbs

    def _entity(self, raw: str, last: Optional[str]) -> Optional[str]:
        low = raw.lower().strip()
        if low in _PRONOUNS:
            return last
        if low in ("something", "someone"):
            return VAR
        e = re.sub(r"^the\s+", "", raw.strip(), flags=re.I)
        for cand in self.th.entities:
            if cand.lower() == e.lower():
                return cand
        return None

    def atoms(self, text: str, last: Optional[str] = None) -> tuple:
        """(literals in order of appearance, entity a following pronoun refers to).

        Parsed conjunct by conjunct, so an elided subject is filled from the previous literal:
        "Fiona is green and young" -> Fiona is green, Fiona is young;
        "the squirrel does not like the lion and does not chase the lion" -> two literals.
        """
        atoms, subj = [], None
        for piece in re.split(r"\s*,\s*(?:and\s+|but\s+)?|\s+(?:and|but)\s+", text):
            piece = piece.strip()
            if not piece:
                continue
            found = self._atoms_in(piece, subj or last)
            if not found and (subj or last):
                found = self._atoms_in(f"{subj or last} is {piece}", None) or self._atoms_in(f"{subj or last} {piece}", None)
                if found and not re.match(rf"^(?:is\s+|are\s+)?(?:not\s+)?(?:{self.attrs})$|^(?:does not |do not )?(?:{self.verbs})", piece, re.I):
                    found = []  # only fill a subject into a bare attribute or verb phrase
            for a in found:
                if a not in atoms:
                    atoms.append(a)
                subj = a.subj
            if self.ent_re:
                names = [n for n in (self._entity(m.group(1), None) for m in self.ent_re.finditer(piece)) if n and n != VAR]
                if names:
                    last = names[0] if found else names[-1]
        if atoms:
            last = atoms[-1].subj
        return atoms, last

    def _atoms_in(self, text: str, last: Optional[str]) -> list:
        found = []
        for m in self.is_re.finditer(text):
            s = self._entity(m.group("s"), last)
            if s is not None and s != VAR:
                found.append((m.start(), Atom(s, "is", m.group("a").lower(), bool(m.group("neg")))))
        for m in self.rel_re.finditer(text):
            s, o = self._entity(m.group("s"), last), self._entity(m.group("o"), last)
            v = _lemma(m.group("v"))
            if s is not None and o is not None and VAR not in (s, o) and v in self.th.verbs:
                found.append((m.start(), Atom(s, v, o, bool(m.group("neg")))))
        return [a for _, a in sorted(found, key=lambda x: x[0])]

    def rules(self, text: str) -> list:
        """Rules stated in the text: quoted ones, and "if ... then ..." / "X things are Y" clauses."""
        out = []
        for q in _QUOTED.findall(text):
            r = parse_rule(q, self.th.verbs)
            if r is not None:
                out.append(r)
        unquoted = _QUOTED.sub(" ", text)
        for m in _VAR_RULE.finditer(unquoted):
            r = parse_rule(m.group(), self.th.verbs)
            if r is not None:
                out.append(r)
        for m in re.finditer(rf"\b(?:all\s+)?(?:{self.attrs})(?:\s*,\s*(?:{self.attrs}))*\s+"
                             rf"(?:things|people|ones)\s+are\s+(?:not\s+)?(?:{self.attrs})\b", unquoted, re.I):
            r = parse_rule(m.group(), self.th.verbs)
            if r is not None:
                out.append(r)
        return out


_VAR_RULE = re.compile(r"\bif\s+(?:something|someone|somebody)\b.+?(?:\bthen\b|,)\s*(?:it|they|he|she|something|someone|the\s+\w+|[A-Z]\w+)\b[^,.;]*", re.I)


def _without_rules(text: str) -> str:
    s = _QUOTED.sub(" ", text)
    s = _VAR_RULE.sub(" ", s)
    s = re.sub(r"\b(?:all\s+)?[a-z]+(?:\s*,\s*[a-z]+)*\s+(?:things|people|ones)\s+are\s+(?:not\s+)?[a-z]+\b", " ", s, flags=re.I)
    return s


class SymbolicLogicVerifier:
    """Check ProofWriter reasoning steps against the closure of the theory given as step.context."""

    name = "symbolic_logic"

    def __init__(self, check_premises: bool = True, check_rules: bool = True):
        self.check_premises = check_premises
        self.check_rules = check_rules
        self._cache = {}

    def theory(self, context: str) -> Theory:
        if context not in self._cache:
            m = re.search(r"Theory:\s*(.*?)\s*(?:Hypothesis:|Question:|$)", context, re.S)
            self._cache[context] = parse_theory(m.group(1) if m else context)
        return self._cache[context]

    def verify(self, step: StepInput) -> Verdict:
        if has_mask(step.text):
            return unverifiable(self.name, "step still contains masked tokens")
        th = self.theory(step.context)
        if not th.facts and not th.rules:
            return unverifiable(self.name, "no theory found in context")
        reader = _Reader(th)
        checks, last = [], None
        for p in step.premises[-1:]:  # a pronoun at the start of a step may refer to the previous step
            _, last = reader.atoms(clean(p))

        for sent in sentences(step.text):
            if _SKIP.search(sent) or _QUESTION.search(sent):
                continue
            if self.check_rules:
                for r in reader.rules(sent):
                    ok = th.has_rule(r)
                    checks.append(Check("rule", ok, ("cited rule in theory: " if ok else "rule not in theory: ") + _rule_text(r)))
            hedge = _HEDGE.search(sent)
            if hedge:
                # only what follows the hedge is claimed unknowable: "From the fact that Harry is green,
                # we cannot infer anything about his intelligence" says nothing about "Harry is green"
                _, last = reader.atoms(_without_rules(sent[:hedge.start()]), last)
                atoms, last = reader.atoms(_without_rules(sent[hedge.end():]), last)
                for a in atoms:
                    st = th.status(a)
                    checks.append(Check("unknown", st == "unknown", f"claims '{a.text()}' cannot be established, but it is {st}"
                                        if st != "unknown" else f"'{a.text()}' is indeed not provable"))
                continue
            rest = _without_rules(sent)
            split = split_causal(rest)
            if split.cue == "if" and split.premise:
                # "if Fiona is green and young, she is round": a hypothetical, i.e. a rule instance, not a claim
                conds, last = reader.atoms(split.premise, last)
                concl, last = reader.atoms(split.conclusion, last)
                if conds and len(concl) == 1 and self.check_rules:
                    r = Rule(frozenset(conds), concl[0])
                    ok = th.has_rule(r)
                    checks.append(Check("rule", ok, ("applies rule: " if ok else "no such rule: ") + _rule_text(r)))
                continue
            if split.premise and self.check_premises:
                atoms, last = reader.atoms(split.premise, last)
                for a in atoms:
                    st = th.status(a)
                    checks.append(Check("premise", st == "proved", f"premise '{a.text()}' is {st}"))
            atoms, last = reader.atoms(split.conclusion, last)
            for a in atoms:
                st = th.status(a)
                checks.append(Check("conclusion", st == "proved", f"conclusion '{a.text()}' is {st}"))

        if not checks:
            return unverifiable(self.name, "no literal or rule from the theory found in step")
        failed = [c for c in checks if c.passed is False]
        if not failed:
            return Verdict(VALID, 0.0, self.name, checks=checks)
        return Verdict(INVALID, 1.0, self.name, _error_type(failed[0]), checks)


def _error_type(check: Check) -> str:
    if check.name == "conclusion":
        return "contradiction" if check.detail.endswith("disproved") else "unsupported"
    if check.name == "premise":
        return "false_premise" if check.detail.endswith("disproved") else "unsupported_premise"
    if check.name == "rule":
        return "hallucinated_rule"
    return "missed_inference"


def _rule_text(r: Rule) -> str:
    conds = " and ".join(a.text().replace(VAR, "something") for a in sorted(r.conds, key=lambda a: (a.rel, a.obj)))
    return f"if {conds} then {r.concl.text().replace(VAR, 'it')}"
