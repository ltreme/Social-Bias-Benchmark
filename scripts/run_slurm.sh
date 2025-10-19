#!/bin/bash
#SBATCH --job-name=bias-benchmarks
#SBATCH --output=logs/slurm-%j.out
#SBATCH --nodes=1
#SBATCH --gres=gpu:a6000:2 # Behalten Sie dies vorerst bei 2 GPUs
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=24:00:00

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

# RUN_ID erzeugen (bevor wir irgendwas starten)
if [ -z "${RUN_ID:-}" ]; then
    TS=$(date -u +%Y%m%dT%H%M%SZ)
    # Nutze Slurm Job ID (falls vorhanden) plus kurzen Random Suffix
    RAND=$(head -c4 /dev/urandom | LC_ALL=C tr -dc 'a-z0-9' | head -c4 || echo rnd)
    if [ -n "${SLURM_JOB_ID:-}" ]; then
        RUN_ID="${SLURM_JOB_ID}_${TS}_${RAND}"
    else
        RUN_ID="local_${TS}_${RAND}"
    fi
    export RUN_ID
fi

# Optionaler Prefix für Jobname
DEFAULT_JOB_NAME="bias-benchmarks"
USER_JOB_NAME=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --job-name|-J)
            shift
            USER_JOB_NAME="$1"; shift || true ;;
        *)
            # Stop parsing custom flags; rest sind Skript + Args
            break ;;
    esac
done

if [ -n "$USER_JOB_NAME" ]; then
    export SLURM_JOB_NAME="${DEFAULT_JOB_NAME}-${USER_JOB_NAME}-${RUN_ID}" || true
else
    export SLURM_JOB_NAME="${DEFAULT_JOB_NAME}-${RUN_ID}" || true
fi

# Define variables (nach RUN_ID)
JOB_ID="${SLURM_JOB_ID:-$RUN_ID}"
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
echo "🔧 Initial GPU Status (RUN_ID=$RUN_ID):" | tee -a "$LOGFILE" | send_to_telemetry
echo "CUDA_VISIBLE_DEVICES (initial by Slurm): $CUDA_VISIBLE_DEVICES" | tee -a "$LOGFILE" | send_to_telemetry
echo "SLURM_JOB_GPUS: $SLURM_JOB_GPUS" | tee -a "$LOGFILE" | send_to_telemetry
echo "SLURM_GPUS_ON_NODE: $SLURM_GPUS_ON_NODE" | tee -a "$LOGFILE" | send_to_telemetry
echo "SLURM_STEP_GPUS: $SLURM_STEP_GPUS" | tee -a "$LOGFILE" | send_to_telemetry
echo "SLURM_LOCALID: $SLURM_LOCALID" | tee -a "$LOGFILE" | send_to_telemetry
echo "SLURMD_NODENAME: $SLURMD_NODENAME" | tee -a "$LOGFILE" | send_to_telemetry
echo "nvidia-smi Output:" | tee -a "$LOGFILE" | send_to_telemetry
nvidia-smi 2>&1 | tee -a "$LOGFILE" | send_to_telemetry

# WORKAROUND: Manually set CUDA_VISIBLE_DEVICES to use only healthy GPUs
# Based on slurm-2204.out, nvidia-smi physical GPUs 1 and 3 are healthy.
# Slurm set CUDA_VISIBLE_DEVICES=0,1,2,3.
# So we want to use the 2nd and 4th device from that list, which are indices 1 and 3.
export CUDA_VISIBLE_DEVICES=1
echo "CUDA_VISIBLE_DEVICES (für PyTorch): $CUDA_VISIBLE_DEVICES" | tee -a "$LOGFILE" | send_to_telemetry

# # Run CUDA environment fix (Vorerst auskommentieren)
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
echo "CUDA_VISIBLE_DEVICES (vor Python, nach Workaround): $CUDA_VISIBLE_DEVICES" | tee -a "$LOGFILE" | send_to_telemetry
nvidia-smi 2>&1 | tee -a "$LOGFILE" | send_to_telemetry # Erneut ausgeben

# Enable detailed CUDA device-side assertions
export TORCH_USE_CUDA_DSA=1
echo "TORCH_USE_CUDA_DSA in bash is set to: $TORCH_USE_CUDA_DSA" | tee -a "$LOGFILE" | send_to_telemetry

# Final Python GPU diagnostics
echo "🐍 Python GPU Detection:" | tee -a "$LOGFILE" | send_to_telemetry
python scripts/gpu_diag.py 2>&1 | tee -a "$LOGFILE" | send_to_telemetry

if [ $# -lt 1 ]; then
    echo "❌ Kein Zielskript übergeben. Aufruf: scripts/run_slurm.sh <script> [args...]" | tee -a "$LOGFILE" | send_to_telemetry
    exit 2
fi

TARGET_SCRIPT="$1"; shift
if [ ! -f "$TARGET_SCRIPT" ]; then
    echo "❌ Zielskript nicht gefunden: $TARGET_SCRIPT" | tee -a "$LOGFILE" | send_to_telemetry
    exit 3
fi
if [ ! -x "$TARGET_SCRIPT" ]; then
    # Versuchen ausführbar zu machen
    chmod +x "$TARGET_SCRIPT" 2>/dev/null || true
fi

{
echo "🚀 Launching benchmark command (RUN_ID=$RUN_ID): $TARGET_SCRIPT $*" | tee -a "$LOGFILE" | send_to_telemetry
export RUN_ID  # sicherstellen dass Subskripte es sehen
   bash "$TARGET_SCRIPT" "$@"
} 2>&1 | tee -a "$LOGFILE" | send_to_telemetry # Diesen Block für den Diagnoselauf auskommentieren

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
