"""Deterministic arithmetic verifier (Phase 4.1).

Every "=" in a step is read as a claimed equality between the arithmetic expressions touching
it. Both sides are turned into sympy expressions over exact rationals and recomputed, so
"$126/month * 6 months = $702" is caught (126 * 6 = 756) without float noise.

Two checks per step:
  arithmetic  each claimed equality holds (exactly, or to the precision the result is shown at)
  grounding   every operand on a computing side was given in the problem, produced by a premise
              step, produced earlier in the same step, or is a common constant (60 min/h, 100 %)
A failed arithmetic check is a hard error; an ungrounded operand is a soft one (the number may be
an unstated conversion), so it is flagged with a lower score.
"""
import itertools
import re
from dataclasses import dataclass
from typing import Optional

import sympy

from src.verify.base import INVALID, VALID, Check, StepInput, Verdict, has_mask, unverifiable

# ---------------------------------------------------------------- normalisation

_LATEX_TEXT = re.compile(r"\\(?:text|mathrm|textbf|mbox|textit)\s*\{([^{}]*)\}")
_LATEX_FRAC = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_LATEX_BOXED = re.compile(r"\\boxed\s*\{([^{}]*)\}")
_LATEX_SUBS = [
    (re.compile(r"\\(?:times|cdot|ast)"), " * "),
    (re.compile(r"\\div"), " / "),
    (re.compile(r"\\(?:left|right)"), ""),
    (re.compile(r"\\[()\[\]]"), " "),
    (re.compile(r"\\([$%,])"), r"\1"),
    (re.compile(r"\\[a-zA-Z]+"), " "),
    (re.compile(r"[{}]"), " "),
]
_UNICODE = str.maketrans({"×": "*", "∗": "*", "·": "*", "÷": "/", "−": "-", "–": "-", "—": " "})
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_WORD_PARENS = re.compile(r"\(\s*[A-Za-z][A-Za-z\s'’.-]*\)")  # "5 (Monday)" -> "5"
_GSM8K_CALC = re.compile(r"<<[^<>]*>>")  # GSM8K calculator annotations duplicate the visible maths


def normalize(text: str) -> str:
    s = _GSM8K_CALC.sub("", text)
    if "\\" in s:
        s = _LATEX_TEXT.sub(r" \1 ", s)
        s = _LATEX_BOXED.sub(r"\1", s)
        prev = None
        while prev != s:  # nested fractions
            prev, s = s, _LATEX_FRAC.sub(r"((\1) / (\2))", s)
        for pat, repl in _LATEX_SUBS:
            s = pat.sub(repl, s)
    s = s.translate(_UNICODE)
    s = _THOUSANDS.sub("", s)
    s = s.replace("$", " ")
    s = _WORD_PARENS.sub(" ", s)
    return s


# ---------------------------------------------------------------- tokens

_TOKEN = re.compile(
    r"(?P<num>(?<![\w.])\d+(?:\.\d+)?|(?<![\w.\d])\.\d+)(?P<pct>\s?%)?"
    r"|(?P<op>[+\-*/^])"
    r"|(?P<lp>\()|(?P<rp>\))"
    r"|(?P<eq>(?<![<>!=])=(?![=>]))"
    r"|(?P<word>[A-Za-z](?:[A-Za-z'’-]*[A-Za-z])?)"
    r"|(?P<ws>\s+)"
    r"|(?P<other>.)"
)
_WORD_OPS = {"times": "*", "x": "*", "plus": "+", "minus": "-", "multiplied": "*", "divided": "/"}
_SKIP_AFTER_WORD_OP = {"multiplied": "by", "divided": "by"}
_MAX_UNIT_WORDS = 3
_OPERAND_NEXT = re.compile(r"\s*(?:by\s+)?[\d(.$]")  # "4 times 21", not "84 times a day"
# A number glued to a one-letter variable ("11H", "0.75P", "3x") is algebra, which this verifier does not solve.
_ALGEBRA_VAR = re.compile(r"[A-Za-z](?![A-Za-z])")


@dataclass
class Tok:
    kind: str  # num | op | lp | rp | eq | break
    text: str
    value: Optional[str] = None  # decimal literal for numbers
    percent: bool = False
    has_unit: bool = False


def tokenize(text: str) -> list:
    """Arithmetic tokens; unit words after a number are dropped, other words become breaks."""
    toks, unit_words, pending_by = [], 0, None
    for m in _TOKEN.finditer(text):
        kind = m.lastgroup if m.lastgroup != "pct" else "num"
        prev = toks[-1] if toks else None
        if kind == "ws":
            continue
        if kind == "num":
            if _ALGEBRA_VAR.match(text, m.end()):
                toks.append(Tok("break", m.group()))
                continue
            toks.append(Tok("num", m.group(), value=m.group("num"), percent=bool(m.group("pct"))))
            unit_words = 0
            continue
        if kind == "word":
            w = m.group().lower()
            if pending_by and w == pending_by:
                pending_by = None
                continue
            if w in _WORD_OPS and prev is not None and prev.kind in ("num", "rp") and _OPERAND_NEXT.match(text, m.end()):
                toks.append(Tok("op", _WORD_OPS[w]))
                pending_by = _SKIP_AFTER_WORD_OP.get(w)
                continue
            if w == "of" and prev is not None and (prev.percent or _ends_with_fraction(toks)) and _OPERAND_NEXT.match(text, m.end()):
                toks.append(Tok("op", "*"))  # "25% of 80", "3/4 of 20"
                continue
            if prev is not None and prev.kind == "op" and prev.text == "/" and len(toks) >= 2 and toks[-2].kind in ("num", "rp"):
                toks.pop()  # "$10/hour": the slash belongs to the unit
                toks[-1].has_unit = True
                unit_words = 1
                continue
            if prev is not None and prev.kind in ("num", "rp") and unit_words < _MAX_UNIT_WORDS:
                unit_words += 1
                prev.has_unit = True
                continue
            toks.append(Tok("break", m.group()))
            continue
        pending_by = None
        if kind == "op":
            toks.append(Tok("op", m.group()))
        elif kind in ("lp", "rp", "eq"):
            toks.append(Tok(kind, m.group()))
        else:
            toks.append(Tok("break", m.group()))
        unit_words = 0
    return toks


def _ends_with_fraction(toks) -> bool:
    return len(toks) >= 3 and toks[-1].kind == "num" and toks[-2].kind == "op" and toks[-2].text == "/" and toks[-3].kind == "num"


def well_formed(toks) -> bool:
    expect_operand, depth = True, 0
    for t in toks:
        if expect_operand:
            if t.kind == "lp":
                depth += 1
            elif t.kind == "num":
                expect_operand = False
            else:
                return False
        else:
            if t.kind == "op" and t.text in "+-*/":
                expect_operand = True
            elif t.kind == "rp" and depth > 0:
                depth -= 1
            else:
                return False
    return not expect_operand and depth == 0


def has_operator(toks) -> bool:
    return any(t.kind == "op" for t in toks)


# ---------------------------------------------------------------- sympy evaluation

_R = sympy.Rational


def to_sympy(toks, pct_readings: tuple) -> sympy.Expr:
    """sympy expression of a well-formed token run; the i-th percent reads as x/100 if pct_readings[i]."""
    parts, k = [], 0
    for t in toks:
        if t.kind == "num":
            v = f"R('{t.value}')"
            if t.percent:
                if pct_readings[k]:
                    v = f"({v}/100)"
                k += 1
            parts.append(v)
        elif t.kind == "op":
            parts.append(t.text)
        else:
            parts.append(t.text)
    return sympy.parse_expr(" ".join(parts), local_dict={"R": _R}, evaluate=True)


def readings(toks):
    """All values of an expression, one per reading of its percentages (x% as x/100 or as x)."""
    n = sum(t.percent for t in toks)
    out = []
    for combo in itertools.product((True, False), repeat=min(n, 3)):
        combo = combo + (True,) * (n - len(combo))
        try:
            v = to_sympy(toks, combo)
        except (SyntaxError, TypeError, ZeroDivisionError, sympy.SympifyError):
            continue
        if v.is_finite and v.is_real:
            out.append(v)
    return out


def shown_decimals(toks) -> int:
    if len(toks) == 1 and toks[0].kind == "num" and "." in toks[0].value:
        return len(toks[0].value.split(".")[1])
    return 0


def equal_as_shown(a: sympy.Expr, b: sympy.Expr, decimals: int) -> bool:
    if a == b:
        return True
    if decimals:  # "10 / 3 = 3.33": the result is rounded to the precision it is written at
        return abs(a - b) <= _R(1, 2) * _R(10) ** -decimals + _R(1, 10**9)
    return False


# ---------------------------------------------------------------- equations in a step

@dataclass
class ClaimedEquality:
    lhs: list
    rhs: list
    raw: str
    continues: bool = False  # lhs is the previous equality's rhs ("a = b = c")

    def describe(self) -> str:
        return f"{_render(self.lhs)} = {_render(self.rhs)}"


def _render(toks) -> str:
    out = []
    for t in toks:
        out.append(t.value + ("%" if t.percent else "") if t.kind == "num" else t.text)
    return " ".join(out).replace("( ", "(").replace(" )", ")")


def _edge_expression(toks, from_end: bool) -> list:
    """Longest well-formed expression touching the '=' side of a token run."""
    run = []
    for t in (reversed(toks) if from_end else toks):
        if t.kind == "break":
            break
        run.append(t)
    if from_end:
        run.reverse()
    for size in range(len(run), 0, -1):
        cand = run[len(run) - size:] if from_end else run[:size]
        if well_formed(cand):
            beyond = (run[len(run) - size - 1] if from_end else run[size]) if size < len(run) else None
            if beyond is not None and beyond.kind == "op":
                return []  # cut out of a larger (unparseable) expression, so not what "=" refers to
            return cand
    return []


def claimed_equalities(text: str) -> list:
    toks = tokenize(normalize(text.replace("**", " ")))
    sides, cur = [], []
    for t in toks:
        if t.kind == "eq":
            sides.append(cur)
            cur = []
        else:
            cur.append(t)
    sides.append(cur)

    out, last_i = [], None
    for i in range(len(sides) - 1):
        lhs = _edge_expression(sides[i], from_end=True)
        rhs = _edge_expression(sides[i + 1], from_end=False)
        if not lhs or not rhs:
            continue
        if not has_operator(lhs) and not has_operator(rhs):
            continue  # "20 years = 50000": a correspondence, nothing to compute
        if len(lhs) == 1 and lhs[0].has_unit and has_operator(rhs):
            continue  # "8 glasses = 8 * 5 = 40": a quantity used as a label
        out.append(ClaimedEquality(lhs, rhs, f"{_render(lhs)} = {_render(rhs)}", continues=last_i == i - 1))
        last_i = i
    return out


def check_equality(eq: ClaimedEquality) -> Optional[bool]:
    """True/False if the equality holds under some reading of its percentages, None if uncheckable."""
    lv, rv = readings(eq.lhs), readings(eq.rhs)
    if not lv or not rv:
        return None
    d = max(shown_decimals(eq.rhs), shown_decimals(eq.lhs))
    return any(equal_as_shown(a, b, d) for a in lv for b in rv)


# ---------------------------------------------------------------- grounding

_WORD_VALUES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "hundred": 100, "thousand": 1000, "dozen": 12, "twice": 2, "double": 2, "triple": 3,
    "thrice": 3, "half": _R(1, 2), "halves": 2, "quarter": _R(1, 4), "third": 3, "fourth": 4, "week": 7,
    "weekly": 7, "hour": 60, "minute": 60, "year": 12, "month": 30, "day": 24, "percent": 100,
    "nickel": _R(1, 20), "dime": _R(1, 10), "penny": _R(1, 100), "pennies": _R(1, 100), "cent": _R(1, 100),
}
# Conversions a solution may use without the problem stating them.
DEFAULT_CONSTANTS = (1, 2, 3, 4, 7, 10, 12, 24, 28, 30, 31, 52, 60, 100, 365, 1000, _R(1, 2), _R(1, 4))


def numbers_in(text: str) -> set:
    vals = set()
    s = normalize(text)
    for t in tokenize(s):
        if t.kind == "num":
            v = _R(t.value)
            vals.add(v)
            if t.percent:
                vals.add(v / 100)
    return vals | word_values(s)


def word_values(text: str) -> set:
    """Quantities named in words: "twice", "a dozen", "quarters", "a minute and a half"."""
    vals = set()
    for m in re.finditer(r"[A-Za-z]+", text):
        w = m.group().lower()
        w = w if w in _WORD_VALUES else w[:-1] if w.endswith("s") else w
        if w in _WORD_VALUES:
            vals.add(_R(_WORD_VALUES[w]))
    if re.search(r"\band a half\b", text, re.I):
        vals.update({_R(3, 2), _R(1, 2)})
    return vals


def values_known_from(texts: list) -> set:
    """Numbers stated in the given texts plus every result their equalities compute."""
    vals = set()
    for text in texts:
        vals |= numbers_in(text)
        for eq in claimed_equalities(text):
            for side in (eq.lhs, eq.rhs):
                vals.update(readings(side))
    return vals


def _grounded(v, known: set) -> bool:
    return any(v == k or v == k * 100 or v * 100 == k for k in known)


# ---------------------------------------------------------------- verifier

class ArithmeticVerifier:
    """Recompute every claimed equality with sympy; flag wrong ones and ungrounded operands."""

    name = "arithmetic"

    def __init__(self, check_grounding: bool = True, grounding_score: float = 0.6, constants=DEFAULT_CONSTANTS):
        self.check_grounding = check_grounding
        self.grounding_score = grounding_score
        self.constants = {_R(c) for c in constants}

    def verify(self, step: StepInput) -> Verdict:
        if has_mask(step.text):
            return unverifiable(self.name, "step still contains masked tokens")
        eqs = claimed_equalities(step.text)
        if not eqs:
            return unverifiable(self.name, "no arithmetic equality in step")

        checks = []
        for eq in eqs:
            ok = check_equality(eq)
            if ok is None:
                checks.append(Check("arithmetic", None, f"could not evaluate {eq.raw}"))
                continue
            lv = readings(eq.lhs)
            detail = eq.raw if ok else f"{eq.raw} but {_render(eq.lhs)} = {_fmt(lv[0])}"
            checks.append(Check("arithmetic", ok, detail))

        if self.check_grounding:
            # the step's own words count too ("one-quarter of the 500 pieces ... 500 * .25")
            known = values_known_from([step.context] + list(step.premises)) | self.constants | word_values(step.text)
            for side in _chain_heads(eqs):
                for t in side:
                    if t.kind != "num":
                        continue
                    v = _R(t.value)
                    if not any(_grounded(x, known) for x in ((v, v / 100) if t.percent else (v,))):
                        checks.append(Check("grounding", False, f"operand {t.value} not given in problem or premises"))
                for eq in eqs:  # results computed in this step can feed its later calculations
                    known |= set(readings(eq.lhs)) | set(readings(eq.rhs))

        if any(c.name == "arithmetic" and c.passed is False for c in checks):
            return Verdict(INVALID, 1.0, self.name, "arithmetic", checks)
        if not any(c.name == "arithmetic" and c.passed for c in checks):
            return unverifiable(self.name, "; ".join(c.detail for c in checks))
        if any(c.name == "grounding" and c.passed is False for c in checks):
            return Verdict(INVALID, self.grounding_score, self.name, "ungrounded_operand", checks)
        return Verdict(VALID, 0.0, self.name, checks=checks)


def _chain_heads(eqs) -> list:
    """The side of each "a = b = c" chain that does the computing from given values; the later
    sides are rewrites whose numbers are intermediates ("5 + 2/5 * 5 = 5 + 2 = 7")."""
    heads, done = [], False
    for eq in eqs:
        if not eq.continues:
            done = False
        if done:
            continue
        for side in (eq.lhs, eq.rhs):
            if has_operator(side):
                heads.append(side)
                done = True
                break
    return heads


def _fmt(v) -> str:
    v = sympy.nsimplify(v)
    return str(v) if v.is_Integer else f"{float(v):g}"
