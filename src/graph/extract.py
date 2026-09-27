import re
from dataclasses import dataclass
from typing import Optional

from src.graph.schema import Equation

# Negative numbers are deliberately not parsed: "16 - 3" must read as 16 and 3, not 16 and -3.
# Clock times ("5:00 PM") are not numbers: digits touching a ":" are skipped.
_NUMBER = r"(?<![\w.:])\$?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?!:\d)(\s?%)?"
NUMBER_RE = re.compile(_NUMBER)

_TOKEN_RE = re.compile(
    rf"(?P<num>{_NUMBER})"
    r"|(?P<op>[+\-*/×÷]|\b(?:x|times|of)\b(?=\s*[$(\d]))"
    r"|(?P<lp>\()|(?P<rp>\))"
    r"|(?P<word>[A-Za-z](?:[A-Za-z'-]*[A-Za-z])?)"
    r"|(?P<ws>\s+)"
    r"|(?P<other>.)"
)
_OP_SYMBOL = {"+": "+", "-": "-", "*": "*", "×": "*", "x": "*", "times": "*", "of": "*", "/": "/", "÷": "/"}
_MAX_UNIT_WORDS = 3

WORD_NUMBERS = {
    "one": [1], "two": [2], "three": [3], "four": [4], "five": [5], "six": [6],
    "seven": [7], "eight": [8], "nine": [9], "ten": [10], "eleven": [11], "twelve": [12],
    "twenty": [20], "thirty": [30], "fifty": [50], "hundred": [100], "dozen": [12],
    "twice": [2], "double": [2], "triple": [3], "thrice": [3],
    "half": [0.5, 2], "quarter": [0.25, 4],
}
WORD_NUMBER_RE = re.compile(r"\b(" + "|".join(WORD_NUMBERS) + r")\b", re.I)


_LATEX_SUBS = [
    (re.compile(r"\\(?:text|mathrm|textbf)\{([^{}]*)\}"), r" \1 "),
    (re.compile(r"\\boxed\{([^{}]*)\}"), r"\1"),
    (re.compile(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}"), r"\1 / \2"),
    (re.compile(r"\\(?:times|cdot)"), "×"),
    (re.compile(r"\\div"), "÷"),
    (re.compile(r"\\left|\\right"), ""),
    (re.compile(r"\\[()\[\]]"), " "),
    (re.compile(r"\\([$%,])"), r"\1"),
    (re.compile(r"[{}]"), ""),
]


def normalize_math(text: str) -> str:
    """Rewrite LaTeX maths (`9 \\times 2`, `\\frac{2}{2}`, `3 \\text{ eggs}`) as plain text for parsing."""
    if "\\" not in text:
        return text
    for pattern, repl in _LATEX_SUBS:
        text = pattern.sub(repl, text)
    return re.sub(r"[ \t]+", " ", text).strip()


@dataclass
class NumberMention:
    value: float
    start: int
    end: int
    percent: bool = False
    unit: Optional[tuple] = None  # (head noun, container noun) after the number, e.g. ("pant", "pair")

    def candidates(self) -> list:
        return [self.value, self.value / 100] if self.percent else [self.value]


def find_numbers(text: str, start: int = 0, end: Optional[int] = None) -> list:
    end = len(text) if end is None else end
    out = []
    for m in NUMBER_RE.finditer(text, start, end):
        value = float(m.group(1).replace(",", "") + (m.group(2) or ""))
        out.append(NumberMention(value, m.start(), m.end(), bool(m.group(3))))
    return out


def find_word_numbers(text: str) -> list:
    out = []
    for m in WORD_NUMBER_RE.finditer(text):
        for v in WORD_NUMBERS[m.group(1).lower()]:
            out.append(NumberMention(float(v), m.start(), m.end()))
    return out


def values_match(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))


@dataclass
class _Tok:
    kind: str  # "num" | "op" | "lp" | "rp" | "break"
    start: int
    end: int
    mention: Optional[NumberMention] = None
    op: str = ""
    has_unit: bool = False


# A number glued to a single capital letter or x/y/n ("0.75P", "2S", "3x") is an algebra coefficient.
_VARIABLE_AFTER_NUMBER_RE = re.compile(r"[A-Z]\b|[xyn]\b")


def _tokens(text: str, start: int, end: int) -> list:
    """Arithmetic tokens of text[start:end]; unit words after a number ("200 GB", "$10/hour") are dropped,
    any other word or punctuation becomes a "break" that ends an expression."""
    toks, unit_words = [], 0
    for m in _TOKEN_RE.finditer(text, start, end):
        kind = m.lastgroup
        if kind == "ws":
            continue
        prev = toks[-1] if toks else None
        if kind == "num":
            if _VARIABLE_AFTER_NUMBER_RE.match(text, m.end(), end):
                toks.append(_Tok("break", m.start(), m.end()))
                continue
            v = float(m.group(2).replace(",", "") + (m.group(3) or ""))
            toks.append(_Tok("num", m.start(), m.end(), NumberMention(v, m.start(), m.end(), bool(m.group(4)))))
            unit_words = 0
        elif kind == "op":
            word_op = m.group() in ("x", "times", "of")
            if m.group() == "of" and not (prev and prev.kind == "num" and (prev.mention.percent or _is_fraction_end(toks))):
                toks.append(_Tok("break", m.start(), m.end()))
            elif word_op and not (prev and prev.kind in ("num", "rp")):
                toks.append(_Tok("break", m.start(), m.end()))
            else:
                toks.append(_Tok("op", m.start(), m.end(), op=m.group()))
        elif kind == "lp":
            toks.append(_Tok("lp", m.start(), m.end()))
        elif kind == "rp":
            toks.append(_Tok("rp", m.start(), m.end()))
        elif kind == "word":
            if prev and prev.kind == "op" and prev.op == "/" and len(toks) >= 2 and toks[-2].kind == "num":
                toks.pop()  # "$10/hour": the "/" belongs to the unit
                unit_words = 1
            elif prev and prev.kind == "num" and unit_words < _MAX_UNIT_WORDS:
                unit_words += 1
                prev.has_unit = True
            else:
                toks.append(_Tok("break", m.start(), m.end()))
        else:
            toks.append(_Tok("break", m.start(), m.end()))
        if kind != "word":
            unit_words = 0 if kind != "num" else unit_words
    return toks


def _is_small_fraction(toks, i) -> bool:
    """toks[i:i+3] is a fraction like "1/2" or "3 / 4" (integers, numerator < denominator <= 12)."""
    if i + 2 >= len(toks) or toks[i].kind != "num" or toks[i + 2].kind != "num":
        return False
    if toks[i + 1].kind != "op" or _OP_SYMBOL[toks[i + 1].op] != "/":
        return False
    a, b = toks[i].mention, toks[i + 2].mention
    return (not a.percent and not b.percent and float(a.value).is_integer() and float(b.value).is_integer()
            and 0 < a.value < b.value <= 12)


def _is_fraction_end(toks) -> bool:
    return len(toks) >= 3 and toks[-2].kind == "op" and toks[-2].op in ("/", "÷") and toks[-3].kind == "num"


def _expr_string(toks, pct_as_fraction: bool = True) -> str:
    """Python expression for the tokens; small fractions are bracketed so "9 ÷ 1/2" means 9 ÷ (1/2)."""
    parts, i = [], 0
    while i < len(toks):
        if _is_small_fraction(toks, i):
            parts.append(f"({toks[i].mention.value!r} / {toks[i + 2].mention.value!r})")
            i += 3
            continue
        t = toks[i]
        i += 1
        if t.kind == "num":
            v = t.mention.value
            parts.append(f"({v!r}/100)" if t.mention.percent and pct_as_fraction else repr(v))
        elif t.kind == "op":
            parts.append(_OP_SYMBOL[t.op])
        else:
            parts.append("(" if t.kind == "lp" else ")")
    return " ".join(parts)


def _well_formed(toks) -> bool:
    """Numbers and operators alternate (no unary signs, no "x" as a variable), brackets balance."""
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
            if t.kind == "op":
                expect_operand = True
            elif t.kind == "rp" and depth > 0:
                depth -= 1
            else:
                return False
    return not expect_operand and depth == 0


def _evaluate(toks, pct_as_fraction: bool = True) -> Optional[float]:
    if not toks or not _well_formed(toks):
        return None
    try:
        return float(eval(_expr_string(toks, pct_as_fraction), {"__builtins__": {}}))
    except (SyntaxError, ZeroDivisionError, TypeError):
        return None


def _expression_at(toks, from_end: bool) -> list:
    """The longest valid arithmetic expression touching one edge of the token run (the edge next to "=")."""
    run = []
    for t in (reversed(toks) if from_end else toks):
        if t.kind == "break":
            break
        run.append(t)
    if from_end:
        run.reverse()
    for size in range(len(run), 0, -1):
        cand = run[len(run) - size:] if from_end else run[:size]
        if _evaluate(cand) is not None:
            # An operator just beyond the expression means it was cut out of a larger one
            # (e.g. the "1 + 1" in "(1/3)x - 1 + 1"), so it's not what the "=" refers to.
            beyond = None
            if size < len(run):
                beyond = run[len(run) - size - 1] if from_end else run[size]
            return [] if beyond is not None and beyond.kind == "op" else cand
    return []


def _describe(toks) -> str:
    """Canonical text of an expression, keeping % so either reading of a percentage can be checked."""
    parts = []
    for t in toks:
        if t.kind == "num":
            parts.append(f"{t.mention.value:g}" + ("%" if t.mention.percent else ""))
        elif t.kind == "op":
            parts.append(_OP_SYMBOL[t.op])
        else:
            parts.append("(" if t.kind == "lp" else ")")
    return " ".join(parts).replace("( ", "(").replace(" )", ")")


def parse_equations(text: str):
    """Parse every "=" in one step as a claimed equality between the expressions on either side.

    A chain `a = b = c` gives two equations (a = b, b = c), so a wrong rewrite in the middle of a
    chain is checkable. Returns (equations, results, warnings); results are (mention, is_assignment)
    pairs for right-hand sides that are a single number. An assignment (`Total hours = 45`) has no
    arithmetic on its left. Word-only formulas (`Profit = Selling price - Total cost`) are skipped.
    """
    eq_positions = [m.start() for m in re.finditer(r"(?<![<>!=])=(?![=>])", text)]
    bounds = [0] + [p + 1 for p in eq_positions] + [len(text)]
    segments = [_tokens(text, bounds[i], (eq_positions + [len(text)])[i]) for i in range(len(eq_positions) + 1)]

    equations, results, warnings = [], [], []
    for i, eq_pos in enumerate(eq_positions):
        lhs = _expression_at(segments[i], from_end=True)
        rhs = _expression_at(segments[i + 1], from_end=False)
        is_last = i == len(eq_positions) - 1
        if len(lhs) == 1 and lhs[0].has_unit and any(t.kind == "op" for t in rhs):
            lhs = []  # "8 glasses = 8 × $5": a quantity used as a label for a calculation, not an equality
        if not lhs and not rhs:
            continue
        if not rhs:
            if is_last:
                warnings.append(f"equation without numeric result: {text[bounds[i]:].strip()!r}")
                equations.append(Equation(raw=text[lhs[0].start:eq_pos + 1].strip(),
                                          operands=[t.mention.value for t in lhs if t.kind == "num"],
                                          operators=[t.op for t in lhs if t.kind == "op"],
                                          result=None, lhs=_describe(lhs), rhs=""))
            continue
        single = rhs[0].mention if len(rhs) == 1 and rhs[0].kind == "num" else None
        if single is not None:
            results.append((single, not lhs))
        equations.append(Equation(
            raw=text[(lhs[0].start if lhs else bounds[i]):rhs[-1].end].strip(),
            operands=[t.mention.value for t in lhs if t.kind == "num"],
            operators=[t.op for t in lhs if t.kind == "op"],
            result=single.value if single else None,
            lhs=_describe(lhs),
            rhs=_describe(rhs),
        ))
    return equations, results, warnings


_PERCENT_CHANGE_RE = re.compile(r"[+-] \(?[\d.]+%")
_HAS_OPERATOR_RE = re.compile(r" [-+*/] ")


def evaluate_expression(expr: str, replace=None, pct_as_fraction: bool = True) -> Optional[float]:
    """Value of a canonical expression (Equation.lhs/rhs); `replace(value) -> value` can substitute numbers."""
    toks = _tokens(expr, 0, len(expr))
    if replace is not None:
        for t in toks:
            if t.kind == "num":
                t.mention = NumberMention(replace(t.mention.value), t.start, t.end, t.mention.percent)
    return _evaluate(toks, pct_as_fraction)


def _decimals(expr: str) -> int:
    """Decimal places shown in a single-number expression like "3.33" (0 for anything else)."""
    m = re.fullmatch(r"\d+\.(\d+)%?", expr.strip())
    return len(m.group(1)) if m else 0


def equation_holds(eq: Equation) -> Optional[bool]:
    """Whether the step's arithmetic is right; None if it can't be checked (no expression on one side).

    A percentage may be read as a fraction or as a plain number ("40% × 200 = 80", "(12/20) × 100 = 60%").
    A stated result may be rounded to the decimals it shows ("10/3 = 3.33"); whole-number results must be exact.
    """
    if not eq.lhs or not eq.rhs:
        return None
    if not _HAS_OPERATOR_RE.search(eq.lhs) and not _HAS_OPERATOR_RE.search(eq.rhs):
        return None  # "20 years = $50,000": a correspondence between two numbers, no arithmetic to check
    if _PERCENT_CHANGE_RE.search(eq.lhs) or _PERCENT_CHANGE_RE.search(eq.rhs):
        return None  # "$40 + 50%" means "plus 50% of $40", which plain arithmetic can't express
    lhs_toks = _tokens(eq.lhs, 0, len(eq.lhs))
    rhs_toks = _tokens(eq.rhs, 0, len(eq.rhs))
    d = _decimals(eq.rhs)
    tol = 0.5 * 10 ** -d + 1e-9 if d else None
    checked = False
    for lhs_frac in (True, False):
        for rhs_frac in (True, False):
            lv, rv = _evaluate(lhs_toks, lhs_frac), _evaluate(rhs_toks, rhs_frac)
            if lv is None or rv is None:
                continue
            checked = True
            if (abs(lv - rv) <= tol) if tol else values_match(lv, rv):
                return True
    return False if checked else None
