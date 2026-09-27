#!/bin/bash
# Downloads all three datasets. Run from the repo root.
set -e

mkdir -p data/raw

echo "=== GSM8K (HuggingFace Hub) ==="
python -c "from datasets import load_dataset; load_dataset('openai/gsm8k', 'main')"
echo "OK: cached via HF datasets."

echo ""
echo "=== SVAMP (GitHub, arkilpatel/SVAMP) ==="
if [ ! -d "data/raw/SVAMP" ]; then
  git clone --depth 1 https://github.com/arkilpatel/SVAMP.git data/raw/SVAMP
else
  echo "Already cloned, skipping."
fi
test -f data/raw/SVAMP/SVAMP.json && echo "OK: data/raw/SVAMP/SVAMP.json"

echo ""
echo "=== ProofWriter (AllenAI) ==="
# Direct link behind https://allenai.org/data/proofwriter. If it has moved, download the
# zip from that page by hand and unzip it into data/raw/proofwriter/.
PW_URL="https://aristo-data-public.s3.amazonaws.com/proofwriter/proofwriter-dataset-V2020.12.3.zip"
mkdir -p data/raw/proofwriter
if ! find data/raw/proofwriter -path "*OWA/depth-3/meta-test.jsonl" | grep -q .; then
  wget -O data/raw/proofwriter/proofwriter.zip "$PW_URL"
  unzip -q data/raw/proofwriter/proofwriter.zip -d data/raw/proofwriter/
  rm data/raw/proofwriter/proofwriter.zip
fi
PW_FILE=$(find data/raw/proofwriter -path "*OWA/depth-3/meta-test.jsonl" | head -1)
if [ -n "$PW_FILE" ]; then
  echo "OK: $PW_FILE"
else
  echo "ERROR: OWA/depth-3/meta-test.jsonl not found under data/raw/proofwriter/"; exit 1
fi

echo ""
echo "Sanity check: load 5 examples of each."
python - <<'EOF'
import sys; sys.path.insert(0, ".")
from data.loaders import load_dataset_unified
for cfg in ["configs/dataset/gsm8k.yaml", "configs/dataset/svamp.yaml", "configs/dataset/proofwriter_depth3.yaml"]:
    ex = load_dataset_unified(cfg, sample_size=5)
    print(f"{cfg}: {len(ex)} loaded, refs = {[e['reference_answer'] for e in ex]}")
EOF
