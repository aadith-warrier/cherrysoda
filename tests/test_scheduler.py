import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.methods.graph_remask import token_char_spans
from src.methods.scheduler import DependencyPlan, ScheduleConfig, ScheduledDecoder
from tests.test_graph_remask import DRAFT, EXAMPLE, FIXED, GEN_CFG, L, FakeModel, eq_verifier
from src.graph.registry import build_graph


def line(i):
    start = sum(len(x) + 1 for x in DRAFT.split("\n")[:i])
    return range(start, start + len(DRAFT.split("\n")[i]))


def test_plan_levels_and_units():
    model = FakeModel()
    ids = model.generate(None, L, L).token_ids
    graph = build_graph({"example_id": "t", "dataset": "gsm8k", "prompt": EXAMPLE["prompt"], "generation": DRAFT})
    _, spans = token_char_spans(model.tokenizer, ids[: len(DRAFT)])
    plan = DependencyPlan(graph, spans, len(DRAFT), L)
    assert plan.levels() == {"1": 0, "2": 0, "3": 1, "4": 2}
    assert plan.parents["3"] == ["1", "2"] and plan.parents["4"] == ["3"]
    assert plan.pos["1"] == set(line(0)) and plan.tail == set(range(len(DRAFT), L))
    assert plan.scaffold == {len(DRAFT.split("\n")[0]), 20, 32}


def test_schedule_respects_dependencies_and_runs_independent_steps_together():
    model = FakeModel()
    res = ScheduledDecoder(model, eq_verifier, ScheduleConfig()).run(EXAMPLE, GEN_CFG)
    cp = model.commit_pass
    last = lambda i: max(cp[p] for p in line(i))
    first = lambda i: min(cp[p] for p in line(i))
    assert first(0) == first(1) == 0, "independent steps 1 and 2 start in the same pass"
    assert first(2) > last(0) and first(2) > last(1), "step 3 waits for steps 1 and 2"
    assert first(3) > last(2), "the answer line waits for step 3"
    tail_passes = {cp[p] for p in range(len(DRAFT), L)}
    assert len(tail_passes) == 1 and tail_passes.pop() > last(3), "padding is committed last, in one pass"
    assert res.n_levels == 3

    assert res.nfe_schedule < L and res.nfe_total == L + res.nfe_schedule
    assert res.final_text == FIXED and (res.flags_before, res.flags_after) == (1, 0)
    assert model.calls[0]["positions"] == list(range(L)) and model.calls[0]["allow_end_from"] == len(DRAFT)


def test_no_steps_falls_back_to_draft():
    model = FakeModel()
    ex = dict(EXAMPLE)
    model.generate = lambda *a, **k: __import__("src.models.base", fromlist=["x"]).GenerationResult(
        None, "", L, 0.0, L, token_ids=[0] * L)
    res = ScheduledDecoder(model, eq_verifier).run(ex, GEN_CFG)
    assert res.skipped_reason and not model.calls and res.nfe_total == L


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)
