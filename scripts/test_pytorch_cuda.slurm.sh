  Beispiel `test_pytorch_cuda.slurm`:
  ```bash
  #!/bin/bash
  #SBATCH --job-name=pytorch_cuda_test
  #SBATCH --output=pytorch_cuda_test_%j.out
  #SBATCH --error=pytorch_cuda_test_%j.err
  #SBATCH --nodes=1
  #SBATCH --ntasks-per-node=1
  #SBATCH --cpus-per-task=2 # Gib dem Job ein paar CPUs
  #SBATCH --gres=gpu:1      # Fordere 1 GPU an (oder mehr, wenn dein Benchmark es braucht)
  #SBATCH --time=00:15:00   # Zeitlimit (z.B. 15 Minuten für den Test)

  # Ggf. Modulpfade laden, falls auf dem Cluster nötig (z.B. für CUDA Toolkit)
  # module load cuda/12.1 # Beispiel, an deine Cluster-Konfiguration anpassen

  echo "Job gestartet auf Host: $(hostname)"
  echo "SLURM Job ID: $SLURM_JOB_ID"
  echo "Zugewiesene GPUs (SLURM_JOB_GPUS): $SLURM_JOB_GPUS"
  echo "CUDA_VISIBLE_DEVICES (von Slurm gesetzt?): $CUDA_VISIBLE_DEVICES"

  # Aktiviere dein virtuelles Environment
  source /mnt/md0/mertl/projects/Social-Bias-Benchmark/venv/bin/activate

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
  ```
  Speichere dies als `test_pytorch_cuda.slurm` und starte es mit `sbatch test_pytorch_cuda.slurm`. Überprüfe dann die `.out` und `.err` Dateien.