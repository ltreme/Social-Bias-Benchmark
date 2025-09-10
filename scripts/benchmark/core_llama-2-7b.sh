#!/bin/bash
#SBATCH --job-name=core-llama-2-7b
#SBATCH --output=logs/slurm-core-llama-2-7b-%j.out
#SBATCH --nodes=1
#SBATCH --gres=gpu:a6000:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=24:00:00

set -euo pipefail

# Ensure we run from submission directory (if set by Slurm)
cd "${SLURM_SUBMIT_DIR:-$PWD}"

# Load secrets from .env if available
if [ -f .env ]; then
  set -a; source .env; set +a
fi

# Ensure HuggingFace token is available
if [ -n "${HF_TOKEN:-}" ]; then
  export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
  echo "✅ HuggingFace token configured"
else
  echo "⚠️ No HuggingFace token found. Gated models may not be accessible."
  echo "Please set HF_TOKEN in your .env file for access to gated models like Llama."
fi

# Define variables (nach RUN_ID)
JOB_ID="${SLURM_JOB_ID:-${RUN_ID:-local}}"
LOGFILE="logs/slurm-${JOB_ID}.out"
TELEMETRY_URL="https://s1335277.eu-nbg-2.betterstackdata.com"
TELEMETRY_SECRET="${LOGTAIL_SECRET:-}"

# Ensure logs directory exists
mkdir -p "$(dirname "$LOGFILE")"

# Minimal telemetry function (no-op if secret/url missing)
send_to_telemetry() {
  if [ -z "${TELEMETRY_SECRET:-}" ] || [ -z "${TELEMETRY_URL:-}" ]; then
    cat >/dev/null
    return 0
  fi
  while IFS= read -r line; do
    curl -s -X POST \
      -H 'Content-Type: application/json' \
      -H "Authorization: Bearer $TELEMETRY_SECRET" \
      -d "{\"dt\":\"$(date -u +'%Y-%m-%d %T UTC')\",\"message\":\"$(echo "$line" | sed 's/\"/\\\"/g')\"}" \
      "$TELEMETRY_URL" >/dev/null || true
  done
}

# Activate virtualenv
if [ ! -d "venv" ]; then
  echo "❌ Virtual environment not found. Please run 'python -m venv venv' first." | tee -a "$LOGFILE" | send_to_telemetry
  exit 1
fi
if [ ! -f "venv/bin/activate" ]; then
  echo "❌ Virtual environment activation script not found. Please check your setup." | tee -a "$LOGFILE" | send_to_telemetry
  exit 1
fi
if ! source venv/bin/activate; then
  echo "❌ Failed to activate virtual environment." | tee -a "$LOGFILE" | send_to_telemetry
  exit 1
fi

# Launch benchmark
python apps/benchmark/src/benchmark/cli/run_core_benchmark.py \
  --gen-id=11 \
  --llm=hf \
  --hf-model=meta-llama/Llama-2-7b-chat-hf \
  --persist=peewee \
  --batch-size=2 \
  2>&1 | tee -a "$LOGFILE" | send_to_telemetry
