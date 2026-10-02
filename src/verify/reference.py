"""Reference (gold) reasoning graphs and labelled verifier test cases built from them.

The verifiers are developed against gold reasoning rather than our own parsed model outputs:

  GSM8K        each solution line is a step; the calculator annotations <<48/2=24>> give the exact
               computation, and a later line that uses 24 depends on it
  SVAMP        the gold equation is a single step
  ProofWriter  each rule application in the gold proof (proofsWithIntermediates) is a step whose
               premises are the facts / earlier conclusions it uses

Each gold step is a VALID case; a perturbed copy of it is an INVALID case with a known error type:

  math   arithmetic     the stated result is wrong                        ("9 * 2 = $19")
         operator_swap  an operator is changed, result kept               ("9 + 2 = $18")
         copy_error     an operand is replaced by a number that appears nowhere earlier, and the
                        result recomputed, so the arithmetic holds but the value is not grounded
  logic  contradiction  the conclusion is negated                         (NLI label: contradiction)
         unsupported    the conclusion is swapped for a statement the theory neither proves nor
                        refutes                                            (NLI label: neutral)
         false_premise  one stated premise is negated                     (NLI label: contradiction)
"""
import json
import random
import re
from dataclasses import dataclass, field

import sympy

from src.graph.build_math import build_math_graph
from src.graph.schema import PROBLEM_NODE_ID, DependencyEdge, ReasoningGraph, ReasoningNode
from src.verify.arithmetic import DEFAULT_CONSTANTS, readings, tokenize, values_known_from
from src.verify.base import StepInput
from src.verify.logic import Atom, parse_atom, parse_theory

NLI_LABEL = {
    "": "entailment", "contradiction": "contradiction", "false_premise": "contradiction",
    "unsupported": "neutral", "arithmetic": "contradiction", "operator_swap": "contradiction", "copy_error": "neutral",
}


@dataclass
class Case:
    case_id: str
    dataset: str
    step: StepInput
    error_type: str = ""  # "" for a gold (valid) step
    meta: dict = field(default_factory=dict)

    @property
    def invalid(self) -> bool:
        return bool(self.error_type)

    @property
    def nli_label(self) -> str:
        return NLI_LABEL[self.error_type]


# ================================================================ maths

_ANN = re.compile(r"<<([^=<>]*)=([^<>]*)>>")
# The visible "15 x 3 = " written before an annotation; "x" / "×" count only as standalone operators.
_VISIBLE_EXPR = re.compile(r"((?:[\d\s.+\-–−*/÷×(),%$]|(?<![^\s])x(?=\s))*?[\d)]\s*)=\s*(\$?)\s*$")


def _pretty(expr: str) -> str:
    s = re.sub(r"\s*([+\-*/])\s*", r" \1 ", expr.strip())
    s = re.sub(r"\(\s+", "(", s)
    return re.sub(r"\s+\)", ")", s).strip()


def _value(expr: str):
    vals = readings(tokenize(expr))
    return vals[0] if vals else None


def _fmt(v) -> str:
    v = sympy.nsimplify(v)
    if v.is_Integer:
        return str(int(v))
    f = float(v)
    return f"{f:.2f}".rstrip("0").rstrip(".") if abs(f * 100 - round(f * 100)) < 1e-9 else None


def render_gsm8k_line(line: str, override: dict = None) -> str:
    """Solution line with calculator annotations turned into visible "expr = result" text.

    `override` replaces (expr, result) of the last annotation, for perturbed copies.
    """
    anns = list(_ANN.finditer(line))
    out, cursor = [], 0
    for k, m in enumerate(anns):
        expr, res = m.group(1), m.group(2)
        before = line[cursor:m.start()]
        after_start = m.end()
        shown = re.match(r"\d[\d,]*(?:\.\d+)?", line[after_start:])
        if line[after_start:].startswith(res):
            after_start += len(res)
        elif shown and shown.group().replace(",", "") == res.replace(",", ""):
            after_start += shown.end()  # the visible copy of the result ("130,000")
        if override and k == len(anns) - 1:
            expr, res = override.get("expr", expr), override.get("result", res)
        vis = _VISIBLE_EXPR.search(before)
        dollar = ""
        if vis:
            dollar = vis.group(2)
            before = before[:vis.start()] + (" " if vis.start() and not before[vis.start() - 1].isspace() else "")
        elif before.endswith("$"):
            before, dollar = before[:-1], "$"
        out.append(f"{before}{_pretty(expr)} = {dollar}{res}")
        cursor = after_start
    out.append(line[cursor:])
    return "".join(out).strip()


def gold_record(example_id: str, question: str, lines: list) -> dict:
    """A generations.jsonl-style record for a gold solution, so the team's graph builder can parse it."""
    return {"example_id": example_id, "dataset": "gsm8k", "prompt": f"Question: {question}\nLet's think step by step\nAnswer:",
            "generation": "\n".join(lines)}


def gsm8k_reference_graph(example_id: str, question: str, solution: str) -> ReasoningGraph:
    """Gold solution parsed by the Phase 1 graph builder (src.graph.build_math)."""
    lines = [render_gsm8k_line(l) for l in solution.split("####")[0].strip().split("\n") if l.strip()]
    return build_math_graph(gold_record(example_id, question, lines))


@dataclass
class GraphCase:
    graph: ReasoningGraph
    target: str = ""  # node id of the injected error ("" for a clean gold graph)
    error_type: str = ""
    gold: ReasoningGraph = None  # the clean graph a perturbed one came from (same node ids)


def _node_at(graph: ReasoningGraph, char_start: int, char_end: int) -> str:
    """Id of the graph node covering a character span of the generation."""
    for n in graph.nodes:
        if n.char_start >= 0 and n.char_start < char_end and n.char_end > char_start:
            return n.node_id
    return ""


def gsm8k_graph_cases(rows: list, seed: int = 0) -> list:
    """For each gold solution: the clean graph, and the graph of a copy with one calculation perturbed
    (the perturbed node is recorded, so detection and localisation can be scored per node)."""
    rng = random.Random(seed)
    constants = {sympy.Rational(c) for c in DEFAULT_CONSTANTS}
    cases = []
    for i, row in enumerate(rows):
        eid = f"gsm8k_{i:05d}"
        raw = [l for l in row["answer"].split("####")[0].strip().split("\n") if l.strip()]
        rendered = [render_gsm8k_line(l) for l in raw]
        gold = build_math_graph(gold_record(eid, row["question"], rendered))
        cases.append(GraphCase(gold))
        candidates = [j for j, l in enumerate(raw) if _ANN.findall(l)]
        rng.shuffle(candidates)
        for j in candidates:
            known = values_known_from([row["question"]] + rendered[:j]) | constants
            perts = _math_perturbations(*_ANN.findall(raw[j])[-1], known, rng)
            if not perts:
                continue
            err = rng.choice(sorted(perts))
            lines = list(rendered)
            lines[j] = render_gsm8k_line(raw[j], perts[err])
            g = build_math_graph(gold_record(f"{eid}_{err}", row["question"], lines))
            start = sum(len(l) + 1 for l in lines[:j])
            cases.append(GraphCase(g, _node_at(g, start, start + len(lines[j])), err, gold))
            break
    return cases


def _wrong_results(r):
    cands = [r + 1, r - 1, r * 10, r + 10, r * 2]
    s = _fmt(r)
    if s and s.isdigit() and len(s) >= 2 and s[-1] != s[-2]:
        cands.append(sympy.Integer(s[:-2] + s[-1] + s[-2]))
    return [c for c in cands if c != r and c >= 0 and _fmt(c)]


_OPS = {"+": "-", "-": "+", "*": "+", "/": "*"}


def _math_perturbations(expr: str, res: str, known: set, rng: random.Random) -> dict:
    """{error_type: override} for one annotated calculation."""
    out = {}
    r = _value(res)
    if r is None or _value(expr) is None:
        return out
    wrong = _wrong_results(r)
    if wrong:
        out["arithmetic"] = {"result": _fmt(rng.choice(wrong))}

    ops = [m for m in re.finditer(r"(?<=[\d)\s])([+\-*/])(?=[\s\d(])", expr)]
    rng.shuffle(ops)
    for m in ops:
        e2 = expr[:m.start()] + _OPS[m.group(1)] + expr[m.end():]
        v2 = _value(e2)
        if v2 is not None and v2 != r:
            out["operator_swap"] = {"expr": e2}
            break

    nums = list(re.finditer(r"\d+(?:\.\d+)?", expr))
    rng.shuffle(nums)
    for m in nums:
        v = sympy.Rational(m.group())
        for delta in rng.sample([1, 2, 3, 5, 7, 11, 13], 7):
            v2 = v + delta
            if any(v2 == k or v2 == k * 100 or v2 * 100 == k for k in known):
                continue
            e2 = expr[:m.start()] + _fmt(v2) + expr[m.end():]
            r2 = _value(e2)
            if r2 is not None and r2 >= 0 and _fmt(r2):
                out["copy_error"] = {"expr": e2, "result": _fmt(r2)}
                break
        if "copy_error" in out:
            break
    return out


def gsm8k_cases(rows: list, max_cases: int = None, seed: int = 0) -> list:
    """rows: dicts with question / answer (the HF openai/gsm8k format)."""
    rng = random.Random(seed)
    cases = []
    constants = {sympy.Rational(c) for c in DEFAULT_CONSTANTS}
    for i, row in enumerate(rows):
        lines = [l for l in row["answer"].split("####")[0].strip().split("\n") if l.strip()]
        rendered = [render_gsm8k_line(l) for l in lines]
        for j, line in enumerate(lines):
            anns = _ANN.findall(line)
            if not anns:
                continue
            step = StepInput(rendered[j], premises=rendered[:j], context=row["question"], step_id=str(j + 1))
            sid = f"gsm8k_{i:05d}_s{j + 1}"
            cases.append(Case(sid, "gsm8k", step))
            known = values_known_from([row["question"]] + rendered[:j]) | constants
            perts = _math_perturbations(*anns[-1], known, rng)
            if perts:
                err = rng.choice(sorted(perts))
                text = render_gsm8k_line(line, perts[err])
                cases.append(Case(f"{sid}_{err}", "gsm8k", StepInput(text, rendered[:j], row["question"], str(j + 1)), err,
                                  {"gold": rendered[j]}))
        if max_cases and len(cases) >= max_cases:
            break
    return cases


def svamp_cases(rows: list, seed: int = 0) -> list:
    rng = random.Random(seed)
    cases = []
    constants = {sympy.Rational(c) for c in DEFAULT_CONSTANTS}
    for i, row in enumerate(rows):
        body = row["Body"].strip()
        question = f"{body}{'' if body.endswith('.') else '.'} {row['Question'].strip()}"
        expr = re.sub(r"(\d+)\.0\b", r"\1", row["Equation"]).strip()
        res = _fmt(sympy.nsimplify(row["Answer"]))
        if res is None or _value(expr) is None:
            continue
        line = f"<<{expr}={res}>>{res}"
        sid = f"svamp_{i:05d}"
        cases.append(Case(sid, "svamp", StepInput(render_gsm8k_line(line), [], question, "1")))
        perts = _math_perturbations(expr, res, values_known_from([question]) | constants, rng)
        if perts:
            err = rng.choice(sorted(perts))
            cases.append(Case(f"{sid}_{err}", "svamp", StepInput(render_gsm8k_line(line, perts[err]), [], question, "1"), err))
    return cases


# ================================================================ ProofWriter

_PROOF_TOKEN = re.compile(r"\(|\)|->|%|[A-Za-z]+\d+")


def parse_proof(representation: str) -> list:
    """Rule applications of a proofsWithIntermediates tree, premises first:
    "((triple2 triple1) -> (rule3 % int1))" -> [(["triple2", "triple1"], "rule3", "int1")]."""
    toks = _PROOF_TOKEN.findall(representation)
    steps = []

    def parse(i):
        assert toks[i] == "("
        i += 1
        items = []
        while toks[i] != ")":
            t = toks[i]
            if t == "(":
                sub, i = parse(i)
                items.extend(sub)
            elif t == "->":
                if toks[i + 1] == "(" and toks[i + 3] == "%":
                    rule, concl = toks[i + 2], toks[i + 4]
                    i += 6
                else:  # a proof without intermediates: "-> rule3"
                    rule, concl = toks[i + 1], None
                    i += 2
                steps.append((list(items), rule, concl))
                items = [concl] if concl else []
            else:
                items.append(t)
                i += 1
        return items, i + 1

    if toks and toks[0] == "(":
        parse(0)
    else:
        return []
    return steps


def _lower_first(s: str, names: set) -> str:
    first = s.split(" ", 1)[0]
    return s if first in names else s[:1].lower() + s[1:]


def _sentence(s: str) -> str:
    s = s.strip().rstrip(".")
    return s[:1].upper() + s[1:]


def _atom_text(a: Atom) -> str:
    return _sentence(a.text())


_TEMPLATES = (
    "Since {facts}, and {rule}, {concl}.",
    "{Facts}. {Rule}. So {concl}.",
    "Because {facts} and {rule}, {concl}.",
    "According to the rule \"{Rule}\", since {facts}, {concl}.",
    "{Concl} because {facts}.",
)


def proofwriter_reference(row: dict, qid: str, template_rng: random.Random):
    """(graph, steps) for one question's first gold proof; steps are (StepInput, detail dict)."""
    q = row["questions"][qid]
    th = parse_theory(row["theory"])
    names = {e for e in th.entities if e[:1].isupper()}
    texts = {k: v["text"] for k, v in row["triples"].items()} | {k: v["text"] for k, v in row["rules"].items()}
    pwi = q.get("proofsWithIntermediates") or []
    if not pwi or not isinstance(pwi[0].get("intermediates"), dict):
        return None
    texts |= {k: v["text"] for k, v in pwi[0]["intermediates"].items()}
    raw_steps = parse_proof(pwi[0]["representation"])
    if not raw_steps or any(c is None for _, _, c in raw_steps):
        return None

    context = f"Theory: {row['theory']}"
    nodes = [ReasoningNode(PROBLEM_NODE_ID, row["theory"], -1, -1, "problem")]
    edges, step_of, steps = [], {}, []
    seen, unique = set(), []
    for st in raw_steps:  # a sub-proof used twice appears twice in the tree
        if st[2] not in seen:
            seen.add(st[2])
            unique.append(st)
    for k, (prems, rule, concl) in enumerate(unique, start=1):
        facts = [texts[p].rstrip(".") for p in prems]
        tpl = template_rng.choice(_TEMPLATES)
        parts = {"facts": " and ".join(_lower_first(f, names) for f in facts), "rule": _lower_first(texts[rule].rstrip("."), names),
                 "concl": _lower_first(texts[concl].rstrip("."), names)}
        detail = {"template": tpl, "parts": parts, "facts": facts, "concl": texts[concl], "names": names}
        text = _fill(tpl, parts)
        nid = str(k)
        nodes.append(ReasoningNode(nid, text, -1, -1, "claim"))
        parents = [step_of[p] for p in prems if p in step_of]
        for p in parents:
            edges.append(DependencyEdge(p, nid, "explicit_ref", ""))
        if any(p.startswith("triple") for p in prems) or not parents:
            edges.append(DependencyEdge(PROBLEM_NODE_ID, nid, "explicit_ref", rule))
        step_of[concl] = nid
        premises = [nodes[int(p)].text for p in parents]
        steps.append((StepInput(text, premises, context, nid), detail))
    graph = ReasoningGraph(f"{row['id']}_{qid}", "proofwriter", nodes, edges)
    return graph, steps, th


def _fill(tpl: str, parts: dict) -> str:
    cap = {k[:1].upper() + k[1:]: _sentence(v) for k, v in parts.items()}
    return tpl.format(**parts, **cap)


def _logic_perturbations(detail: dict, th, rng: random.Random) -> dict:
    """{error_type: new step text}."""
    out, names = {}, detail["names"]
    concl = parse_atom(detail["concl"], th.verbs)
    if concl is None:
        return out

    def with_concl(atom):
        parts = dict(detail["parts"], concl=_lower_first(atom.text(), names))
        return _fill(detail["template"], parts)

    out["contradiction"] = with_concl(concl.negated())
    unknown = [Atom(concl.subj, "is", a, neg) for a in sorted(th.attributes) for neg in (False, True)
               if th.status(Atom(concl.subj, "is", a, neg)) == "unknown"]
    if unknown:
        out["unsupported"] = with_concl(rng.choice(unknown))
    facts = [(i, parse_atom(f, th.verbs)) for i, f in enumerate(detail["facts"])]
    facts = [(i, a) for i, a in facts if a is not None]
    if facts:
        i, a = rng.choice(facts)
        new_facts = list(detail["facts"])
        new_facts[i] = a.negated().text()
        parts = dict(detail["parts"], facts=" and ".join(_lower_first(f, names) for f in new_facts))
        out["false_premise"] = _fill(detail["template"], parts)
    return out


def proofwriter_cases(meta_path: str, max_steps: int = 400, min_depth: int = 1, seed: int = 0) -> tuple:
    """(cases, reference graphs) from a ProofWriter meta-*.jsonl file; one question per theory."""
    rng = random.Random(seed)
    rows = [json.loads(l) for l in open(meta_path) if l.strip()]
    rng.shuffle(rows)
    cases, graphs, n_valid = [], [], 0
    for row in rows:
        qids = [qid for qid, q in row["questions"].items()
                if q.get("strategy") in ("proof", "inv-proof") and (q.get("QDep") or 0) >= min_depth]
        if not qids:
            continue
        ref = proofwriter_reference(row, rng.choice(qids), rng)
        if ref is None:
            continue
        graph, steps, th = ref
        graphs.append(graph)
        for step, detail in steps:
            sid = f"{graph.example_id}_s{step.step_id}"
            cases.append(Case(sid, "proofwriter", step, meta={"template": detail["template"]}))
            n_valid += 1
            perts = _logic_perturbations(detail, th, rng)
            if perts:
                err = rng.choice(sorted(perts))
                cases.append(Case(f"{sid}_{err}", "proofwriter", StepInput(perts[err], step.premises, step.context, step.step_id),
                                  err, {"template": detail["template"], "gold": step.text}))
        if n_valid >= max_steps:
            break
    return cases, graphs
