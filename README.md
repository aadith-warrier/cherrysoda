# Graph-Guided Reasoning and Refinement in Diffusion Language Models

CherrySoda — Sriharini Margapuri, Arkaprava Gaine, Aadith Warrier, Tarun R

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
configs/          # model / dataset / run configs (YAML, single source of truth per run)
src/models/       # base DLM wrappers (Track A) — implements BaseDLMWrapper interface
src/graph/        # dependency graph extraction (Track B)
src/verify/       # deterministic + NLI verifiers (Track C)
src/schedule/     # dependency-aware denoising scheduler (Track D)
src/correct/      # subgraph identification + localized remasking (Track D/B)
baselines/        # vanilla, correction baselines, scheduling baselines (Track A)
data/             # dataset loaders, unified schema output
scripts/          # entrypoints (run_baseline.py, download_data.sh, timing check)
logs/             # per-run outputs (gitignored — see below)
```

## Running a baseline

```bash
python scripts/run_baseline.py --config configs/run/prelim_vanilla_gsm8k_{model}.yaml
```

Every run is defined entirely by its config file under `configs/run/`. Do not
hand-edit Python to change model/dataset/baseline combos — add a new run config
instead, so every run stays reproducible from git history alone.

## First-time setup checklist (Week 1)

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

## Status (updated per mid-sem submission)

| Component | Status | Owner |
|---|---|---|
| Base DLM (LLaDA) running + intermediate states confirmed | TODO | Track A |
| Second base DLM (optional) | TODO | Track A |
| Dataset loaders (GSM8K/SVAMP/ProofWriter) | TODO | Track A |
| Vanilla baseline | TODO | Track A |
| Remask-Don't-Replace baseline | TODO | Track A |
| DAPD scheduling baseline | TODO | Track A |
| RemeDi / ProSeCo baselines | TODO | Track A |
| Oracle baseline (GSM8K/SVAMP) | TODO | Track A |
| Graph extraction (Tiers 1-3) | TODO | Track B |
| Gold graph annotation | TODO | Track B |
| Deterministic verifier | TODO | Track C |
| NLI verifier + calibration | TODO | Track C |
| Dependency-aware scheduler | TODO | Track D |
| Subgraph correction + remasking | TODO | Track D |

## Access

Repo is [public / TA mentors granted access — update before mid-sem deadline].
