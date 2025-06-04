#!/bin/bash
#SBATCH --job-name=bias-benchmarks-single
#SBATCH --output=logs/slurm-single-%j.out
#SBATCH --nodes=1
#SBATCH --gres=gpu:a6000:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=01:00:00

echo "🚀 Single GPU SLURM Job (Fallback Strategy)"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURMD_NODENAME"

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
fi

# Define variables
JOB_ID="${SLURM_JOB_ID}"
LOGFILE="logs/slurm-single-${JOB_ID}.out"
TELEMETRY_URL="https://s1335277.eu-nbg-2.betterstackdata.com"
TELEMETRY_SECRET="$LOGTAIL_SECRET"
DROPBOX_SECRET="$DROPBOX_TOKEN"

# Make sure logs dir exists
mkdir -p "$(dirname "$LOGFILE")"

# Define telemetry function
send_to_telemetry() {
    while IFS= read -r line; do
        curl -s -X POST \
            -H 'Content-Type: application/json' \
            -H "Authorization: Bearer $TELEMETRY_SECRET" \
            -d "{\"dt\":\"$(date -u +'%Y-%m-%d %T UTC')\",\"message\":\"$(echo "$line" | sed 's/"/\\"/g')\"}" \
            "$TELEMETRY_URL" >/dev/null 2>&1 || true
    done
}

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run 'python -m venv venv' first." | tee -a "$LOGFILE" | send_to_telemetry
    exit 1
fi

source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "❌ Failed to activate virtual environment." | tee -a "$LOGFILE" | send_to_telemetry
    exit 1
fi

# GPU Diagnostics
echo "🔍 SLURM GPU Assignment:"
echo "SLURM_GPUS_ON_NODE: ${SLURM_GPUS_ON_NODE:-'Not set'}"
echo "SLURM_JOB_GPUS: ${SLURM_JOB_GPUS:-'Not set'}"

echo "🔧 Hardware GPU Status:"
nvidia-smi --query-gpu=index,name,memory.total,temperature.gpu,pstate --format=csv,noheader,nounits

# Simple single GPU setup
if [[ -n "$SLURM_JOB_GPUS" ]]; then
    # Use first assigned GPU
    first_gpu=$(echo "$SLURM_JOB_GPUS" | cut -d',' -f1)
    export CUDA_VISIBLE_DEVICES="$first_gpu"
    echo "🎯 Using SLURM assigned GPU: $first_gpu"
else
    # Fallback to auto-detection of working GPU
    echo "🔍 Auto-detecting working GPU..."
    for gpu_id in 1 2 3; do
        gpu_status=$(nvidia-smi --query-gpu=pstate --format=csv,noheader,nounits --id=$gpu_id 2>/dev/null)
        if [[ "$gpu_status" != *"[GPU requires reset]"* ]] && [[ -n "$gpu_status" ]]; then
            export CUDA_VISIBLE_DEVICES="$gpu_id"
            echo "✅ Found working GPU: $gpu_id"
            break
        fi
    done
fi

echo "CUDA_VISIBLE_DEVICES: $CUDA_VISIBLE_DEVICES"

# Test CUDA functionality
echo "🧪 Testing CUDA setup..."
python3 -c "
import torch
import os

print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'Device count: {torch.cuda.device_count()}')
print(f'CUDA_VISIBLE_DEVICES: {os.environ.get(\"CUDA_VISIBLE_DEVICES\", \"Not set\")}')

if torch.cuda.is_available() and torch.cuda.device_count() > 0:
    device = torch.device('cuda:0')
    props = torch.cuda.get_device_properties(device)
    print(f'GPU 0: {props.name} - {props.total_memory / 1024**3:.1f}GB')
    
    # Test tensor operations
    test = torch.randn(1000, 1000, device=device)
    result = torch.matmul(test, test.T)
    print('✅ CUDA operations successful')
else:
    print('❌ No CUDA GPUs available')
    import sys
    sys.exit(1)
" | tee -a "$LOGFILE" | send_to_telemetry

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "❌ CUDA test failed. Exiting." | tee -a "$LOGFILE" | send_to_telemetry
    exit 1
fi

# Create single GPU accelerate config
echo "📝 Creating single GPU configuration..."
cat > accelerate_config_single.yaml << EOF
compute_environment: LOCAL_MACHINE
deepspeed_config: {}
distributed_type: NO
downcast_bf16: 'no'
machine_rank: 0
main_training_function: main
mixed_precision: fp16
num_machines: 1
num_processes: 1
tpu_env: []
tpu_use_cluster: false
tpu_use_sudo: false
use_cpu: false
EOF

echo "📋 Single GPU Config:"
cat accelerate_config_single.yaml

{
  echo "🚀 Launching single GPU benchmark: $*"
  
  # Override config for single GPU
  cp accelerate_config_single.yaml accelerate_config.yaml
  
  # Run benchmark
  bash "$@"
} 2>&1 | tee -a "$LOGFILE" | send_to_telemetry

exit_code=${PIPESTATUS[0]}

# Upload log to Dropbox
if [ -n "$DROPBOX_SECRET" ]; then
    DROPBOX_PATH="/slurm_logs/$(basename "$LOGFILE")"
    status=$(curl -s -w "%{http_code}" -o /dev/null \
    -X POST https://content.dropboxapi.com/2/files/upload \
    --header "Authorization: Bearer $DROPBOX_SECRET" \
    --header "Dropbox-API-Arg: {\"path\": \"$DROPBOX_PATH\",\"mode\": \"add\",\"autorename\": true,\"mute\": false}" \
    --header "Content-Type: application/octet-stream" \
    --data-binary @"$LOGFILE" 2>/dev/null || true)

    if [ "$status" -eq 200 ]; then
        echo "✅ Log uploaded to Dropbox: $DROPBOX_PATH" | tee -a "$LOGFILE" | send_to_telemetry
    fi
fi

# Telegram notification
python app/notification/telegram_notifier.py \
    "${SLURM_JOB_NAME}" \
    "${JOB_ID}" \
    "${exit_code}" \
    "${LOGFILE}" 2>/dev/null || true

echo "🏁 Single GPU job completed with exit code: $exit_code"
