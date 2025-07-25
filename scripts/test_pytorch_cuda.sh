echo "Job gestartet auf Host: $(hostname)"
echo "SLURM Job ID: $SLURM_JOB_ID"
echo "Zugewiesene GPUs (SLURM_JOB_GPUS): $SLURM_JOB_GPUS"
echo "CUDA_VISIBLE_DEVICES (von Slurm gesetzt?): $CUDA_VISIBLE_DEVICES"

# Führe den Python-Testcode aus
python -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    cuda_version = torch.version.cuda
    num_gpus_detected = torch.cuda.device_count()
    print(f'CUDA version used by PyTorch: {cuda_version}')
    print(f'Number of GPUs detected by PyTorch (innerhalb Slurm-Job): {num_gpus_detected}')
    for i in range(num_gpus_detected):
        try:
            # Wichtig: PyTorch sieht innerhalb des Jobs nur die zugewiesenen GPUs.
            # Der Index 'i' ist hier relativ zu den zugewiesenen GPUs.
            print(f'Attempting to get properties for logical GPU {i}...')
            props = torch.cuda.get_device_properties(i)
            print(f'  Logical GPU {i}: {props.name}, Total Memory: {props.total_memory / (1024**3):.2f} GB')
        except RuntimeError as e:
            print(f'  Error accessing logical GPU {i}: {e}')
else:
    print('CUDA is not available to PyTorch within this Slurm job.')
"

echo "Python-Test beendet."