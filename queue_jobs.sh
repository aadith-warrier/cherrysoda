#!/bin/bash
# 1) zero-shot LLaDA graph+scheduler, 300 problems   2) rest of DAPD LLaDA (resumes)
cd ~/cherrysoda
mkdir -p logs/_nohup

free_gpu() {
  nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits \
    | awk -F', ' '$2 < 2000 {print $1; exit}'
}

run_job() {    # $1 = name, $2 = command with @GPU@
  while true; do
    g=$(free_gpu)
    if [ -n "$g" ]; then break; fi
    sleep 60
  done
  cmd=${2//@GPU@/$g}
  echo "[$(date +%H:%M)] starting $1 on cuda:$g"
  bash -c "$cmd" >> logs/_nohup/$1.log 2>&1
  echo "[$(date +%H:%M)] finished $1"
  sleep 20
}

run_job zs_300    "python -m scripts.run_graph_method --config configs/run/graph_sched_gsm8k_llada_zs.yaml --device cuda:@GPU@"
run_job dapd_llada "python -m scripts.run_baseline --config configs/run/dapd_gsm8k_llada_onebl.yaml --device cuda:@GPU@ --resume --no_wandb"
echo "[$(date +%H:%M)] queue done"
