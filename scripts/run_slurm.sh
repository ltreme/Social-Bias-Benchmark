#!/bin/bash
#SBATCH --job-name=bias-benchmarks
#SBATCH --output=logs/slurm-%j.out
#SBATCH --nodes=1
#SBATCH --gres=gpu:a6000:2 # Behalten Sie dies vorerst bei 1 GPU
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=01:00:00

# Set working directory
cd "$SLURM_SUBMIT_DIR"

# Load secrets from .env if available
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Ensure HuggingFace token is available
if [ -n "$HF_TOKEN" ]; then
    export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
    echo "✅ HuggingFace token configured"
else
    echo "⚠️ No HuggingFace token found. Gated models may not be accessible."
    echo "Please set HF_TOKEN in your .env file for access to gated models like Llama."
fi

# Define variables
JOB_ID="${SLURM_JOB_ID}"
LOGFILE="logs/slurm-${JOB_ID}.out"
TELEMETRY_URL="https://s1335277.eu-nbg-2.betterstackdata.com"
TELEMETRY_SECRET="$LOGTAIL_SECRET"
DROPBOX_SECRET="$DROPBOX_TOKEN"

# Make sure logs dir exists (if not SLURM-controlled)
mkdir -p "$(dirname "$LOGFILE")"

# Define telemetry function
send_to_telemetry() {
    while IFS= read -r line; do
        curl -s -X POST \
            -H 'Content-Type: application/json' \
            -H "Authorization: Bearer $TELEMETRY_SECRET" \
            -d "{\"dt\":\"$(date -u +'%Y-%m-%d %T UTC')\",\"message\":\"$(echo "$line" | sed 's/"/\\"/g')\"}" \
            "$TELEMETRY_URL" >/dev/null
    done
}

# Activate virtualenv
source venv/bin/activate
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

# GPU Setup and Diagnostics
echo "🔧 Initial GPU Status (direkt nach Aktivierung venv):" | tee -a "$LOGFILE" | send_to_telemetry
echo "CUDA_VISIBLE_DEVICES (initial): $CUDA_VISIBLE_DEVICES" | tee -a "$LOGFILE" | send_to_telemetry
echo "SLURM_JOB_GPUS: $SLURM_JOB_GPUS" | tee -a "$LOGFILE" | send_to_telemetry
echo "SLURM_GPUS_ON_NODE: $SLURM_GPUS_ON_NODE" | tee -a "$LOGFILE" | send_to_telemetry
echo "SLURM_STEP_GPUS: $SLURM_STEP_GPUS" | tee -a "$LOGFILE" | send_to_telemetry
echo "SLURM_LOCALID: $SLURM_LOCALID" | tee -a "$LOGFILE" | send_to_telemetry
echo "SLURMD_NODENAME: $SLURMD_NODENAME" | tee -a "$LOGFILE" | send_to_telemetry
echo "nvidia-smi Output:" | tee -a "$LOGFILE" | send_to_telemetry
nvidia-smi 2>&1 | tee -a "$LOGFILE" | send_to_telemetry

# # Run CUDA environment fix (Vorerst auskommentieren, um die Basis-Slurm-Umgebung zu testen)
# echo "🛠️ Running CUDA environment fix..." | tee -a "$LOGFILE" | send_to_telemetry
# bash scripts/fix_cuda_environment.sh 2>&1 | tee -a "$LOGFILE" | send_to_telemetry

# # Source the generated CUDA environment (Vorerst auskommentieren)
# if [ -f "cuda_env.sh" ]; then
#     source cuda_env.sh
#     echo "✅ Loaded CUDA environment from fix script" | tee -a "$LOGFILE" | send_to_telemetry
# else
#     echo "⚠️ No cuda_env.sh found, using default configuration" | tee -a "$LOGFILE" | send_to_telemetry
# fi

echo "🔍 GPU Configuration vor Python-Diagnose (nach potenziellen Skripten, falls diese aktiviert wären):" | tee -a "$LOGFILE" | send_to_telemetry
echo "CUDA_VISIBLE_DEVICES (vor Python): $CUDA_VISIBLE_DEVICES" | tee -a "$LOGFILE" | send_to_telemetry
nvidia-smi 2>&1 | tee -a "$LOGFILE" | send_to_telemetry # Erneut ausgeben, falls sich durch obige Skripte etwas geändert haben könnte

# Enable detailed CUDA device-side assertions
export TORCH_USE_CUDA_DSA=1
echo "TORCH_USE_CUDA_DSA in bash is set to: $TORCH_USE_CUDA_DSA" | tee -a "$LOGFILE" | send_to_telemetry

# Final Python GPU diagnostics
echo "🐍 Python GPU Detection:" | tee -a "$LOGFILE" | send_to_telemetry
python scripts/gpu_diag.py 2>&1 | tee -a "$LOGFILE" | send_to_telemetry

# {
#   echo "🚀 Launching benchmark command: $*" | tee -a "$LOGFILE" | send_to_telemetry
#   # Call benchmark script (e.g. accelerate launch ...) directly
#   bash "$@"
# } 2>&1 | tee -a "$LOGFILE" | send_to_telemetry # Diesen Block für den Diagnoselauf auskommentieren

exit_code=${PIPESTATUS[0]} # Nimmt den Exit-Code des Python-Skripts

# Upload log to Dropbox (if token exists)
if [ -n "$DROPBOX_SECRET" ]; then
    DROPBOX_PATH="/slurm_logs/$(basename "$LOGFILE")"
    status=$(curl -s -w "%{http_code}" -o /dev/null \
    -X POST https://content.dropboxapi.com/2/files/upload \
    --header "Authorization: Bearer $DROPBOX_SECRET" \
    --header "Dropbox-API-Arg: {\"path\": \"$DROPBOX_PATH\",\"mode\": \"add\",\"autorename\": true,\"mute\": false}" \
    --header "Content-Type: application/octet-stream" \
    --data-binary @"$LOGFILE")

    if [ "$status" -eq 200 ]; then
        echo "✅ Log uploaded to Dropbox: $DROPBOX_PATH" | tee -a "$LOGFILE" | send_to_telemetry
    else
        echo "❌ Dropbox upload failed (HTTP $status)" | tee -a "$LOGFILE" | send_to_telemetry
    fi

else
    echo "⚠️  No Dropbox token found. Skipping upload." | tee -a "$LOGFILE" | send_to_telemetry
fi

# Telegram notification
python app/notification/telegram_notifier.py \
    "${SLURM_JOB_NAME}" \
    "${JOB_ID}" \
    "${exit_code}" \
    "${LOGFILE}"
