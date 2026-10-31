#!/usr/bin/env bash
# Dream, main method + answer check + ban, all 600 ProofWriter questions, so the main table's Dream ProofWriter
# cell uses the same questions as every other row. Questions 0-299 are taken from the finished n=300 run
# (same settings); only 300-599 are computed (~2 h).
#
#   bash run_answer_check5.sh            # GPU cuda:0
#
# When it finishes, send results/answer_check_report5.md (also printed). Safe to re-run.
set -uo pipefail
cd "$(dirname "$0")"
export PYTHONNOUSERSITE=1
DEVICE="${1:-cuda:0}"
exec > >(tee -a logs/run_answer_check5.log) 2>&1
say() { echo; echo "=== $(date '+%F %T')  $*"; }
PY="pixi run python"
SRC=graph_sched_ans_proofwriter_d3_dream_n300
RID=graph_sched_ans_proofwriter_d3_dream_n600
REPORT=results/answer_check_report5.md

[ -f "logs/${SRC}/generations.jsonl" ] || { echo "missing logs/${SRC}/generations.jsonl"; exit 1; }
mkdir -p "logs/${RID}"
if [ ! -f "logs/${RID}/generations.jsonl" ]; then
  cp "logs/${SRC}/generations.jsonl" "logs/${RID}/generations.jsonl"
  say "seeded ${RID} with the $(wc -l < logs/${SRC}/generations.jsonl) finished questions of ${SRC}"
fi

say "run $RID"
$PY -m scripts.run_graph_method --config "configs/run/${RID}.yaml" --device "$DEVICE" 2>&1 \
  | tee -a "logs/${RID}.stdout.log" \
  | awk '/^\[[^]]*\] [0-9]+\/[0-9]+ /{split($2,a,"/"); if (a[1]%50==0 || a[1]==a[2]) print; next} {print}' \
  || { echo "!!! $RID FAILED (see logs/${RID}.stdout.log)"; exit 1; }

{
  echo "# Dream ProofWriter, main method + answer check + ban, all 600 ($(date '+%F %T')), repo $(git rev-parse --short HEAD 2>/dev/null)"
  echo; cat "logs/${RID}/summary.md"
  echo; echo "## design (0-149) vs held-out (150-599)"
  $PY -m scripts.split_report --split 150 --names "graph+sched+check+ban" --runs "logs/${RID}" 2>&1
  echo; echo "## model-free rule relabel vs the method"; echo '```'
  $PY -m scripts.answer_rule_baseline "logs/${RID}" 2>&1
  echo '```'
} > "$REPORT" 2>&1
cat "$REPORT"
say "done. Send $REPORT"
