import json, os, sys, subprocess, textwrap
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest, yaml
from data.loaders import load_dataset_unified
from src.eval.scoring import extract_numeric, extract_label, score_record, summarize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------- scoring ----------
@pytest.mark.parametrize("text,val,method", [
    ("5 + 3 = 8\nThe answer is: 8", 8.0, "pattern"),
    ("The answer is: 8.\nWait, check 12 + 3 = 15", 8.0, "pattern"),
    ("The answer is $1,234.50.", 1234.5, "pattern"),
    ("so the answer is -7", -7.0, "pattern"),
    ("The answer is: **42**", 42.0, "pattern"),
    ("\\boxed{17}", 17.0, "pattern"),
    ("She has 3 apples then 5, total 8", 8.0, "fallback"),
    ("no numbers here", None, "none"),
    ("", None, "none"),
])
def test_extract_numeric(text, val, method):
    assert extract_numeric(text) == (val, method)

@pytest.mark.parametrize("text,val,method", [
    ("Since Bob is red ... The answer is: True", "True", "pattern"),
    ("It is not true that X. The answer is: Unknown", "Unknown", "pattern"),
    ("The answer is **False**.", "False", "pattern"),
    ("Therefore the hypothesis is false.", "False", "fallback"),
    ("hmm", None, "none"),
])
def test_extract_label(text, val, method):
    assert extract_label(text) == (val, method)

def test_score_numeric_tolerance():
    assert score_record({"dataset": "svamp", "generation": "The answer is: 51", "reference_answer": "51"})["correct"]
    assert score_record({"dataset": "svamp", "generation": "The answer is: 2.50", "reference_answer": "2.5"})["correct"]
    assert not score_record({"dataset": "gsm8k", "generation": "The answer is: 52", "reference_answer": "51"})["correct"]

def test_old_logs_rescore():  # old records have no answer_type
    assert score_record({"dataset": "gsm8k", "generation": "... 18", "reference_answer": "18"})["correct"]

# ---------- loaders ----------
def test_svamp_real():
    ex = load_dataset_unified(os.path.join(ROOT, "configs/dataset/svamp.yaml"), "full")
    assert len(ex) == 1000
    assert ex[0]["reference_answer"] == "51"
    assert "each pack. How much" in ex[0]["prompt"]
    assert "The answer is: <number>" in ex[0]["prompt"]
    assert len(load_dataset_unified(os.path.join(ROOT, "configs/dataset/svamp.yaml"))) == 100

@pytest.fixture
def pw_cfg(tmp_path):
    d = tmp_path / "proofwriter-dataset-V2020.12.3" / "OWA" / "depth-3"
    d.mkdir(parents=True)
    (tmp_path / "proofwriter-dataset-V2020.12.3" / "OWA" / "depth-2").mkdir()
    (tmp_path / "proofwriter-dataset-V2020.12.3" / "OWA" / "depth-2" / "meta-test.jsonl").write_text("garbage\n")
    lines = []
    for t in range(300):
        qs = {}
        for q, ans in enumerate([True, False, "Unknown", True, False]):
            qs[f"Q{q+1}"] = {"question": f"Thing{t} is q{q}.", "answer": ans, "QDep": q % 4,
                             "strategy": "proof", "proofs": "[(triple1)]"}
        lines.append(json.dumps({"id": f"AttNeg-OWA-D3-{t}", "maxD": 3, "theory": f"Theory {t}.",
                                 "triples": {}, "rules": {}, "questions": qs}))
    (d / "meta-test.jsonl").write_text("\n".join(lines) + "\n")
    cfg = yaml.safe_load(open(os.path.join(ROOT, "configs/dataset/proofwriter_depth3.yaml")))
    cfg["raw_data_path"] = str(tmp_path)
    p = tmp_path / "pw.yaml"; p.write_text(yaml.dump(cfg))
    return str(p)

def test_proofwriter_balanced_and_prefix(pw_cfg):
    full = load_dataset_unified(pw_cfg, "full")
    pre = load_dataset_unified(pw_cfg, None)
    assert len(full) == 600 and len(pre) == 100
    from collections import Counter
    assert Counter(e["reference_answer"] for e in full) == {"True": 200, "False": 200, "Unknown": 200}
    assert [e["metadata"]["source_uid"] for e in pre] == [e["metadata"]["source_uid"] for e in full[:100]]
    assert len({e["metadata"]["source_uid"] for e in full}) == 600
    assert "Theory: Theory" in full[0]["prompt"] and "Hypothesis: Thing" in full[0]["prompt"]
    # deterministic
    assert [e["metadata"]["source_uid"] for e in load_dataset_unified(pw_cfg, "full")] == \
           [e["metadata"]["source_uid"] for e in full]

def test_proofwriter_missing(tmp_path):
    cfg = yaml.safe_load(open(os.path.join(ROOT, "configs/dataset/proofwriter_depth3.yaml")))
    cfg["raw_data_path"] = str(tmp_path); p = tmp_path / "pw.yaml"; p.write_text(yaml.dump(cfg))
    with pytest.raises(FileNotFoundError):
        load_dataset_unified(str(p), 5)

# ---------- configs are matched ----------
def test_model_configs_matched():
    l = yaml.safe_load(open(os.path.join(ROOT, "configs/model/llada_8b.yaml")))["generation"]
    d = yaml.safe_load(open(os.path.join(ROOT, "configs/model/dream_7b.yaml")))["generation"]
    for k in ("max_new_tokens", "num_denoising_steps"):
        assert l[k] == d[k], k
    assert l["temperature"] == 0.0                              # LLaDA official: greedy
    assert (d["temperature"], d["top_p"]) == (0.2, 0.95)        # Dream README sampling
    assert l["max_new_tokens"] % l["block_length"] == 0
    assert l["num_denoising_steps"] % (l["max_new_tokens"] // l["block_length"]) == 0
    assert d["block_length"] is None

def test_run_configs_exist():
    for ds in ("gsm8k", "svamp", "proofwriter_d3"):
        for m in ("llada", "dream"):
            c = yaml.safe_load(open(os.path.join(ROOT, f"configs/run/vanilla_{ds}_{m}.yaml")))
            assert os.path.exists(os.path.join(ROOT, c["model_config"]))
            assert os.path.exists(os.path.join(ROOT, c["dataset_config"]))

# ---------- runner end to end with a stub model ----------
def test_runner_with_fake_model(tmp_path):
    import runpy, shutil
    from src.models import model_registry
    import tests.fake_wrapper as fw
    model_registry.REGISTRY["fake"] = ("tests.fake_wrapper", "FakeWrapper")
    mcfg = tmp_path / "fake.yaml"
    mcfg.write_text(yaml.dump({"name": "fake", "wrapper": "fake", "device": "cpu", "generation": {
        "max_new_tokens": 256, "num_denoising_steps": 256, "block_length": 32,
        "temperature": 0.0, "remasking_strategy": "low_confidence"}}))
    rcfg = yaml.safe_load(open(os.path.join(ROOT, "configs/run/vanilla_svamp_llada.yaml")))
    rcfg["model_config"] = str(mcfg)
    rcfg["generation_overrides"] = {"remasking_strategy": "random"}
    rpath = tmp_path / "run.yaml"; rpath.write_text(yaml.dump(rcfg))
    run_id = "pytest_fake_run"
    log_dir = os.path.join(ROOT, "logs", run_id)
    shutil.rmtree(log_dir, ignore_errors=True)
    cwd = os.getcwd(); os.chdir(ROOT)
    try:
        base = ["run_baseline.py", "--config", str(rpath), "--run_id", run_id, "--sample_size", "12", "--no_wandb"]
        fw.FakeWrapper.crash_after = 5
        sys.argv = base
        with pytest.raises(RuntimeError):
            runpy.run_path("scripts/run_baseline.py", run_name="__main__")
        fw.FakeWrapper.crash_after = None
        sys.argv = base + ["--resume"]
        runpy.run_path("scripts/run_baseline.py", run_name="__main__")
        recs = [json.loads(l) for l in open(os.path.join(log_dir, "generations.jsonl"))]
        assert len(recs) == 12 and len({r["example_id"] for r in recs}) == 12
        m = json.load(open(os.path.join(log_dir, "metrics.json")))
        assert m["num_examples"] == 12 and m["generation"]["remasking_strategy"] == "random"
        assert m["empty_generations"] > 0 and "accuracy" in m
        seeds = {r["example_id"]: r["seed"] for r in recs}
        assert len(set(seeds.values())) == 12             # one distinct seed per example
    finally:
        os.chdir(cwd); shutil.rmtree(log_dir, ignore_errors=True)

# ---------- correction baselines: pure logic ----------
from src.methods.correction import TemporalVote

def test_temporal_vote_exp_weighting():
    v = TemporalVote(lambda t: float(t) if t else None, total_steps=10, weighting="exp", alpha=5.0)
    for s in range(6):
        v.add(s, "9")          # many early votes
    for s in range(6, 10):
        v.add(s, "7")          # fewer, later votes
    assert v.result() == 7.0   # late steps dominate under exp weighting
    f = TemporalVote(lambda t: float(t) if t else None, total_steps=10, weighting="fixed")
    for s in range(6):
        f.add(s, "9")
    for s in range(6, 10):
        f.add(s, "7")
    assert f.result() == 9.0
    empty = TemporalVote(lambda t: None, total_steps=5)
    empty.add(0, "x")
    assert empty.result() is None and empty.num_votes == 0

def test_score_uses_voted_answer():
    r = score_record({"dataset": "svamp", "generation": "The answer is: 3", "reference_answer": "7", "voted_answer": 7.0})
    assert r == {"predicted": 7.0, "extraction": "vote", "correct": True}
    r = score_record({"dataset": "proofwriter", "generation": "The answer is: True", "reference_answer": "Unknown",
                      "voted_answer": "Unknown"})
    assert r["correct"] and r["extraction"] == "vote"
    r = score_record({"dataset": "svamp", "generation": "The answer is: 7", "reference_answer": "7", "voted_answer": None})
    assert r["correct"] and r["extraction"] == "pattern"

def _run_fake(tmp_path, baseline, overrides, run_id):
    import runpy, shutil
    from src.models import model_registry
    model_registry.REGISTRY["fake"] = ("tests.fake_wrapper", "FakeWrapper")
    mcfg = tmp_path / "fake.yaml"
    mcfg.write_text(yaml.dump({"name": "fake", "wrapper": "fake", "device": "cpu", "generation": {
        "max_new_tokens": 256, "num_denoising_steps": 30, "block_length": 32,
        "temperature": 0.0, "remasking_strategy": "low_confidence"}}))
    rcfg = yaml.safe_load(open(os.path.join(ROOT, f"configs/run/{run_id.split('__')[0]}.yaml")))
    rcfg["model_config"] = str(mcfg)
    assert rcfg["baseline"] == baseline and rcfg["generation_overrides"] == overrides
    rpath = tmp_path / "run.yaml"; rpath.write_text(yaml.dump(rcfg))
    log_dir = os.path.join(ROOT, "logs", run_id)
    shutil.rmtree(log_dir, ignore_errors=True)
    cwd = os.getcwd(); os.chdir(ROOT)
    try:
        sys.argv = ["run_baseline.py", "--config", str(rpath), "--run_id", run_id, "--sample_size", "4", "--no_wandb"]
        runpy.run_path("scripts/run_baseline.py", run_name="__main__")
        recs = [json.loads(l) for l in open(os.path.join(log_dir, "generations.jsonl"))]
        m = json.load(open(os.path.join(log_dir, "metrics.json")))
        return recs, m
    finally:
        os.chdir(cwd); shutil.rmtree(log_dir, ignore_errors=True)

def test_runner_temporal_vote(tmp_path):
    recs, m = _run_fake(tmp_path, "temporal_vote", {"vote_weighting": "exp", "vote_alpha": 5.0},
                        "vote_svamp_llada__pytest")
    assert all(r["voted_answer"] == 7.0 and r["extraction"] == "vote" for r in recs)
    assert all(r["num_votes"] == 30 for r in recs)
    assert m["extraction_vote"] == 4 and m["empty_generations"] == 2   # vote still scores empty final texts


# ---------- RemeDi / ProSeCo configs (the models themselves need a GPU) ----------
def test_official_baseline_configs():
    from src.models.model_registry import REGISTRY
    for rid in ("remedi_rl", "proseco", "proseco_nocorr", "proseco_sampler_llada"):
        for ds in ("gsm8k", "svamp", "proofwriter_d3"):
            c = yaml.safe_load(open(os.path.join(ROOT, f"configs/run/{rid}_{ds}.yaml")))
            m = yaml.safe_load(open(os.path.join(ROOT, c["model_config"])))
            assert m["wrapper"] in REGISTRY
            g = {**m["generation"], **(c["generation_overrides"] or {})}
            assert (g["max_new_tokens"], g["num_denoising_steps"], g["block_length"]) == (256, 256, 32)
            if rid == "proseco_nocorr":
                assert g["max_corrector_steps_per_loop"] == 0
            if rid in ("proseco", "proseco_sampler_llada"):
                assert (g["apply_corrector_every_n_steps"], g["max_corrector_steps_per_loop"]) == (2, 4)

def test_dapd_configs():
    from src.models.model_registry import REGISTRY
    for m, (block, tmin, tmax) in {"llada": (64, 0.005, 0.05), "dream": (None, 0.005, 0.01)}.items():
        for ds in ("gsm8k", "svamp", "proofwriter_d3"):
            c = yaml.safe_load(open(os.path.join(ROOT, f"configs/run/dapd_{ds}_{m}.yaml")))
            mc = yaml.safe_load(open(os.path.join(ROOT, c["model_config"])))
            assert mc["wrapper"] == "dapd" and mc["wrapper"] in REGISTRY and mc["base"] == m
            g = mc["generation"]
            assert (g["block_length"], g["tau_min"], g["tau_max"], g["dapd_alg"]) == (block, tmin, tmax, "dapd_direct")
            assert g["max_new_tokens"] == 256

def test_load_package_does_not_shadow_baselines(tmp_path):
    from src.models.base import load_package_from_dir
    repo = tmp_path / "FakeRepo"
    (repo / "fakepkg_dapd").mkdir(parents=True)
    (repo / "baselines").mkdir()
    (repo / "baselines" / "__init__.py").write_text("")
    (repo / "fakepkg_dapd" / "__init__.py").write_text("from .core import VALUE\n")
    (repo / "fakepkg_dapd" / "core.py").write_text("VALUE = 42\n")
    mod = load_package_from_dir("fakepkg_dapd", str(repo / "fakepkg_dapd"))
    assert mod.VALUE == 42
    assert str(repo) not in sys.path
    import importlib
    cwd = os.getcwd(); os.chdir(ROOT)
    try:
        assert hasattr(importlib.import_module("baselines.vanilla"), "run")   # ours, not the fake repo's
    finally:
        os.chdir(cwd)
