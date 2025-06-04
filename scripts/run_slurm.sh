#!/bin/bash
#SBATCH --job-name=bias-benchmarks
#SBATCH --output=logs/slurm-%j.out
#SBATCH --nodes=1
#SBATCH --gres=gpu:a6000:6
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=01:00:00

# Set working directory
cd "$SLURM_SUBMIT_DIR"

# Load secrets from .env if available
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
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

export CUDA_VISIBLE_DEVICES=0,1,2,3,4,5

{
  echo "✅ CUDA_VISIBLE_DEVICES: $CUDA_VISIBLE_DEVICES"
  nvidia-smi
  echo "Launching benchmark command: $*"
  
  # Call benchmark script (e.g. accelerate launch ...) directly
  bash "$@"
} 2>&1 | tee -a "$LOGFILE" | send_to_telemetry

exit_code=${PIPESTATUS[0]}


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
