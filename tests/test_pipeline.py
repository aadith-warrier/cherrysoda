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
    """Fake ProofWriter tree in the real AllenAI layout."""
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
    """Reproduces the DAPD clash: a third-party repo with its own `baselines/` folder."""
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

def test_run_lock_blocks_second_process(tmp_path):
    """A live lock (this test's own pid) must stop a second run into the same folder."""
    import runpy, shutil
    from src.models import model_registry
    model_registry.REGISTRY["fake"] = ("tests.fake_wrapper", "FakeWrapper")
    mcfg = tmp_path / "fake.yaml"
    mcfg.write_text(yaml.dump({"name": "fake", "wrapper": "fake", "device": "cpu", "generation": {
        "max_new_tokens": 256, "num_denoising_steps": 4, "block_length": 32,
        "temperature": 0.0, "remasking_strategy": "low_confidence"}}))
    rcfg = yaml.safe_load(open(os.path.join(ROOT, "configs/run/vanilla_svamp_llada.yaml")))
    rcfg["model_config"] = str(mcfg)
    rpath = tmp_path / "run.yaml"; rpath.write_text(yaml.dump(rcfg))
    run_id = "pytest_lock_run"
    log_dir = os.path.join(ROOT, "logs", run_id)
    shutil.rmtree(log_dir, ignore_errors=True); os.makedirs(log_dir)
    open(os.path.join(log_dir, ".lock"), "w").write(str(os.getpid()))    # "another" live process
    cwd = os.getcwd(); os.chdir(ROOT)
    try:
        sys.argv = ["run_baseline.py", "--config", str(rpath), "--run_id", run_id, "--sample_size", "2", "--no_wandb"]
        with pytest.raises(SystemExit):
            runpy.run_path("scripts/run_baseline.py", run_name="__main__")
        assert not os.path.exists(os.path.join(log_dir, "generations.jsonl"))
        # stale lock (dead pid) must NOT block
        open(os.path.join(log_dir, ".lock"), "w").write("999999")
        runpy.run_path("scripts/run_baseline.py", run_name="__main__")
        assert len(open(os.path.join(log_dir, "generations.jsonl")).readlines()) == 2
    finally:
        os.chdir(cwd); shutil.rmtree(log_dir, ignore_errors=True)

# ---------- analysis scripts (compare_runs, error_analysis, arith_check) ----------
from src.eval.arith_check import check_equations

@pytest.mark.parametrize("text,expected", [
    ("16 - 3 = 13", [True]),
    ("13 - 4 = 8", [False]),
    ("9 × 2 = 18 dollars", [True]),
    ("\\[ 16 \\text{ (total eggs)} - 7 \\text{ (eggs used)} = 9 \\text{ eggs} \\]", [True]),
    ("Half of 2 is 2 ÷ 2 = 1 bolt of white fiber.", [True]),
    ("So 12 + 3 = 15, and 15 * 2 = 31.", [True, False]),
    ("y = x + 5 = 15", []),          # variables are never judged
    ("2x + 5 = 15", []),
    ("20% of 50 = 10", []),
    ("10 / 3 = 3.33", [True]),       # rounding to shown decimals
    ("1,200 + 300 = 1,500", [True]),
    ("The answer is: 18", []),
])
def test_arith_check(text, expected):
    assert [r["ok"] for r in check_equations(text)] == expected

def _write_run(root, name, rows):
    d = root / name; d.mkdir(parents=True)
    with open(d / "generations.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return str(d)

def test_compare_runs_counts_and_mcnemar(tmp_path):
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import importlib; cr = importlib.import_module("compare_runs")
    base = [{"example_id": f"e{i}", "dataset": "svamp", "model": "llada_8b", "reference_answer": "1",
             "generation": f"The answer is: {1 if i < 6 else 2}", "num_forward_passes": 256, "wall_time_sec": 10}
            for i in range(10)]                                    # 6/10 right
    meth = [{**r, "generation": f"The answer is: {1 if i in (0,1,2,3,4,6,7,8) else 2}", "num_forward_passes": 60,
             "wall_time_sec": 3} for i, r in enumerate(base)]       # fixes 6,7,8 ; breaks 5 -> 8/10
    b = _write_run(tmp_path, "vanilla_svamp_llada", base)
    m = _write_run(tmp_path, "dapd_svamp_llada", meth)
    res = cr.compare(cr.load_run(b), cr.load_run(m))
    assert (res["n"], res["fixed"], res["broken"]) == (10, 3, 1)
    assert abs(res["diff"] - 0.2) < 1e-9 and res["method_nfe"] == 60
    assert abs(res["p_mcnemar"] - 0.625) < 1e-9                    # exact binomial, n=4, k=1
    assert cr.auto_pairs(str(tmp_path)) == [(b, m)]

def test_error_analysis_categories(tmp_path):
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import importlib; ea = importlib.import_module("error_analysis")
    rows = [
        {"example_id": "ok", "dataset": "gsm8k", "reference_answer": "9", "generation": "13 - 4 = 9\nThe answer is: 9"},
        {"example_id": "slip", "dataset": "gsm8k", "reference_answer": "9", "generation": "16 - 3 = 13\n13 - 4 = 8\nThe answer is: 8"},
        {"example_id": "logic", "dataset": "gsm8k", "reference_answer": "9", "generation": "16 - 4 = 12\nThe answer is: 12"},
        {"example_id": "none", "dataset": "gsm8k", "reference_answer": "9", "generation": ""},
    ]
    summary, ids = ea.analyse_numeric(rows)
    assert summary["wrong_breakdown"] == {"arith_slip": 1, "no_slip": 1, "no_answer": 1}
    assert summary["arith_slip_num_wrong_calcs"] == {"1": 1}
    assert summary["arith_slip_first_error_position"] == {"late": 1}
    loop = "Since the cat is red, the cat is big. " * 4
    pw = [{"example_id": "p1", "dataset": "proofwriter", "reference_answer": "True", "generation": loop,
           "metadata": {"qdep": 2}},
          {"example_id": "p2", "dataset": "proofwriter", "reference_answer": "Unknown",
           "generation": "The answer is: Unknown", "metadata": {"qdep": 0}}]
    s2, ids2 = ea.analyse_label(pw)
    assert s2["looping"] == 1 and s2["no_answer"] == 1 and s2["num_correct"] == 1
    assert s2["accuracy_by_depth"] == {"0": 1.0, "2": 0.0}
