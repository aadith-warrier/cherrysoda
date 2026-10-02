"""Split a reasoning sentence into its stated reasons and its conclusion using causal cues.

    "Since Fiona is red and all red things are young, Fiona is young."
        -> premise "Fiona is red and all red things are young", conclusion "Fiona is young"
    "The squirrel is green because it is rough."   -> premise "it is rough", conclusion "The squirrel is green"
    "Bob is big, so Bob is red."                    -> premise "Bob is big", conclusion "Bob is red"
    "If Fiona is green and young, she must be round." -> conditional: premise "Fiona is green and young"
    "Therefore, the squirrel is green."             -> no stated premise; the reasons are the parent steps
"""
import re
from dataclasses import dataclass
from typing import Optional

_MD = re.compile(r"\*\*|__|`")
_LIST_MARKER = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+")
_LEADING_FILLER = re.compile(
    r"^(?:(?:however|also|additionally|furthermore|moreover|now|next|first(?:ly)?|second(?:ly)?|finally|"
    r"and|but|then|step \d+|inference|conclusion|fact|rule)\s*[,:]?\s+)+", re.I)
# "Fact 6:", "From the second fact, we know that", "According to rule 3 (Fact 12),"
_SOURCE_PREFIX = re.compile(
    r"^(?:(?:fact|rule|step|inference|conclusion)\s*\d*\s*[:.)-]\s*|"
    r"(?:from|according to|by|using|applying|based on)\s+(?:the\s+)?(?:\w+\s+)?(?:facts?|rules?|statements?)(?:\s*\d+)?"
    r"(?:\s*\([^)]*\))?\s*,?\s*|"
    r"(?:this|that|the)\s+(?:\w+\s+)?(?:fact|rule|statement)s?\s+(?:tells us|says|states|means|implies|shows)(?:\s+that)?\s+|"
    r"(?:we can|we could|we)\s+(?:also\s+)?(?:infer|conclude|deduce|see|say)\s+that\s+(?=if\b))", re.I)
_KNOW_THAT = re.compile(r"^(?:we (?:also )?(?:know|see|have|find|can see|can infer|can conclude|conclude|infer) that|"
                        r"it is (?:given|stated|known) that|we are (?:told|given) that)\s+", re.I)
_MODAL = re.compile(r"\b(?:must|would|will|should|can|could) (?:also )?be\b", re.I)
_NEG_MODAL = re.compile(r"\b(?:cannot|can not|must not|would not|will not|could not|should not) (?:also )?be\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")

_QUOTE_CHARS = "\"“”"


@dataclass
class CausalSplit:
    premise: Optional[str]  # stated reasons; None when the sentence gives none
    conclusion: str
    cue: str  # "since", "because", "so", "therefore", "if", "none"


def clean(text: str) -> str:
    s = _MD.sub("", text)
    s = _LIST_MARKER.sub("", s).strip()
    s = s.replace("’", "'").replace("can't", "cannot").replace("n't", " not")
    s = _NEG_MODAL.sub("is not", s)
    return _MODAL.sub("is", s)


def sentences(text: str) -> list:
    return [s.strip() for s in _SENTENCE.split(clean(text)) if s.strip()]


def _strip(s: str) -> str:
    s = s.strip().strip(",;:").strip()
    prev = None
    while prev != s:
        prev = s
        s = _LEADING_FILLER.sub("", _SOURCE_PREFIX.sub("", s))
    s = _KNOW_THAT.sub("", s)
    return s.rstrip(".!").strip()


def _last_comma_outside_quotes(s: str) -> int:
    depth, last = False, -1
    for i, ch in enumerate(s):
        if ch in _QUOTE_CHARS:
            depth = not depth
        elif ch == "," and not depth:
            last = i
    return last


_SINCE = re.compile(r"^(?:since|because|as|given that|given)\s+(.+)$", re.I)
_IF = re.compile(r"^if\s+(.+?)(?:,\s*then\s+|\s+then\s+|,\s*)(.+)$", re.I)
_CONSEQ = re.compile(
    r"^(.+?),?\s+(?:so|therefore|thus|hence|which means(?: that)?|this means(?: that)?|implies(?: that)?|"
    r"it follows that|meaning(?: that)?)\s+(.+)$", re.I)
_TRAILING_IF = re.compile(r"^(.+?)\s+(?:only\s+)?if\s+(.+)$", re.I)
_BECAUSE = re.compile(r"^(.+?)\s+(?:because|since)\s+(.+)$", re.I)
_THEREFORE = re.compile(r"^(?:therefore|thus|so|hence|consequently|as a result|this means(?: that)?|"
                        r"which means(?: that)?)\s*,?\s+(.+)$", re.I)
_ACCORDING = re.compile(r"^(?:according to|by|using|applying|from) (?:the )?(?:rule|fact)s?\s*(\"[^\"]*\"|“[^”]*”)?\s*,?\s*(.+)$", re.I)


def split_causal(sentence: str) -> CausalSplit:
    s = _LEADING_FILLER.sub("", clean(sentence).strip())
    cited = ""
    m = _ACCORDING.match(s)
    if m:  # "According to the rule "X", if A then B" -> the quoted rule is an extra premise
        cited = (m.group(1) or "").strip(_QUOTE_CHARS + " ,")
        s = m.group(2)
    s = _strip(s)

    def done(p, c, cue):
        p = _strip(p) if p else None
        if cited:
            p = f"{cited} and {p}" if p else cited
        return CausalSplit(p, _strip(c), cue)

    m = _SINCE.match(s)
    if m:
        body = m.group(1)
        k = _last_comma_outside_quotes(body)
        if k > 0:
            return done(body[:k], re.sub(r"^(?:then|so|therefore|thus)\s+", "", body[k + 1:].strip(), flags=re.I), "since")
    m = _IF.match(s)
    if m:
        return done(m.group(1), m.group(2), "if")
    m = _THEREFORE.match(s)
    if m:
        return done(None, m.group(1), "therefore")
    m = _CONSEQ.match(s)
    if m:
        return done(m.group(1), m.group(2), "so")
    m = _BECAUSE.match(s)
    if m:
        return done(m.group(2), m.group(1), "because")
    m = _TRAILING_IF.match(s)
    if m:  # "Harry is young if he is quiet and big": a conditional, not a claim that Harry is young
        return done(m.group(2), m.group(1), "if")
    return done(None, s, "none")
