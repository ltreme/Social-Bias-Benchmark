#!/bin/bash
# fix_cuda_environment.sh - Fix CUDA environment issues on SLURM

echo "🔧 CUDA Environment Fix"

# Check SLURM GPU allocation
echo "SLURM GPU Info:"
echo "SLURM_GPUS_ON_NODE: ${SLURM_GPUS_ON_NODE:-'Not set'}"
echo "SLURM_JOB_GPUS: ${SLURM_JOB_GPUS:-'Not set'}"
echo "SLURM_LOCALID: ${SLURM_LOCALID:-'Not set'}"

# Get actual allocated GPUs from SLURM
if [[ -n "$SLURM_JOB_GPUS" ]]; then
    # Convert SLURM GPU list to array
    IFS=',' read -ra SLURM_GPU_ARRAY <<< "$SLURM_JOB_GPUS"
    echo "📋 SLURM allocated GPUs: ${SLURM_GPU_ARRAY[@]}"
else
    echo "⚠️ No SLURM GPU allocation found, using default detection"
    SLURM_GPU_ARRAY=(0 1 2 3)  # Fallback to all possible GPUs
fi

# Check GPU hardware status first
echo "🔍 Hardware GPU Status:"
nvidia-smi --query-gpu=index,name,memory.total,temperature.gpu,pstate --format=csv,noheader,nounits

# Force CUDA device reset for problematic GPUs
echo "🔄 Resetting CUDA context..."
nvidia-smi --gpu-reset-ecc=0 2>/dev/null || echo "ECC reset not available"
nvidia-smi --reset-ecc=0 2>/dev/null || echo "Global ECC reset not available"

# Test individual GPUs from SLURM allocation
echo "🧪 Testing SLURM allocated GPUs..."
working_gpus=""

for gpu_id in "${SLURM_GPU_ARRAY[@]}"; do
    echo "Testing GPU $gpu_id:"
    
    # Check hardware status first
    gpu_status=$(nvidia-smi --query-gpu=pstate --format=csv,noheader,nounits --id=$gpu_id 2>/dev/null)
    echo "  Hardware status: $gpu_status"
    
    if [[ "$gpu_status" == *"[GPU requires reset]"* ]]; then
        echo "  ⚠️ GPU $gpu_id requires reset - attempting recovery"
        nvidia-smi --id=$gpu_id --reset-gpu 2>/dev/null || echo "  GPU reset failed"
        sleep 2
    fi
    
    # Test CUDA functionality
    export CUDA_VISIBLE_DEVICES=$gpu_id
    result=$(python3 -c "
import torch
import gc
import sys
try:
    # Clear any existing CUDA context
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()
    
    if torch.cuda.is_available() and torch.cuda.device_count() > 0:
        device = torch.device('cuda:0')
        # Simple tensor test
        test = torch.tensor([1.0], device=device)
        result = test + 1
        # Memory test
        large_tensor = torch.randn(1000, 1000, device=device)
        del large_tensor
        torch.cuda.empty_cache()
        print('WORKING')
    else:
        print('NO_CUDA')
except Exception as e:
    print(f'ERROR: {str(e)[:100]}')  # Truncate long error messages
" 2>/dev/null)
    
    echo "  Test result: $result"
    
    if [[ "$result" == "WORKING" ]]; then
        if [[ -z "$working_gpus" ]]; then
            working_gpus="$gpu_id"
        else
            working_gpus="$working_gpus,$gpu_id"
        fi
        echo "  ✅ GPU $gpu_id is functional"
    else
        echo "  ❌ GPU $gpu_id failed: $result"
    fi
done

echo "🎯 Working GPUs: $working_gpus"

# Set optimal CUDA configuration
if [[ -n "$working_gpus" ]]; then
    export CUDA_VISIBLE_DEVICES="$working_gpus"
    echo "✅ Set CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
    
    # Count working GPUs
    IFS=',' read -ra WORKING_GPU_ARRAY <<< "$working_gpus"
    gpu_count=${#WORKING_GPU_ARRAY[@]}
    echo "📊 Working GPU count: $gpu_count"
    
    # Generate appropriate accelerate config
    if [[ $gpu_count -gt 1 ]]; then
        echo "🔧 Generating multi-GPU accelerate config..."
        cat > accelerate_config_dynamic.yaml << EOF
compute_environment: LOCAL_MACHINE
deepspeed_config: {}
distributed_type: MULTI_GPU
downcast_bf16: 'no'
gpu_ids: '$(seq -s',' 0 $((gpu_count-1)))'
machine_rank: 0
main_training_function: main
mixed_precision: fp16
num_machines: 1
num_processes: $gpu_count
rdzv_backend: static
same_network: true
tpu_env: []
tpu_use_cluster: false
tpu_use_sudo: false
use_cpu: false
EOF
    else
        echo "🔧 Generating single-GPU accelerate config..."
        cat > accelerate_config_dynamic.yaml << EOF
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
    fi
    
    echo "📋 Generated accelerate config:"
    cat accelerate_config_dynamic.yaml
    
    # Test final configuration
    echo "🧪 Testing final CUDA configuration..."
    python3 -c "
import torch
import os
print(f'Final test - CUDA_VISIBLE_DEVICES: {os.environ.get(\"CUDA_VISIBLE_DEVICES\")}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'Device count: {torch.cuda.device_count()}')
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        try:
            device = torch.device(f'cuda:{i}')
            name = torch.cuda.get_device_name(device)
            # Test tensor operations
            test = torch.randn(100, device=device)
            result = test.sum()
            memory_allocated = torch.cuda.memory_allocated(device) / 1024**2
            print(f'✅ GPU {i}: {name} - Working (Memory: {memory_allocated:.1f}MB)')
        except Exception as e:
            print(f'❌ GPU {i}: Failed - {str(e)[:50]}...')
else:
    print('❌ CUDA not available in final test')
"
    
    # Save configuration for later use
    echo "export CUDA_VISIBLE_DEVICES=\"$working_gpus\"" > cuda_env.sh
    echo "export GPU_COUNT=\"$gpu_count\"" >> cuda_env.sh
    echo "💾 Saved configuration to cuda_env.sh"
    
else
    echo "❌ No working GPUs found!"
    echo "🔍 Diagnostics:"
    echo "  - Hardware status above shows GPU issues"
    echo "  - Try requesting different GPUs with: #SBATCH --gres=gpu:a6000:2 --exclude=<problem_node>"
    echo "  - Or use single GPU: #SBATCH --gres=gpu:a6000:1"
    exit 1
fi

echo "✅ CUDA environment fix completed"
echo "🚀 Ready for benchmark execution"
