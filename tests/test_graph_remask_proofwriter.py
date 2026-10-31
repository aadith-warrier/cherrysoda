"""Localized remasking on ProofWriter, end to end with a fake model (no GPU, no torch).

draft -> ProofWriter graph -> symbolic logic verifier -> affected subgraph A(B) -> token positions -> refine -> verify.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.graph.registry import build_graph
from src.methods.graph_remask import GraphRemasker, RemaskConfig, affected_subgraph
from src.models.base import GenerationResult
from src.verify.base import INVALID
from src.verify.registry import make_verify_fn

STOP, L = 0, 160
PROMPT = ("Given the following facts and rules, determine whether the hypothesis is True, False, or Unknown.\n\n"
          "Theory: Bob is big. Fiona is red. Red things are young.\n"
          "Hypothesis: Fiona is young.\n\nReasoning:\n")
EXAMPLE = {"example_id": "pw0", "prompt": PROMPT, "reference_answer": "True",
           "metadata": {"dataset": "proofwriter", "answer_type": "label"}}
# line 3 wrongly says "Fiona is young" cannot be proved; line 4 (the answer) depends on it; lines 1-2 are fine
DRAFT = "Fiona is red.\nRed things are young.\nWe cannot prove that Fiona is young.\nThe answer is: Unknown"
FIXED = "Fiona is red.\nRed things are young.\nSince Fiona is red,  Fiona is young.\nThe answer is: True   "
assert len(DRAFT) == len(FIXED)


class CharTokenizer:
    def decode(self, ids, skip_special_tokens=True):
        return "".join(chr(i) for i in ids if i > 1)


def encode(text):
    return [ord(c) for c in text] + [STOP] * (L - len(text))


class FakeModel:
    stop_token_ids = {STOP}
    tokenizer = CharTokenizer()

    def __init__(self):
        self.calls, self.repair = [], encode(FIXED)

    def generate(self, prompt, max_new_tokens, num_denoising_steps, **kw):
        return GenerationResult(prompt, DRAFT, num_denoising_steps, 0.0, num_denoising_steps, token_ids=encode(DRAFT))

    def refine(self, prompt, token_ids, remask_positions, num_denoising_steps=None, temperature=None,
               allow_end_from=None, confidence_eos_eot_inf=True, select_fn=None):
        self.calls.append(sorted(remask_positions))
        out = list(token_ids)
        for p in remask_positions:
            out[p] = self.repair[p]
        text = "".join(chr(i) for i in out if i > 1)
        return GenerationResult(prompt, text, len(remask_positions), 0.0, len(remask_positions),
                                num_remasked_tokens=len(remask_positions), token_ids=out)


GEN_CFG = {"max_new_tokens": L, "num_denoising_steps": L, "remasking_strategy": "low_confidence"}


def test_verifier_registered_under_both_names():
    for name in ("proofwriter", "proofwriter_depth3"):
        assert callable(make_verify_fn(name))


def test_verifier_flags_the_wrong_hedge_only():
    g = build_graph({"example_id": "pw0", "dataset": "proofwriter", "prompt": PROMPT, "generation": DRAFT})
    verdicts = make_verify_fn("proofwriter_depth3")(g)
    bad = [k for k, v in verdicts.items() if v.status == INVALID]
    assert bad == ["3"]
    assert affected_subgraph(g, bad) == ["3", "4"]  # the answer line follows the hedge; lines 1-2 are kept


def test_meta_lines_are_not_verified():
    gen = "Hypothesis:\n- Bob is small.\nBob is big.\nThe answer is: False"
    g = build_graph({"example_id": "pw1", "dataset": "proofwriter", "prompt": PROMPT, "generation": gen})
    assert g.node("2").kind == "meta"
    assert "2" not in make_verify_fn("proofwriter")(g)


def test_remask_loop_repairs_only_the_affected_lines():
    model = FakeModel()
    res = GraphRemasker(model, make_verify_fn("proofwriter_depth3"), RemaskConfig(mode="graph", max_rounds=3)).run(
        EXAMPLE, GEN_CFG)
    first = model.calls[0]
    line3_start = DRAFT.index("We cannot")
    assert min(first) == line3_start                     # nothing before the flagged step is touched
    assert res.final_text == FIXED.strip()
    assert res.flags_before == 1 and res.flags_after == 0
    r = res.rounds[0]
    assert r.flagged == ["3"] and r.affected == ["3", "4"]
    assert res.n_steps == 4 and abs(r.affected_ratio - 0.5) < 1e-9


def test_full_mode_remasks_everything():
    model = FakeModel()
    GraphRemasker(model, make_verify_fn("proofwriter"), RemaskConfig(mode="full", max_rounds=1)).run(EXAMPLE, GEN_CFG)
    assert model.calls[0] == list(range(L))


def test_scorer_reads_labels():
    from scripts.run_graph_method import make_scorer
    score = make_scorer("proofwriter_depth3", "label")
    assert score(DRAFT, "True") == ("Unknown", False)
    assert score(FIXED, "True") == ("True", True)


# ---------------------------------------------------------------- answer-support check + label ban

from src.methods.graph_remask import label_token_ids  # noqa: E402
from src.verify.registry import answer_label  # noqa: E402

# the trace derives the hypothesis, yet the answer says Unknown
DRAFT2 = "Fiona is red.\nRed things are young.\nSo Fiona is young.\nThe answer is: Unknown"
FIX2 = "Fiona is red.\nRed things are young.\nSo Fiona is young.\nThe answer is: True   "
assert len(DRAFT2) == len(FIX2)


class EncTokenizer(CharTokenizer):
    def encode(self, text, add_special_tokens=False):
        return [ord(c) for c in text]


class StubbornModel(FakeModel):
    """Rewrites a remasked answer line with the same label unless that label is banned (what LLaDA did)."""
    tokenizer = EncTokenizer()

    def __init__(self):
        super().__init__()
        self.repair, self.bans = encode(FIX2), []

    def generate(self, prompt, max_new_tokens, num_denoising_steps, **kw):
        return GenerationResult(prompt, DRAFT2, num_denoising_steps, 0.0, num_denoising_steps, token_ids=encode(DRAFT2))

    def refine(self, prompt, token_ids, remask_positions, ban=None, **kw):
        self.calls.append(sorted(remask_positions))
        self.bans.append(ban)
        out = list(token_ids)
        if ban and any(token_ids[p] in ids for p, ids in ban.items()):
            for p in remask_positions:
                out[p] = self.repair[p]
        text = "".join(chr(i) for i in out if i > 1)
        return GenerationResult(prompt, text, len(remask_positions), 0.0, len(remask_positions),
                                num_remasked_tokens=len(remask_positions), token_ids=out)


def graph_of(gen):
    return build_graph({"example_id": "pw", "dataset": "proofwriter", "prompt": PROMPT, "generation": gen})


def test_answer_label():
    assert answer_label("The answer is: Unknown.") == "Unknown"
    assert answer_label("Since Bob is big, the hypothesis is false.") == "False"
    assert answer_label("Therefore the hypothesis can be proved.") is None


def test_answer_check_is_off_by_default():
    v = make_verify_fn("proofwriter")(graph_of(DRAFT2))
    assert not any(x.error_type == "unsupported_answer" for x in v.values())


def test_answer_check_rules():
    vf = make_verify_fn("proofwriter", {"check_answer": True})
    bad = lambda gen: [k for k, x in vf(graph_of(gen)).items() if x.error_type == "unsupported_answer"]
    assert bad(DRAFT2) == ["4"]                                              # derived, but answered Unknown
    assert bad("Fiona is red.\nSo Fiona is young.\nThe answer is: True") == []
    assert bad("Bob is big.\nThe answer is: True") == ["2"]                  # True with nothing derived
    assert bad("Bob is big.\nThe answer is: False") == ["2"]                 # False needs the negation derived
    assert bad("Bob is big.\nThe answer is: Unknown") == []
    # a hedge or a hypothetical "if ... then" does not assert the hypothesis
    assert bad("We cannot prove that Fiona is young.\nThe answer is: True") == ["2"]
    assert bad("If Fiona is red then Fiona is young.\nThe answer is: True") == ["2"]


def test_label_tokens():
    ids = label_token_ids(EncTokenizer(), "Unknown")
    assert set(ids) == {ord("U"), ord("u")}


def test_without_ban_the_label_survives():
    m = StubbornModel()
    res = GraphRemasker(m, make_verify_fn("proofwriter", {"check_answer": True}),
                        RemaskConfig(mode="graph", max_rounds=3)).run(EXAMPLE, GEN_CFG)
    assert res.final_text == DRAFT2 and m.bans == [None]   # remasked once, came back identical, stopped


def test_ban_rewrites_only_the_answer_line():
    m = StubbornModel()
    res = GraphRemasker(m, make_verify_fn("proofwriter", {"check_answer": True}),
                        RemaskConfig(mode="graph", max_rounds=3, ban_flagged_label=True)).run(EXAMPLE, GEN_CFG)
    answer_start = DRAFT2.index("The answer")
    assert min(m.calls[0]) == answer_start                 # steps 1-3 untouched
    ban = m.bans[0]
    assert ban and min(ban) >= answer_start and all(set(v) == {ord("U"), ord("u")} for v in ban.values())
    assert set(range(len(DRAFT2), L)) <= set(ban)          # the freed tail after the answer is covered too
    assert res.final_text == FIX2.strip() and res.flags_after == 0
    assert res.rounds[0].banned_labels == ["Unknown"]
    from scripts.run_graph_method import make_scorer
    assert make_scorer("proofwriter_depth3", "label")(res.final_text, "True") == ("True", True)


def test_ban_also_works_with_the_scheduler():
    m = StubbornModel()
    res = GraphRemasker(m, make_verify_fn("proofwriter", {"check_answer": True}),
                        RemaskConfig(mode="graph", max_rounds=3, ban_flagged_label=True, schedule=True)).run(EXAMPLE, GEN_CFG)
    assert m.bans[0] and res.final_text == FIX2.strip()
