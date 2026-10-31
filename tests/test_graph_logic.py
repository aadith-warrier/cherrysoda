"""ProofWriter dependency graphs (src/graph/build_logic.py)."""
import networkx as nx

from src.graph.registry import build_graph
from src.graph.stats import graph_stats, unsourced_values

PROMPT = (
    "Given the following facts and rules, determine whether the hypothesis is True, False, or Unknown.\n\n"
    "Theory: Bob is big. Bob is green. Fiona is green. Fiona is red. Red things are young. "
    "Round, young things are white. Green, young things are round. "
    "If the cat does not like the tiger then the cat is blue.\n"
    "Hypothesis: Fiona is young.\n\nReasoning:\n"
)

FIONA = """To determine whether the hypothesis "Fiona is young" is True, False, or Unknown, let's analyze.

1. **Facts:**
   - Fiona is green.
   - Fiona is red.

2. **Rules:**
   - Red things are young.
   - Green, young things are round.

3. **Inference:**
   - Since Fiona is red and all red things are young, Fiona is young.
   - According to the rule "Green, young things are round," if Fiona is green and young, she must be round.
   - But we have no information that Fiona is round.

4. **Conclusion:**
   - Therefore, we cannot definitively prove that Fiona is young.

Since we cannot prove that Fiona is young, the answer is Unknown.

The answer is: Unknown."""


def graph(generation: str, prompt: str = PROMPT):
    return build_graph({"example_id": "t", "dataset": "proofwriter", "prompt": prompt, "generation": generation})


def by_text(g, prefix: str) -> str:
    return next(n.node_id for n in g.nodes if n.text.startswith(prefix))


def edge(g, src: str, dst: str):
    return next((e for e in g.edges if e.src == src and e.dst == dst), None)


def test_registered_and_acyclic():
    g = graph(FIONA)
    assert g.dataset == "proofwriter" and not g.parse_warnings
    assert nx.is_directed_acyclic_graph(g.to_networkx())
    assert all(int(e.src if e.src != "P" else 0) < int(e.dst) for e in g.edges)


def test_problem_node_keeps_theory_and_hypothesis():
    p = graph(FIONA).nodes[0]
    assert p.kind == "problem" and "Theory:" in p.text and "Hypothesis: Fiona is young." in p.text
    assert "Fiona is red" in p.values_produced
    assert "rule: if something is red then it is young" in p.values_produced


def test_node_kinds():
    g = graph(FIONA)
    kind = {n.text: n.kind for n in g.nodes}
    assert kind["Facts:"] == "header"
    assert kind["Fiona is red."] == "fact"
    assert kind["Red things are young."] == "rule"
    assert kind["Since Fiona is red and all red things are young, Fiona is young."] == "inference"
    assert kind["But we have no information that Fiona is round."] == "hedge"
    assert kind["The answer is: Unknown."] == "answer"
    assert g.node("1").kind == "meta"  # the intro names the hypothesis; it is not an answer


def test_literal_and_rule_flow():
    g = graph(FIONA)
    inf = by_text(g, "Since Fiona is red")
    assert edge(g, by_text(g, "Fiona is red."), inf).reason == "value_flow"
    assert edge(g, by_text(g, "Red things are young."), inf).reason == "rule_flow"
    restated = edge(g, "P", by_text(g, "Fiona is red."))
    assert restated is not None and restated.evidence == "Fiona is red"


def test_rule_instance_links_to_general_rule():
    g = graph(FIONA)
    cond = by_text(g, "According to the rule")
    assert edge(g, by_text(g, "Green, young things are round."), cond).reason == "rule_flow"
    assert edge(g, by_text(g, "Since Fiona is red"), cond) is not None  # "Fiona is young" comes from there


def test_flagged_steps_reach_the_answer():
    g = graph(FIONA)
    G = g.to_networkx()
    hedge_round, hedge_young = by_text(g, "But we have no information"), by_text(g, "Therefore, we cannot")
    answer = by_text(g, "The answer is")
    affected = {hedge_round, hedge_young}.union(*(nx.descendants(G, b) for b in (hedge_round, hedge_young)))
    assert answer in affected and by_text(g, "Since we cannot prove") in affected
    assert by_text(g, "Since Fiona is red") not in affected  # independent reasoning is kept


def test_verbatim_theory_rule_is_a_rule_statement():
    g = graph("If the cat does not like the tiger then the cat is blue.\nThe cat is blue.\nThe answer is: Unknown.")
    rule, fact = g.node("1"), g.node("2")
    assert rule.kind == "rule" and rule.values_produced == ["rule: if the cat does not like the tiger then the cat is blue"]
    e = edge(g, "1", "2")  # restating a rule does not establish its consequent
    assert e is None or e.reason == "shared_entity"


def test_hypothesis_section_is_meta():
    g = graph("Hypothesis:\n- Fiona is young.\nSince Fiona is red, Fiona is young.\nThe answer is: True.")
    assert g.node("2").kind == "meta" and g.node("2").values_produced == []
    assert edge(g, "P", "2").reason == "hypothesis"
    assert edge(g, "3", "4").reason == "hypothesis"  # the step that settled the hypothesis feeds the answer
    assert edge(g, "2", "3") is None


def test_hedge_with_being_and_annotation():
    g = graph("There is no information about Bob being round.\nIf something is red then it is young (rule).\nThe answer is: Unknown.")
    assert g.node("1").kind == "hedge" and "Bob is round" in g.node("1").values_used
    assert g.node("2").kind == "rule"


def test_answer_phrasings():
    g = graph('Fiona is red.\nTherefore, the hypothesis "Fiona is young" can be proved from the facts.')
    assert g.node("2").kind == "answer"


def test_answer_fallback_links_last_step():
    g = graph("Bob is big.\nBob is green.\nThe answer is: False.")  # never mentions Fiona
    e = edge(g, "2", "3")
    assert e is not None and e.reason == "answer_fallback"


def test_answer_without_reasoning_links_problem():
    g = graph("The answer is: True.")
    assert [(e.src, e.reason) for e in g.edges] == [("P", "hypothesis")]


def test_stats_accept_text_values():
    g = graph(FIONA)
    s = graph_stats(g)
    assert s["graph_steps"] == sum(n.kind not in ("problem", "header") for n in g.nodes)
    assert unsourced_values(g) == []


def test_round_trip_dict():
    from src.graph.schema import ReasoningGraph
    g = graph(FIONA)
    g2 = ReasoningGraph.from_dict(g.to_dict())
    assert [(e.src, e.dst, e.reason) for e in g2.edges] == [(e.src, e.dst, e.reason) for e in g.edges]
