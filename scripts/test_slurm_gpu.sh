#!/bin/bash
#SBATCH --job-name=gpu-test
#SBATCH --output=logs/gpu-test-%j.out
#SBATCH --nodes=1
#SBATCH --gres=gpu:a6000:2
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:10:00

echo "🧪 SLURM GPU Test Job - Running on Cluster"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURMD_NODENAME"

# Set working directory
cd "$SLURM_SUBMIT_DIR"

# Load environment
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Activate virtual environment
source venv/bin/activate

# GPU Configuration
export CUDA_VISIBLE_DEVICES=1,3
echo "CUDA_VISIBLE_DEVICES: $CUDA_VISIBLE_DEVICES"

echo "=== SLURM GPU Environment ==="
echo "SLURM_GPUS_ON_NODE: $SLURM_GPUS_ON_NODE"
echo "SLURM_GPUS: $SLURM_GPUS"
echo "SLURM_GPU_BIND: $SLURM_GPU_BIND"

echo "=== Hardware GPU Status ==="
nvidia-smi --list-gpus
nvidia-smi --query-gpu=index,name,memory.total,temperature.gpu,pstate,memory.used --format=csv,noheader,nounits

echo "=== Python/PyTorch GPU Detection ==="
python3 -c "
import torch
import os

print(f'🐍 PyTorch version: {torch.__version__}')
print(f'🔥 CUDA available: {torch.cuda.is_available()}')
print(f'🔢 CUDA version: {torch.version.cuda if torch.cuda.is_available() else \"N/A\"}')
print(f'📊 Device count: {torch.cuda.device_count()}')
print(f'🎯 CUDA_VISIBLE_DEVICES: {os.environ.get(\"CUDA_VISIBLE_DEVICES\", \"Not set\")}')

if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        device = torch.device(f'cuda:{i}')
        props = torch.cuda.get_device_properties(device)
        print(f'  GPU {i}: {props.name} - {props.total_memory / 1024**3:.1f}GB')
        
        # Test tensor operations
        try:
            test_tensor = torch.randn(1000, 1000, device=device)
            result = torch.matmul(test_tensor, test_tensor.T)
            print(f'    ✅ Tensor operations successful on GPU {i}')
        except Exception as e:
            print(f'    ❌ Tensor operations failed on GPU {i}: {e}')
else:
    print('❌ No CUDA GPUs detected by PyTorch')
"

echo "=== Accelerate Configuration Test ==="
if [ -f "accelerate_config.yaml" ]; then
    echo "📋 Using accelerate_config.yaml:"
    cat accelerate_config.yaml
    
    echo "🚀 Testing accelerate launch (dry run):"
    accelerate launch --config_file accelerate_config.yaml --help | head -10
else
    echo "❌ accelerate_config.yaml not found"
fi

echo "=== HuggingFace Authentication Test ==="
python3 -c "
import os
from huggingface_hub import login, whoami

hf_token = os.getenv('HF_TOKEN') or os.getenv('HUGGINGFACE_HUB_TOKEN')
if hf_token:
    try:
        login(token=hf_token)
        user_info = whoami()
        print(f'✅ HuggingFace authenticated as: {user_info[\"name\"]}')
    except Exception as e:
        print(f'❌ HuggingFace authentication failed: {e}')
else:
    print('⚠️ No HuggingFace token found')
"

echo "🧪 SLURM GPU test completed"
