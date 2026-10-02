import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pytest

from src.graph.schema import DependencyEdge, ReasoningGraph, ReasoningNode
from src.verify.arithmetic import ArithmeticVerifier, claimed_equalities
from src.verify.base import INVALID, UNVERIFIABLE, VALID, CascadeVerifier, StepInput, verify_graph
from src.verify.calibration import binary_metrics, ece, fit_temperature
from src.verify.causal import split_causal
from src.verify.logic import SymbolicLogicVerifier, parse_theory
from src.verify.nli import NLIVerifier, softmax
from src.verify.reference import parse_proof, render_gsm8k_line

# ---------- arithmetic ----------
JANET = "Janet's ducks lay 16 eggs per day. She eats three for breakfast and bakes muffins with four. She sells eggs for $2 each."


@pytest.mark.parametrize("text,status,err", [
    ("Janet sells 16 - 3 - 4 = 9 duck eggs a day.", VALID, ""),
    ("She makes 9 * 2 = $18 every day.", VALID, ""),
    ("She makes 9 * 2 = $19 every day.", INVALID, "arithmetic"),
    ("Total revenue: $360 + $160 = $800.", INVALID, "arithmetic"),                  # real LLaDA error
    ("Allen's age is \\(99 + 10 = 99\\).", INVALID, "arithmetic"),                  # LaTeX
    ("\\text{Aaron} = \\frac{16}{2} + 3 = 8 + 3 = 11", VALID, ""),                 # chain + \frac
    ("\\text{Aaron} = \\frac{16}{2} + 3 = 8 + 3 = 12", INVALID, "arithmetic"),     # wrong last link
    ("10 / 3 = 3.33 hours", VALID, ""),                                             # rounded as shown
    ("10 / 3 = 3.4 hours", INVALID, "arithmetic"),
    ("25% of 16 = 4 eggs", VALID, ""),
    ("She sells 9 * 7 = $63", VALID, ""),                                           # 7 days: a constant
    ("She sells 9 * 13 = $117", INVALID, "ungrounded_operand"),                     # 13 comes from nowhere
    ("She has 16 eggs.", UNVERIFIABLE, ""),
    ("11H = 88,000", UNVERIFIABLE, ""),                                             # algebra
    ("She needs 16 - <|mdm_mask|> = 9 eggs", UNVERIFIABLE, ""),                     # still masked
    ("He was over 16 years old, so 16 + 2 = 18", VALID, ""),                        # "over" is not division
    ("She went 4 times, so 4 + 3 = 7 times a week", VALID, ""),                     # trailing "times"
])
def test_arithmetic(text, status, err):
    v = ArithmeticVerifier().verify(StepInput(text, premises=["Janet sells 16 - 3 - 4 = 9 duck eggs a day."], context=JANET))
    assert (v.status, v.error_type) == (status, err), v.checks


def test_unit_label_is_not_an_equation():
    assert [e.raw for e in claimed_equalities("Total cost for 8 glasses = 8 × 5 = 40 dollars")] == ["8 * 5 = 40"]


def test_render_gsm8k_annotations():
    assert render_gsm8k_line("Janet sells 16 - 3 - 4 = <<16-3-4=9>>9 duck eggs a day.") == "Janet sells 16 - 3 - 4 = 9 duck eggs a day."
    assert render_gsm8k_line("She makes $<<9*2=18>>18 a day.") == "She makes 9 * 2 = $18 a day."
    assert render_gsm8k_line("It came to 80000+50000=$<<80000+50000=130000>>130,000") == "It came to 80000 + 50000 = $130000"
    assert render_gsm8k_line("She needs 15 x 3 = <<15*3=45>>45 eggs.", {"result": "46"}) == "She needs 15 * 3 = 46 eggs."


# ---------- logic ----------
THEORY = ("Theory: Bob is big. Bob is green. Fiona is green. Fiona is red. The squirrel does not like the lion. "
          "Red things are young. Round, young things are white. Green, young things are round. "
          "If something is big and not red then it is kind. If someone likes the lion then they chase the lion.\nHypothesis: Fiona is young.")


def test_closure():
    th = parse_theory(THEORY.split("Theory: ")[1].split("\n")[0])
    assert not th.unparsed
    from src.verify.logic import Atom
    assert th.status(Atom("Fiona", "is", "white")) == "proved"          # red -> young -> round -> white
    assert th.status(Atom("Bob", "is", "kind")) == "unknown"            # open world: "not red" is not provable
    assert th.status(Atom("squirrel", "like", "lion")) == "disproved"


@pytest.mark.parametrize("text,status,err", [
    ("Since Fiona is red and all red things are young, Fiona is young.", VALID, ""),
    ("Since Fiona is red and all red things are young, Fiona is not young.", INVALID, "contradiction"),
    ("Since Bob is red and red things are young, Bob is young.", INVALID, "unsupported_premise"),
    ("Since Fiona is green and green things are young, Fiona is young.", INVALID, "hallucinated_rule"),
    ("Therefore, Bob is white.", INVALID, "unsupported"),
    ("We have no information that Fiona is round.", INVALID, "missed_inference"),
    ("We have no information that Bob is round.", VALID, ""),
    ("According to the rule \"Green, young things are round\", if Fiona is green and young, she must be round.", VALID, ""),
    ("If someone likes the lion then they chase the lion.", VALID, ""),                       # restating a rule
    ("Fact 3: The squirrel does not like the lion.", VALID, ""),
    ("Since the squirrel does not like the lion and does not chase the lion, it cannot be kind.", INVALID, "unsupported_premise"),
    ("We need to determine if Bob is white.", UNVERIFIABLE, ""),
    ("The answer is: True", UNVERIFIABLE, ""),
])
def test_symbolic_logic(text, status, err):
    v = SymbolicLogicVerifier().verify(StepInput(text, context=THEORY))
    assert (v.status, v.error_type) == (status, err), v.checks


def test_causal_split():
    s = split_causal("Since Fiona is red and all red things are young, Fiona is young.")
    assert (s.premise, s.conclusion, s.cue) == ("Fiona is red and all red things are young", "Fiona is young", "since")
    s = split_causal("The squirrel is green because it is rough.")
    assert (s.premise, s.conclusion) == ("it is rough", "The squirrel is green")
    assert split_causal("Therefore, the squirrel cannot be green.").conclusion == "the squirrel is not green"
    assert split_causal("Harry is young if he is quiet.").cue == "if"


def test_parse_proof():
    rep = "((((triple2 triple1) -> (rule3 % int2))) -> (rule5 % int1))"
    assert parse_proof(rep) == [(["triple2", "triple1"], "rule3", "int2"), (["int2"], "rule5", "int1")]


# ---------- NLI (fake backend) ----------
class KeywordNLI:
    """Entailment unless the hypothesis contains "not" (contradiction) or "blue" (neutral)."""

    def __init__(self):
        self.pairs = []

    def logits(self, pairs):
        self.pairs.extend(pairs)
        out = []
        for _, h in pairs:
            out.append([0, 0, 5] if " not " in f" {h} " else [0, 5, 0] if "blue" in h else [5, 0, 0])
        return np.array(out, float)


def test_nli_verifier_pairs_and_verdicts():
    be = KeywordNLI()
    v = NLIVerifier(be, top_k_context=3)
    ok, contra, neutral, skip = v.verify_batch([
        StepInput("Since Fiona is red and all red things are young, Fiona is young.", context=THEORY),
        StepInput("Therefore, Fiona is not young.", premises=["Fiona is red."], context=THEORY),
        StepInput("Fiona is blue.", context=THEORY),
        StepInput("The answer is: True", context=THEORY),
    ])
    assert ok.status == VALID and contra.error_type == "contradiction" and neutral.error_type == "unsupported"
    assert skip.status == UNVERIFIABLE
    assert [c.name for c in ok.checks] == ["grounding", "conditional", "inference"]


def test_nli_modus_ponens_decomposition():
    v = NLIVerifier(KeywordNLI())
    checks = v.checks_for(StepInput("Since Fiona is red and all red things are young, Fiona is young.", context=THEORY))
    assert [(n, h) for n, h, _ in checks] == [("grounding", "Fiona is red"), ("conditional", "all red things are young"),
                                              ("inference", "Fiona is young")]
    grounding = checks[0][2]
    assert "Fiona is red." in grounding[0]  # retrieved from the theory
    inference = checks[2][2]
    assert inference["direct"] == ("Fiona is red.", "Fiona is young")
    rule, consequent, antecedents = inference["rules"][0]
    assert rule == "If Fiona is red then Fiona is young"  # variable bound to the entity
    assert consequent == ("Fiona is young.", "Fiona is young")
    assert [h for _, h in antecedents] == ["Fiona is red"]
    # no rule stated: the most relevant theory rules are tried
    checks = v.checks_for(StepInput("Fiona is young because Fiona is red.", context=THEORY))
    assert "If Fiona is red then Fiona is young" in [r for r, _, _ in checks[-1][2]["rules"]]


def test_cascade_falls_back_to_nli():
    cascade = CascadeVerifier([SymbolicLogicVerifier(), NLIVerifier(KeywordNLI())])
    assert cascade.verify(StepInput("Fiona is young.", context=THEORY)).verifier == "symbolic_logic"
    assert cascade.verify(StepInput("Everything purple sings loudly.", context=THEORY)).verifier == "nli"


# ---------- graph adapter + metrics ----------
def test_verify_graph_uses_parents():
    nodes = [ReasoningNode("P", JANET, -1, -1, "problem"), ReasoningNode("1", "16 - 3 - 4 = 9 eggs", 0, 1, "calc"),
             ReasoningNode("2", "Next:", 0, 1, "header"), ReasoningNode("3", "9 * 2 = $18", 0, 1, "calc")]
    g = ReasoningGraph("x", "gsm8k", nodes, [DependencyEdge("1", "3", "value_flow", "9")])
    out = verify_graph(g, ArithmeticVerifier())
    assert set(out) == {"1", "3"} and all(v.status == VALID for v in out.values())


def test_calibration_helpers():
    m = binary_metrics([1, 1, 0, 0], [1, 0, 1, 0])
    assert m["precision"] == 0.5 and m["recall"] == 0.5 and m["false_positive_rate"] == 0.5
    assert ece([0.9, 0.9], [1, 1])[0] == pytest.approx(0.1)
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, 500)
    logits = rng.normal(size=(500, 3))
    logits[np.arange(500), y] += 2.0
    t = fit_temperature(logits * 4, y)  # overconfident logits need T > 1
    assert t > 1.5
    assert softmax(logits * 4, t).max(1).mean() < softmax(logits * 4).max(1).mean()


# ---------- graph-native arithmetic verifier (on the Phase 1 graphs) ----------
from src.graph.build_math import build_math_graph
from src.graph.extract import equation_holds
from src.verify.graph_math import GraphArithmeticVerifier, sympy_equation_holds

RUN_250 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs/analysis_paper_noblock_250")


def _graph(generation, question="Janet has 16 eggs. She eats 3 and bakes with 4. She sells each egg for $2."):
    return build_math_graph({"example_id": "t", "dataset": "gsm8k", "generation": generation,
                             "prompt": f"Question: {question}\nLet's think step by step\nAnswer:"})


@pytest.mark.skipif(not os.path.exists(RUN_250), reason="saved run not present")
def test_sympy_agrees_with_equation_holds_on_saved_graphs():
    import json
    with open(os.path.join(RUN_250, "graphs.jsonl")) as f:
        graphs = [ReasoningGraph.from_dict(json.loads(l)) for l in f]
    eqs = [eq for g in graphs for n in g.nodes for eq in n.equations]
    assert len(eqs) > 1000
    assert all(sympy_equation_holds(eq) == equation_holds(eq) for eq in eqs)


def test_graph_verifier_flags_the_wrong_node():
    g = _graph("She has 16 - 3 - 4 = 9 eggs left.\nShe makes 9 * 2 = $19 a day.")
    out = GraphArithmeticVerifier().verify_graph(g)
    assert out["1"].status == VALID
    assert out["2"].status == INVALID and out["2"].error_type == "arithmetic"
    assert "9 * 2 = 18" in out["2"].checks[0].detail


def test_graph_verifier_grounding():
    ok = GraphArithmeticVerifier().verify_graph(_graph("She has 16 - 3 - 4 = 9 eggs left.\nShe makes 9 * 2 = $18 a day."))
    assert all(v.status == VALID for v in ok.values())
    # 11 appears nowhere earlier: the arithmetic holds but the operand is ungrounded
    bad = GraphArithmeticVerifier().verify_graph(_graph("She has 16 - 3 - 4 = 9 eggs left.\nShe makes 11 * 2 = $22 a day."))
    assert bad["2"].status == INVALID and bad["2"].error_type == "ungrounded_operand"
    # an intermediate rewritten inside a chain is not an operand to source
    chain = GraphArithmeticVerifier().verify_graph(_graph("The total is 2 * (3 + 4) = 2 * 7 = 14 eggs.", "She has 3 and 4 eggs, twice."))
    assert chain["1"].status == VALID


def test_graph_verifier_claims_are_unverifiable():
    out = GraphArithmeticVerifier().verify_graph(_graph("Janet has 16 eggs.\nShe sells what is left."))
    assert all(v.status == UNVERIFIABLE for v in out.values())
