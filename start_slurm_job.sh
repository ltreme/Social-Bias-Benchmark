#!/bin/bash
# run_slurm.sh — Slurm job script for Bias Benchmarks

#SBATCH --job-name=bias-benchmarks           # Job name
#SBATCH --output=bias-benchmarks-%j.out      # Standard output (%j = Job ID)
#SBATCH --nodes=1                          # Number of nodes
#SBATCH --gres=gpu:a6000:6                 # Number of GPUs (jetzt 6)
#SBATCH --cpus-per-task=12                  # CPU cores per task (angepasst)
#SBATCH --mem=128G                          # RAM per node (erhöht für großes Modell)
#SBATCH --time=01:00:00                    # Runtime (HH:MM:SS)

# 1. (Optional) Load modules if necessary
# module load cuda/11.7
# module load python/3.10

# 2. Change to script directory (if necessary)
cd "$SLURM_SUBMIT_DIR"

# 3. Activate Python Virtual Environment
source venv/bin/activate

# 4. Execute job: Accelerate automatically distributes the model to GPU(s)
accelerate launch app/main.py
exit_code=$?

# 5. Notify via our Python module
python app/notification/telegram_notifier.py \
    "${SLURM_JOB_NAME}" \
    "${SLURM_JOB_ID}" \
    "${exit_code}" \
    "${SLURM_SUBMIT_DIR}/hello-mistral-${SLURM_JOB_ID}.out"
