import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.graph.extract import equation_holds
from src.graph.registry import build_graph
from src.methods.graph_remask import (
    GraphRemasker, RemaskConfig, affected_subgraph, positions_overlapping, token_char_spans,
)
from src.models.base import GenerationResult
from src.verify.base import INVALID, UNVERIFIABLE, VALID, Verdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOP, MASK, L = 0, 1, 80


class CharTokenizer:

    def decode(self, ids, skip_special_tokens=True):
        return "".join(chr(i) for i in ids if i > 1)


def eq_verifier(graph):
    out = {}
    for n in graph.nodes:
        if n.kind not in ("calc", "claim"):
            continue
        res = [equation_holds(e) for e in n.equations]
        out[n.node_id] = Verdict(
            INVALID if any(r is False for r in res) else VALID if any(r for r in res) else UNVERIFIABLE,
            1.0 if any(r is False for r in res) else 0.0, "test",
        )
    return out


def encode(text):
    return [ord(c) for c in text] + [STOP] * (L - len(text))


PROMPT = ("Question: Tom has 2 bags with 3 apples each and 4 boxes with 5 oranges each. "
          "How many fruits does he have?\nLet's think step by step\nAnswer:")
EXAMPLE = {"example_id": "t0", "prompt": PROMPT, "metadata": {"dataset": "gsm8k"}, "reference_answer": "26"}
DRAFT = "2 * 3 = 7\n4 * 5 = 20\n7 + 20 = 27\nThe answer is 27"
FIXED = "2 * 3 = 6\n4 * 5 = 20\n6 + 20 = 26\nThe answer is 26"
assert len(DRAFT) == len(FIXED)


class FakeModel:
    stop_token_ids = {STOP}
    tokenizer = CharTokenizer()

    def __init__(self, repair=FIXED):
        self.repair, self.calls = encode(repair), []

    def generate(self, prompt, max_new_tokens, num_denoising_steps, **kw):
        ids = encode(DRAFT)
        return GenerationResult(prompt, DRAFT, num_denoising_steps, 0.0, num_denoising_steps, token_ids=ids)

    def refine(self, prompt, token_ids, remask_positions, num_denoising_steps=None, temperature=None,
               allow_end_from=None, confidence_eos_eot_inf=True, select_fn=None):
        self.calls.append({"positions": sorted(remask_positions), "allow_end_from": allow_end_from})
        out, passes = list(token_ids), len(remask_positions)
        self.commit_pass = {}
        if select_fn is not None:
            remaining, passes = sorted(remask_positions), 0
            while remaining:
                chosen = set(select_fn(remaining, [1.0 - 0.001 * p for p in remaining])) or {remaining[0]}
                for p in chosen:
                    self.commit_pass[p] = passes
                remaining = [p for p in remaining if p not in chosen]
                passes += 1
        for p in remask_positions:
            out[p] = self.repair[p]
        text = "".join(chr(i) for i in out if i > 1)
        return GenerationResult(prompt, text, passes, 0.0, passes,
                                num_remasked_tokens=len(remask_positions), token_ids=out)


GEN_CFG = {"max_new_tokens": L, "num_denoising_steps": L, "remasking_strategy": "low_confidence"}


def test_token_char_spans_roundtrip():
    tok = CharTokenizer()
    ids = [ord(c) for c in "  ab\ncd"] + [STOP, STOP]
    text, spans = token_char_spans(tok, ids)
    assert text == "ab\ncd"
    assert [text[s:e] for s, e in spans[:7]] == ["", "", "a", "b", "\n", "c", "d"]
    assert spans[7] == spans[8] == (5, 5)
    assert positions_overlapping(spans, [(1, 4)]) == [3, 4, 5]


def test_affected_subgraph_figure1():
    """Paper Fig. 1 (gsm8k_00026): steps 5 and 9 are wrong, 13 is independent, 15 and 16 consume the wrong values."""
    path = os.path.join(ROOT, "outputs/analysis_paper_noblock_250/generations.jsonl")
    record = next(json.loads(l) for l in open(path) if json.loads(l)["example_id"] == "gsm8k_00026")
    graph = build_graph(record)
    bad = [i for i, v in eq_verifier(graph).items() if v.status == INVALID]
    assert bad == ["5", "9"]
    assert affected_subgraph(graph, bad) == ["5", "9", "15", "16"]
    assert "13" not in affected_subgraph(graph, bad)


def test_localized_remask_keeps_independent_step():
    model = FakeModel()
    res = GraphRemasker(model, eq_verifier, RemaskConfig(max_rounds=3)).run(EXAMPLE, GEN_CFG)
    assert res.draft_text == DRAFT and res.final_text == FIXED
    assert (res.flags_before, res.flags_after) == (1, 0)
    assert res.consistent_after and not res.consistent_before
    assert len(model.calls) == 1 and len(res.rounds) == 1

    masked = set(model.calls[0]["positions"])
    line2 = range(DRAFT.index("4 * 5"), DRAFT.index("4 * 5") + len("4 * 5 = 20"))
    assert not masked & set(line2), "the independent step 4*5=20 must stay fixed"

    assert all(p in masked for p in range(0, 9))
    assert all(p in masked for p in range(len(DRAFT), L))

    assert model.calls[0]["allow_end_from"] == DRAFT.index("The answer")

    r = res.rounds[0]
    assert r.flagged == ["1"] and r.affected == ["1", "3", "4"]
    assert abs(r.affected_ratio - 3 / 4) < 1e-9
    assert r.n_remasked == len("2 * 3 = 7") + len("7 + 20 = 27") + len("The answer is 27")


def test_nfe_counts_draft_and_refine():
    res = GraphRemasker(FakeModel(), eq_verifier).run(EXAMPLE, GEN_CFG)
    assert res.nfe_draft == L
    assert res.nfe_total == L + res.rounds[0].nfe


def test_full_mode_remasks_everything():
    model = FakeModel()
    GraphRemasker(model, eq_verifier, RemaskConfig(mode="full")).run(EXAMPLE, GEN_CFG)
    assert model.calls[0]["positions"] == list(range(L)) and model.calls[0]["allow_end_from"] == 0


def test_no_flags_no_remask():
    model = FakeModel()
    model.generate = lambda *a, **k: GenerationResult(PROMPT, FIXED, L, 0.0, L, token_ids=encode(FIXED))
    res = GraphRemasker(model, eq_verifier).run(EXAMPLE, GEN_CFG)
    assert not model.calls and res.final_text == FIXED and res.nfe_total == L and res.consistent_before


def test_stops_when_greedy_refine_reproduces_the_draft():
    model = FakeModel(repair=DRAFT)
    res = GraphRemasker(model, eq_verifier, RemaskConfig(max_rounds=5)).run(EXAMPLE, GEN_CFG)
    assert len(model.calls) == 1 and res.flags_after == 1 and not res.rounds[0].changed
    res = GraphRemasker(FakeModel(repair=DRAFT), eq_verifier, RemaskConfig(max_rounds=3, temperature=0.5)).run(EXAMPLE, GEN_CFG)
    assert len(res.rounds) == 3


def test_draft_cache_is_used():
    model = FakeModel()
    draft = model.generate(PROMPT, L, L)
    model.generate = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not regenerate"))
    res = GraphRemasker(model, eq_verifier).run(EXAMPLE, GEN_CFG, draft=draft)
    assert res.final_text == FIXED


def test_runner_statistics_and_cache(tmp_path=None):
    import tempfile
    from scripts.run_graph_method import DraftCache, mcnemar_exact, paired_bootstrap_ci, summarize

    assert mcnemar_exact(0, 0) == 1.0
    assert abs(mcnemar_exact(10, 0) - 2 / 1024) < 1e-12 and mcnemar_exact(5, 5) == 1.0
    assert paired_bootstrap_ci([0, 0, 1, 1], [0, 0, 1, 1]) == (0.0, 0.0)

    rounds = [{"remask_ratio": 0.4, "affected_ratio": 0.5, "changed": True}]
    mk = lambda d, f, flags_b, flags_a, rd: {
        "draft_correct": d, "correct": f, "fixed": (not d) and f, "broken": d and not f, "flags_before": flags_b,
        "flags_after": flags_a, "rounds": rd, "nfe_draft": 256, "num_forward_passes": 256 + 100 * len(rd),
        "predicted_answer": 1.0, "wall_time_sec": 1.0, "hit_length_limit": False}
    recs = [mk(False, True, 1, 0, rounds), mk(True, True, 0, 0, []), mk(False, False, 2, 1, rounds), mk(True, False, 1, 1, rounds)]
    m = summarize(recs)
    assert (m["fixed"], m["broken"]) == (1, 1) and m["draft_accuracy"] == 0.5 == m["accuracy"]
    assert m["reasoning_consistency_before"] == 0.25 and m["reasoning_consistency_after"] == 0.5
    assert m["mean_nfe_overhead"] == 75 and abs(m["mean_remask_ratio_per_round"] - 0.4) < 1e-12
    assert m["flagged_draft_wrong"] == 2 and m["flagged_draft_right"] == 1

    with tempfile.TemporaryDirectory() as d:
        c = DraftCache(d, {"k": 1})
        assert c.get("a") is None
        c.put("a", GenerationResult(None, "x", 7, 0.5, 7, token_ids=[5, 6]))
        got = DraftCache(d, {"k": 1}).get("a")
        assert got.token_ids == [5, 6] and got.num_forward_passes == 7
        assert DraftCache(d, {"k": 2}).get("a") is None


if __name__ == "__main__":
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)
