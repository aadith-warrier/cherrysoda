# Graph-Guided Reasoning and Refinement in Diffusion Language Models

CherrySoda

## Setup (conda)

```bash
conda create -n cherrysoda python=3.10 -y
conda activate cherrysoda
conda install pytorch pytorch-cuda=12.4 -c pytorch -c nvidia -y
pip install -r requirements.txt
bash scripts/download_data.sh
```

Note: SVAMP and ProofWriter are **not** HuggingFace-hosted — `download_data.sh`
clones SVAMP directly from github.com/arkilpatel/SVAMP, and ProofWriter must be
downloaded manually from https://allenai.org/data/proofwriter (script prints
instructions). Only GSM8K comes via `datasets.load_dataset`.

Verify GPU access:
```bash
nvidia-smi
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"
```

## Base models

- **LLaDA-8B-Instruct**: `GSAI-ML/LLaDA-8B-Instruct` — the original from-scratch
  trained base model. NOT `d3LLM/d3LLM_LLaDA` (that's a speed-distilled
  fine-tune of this same base, optimized for fast inference — different
  denoising behavior, not what we want for the core experiments).
- **Dream-7B-Instruct**: `Dream-org/Dream-v0-Instruct-7B` — AR-adapted (from
  Qwen2.5-7B) diffusion model, architecturally distinct from LLaDA's
  from-scratch approach. Optional second base model.

## Repo structure

```
.
├── baselines/                         # Baseline implementations.
│   ├── temporal_vote.py               # Temporal voting baseline.
│   └── vanilla.py                     # Vanilla generation baseline.
├── configs/                           # Reproducible YAML experiment configuration.
│   ├── dataset/                       # GSM8K, SVAMP, and ProofWriter settings.
│   │   ├── gsm8k.yaml
│   │   ├── proofwriter_depth3.yaml
│   │   └── svamp.yaml
│   ├── model/                         # Base and fine-tuned model settings.
│   │   ├── dapd_dream.yaml
│   │   ├── dapd_llada.yaml
│   │   ├── dream_7b.yaml
│   │   ├── llada_8b.yaml
│   │   ├── proseco_llada_sft.yaml
│   │   ├── proseco_sampler_llada_instruct.yaml
│   │   ├── remedi_instruct.yaml
│   │   └── remedi_rl.yaml
│   └── run/                           # Model, dataset, and method combinations.
│       ├── dapd_gsm8k_dream.yaml
│       ├── dapd_gsm8k_llada.yaml
│       ├── dapd_proofwriter_d3_dream.yaml
│       ├── dapd_proofwriter_d3_llada.yaml
│       ├── dapd_svamp_dream.yaml
│       ├── dapd_svamp_llada.yaml
│       ├── proseco_gsm8k.yaml
│       ├── proseco_nocorr_gsm8k.yaml
│       ├── proseco_nocorr_proofwriter_d3.yaml
│       ├── proseco_nocorr_svamp.yaml
│       ├── proseco_proofwriter_d3.yaml
│       ├── proseco_sampler_llada_gsm8k.yaml
│       ├── proseco_sampler_llada_proofwriter_d3.yaml
│       ├── proseco_sampler_llada_svamp.yaml
│       ├── proseco_svamp.yaml
│       ├── remedi_rl_gsm8k.yaml
│       ├── remedi_rl_proofwriter_d3.yaml
│       ├── remedi_rl_svamp.yaml
│       ├── vanilla_gsm8k_dream.yaml
│       ├── vanilla_gsm8k_llada.yaml
│       ├── vanilla_proofwriter_d3_dream.yaml
│       ├── vanilla_proofwriter_d3_llada.yaml
│       ├── vanilla_svamp_dream.yaml
│       ├── vanilla_svamp_llada.yaml
│       ├── vote_gsm8k_dream.yaml
│       ├── vote_gsm8k_llada.yaml
│       ├── vote_proofwriter_d3_dream.yaml
│       ├── vote_proofwriter_d3_llada.yaml
│       └── vote_svamp_dream.yaml
├── data/                              # Dataset loading and normalization.
│   ├── __init__.py
│   └── loaders.py                     # Unified dataset loader interface.
├── scripts/                           # Command-line experiment utilities.
│   ├── compare_generations.py         # Compare saved generations.
│   ├── download_data.sh               # Download or describe required datasets.
│   ├── inspect_generations.py         # Inspect generated answers.
│   ├── probe_short_answers.py         # Probe short-answer generation behavior.
│   ├── run_baseline.py                # Run a configured baseline experiment.
│   ├── score_accuracy.py              # Score generated answers.
│   ├── setup_third_party.sh           # Set up external baseline repositories.
│   └── time_single_example.py         # Measure one-example model runtime.
├── src/                               # Core library code.
│   ├── eval/                          # Evaluation and scoring utilities.
│   │   ├── __init__.py
│   │   └── scoring.py
│   ├── methods/                       # Correction and refinement methods.
│   │   ├── __init__.py
│   │   └── correction.py
│   └── models/                        # Base DLM wrappers and model registry.
│       ├── __init__.py
│       ├── base.py
│       ├── dapd_wrapper.py
│       ├── dream_wrapper.py
│       ├── llada_wrapper.py
│       ├── model_registry.py
│       ├── proseco_wrapper.py
│       └── remedi_wrapper.py
├── tests/                             # Unit and pipeline tests.
│   ├── fake_wrapper.py                # Lightweight model wrapper for tests.
│   └── test_pipeline.py               # End-to-end pipeline coverage.
├── .gitignore                         # Generated, local, and external files to ignore.
├── README.md                          # Project setup, usage, and experiment notes.
├── requirements.txt                   # Python dependencies.
└── log.txt                            # Small local log file kept in the repository.
```

The following directories are intentionally omitted from this overview because
they are generated, downloaded, vendored, or otherwise too large for the source
tree: `logs/`, `wandb/`, `data/raw/`, `third_party/`, `.git/`, `.pytest_cache/`,
and Python `__pycache__/` directories.

## Running a baseline

```bash
python scripts/run_baseline.py --config configs/run/prelim_vanilla_gsm8k_{model}.yaml
```

Every run is defined entirely by its config file under `configs/run/`. Do not
hand-edit Python to change model/dataset/baseline combos — add a new run config
instead, so every run stays reproducible from git history alone.

## First-time setup checklist

1. `bash scripts/download_data.sh` — confirm all 3 datasets download cleanly;
   fix `hf_repo_id` in `configs/dataset/*.yaml` if a mirror has moved.
2. Fill in the real `hf_repo_id` for the base model in `configs/model/llada_8b.yaml`.
3. **Run `scripts/time_single_example.py` FIRST**, before any bulk runs:
   ```bash
   python scripts/time_single_example.py --model configs/model/llada_8b.yaml --dataset configs/dataset/gsm8k.yaml
   ```
   This confirms (a) the model loads and generates correctly, (b) intermediate
   denoising states can be extracted (required for Track D), and (c) gives you
   real per-example timing to size prelim sample counts.

## Experiment tracking

WandB project: `cherrysoda` — [link once created]

HuggingFace models/datasets used: [add links here once confirmed]

## Status

| Component 
|---
| Base DLM (LLaDA) running + intermediate states confirmed 
| Second base DLM (optional) 
| Dataset loaders (GSM8K/SVAMP/ProofWriter) 
| Vanilla baseline 
| Remask-Don't-Replace baseline 
| DAPD scheduling baseline 
| RemeDi / ProSeCo baselines 
| Oracle baseline (GSM8K/SVAMP) 
| Gold graph annotation 
| Deterministic verifier
| NLI verifier + calibration
| Dependency-aware scheduler
| Subgraph correction + remasking 