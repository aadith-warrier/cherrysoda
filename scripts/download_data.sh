#!/bin/bash
# Downloads all three datasets from their REAL, correct sources.
set -e

mkdir -p data/raw

echo "=== GSM8K (HuggingFace Hub) ==="
python -c "from datasets import load_dataset; load_dataset('openai/gsm8k', 'main')"
echo "OK — cached via HF datasets."

echo ""
echo "=== SVAMP (GitHub, arkilpatel/SVAMP) ==="
if [ ! -d "data/raw/SVAMP" ]; then
  git clone https://github.com/arkilpatel/SVAMP.git data/raw/SVAMP
else
  echo "Already cloned, skipping."
fi
echo "OK — SVAMP.json should be at data/raw/SVAMP/SVAMP.json (verify exact filename in the repo)."

echo ""
echo "=== ProofWriter (AllenAI, manual download) ==="
echo "ProofWriter is NOT scriptable — AllenAI's page requires visiting"
echo "  https://allenai.org/data/proofwriter"
echo "and downloading the dataset zip manually (it's a direct download link on that page)."
echo "Once downloaded, unzip it into: data/raw/proofwriter/"
echo "Then confirm the depth-3 split files exist under that directory before running loaders."

echo ""
echo "Done. Remember: SVAMP and ProofWriter are NOT HuggingFace-hosted —"
echo "double check file paths in configs/dataset/svamp.yaml and proofwriter_depth3.yaml"
echo "match what actually landed in data/raw/ after this script + the manual ProofWriter download."
