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

# Load .env for secrets
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Paths
JOB_ID="${SLURM_JOB_ID}"
LOGFILE="logs/slurm-${JOB_ID}.out"
TELEMETRY_URL="https://s1335277.eu-nbg-2.betterstackdata.com"
SECRET="$LOGTAIL_SECRET"

# Telemetry logging function
send_to_telemetry() {
    while IFS= read -r line; do
        curl -s -X POST \
            -H 'Content-Type: application/json' \
            -H "Authorization: Bearer $SECRET" \
            -d "{\"dt\":\"$(date -u +'%Y-%m-%d %T UTC')\",\"message\":\"$(echo "$line" | sed 's/"/\\"/g')\"}" \
            "$TELEMETRY_URL" >/dev/null
    done
}

# Activate virtualenv
source venv/bin/activate

# Run the user-provided script, pipe to log + telemetry
"$@" 2>&1 | tee "$LOGFILE" | send_to_telemetry
exit_code=${PIPESTATUS[0]}

# Telegram notification
python app/notification/telegram_notifier.py \
    "${SLURM_JOB_NAME}" \
    "${JOB_ID}" \
    "${exit_code}" \
    "${LOGFILE}"
