"""Dependency graph for a ProofWriter answer: the logic counterpart of build_math.

The math graph links steps through the numbers they share; here the "values" are literals
("Fiona is young", "the cat does not chase the tiger") and rules ("if something is red then it
is young"). Text is read with the same machinery as the symbolic verifier (src.verify.logic),
so the graph and the verdicts agree on what a step says.

Every step records what it uses and what it produces:

  fact       "Fiona is red." (a restated or bare claim)       uses and produces its literals
  rule       "Red things are young." / "We know that if ..."  uses and produces its rules
  inference  "Since Fiona is red and all red things are young, Fiona is young."
                 uses the stated reasons and cited rules, produces the conclusion
             "If Fiona is green and young, she is round." (a rule applied to an entity)
                 uses the conditions and the rule, produces the (hypothetical) consequence
  hedge      "We have no information that Fiona is round."    uses and produces the literal whose
                                                               status it asserts
  meta       "To determine whether the hypothesis ...", bullets under a "Hypothesis:" header
                 refers to the hypothesis, produces nothing
  answer     "The answer is: Unknown." / "..., the hypothesis is false."
  claim      a step with nothing the reader recognises

Edges, from strongest to weakest (each edge records its reason and evidence):

  value_flow     a used literal links to the most recent earlier step that produced it, else to
                 the problem node if it is a fact of the theory; failing that, a step that produced
                 the same literal with the opposite polarity (a step about "Bob is not smart"
                 depends on the one that settled "Bob is smart")
  rule_flow      a used rule links to the most recent earlier step that stated it (or a rule it is
                 an instance of), else to the problem node if the theory contains it
  hypothesis     an answer step links to the most recent step that settled or discussed the
                 hypothesis literal and to the previous answer step; references to the hypothesis
                 itself link to the problem node. This is what connects a flagged step to an
                 answer line the verifier cannot judge on its own.
  answer_fallback  an answer step whose reasoning never touches the hypothesis links to the last
                 reasoning step before it, so an error anywhere upstream can still reach the answer
  explicit_ref   "step 3", "from above", "previous"
  shared_entity  fallback for a step with no incoming edge: the closest earlier step that names
                 an entity of the theory in common with it

Edges only point from earlier steps to later ones, so the graph is a DAG.
"""
import re
from typing import Optional

from src.graph.build_math import PREV_REF_RE, STEP_REF_RE
from src.graph.schema import PROBLEM_NODE_ID, DependencyEdge, ReasoningGraph, ReasoningNode
from src.graph.segment import segment_generation
from src.verify.causal import sentences, split_causal
from src.verify.logic import (
    _HEDGE, _QUESTION, _QUOTED, VAR, Atom, Rule, Theory, _Reader, _rule_text, _without_rules, parse_atom, parse_rule,
    parse_theory,
)

THEORY_RE = re.compile(r"Theory:\s*(.*?)\s*(?:Hypothesis:|Question:|$)", re.S)
HYPOTHESIS_RE = re.compile(r"Hypothesis:\s*(.*?)\s*(?:\n\s*\n|Reasoning:|Answer:|$)", re.S)
# The step states the final label: "The answer is: True", "the hypothesis is false", "... is Unknown."
ANSWER_RE = re.compile(
    r"\bthe answer is\b|\bhypothesis\b[^.]*?\b(?:is|remains|must be|would be)\s+(?:therefore\s+|thus\s+)?"
    r"[\"“]?(?:true|false|unknown)\b|"
    # causal.clean has already turned "can be proved" into "is proved" and "cannot be" into "is not"
    r"\bhypothesis\b[^.]*?\b(?:is(?: not)?|can(?:not| not)?|could(?: not)?)\s+(?:be\s+)?"
    r"(?:proved|proven|disproved|determined)\b", re.I)
# The step talks about the task rather than reasoning: its literals are references, not claims.
META_RE = re.compile(r"^hypothesis\s*:|\b(?:to determine|determine (?:whether|if)|let's|let us|we need to|we will|step by step|"
                     r"analy[sz]e|the hypothesis (?:states|says|is that|claims))\b", re.I)


# Light rewrites so the verifier's reader sees its template forms (graph only; verdicts are unaffected):
# "Bob being white" -> "Bob is white", "(rule)" / "(from fact 3)" annotations dropped, "is indeed kind" -> "is kind".
_ANNOTATION = re.compile(r"\s*\((?:[^()]*\b(?:rule|fact|step|given|theory|premise)s?\b[^()]*)\)", re.I)
_BEING = re.compile(r"\bbeing\b", re.I)
_ADVERB = re.compile(r"\b(?:indeed|actually|definitely|certainly|clearly|necessarily)\s+", re.I)


def _normalize(sent: str) -> str:
    return _ADVERB.sub("", _BEING.sub("is", _ANNOTATION.sub("", sent)))


class _Items:
    """What one step uses and produces: literals and rules, plus flags for hypothesis handling."""

    def __init__(self):
        self.used_atoms, self.produced_atoms = [], []
        self.used_rules, self.produced_rules = [], []
        self.hyp_refs = []  # literals that name the hypothesis rather than claim it
        self.answer = False
        self.mentions_hypothesis = False
        self.kinds = set()

    @staticmethod
    def _add(lst, x):
        if x not in lst:
            lst.append(x)

    def use(self, a):
        self._add(self.used_atoms, a)

    def produce(self, a):
        self._add(self.produced_atoms, a)


def _problem_parts(prompt, warnings: list) -> tuple:
    if isinstance(prompt, list):
        prompt = [m for m in prompt if m["role"] == "user"][-1]["content"]
    theories = THEORY_RE.findall(prompt)
    hyps = HYPOTHESIS_RE.findall(prompt)
    if not theories:
        warnings.append("theory not found in prompt; using the whole prompt")
    theory = theories[-1].strip() if theories else prompt.strip()
    hypothesis = hyps[-1].strip() if hyps else ""
    if not hypothesis:
        warnings.append("hypothesis not found in prompt")
    return theory, hypothesis


def _quoted_atoms(reader: _Reader, sent: str, last: Optional[str]) -> list:
    out = []
    for q in _QUOTED.findall(sent):
        if parse_rule(q, reader.th.verbs) is None:
            atoms, _ = reader.atoms(q, last)
            out.extend(atoms)
    return out


def _read_clause(reader: _Reader, text: str, items: _Items, last: Optional[str], section: str = "") -> Optional[str]:
    """A clause without hedges: a conditional, an inference (reasons -> conclusion) or a bare claim."""
    split = split_causal(text)
    if split.cue == "if" and split.premise:
        conds, last = reader.atoms(split.premise, last)
        concl, last = reader.atoms(split.conclusion, last)
        if conds and len(concl) == 1:
            r = Rule(frozenset(conds), concl[0])
            if "rule" in section or any(r.canonical() == t.canonical() for t in reader.th.rules):
                # "If the cat is not young then the cat is blue." restates a rule of the theory word for
                # word: it states the rule, it does not apply it to anything.
                items._add(items.used_rules, r)
                items._add(items.produced_rules, r)
                items.kinds.add("rule")
                return last
        for a in conds:
            items.use(a)
        for a in concl:
            items.produce(a)
        if conds and len(concl) == 1:
            items._add(items.used_rules, Rule(frozenset(conds), concl[0]))
        if conds or concl:
            items.kinds.add("inference")
        return last
    if split.premise:
        reasons, last = reader.atoms(split.premise, last)
        for a in reasons:
            items.use(a)
    concl, last = reader.atoms(split.conclusion, last)
    for a in concl:
        if not split.premise:
            items.use(a)  # a bare claim restates something established earlier
        items.produce(a)
    if split.premise and (concl or items.used_atoms):
        items.kinds.add("inference")
    elif concl:
        items.kinds.add("fact")
    return last


def _read_step(reader: _Reader, text: str, section: str, last: Optional[str]) -> tuple:
    items = _Items()
    for sent in sentences(text):
        sent = _normalize(sent)
        low = sent.lower()
        if "hypothes" in low:
            items.mentions_hypothesis = True
        is_meta = section == "hypothesis" or META_RE.search(sent) or _QUESTION.search(sent)
        if ANSWER_RE.search(sent) and not is_meta:
            items.answer = True
        rules = reader.rules(sent)
        quoted = _quoted_atoms(reader, sent, last)
        rest = _without_rules(sent)

        if is_meta:
            # "To determine whether the hypothesis "Fiona is young" is True ...": a reference, not a claim
            atoms, last = reader.atoms(rest, last)
            for a in quoted + atoms:
                items._add(items.hyp_refs, a)
            for r in rules:
                items._add(items.used_rules, r)
            items.kinds.add("meta")
            continue

        for a in quoted:
            if "hypothes" in low:  # 'the hypothesis "Fiona is kind" can be proved': names the hypothesis
                items._add(items.hyp_refs, a)
            else:  # a quoted fact cited as a reason: 'since "Bob is big" ...'
                items.use(a)

        atoms_before = len(items.used_atoms) + len(items.produced_atoms)
        hedge = _HEDGE.search(sent)
        if hedge:
            last = _read_clause(reader, _without_rules(sent[:hedge.start()]), items, last, section)
            hedged, last = reader.atoms(_without_rules(sent[hedge.end():]), last)
            for a in hedged:
                items.use(a)
                items.produce(a)
            if hedged:
                items.kinds.add("hedge")
        else:
            last = _read_clause(reader, rest, items, last, section)

        has_atoms = len(items.used_atoms) + len(items.produced_atoms) > atoms_before
        for r in rules:
            items._add(items.used_rules, r)
            if not has_atoms:  # "Red things are young." / "We know that if someone is blue then they are smart."
                items._add(items.produced_rules, r)
        if rules and not has_atoms:
            items.kinds.add("rule")
        if "rule" in items.kinds and not (items.used_atoms or items.produced_atoms):
            items.kinds.discard("inference")
    return items, last


def _kind(items: _Items) -> str:
    if items.answer:
        return "answer"
    for k in ("inference", "hedge", "fact", "rule", "meta"):
        if k in items.kinds:
            return k
    return "claim"


def _rule_matches(used: Rule, provided: Rule, entities: set) -> bool:
    """Equal rules, or one is an instance of the other with its variable bound to an entity."""
    if used.canonical() == provided.canonical():
        return True
    for general, specific in ((provided, used), (used, provided)):
        if not any(c.has_var for c in general.conds) and not general.concl.has_var:
            continue
        for e in entities:
            if (frozenset(c.bind(e) for c in general.conds) == specific.conds
                    and general.concl.bind(e) == specific.concl):
                return True
    return False


def build_logic_graph(record: dict) -> ReasoningGraph:
    """Build a dependency graph for a ProofWriter answer (see the module docstring)."""
    warnings = []
    generation = record["generation"]
    theory_text, hyp_text = _problem_parts(record["prompt"], warnings)
    th: Theory = parse_theory(theory_text)
    if not th.facts and not th.rules:
        warnings.append("theory could not be parsed")
    reader = _Reader(th)
    hypothesis: Optional[Atom] = parse_atom(hyp_text, th.verbs) if hyp_text else None
    if hyp_text and hypothesis is None:
        warnings.append(f"hypothesis not parsed: {hyp_text!r}")

    problem_text = f"Theory: {theory_text}\nHypothesis: {hyp_text}" if hyp_text else f"Theory: {theory_text}"
    nodes = [ReasoningNode(
        node_id=PROBLEM_NODE_ID, text=problem_text, char_start=-1, char_end=-1, kind="problem",
        values_produced=[a.text() for a in sorted(th.facts, key=Atom.text)] + [f"rule: {_rule_text(r)}" for r in th.rules],
    )]
    steps = [None]  # _Items per node; index 0 is the problem
    section, last = "", None
    for idx, seg in enumerate(segment_generation(generation), start=1):
        node = ReasoningNode(node_id=str(idx), text=seg.text, char_start=seg.start, char_end=seg.end,
                             kind="header", list_marker=seg.list_marker)
        items = _Items()
        if seg.is_header:
            section = re.sub(r"[^a-z ]", "", seg.text.lower()).strip()
            section = "hypothesis" if section.startswith("hypothes") else section
        else:
            items, new_last = _read_step(reader, seg.text, section, last)
            if section == "hypothesis":
                # Under a "Hypothesis:" header only restatements of the hypothesis are references; the
                # first line that says anything else ends the section.
                plain, plain_last = _read_step(reader, seg.text, "", last)
                restates = (hypothesis is not None and not plain.answer and not plain.used_rules
                            and all(a.key() == hypothesis.key() for a in plain.produced_atoms + plain.used_atoms))
                if not restates:
                    section, items, new_last = "", plain, plain_last
            last = new_last
            node.kind = _kind(items)
            node.values_used = ([a.text() for a in items.used_atoms]
                                + [f"hypothesis: {a.text()}" if hypothesis is not None and a.key() == hypothesis.key()
                                   else a.text() for a in items.hyp_refs]
                                + [f"rule: {_rule_text(r)}" for r in items.used_rules])
            node.values_produced = ([a.text() for a in items.produced_atoms]
                                    + [f"rule: {_rule_text(r)}" for r in items.produced_rules])
        nodes.append(node)
        steps.append(items)

    if len(nodes) == 1:
        warnings.append("no reasoning steps found in generation")

    edges = {}

    def add_edge(src: int, dst: int, reason: str, evidence: str):
        key = (nodes[src].node_id, nodes[dst].node_id)
        if key in edges:
            if edges[key].reason == reason and evidence and evidence not in edges[key].evidence.split(","):
                edges[key].evidence += f",{evidence}"
            return
        edges[key] = DependencyEdge(key[0], key[1], reason, evidence)

    def atom_provider(a: Atom, j: int) -> Optional[int]:
        for i in range(j - 1, 0, -1):
            if steps[i] is not None and a in steps[i].produced_atoms:
                return i
        if a in th.facts:
            return 0
        for i in range(j - 1, 0, -1):  # same literal, opposite polarity
            if steps[i] is not None and a.negated() in steps[i].produced_atoms:
                return i
        return None

    def rule_provider(r: Rule, j: int) -> Optional[int]:
        for i in range(j - 1, 0, -1):
            if steps[i] is not None and any(_rule_matches(r, p, th.entities) for p in steps[i].produced_rules):
                return i
        if th.has_rule(r) or any(_rule_matches(r, p, th.entities) for p in th.rules):
            return 0
        return None

    def touches_hypothesis(i: int, produced_only: bool) -> bool:
        if hypothesis is None or steps[i] is None:
            return False
        key = hypothesis.key()
        if any(a.key() == key for a in steps[i].produced_atoms):
            return True
        if produced_only:
            return False
        return (steps[i].mentions_hypothesis or steps[i].answer
                or any(a.key() == key for a in steps[i].used_atoms + steps[i].hyp_refs))

    for j in range(1, len(nodes)):
        s = steps[j]
        if nodes[j].kind == "header":
            continue
        for a in s.used_atoms:
            src = atom_provider(a, j)
            if src is not None:
                add_edge(src, j, "value_flow", a.text())
        for a in s.hyp_refs:
            if hypothesis is not None and a.key() == hypothesis.key():
                add_edge(0, j, "hypothesis", f"hypothesis: {hypothesis.text()}")
            else:
                src = atom_provider(a, j)
                if src is not None:
                    add_edge(src, j, "value_flow", a.text())
        for r in s.used_rules:
            src = rule_provider(r, j)
            if src is not None:
                add_edge(src, j, "rule_flow", f"rule: {_rule_text(r)}")
        if s.mentions_hypothesis and not s.answer and hypothesis is not None:
            add_edge(0, j, "hypothesis", f"hypothesis: {hypothesis.text()}")
        if s.answer:
            ev = f"hypothesis: {hypothesis.text()}" if hypothesis is not None else "hypothesis"
            settled = next((i for i in range(j - 1, 0, -1) if touches_hypothesis(i, produced_only=True)), None)
            discussed = next((i for i in range(j - 1, 0, -1) if touches_hypothesis(i, produced_only=False)), None)
            prev_answer = next((i for i in range(j - 1, 0, -1) if steps[i] is not None and steps[i].answer), None)
            linked = False
            for src in (settled, discussed, prev_answer):
                if src is not None:
                    add_edge(src, j, "hypothesis", ev)
                    linked = True
            if not linked:
                # The reasoning never touches the hypothesis, but the answer still follows from it: link
                # the last reasoning step, so an error anywhere in the chain can reach the answer line.
                last_step = next((i for i in range(j - 1, 0, -1) if nodes[i].kind not in ("header", "meta")), None)
                if last_step is not None:
                    add_edge(last_step, j, "answer_fallback", "preceding step")
                else:
                    add_edge(0, j, "hypothesis", ev)

    for j in range(1, len(nodes)):
        if nodes[j].kind == "header":
            continue
        for m in STEP_REF_RE.finditer(nodes[j].text):
            target = int(m.group(1))
            for i in range(j - 1, 0, -1):
                if nodes[i].list_marker == target and nodes[i].kind != "header":
                    add_edge(i, j, "explicit_ref", m.group(0))
                    break
        prev = PREV_REF_RE.search(nodes[j].text)
        if prev:
            for i in range(j - 1, 0, -1):
                if nodes[i].kind != "header":
                    add_edge(i, j, "explicit_ref", prev.group(0))
                    break

    has_incoming = {e.dst for e in edges.values()}

    def entities_in(text: str) -> set:
        if reader.ent_re is None:
            return set()
        return {e for e in (reader._entity(m.group(1), None) for m in reader.ent_re.finditer(text)) if e and e != VAR}

    for j in range(1, len(nodes)):
        if nodes[j].kind == "header" or nodes[j].node_id in has_incoming:
            continue
        ents_j = entities_in(nodes[j].text)
        for i in range(j - 1, 0, -1):
            if nodes[i].kind == "header":
                continue
            shared = ents_j & entities_in(nodes[i].text)
            if shared:
                add_edge(i, j, "shared_entity", sorted(shared)[0])
                break

    return ReasoningGraph(
        example_id=record["example_id"],
        dataset=record.get("dataset", ""),
        nodes=nodes,
        edges=list(edges.values()),
        parse_warnings=warnings,
    )
