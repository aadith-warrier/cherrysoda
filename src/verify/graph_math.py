"""Deterministic arithmetic verifier on the Phase 1 reasoning graphs (src.graph).

Works on what the graph builder already extracted instead of re-reading the text:

  arithmetic  every Equation on a node (lhs/rhs as parsed by src.graph.extract) is recomputed with sympy
              over exact rationals. Tokenising and expression building are the graph code's own
              (_tokens, _expr_string: percentages, "9 ÷ 1/2" bracketing), and the acceptance rules are
              those of equation_holds (either reading of a percentage, results rounded to the decimals
              they show), so sympy_equation_holds is a drop-in, float-free replacement for equation_holds.
  grounding   numbers a calculation uses that no earlier step or the problem provides
              (src.graph.stats.unsourced_values), minus common constants and quantities named in words.
              A soft flag: the number may be an unstated conversion.
  fallback    a claim node whose text still has "number = number" (an equation the builder missed) is
              checked by the text verifier (src.verify.arithmetic.ArithmeticVerifier).

A VALID verdict means the node's arithmetic was independently checked and holds: the stopping condition
for the Phase 5 minimal-subgraph search.
"""
import itertools
import re
from typing import Optional

import sympy

from src.graph.extract import _HAS_OPERATOR_RE, _PERCENT_CHANGE_RE, _decimals, _expr_string, _tokens, _well_formed
from src.graph.schema import Equation, ReasoningGraph
from src.graph.stats import fmt_value, unsourced_values
from src.verify.arithmetic import DEFAULT_CONSTANTS, ArithmeticVerifier, word_values
from src.verify.base import INVALID, UNVERIFIABLE, VALID, Check, StepInput, Verdict

_R = sympy.Rational
_FLOAT_LITERAL = re.compile(r"\d+(?:\.\d+)?(?:e[-+]?\d+)?")
_TEXT_EQUATION = re.compile(r"\d\s*[-+*/×÷x]\s*\(?\s*\d[^=\n]*=\s*\$?\s*\d")


def sympy_value(expr: str, pct_as_fraction: bool = True) -> Optional[sympy.Rational]:
    """Exact value of a canonical graph expression (Equation.lhs / .rhs), or None if it is not arithmetic."""
    toks = _tokens(expr, 0, len(expr))
    if not toks or not _well_formed(toks):
        return None
    code = _FLOAT_LITERAL.sub(lambda m: f"R('{m.group()}')", _expr_string(toks, pct_as_fraction))
    try:
        v = sympy.parse_expr(code, local_dict={"R": _R}, evaluate=True)
    except (SyntaxError, TypeError, ZeroDivisionError, sympy.SympifyError):
        return None
    return v if v.is_finite and v.is_real else None


def sympy_equation_holds(eq: Equation) -> Optional[bool]:
    """equation_holds (src.graph.extract) with exact rational arithmetic: True / False / None (uncheckable)."""
    if not eq.lhs or not eq.rhs:
        return None
    if not _HAS_OPERATOR_RE.search(eq.lhs) and not _HAS_OPERATOR_RE.search(eq.rhs):
        return None
    if _PERCENT_CHANGE_RE.search(eq.lhs) or _PERCENT_CHANGE_RE.search(eq.rhs):
        return None
    d = _decimals(eq.rhs)
    tol = _R(1, 2) * _R(10) ** -d if d else None
    checked = False
    for lhs_frac, rhs_frac in itertools.product((True, False), repeat=2):
        lv, rv = sympy_value(eq.lhs, lhs_frac), sympy_value(eq.rhs, rhs_frac)
        if lv is None or rv is None:
            continue
        checked = True
        if (abs(lv - rv) <= tol) if tol is not None else lv == rv:
            return True
    return False if checked else None


# "2L = 14", "3r + 5r", "P = 48 + 22", "x = 55": equations over unknowns, whose numbers are not operands to source
_ALGEBRA = re.compile(r"\d[A-Za-z]\b|(?:^|[\s(\[])[A-Za-z]\s*=|=\s*[A-Za-z]\s*(?:$|[\s.\])])")


def _computing_operands(equations) -> set:
    """Numbers on the side of each "a = b = c" chain that computes from given values (not rewrites of
    intermediates such as the 7.5 in "2 * (1.5 + 6) = 2 * 7.5 = 15", nor results)."""
    out, prev_rhs = set(), None
    for eq in equations:
        continues = prev_rhs is not None and eq.lhs == prev_rhs
        prev_rhs = eq.rhs
        if continues:
            continue
        side = eq.lhs if _HAS_OPERATOR_RE.search(eq.lhs or "") else eq.rhs if _HAS_OPERATOR_RE.search(eq.rhs or "") else ""
        for t in _tokens(side, 0, len(side)):
            if t.kind == "num":
                v = _R(repr(t.mention.value))
                out.update({v, v / 100} if t.mention.percent else {v})
    return out


def _show(v) -> str:
    return str(v) if v.is_Integer else f"{float(v):g}"


class GraphArithmeticVerifier:
    name = "graph_arithmetic"

    def __init__(self, check_grounding: bool = True, grounding_score: float = 0.6, text_fallback: bool = True,
                 constants=DEFAULT_CONSTANTS):
        self.check_grounding = check_grounding
        self.grounding_score = grounding_score
        self.text_fallback = ArithmeticVerifier(check_grounding=False) if text_fallback else None
        self.constants = {_R(c) for c in constants}

    def verify_graph(self, graph: ReasoningGraph) -> dict:
        """{node_id: Verdict} for every calc / claim node."""
        problem = next((n for n in graph.nodes if n.kind == "problem"), None)
        context_words = word_values(problem.text) if problem is not None else set()
        unsourced = {}
        if self.check_grounding:
            for node_id, v in unsourced_values(graph):
                unsourced.setdefault(node_id, []).append(v)
        parents = {}
        for e in graph.edges:
            parents.setdefault(e.dst, []).append(e.src)
        by_id = {n.node_id: n for n in graph.nodes}

        out = {}
        for n in graph.nodes:
            if n.kind not in ("calc", "claim"):
                continue
            if n.kind == "claim":
                out[n.node_id] = self._claim(n, [by_id[p].text for p in parents.get(n.node_id, []) if p in by_id],
                                             problem.text if problem else "")
                continue
            checks = []
            for eq in n.equations:
                ok = sympy_equation_holds(eq)
                if ok is False:
                    lv = sympy_value(eq.lhs)
                    detail = f"{eq.raw}: {eq.lhs} = {_show(lv)}" if lv is not None else eq.raw
                else:
                    detail = eq.raw
                checks.append(Check("arithmetic", ok, detail))
            allowed = self.constants | context_words | word_values(n.text)
            operands = _computing_operands(n.equations)
            for v in unsourced.get(n.node_id, []) if not _ALGEBRA.search(n.text) else []:
                x = _R(fmt_value(v))
                if x in operands and not any(x == a for a in allowed):
                    checks.append(Check("grounding", False, f"{fmt_value(v)} is not given by the problem or an earlier step"))
            out[n.node_id] = _verdict(self.name, checks, self.grounding_score)
        return out

    def _claim(self, node, parent_texts, context) -> Verdict:
        if self.text_fallback is not None and _TEXT_EQUATION.search(node.text):
            v = self.text_fallback.verify(StepInput(node.text, parent_texts, context, node.node_id))
            if v.status != UNVERIFIABLE:
                v.verifier = f"{self.name}/text_fallback"
                return v
        return Verdict(UNVERIFIABLE, 0.0, self.name)


def _verdict(name, checks, grounding_score) -> Verdict:
    if any(c.name == "arithmetic" and c.passed is False for c in checks):
        return Verdict(INVALID, 1.0, name, "arithmetic", checks)
    if any(c.name == "grounding" for c in checks):
        return Verdict(INVALID, grounding_score, name, "ungrounded_operand", checks)
    if any(c.name == "arithmetic" and c.passed for c in checks):
        return Verdict(VALID, 0.0, name, checks=checks)
    return Verdict(UNVERIFIABLE, 0.0, name, checks=checks)
