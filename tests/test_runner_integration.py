import json
import os
import sys
import tempfile

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scripts.run_graph_method as runner
import src.models.model_registry as registry
import src.verify.registry as vreg
from tests.test_graph_remask import EXAMPLE, FakeModel, L, eq_verifier


def _fake_model(model_cfg):
    m = FakeModel()
    m.config = model_cfg
    return m


def _run(method, extra=None):
    ex = dict(EXAMPLE, reference_answer="26")
    with tempfile.TemporaryDirectory() as d:
        old = os.getcwd()
        os.chdir(d)
        try:
            yaml.safe_dump({"name": "fake", "wrapper": "fake", "generation": {
                "max_new_tokens": L, "num_denoising_steps": L, "block_length": None, "temperature": 0.0,
                "remasking_strategy": "low_confidence"}}, open("model.yaml", "w"))
            yaml.safe_dump({"name": "gsm8k", "answer_type": "numeric"}, open("data.yaml", "w"))
            cfg = {"run_id": f"t_{method}", "method": method, "model_config": "model.yaml",
                   "dataset_config": "data.yaml", "sample_size": 1, "draft_cache": "cache", **(extra or {})}
            yaml.safe_dump(cfg, open("run.yaml", "w"))
            runner.load_dataset_unified = lambda path, sample_size=None: [ex]
            registry.get_model_wrapper = _fake_model
            vreg.VERIFIER_FACTORIES["gsm8k"] = lambda c: eq_verifier
            sys.argv = ["run", "--config", "run.yaml"]
            runner.main()
            rec = [json.loads(l) for l in open(f"logs/t_{method}/generations.jsonl")]
            metrics = json.load(open(f"logs/t_{method}/metrics.json"))
            drafts = [f for f in os.listdir("cache") if f.startswith("drafts_")]
            return rec, metrics, drafts
        finally:
            os.chdir(old)


def test_remask_method_end_to_end():
    rec, m, drafts = _run("remask")
    r = rec[0]
    assert r["draft_correct"] is False and r["correct"] is True and r["fixed"] is True
    assert (r["flags_before"], r["flags_after"]) == (1, 0) and len(r["rounds"]) == 1
    assert m["fixed"] == 1 and m["accuracy"] == 1.0 and m["method"] == "remask" and len(drafts) == 1


def test_scheduled_method_end_to_end():
    rec, m, _ = _run("scheduled")
    r = rec[0]
    assert r["correct"] and r["schedule"]["levels"] == 3 and r["num_forward_passes"] == L + r["schedule"]["nfe"]
    assert m["method"] == "scheduled" and m["mean_nfe_schedule"] == r["schedule"]["nfe"]


def test_new_diagnostics_and_comparison():
    from scripts.compare_methods import compare, render_md, render_tex
    ex = dict(EXAMPLE, reference_answer="26")
    dirs = {}
    with tempfile.TemporaryDirectory() as d:
        old = os.getcwd()
        os.chdir(d)
        try:
            for method, extra in (("remask", {"remask": {"mode": "graph"}}), ("remask_full", {"remask": {"mode": "full"}}),):
                m = "remask"
                yaml.safe_dump({"name": "fake", "wrapper": "fake", "generation": {
                    "max_new_tokens": L, "num_denoising_steps": L, "block_length": None, "temperature": 0.0,
                    "remasking_strategy": "low_confidence"}}, open("model.yaml", "w"))
                yaml.safe_dump({"name": "gsm8k", "answer_type": "numeric"}, open("data.yaml", "w"))
                yaml.safe_dump({"run_id": f"t_{method}", "method": m, "model_config": "model.yaml",
                                "dataset_config": "data.yaml", "sample_size": 1, "draft_cache": "cache", **extra},
                               open("run.yaml", "w"))
                runner.load_dataset_unified = lambda path, sample_size=None: [ex]
                registry.get_model_wrapper = _fake_model
                vreg.VERIFIER_FACTORIES["gsm8k"] = lambda c: eq_verifier
                sys.argv = ["run", "--config", "run.yaml"]
                runner.main()
                dirs[method] = os.path.abspath(f"logs/t_{method}")
            rec = json.loads(open(dirs["remask"] + "/generations.jsonl").readline())
            assert rec["graph_steps"] == 4 and rec["parse_warnings"] == 0 and rec["flag_types"] == {"unspecified": 1}
            assert rec["tokens_regenerated"] == 36 and rec["tokens_draft"] == 49 and rec["format_ok"] is True
            assert rec["sec_parse_verify"] > 0
            met = json.load(open(dirs["remask"] + "/metrics.json"))
            assert met["flag_precision_draft_wrong"] == 1.0 and met["wrong_drafts_not_flagged"] == 0
            res = compare([dirs["remask"], dirs["remask_full"]], ["graph", "full"])
            assert res["same_draft"] and len(res["pairs"]) == 1 and res["pairs"][0]["p"] == 1.0
            assert res["rows"][0]["tokens_regen"] < res["rows"][1]["tokens_regen"]
            assert "graph vs full" in render_md(res) and r"\toprule" in render_tex(res)
        finally:
            os.chdir(old)


def test_unknown_dataset_has_a_clear_error():
    try:
        vreg.make_verify_fn("proofwriter")
    except ValueError as e:
        assert "src/verify/registry.py" in str(e)
    else:
        raise AssertionError("expected ValueError")


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            failed += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)
