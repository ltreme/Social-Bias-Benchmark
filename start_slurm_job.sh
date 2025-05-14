#!/bin/bash
# run_slurm.sh — Slurm job script for Hello-World with Mistral-7B

#SBATCH --job-name=hello-mistral           # Job name
#SBATCH --output=hello-mistral-%j.out      # Standard output (%j = Job ID)
#SBATCH --nodes=1                          # Number of nodes
#SBATCH --gres=gpu:a6000:1                 # Number of GPUs (here 1)
#SBATCH --cpus-per-task=4                  # CPU cores per task
#SBATCH --mem=32G                          # RAM per node
#SBATCH --time=01:00:00                    # Runtime (HH:MM:SS)

# 1. (Optional) Load modules if necessary
# module load cuda/11.7
# module load python/3.10

# 2. Activate Python Virtual Environment
source ~/venv/bin/activate

# 3. Change to script directory (if necessary)
cd "$SLURM_SUBMIT_DIR"

# 4. Execute job: Accelerate automatically distributes the model to GPU(s)
accelerate launch app/main.py
exit_code=$?

# 3. Notify via our Python module
python app/notification/telegram_notifier.py \
    "${SLURM_JOB_NAME}" \
    "${SLURM_JOB_ID}" \
    "${exit_code}" \
    "${SLURM_SUBMIT_DIR}/hello-mistral-${SLURM_JOB_ID}.out"
