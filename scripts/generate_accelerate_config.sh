#!/bin/bash
# generate_accelerate_config.sh - Generate dynamic accelerate config based on available GPUs

echo "🔧 Generating Accelerate Configuration"

# Count available GPUs
gpu_count=$(python3 -c "
import torch
import os
print(torch.cuda.device_count() if torch.cuda.is_available() else 0)
")

echo "Detected GPU count: $gpu_count"

if [[ "$gpu_count" -eq 0 ]]; then
    echo "❌ No GPUs available, creating CPU config"
    cat > accelerate_config.yaml << EOF
compute_environment: LOCAL_MACHINE
deepspeed_config: {}
distributed_type: NO
downcast_bf16: 'no'
machine_rank: 0
main_training_function: main
mixed_precision: 'no'
num_machines: 1
num_processes: 1
rdzv_backend: static
same_network: true
tpu_env: []
tpu_use_cluster: false
tpu_use_sudo: false
use_cpu: true
EOF

elif [[ "$gpu_count" -eq 1 ]]; then
    echo "✅ Single GPU config"
    cat > accelerate_config.yaml << EOF
compute_environment: LOCAL_MACHINE
deepspeed_config: {}
distributed_type: NO
downcast_bf16: 'no'
gpu_ids: '0'
machine_rank: 0
main_training_function: main
mixed_precision: fp16
num_machines: 1
num_processes: 1
rdzv_backend: static
same_network: true
tpu_env: []
tpu_use_cluster: false
tpu_use_sudo: false
use_cpu: false
EOF

else
    echo "✅ Multi-GPU config for $gpu_count GPUs"
    # Generate GPU IDs (0,1,2,...)
    gpu_ids=$(python3 -c "print(','.join(str(i) for i in range($gpu_count)))")
    
    cat > accelerate_config.yaml << EOF
compute_environment: LOCAL_MACHINE
deepspeed_config: {}
distributed_type: MULTI_GPU
downcast_bf16: 'no'
gpu_ids: '$gpu_ids'
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
fi

echo "✅ Accelerate config generated:"
cat accelerate_config.yaml

echo ""
echo "🧪 Testing generated config:"
python3 -c "
from accelerate import Accelerator
try:
    accelerator = Accelerator()
    print(f'✅ Accelerator initialized successfully')
    print(f'Device: {accelerator.device}')
    print(f'Num processes: {accelerator.num_processes}')
    print(f'Process index: {accelerator.process_index}')
except Exception as e:
    print(f'❌ Accelerator initialization failed: {e}')
"
