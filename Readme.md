### Start Slurm job with this command:
```sh
sbatch scripts/run_slurm.sh <COMMAND OR SCRIPT>
```

### Start Benchmark:
```sh
sbatch scripts/run_slurm.sh ./scripts/benchmark.sh
```

### Debug GPU Issues:
```sh
# Fix CUDA environment on cluster
sbatch scripts/run_slurm.sh scripts/fix_cuda_environment.sh

# Generate dynamic accelerate config on cluster
sbatch scripts/run_slurm.sh scripts/generate_accelerate_config.sh
```

### Troubleshooting:
- If PyTorch shows "No CUDA GPUs available": Run `fix_cuda_environment.sh`
- For GPU allocation issues: Check `nvidia-smi` output and SLURM logs
- For HuggingFace access errors: Ensure HF_TOKEN is set in .env file