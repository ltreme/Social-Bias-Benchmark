#!/bin/bash
#SBATCH --job-name=attrgen-llama2-7b-g16
#SBATCH --output=logs/slurm-attrgen-llama2-7b-g16-%j.out
#SBATCH --nodes=1
#SBATCH --gres=gpu:a6000:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=24:00:00

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"

if [ -f .env ]; then
  set -a; source .env; set +a
fi

if [ -n "${HF_TOKEN:-}" ]; then
  export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
  echo "✅ HuggingFace token configured"
else
  echo "⚠️ No HuggingFace token found. Set HF_TOKEN in .env for gated models."
fi

JOB_ID="${SLURM_JOB_ID:-attrgen-g16}"
LOGFILE="logs/slurm-${JOB_ID}.out"
mkdir -p "$(dirname "$LOGFILE")"

if [ ! -f "venv/bin/activate" ]; then
  echo "❌ venv not found. Create it first." | tee -a "$LOGFILE"
  exit 1
fi
source venv/bin/activate

python apps/benchmark/src/benchmark/cli/run_attr_generation.py \
  --gen-id=16 \
  --llm=hf \
  --hf-model=meta-llama/Llama-2-7b-chat-hf \
  --persist=peewee \
  --batch-size=2 \
  2>&1 | tee -a "$LOGFILE"

