#!/usr/bin/env bash
set -euo pipefail

# Smoke run for datasets:
# - balanced-20250919-v2 (dataset_id=3)
# - cf-of-balanced-20250919 (dataset_id=5)
# Model: stelterlab/Mistral-Small-3.2-24B-Instruct-2506-FP8 (served via vLLM)

export PYTHONPATH=apps

MODEL="stelterlab/Mistral-Small-3.2-24B-Instruct-2506-FP8"
VLLM_URL="http://localhost:8000"

DS_BAL=3     # balanced dataset id (≈2000 members)
DS_CF=5      # counterfactual dataset id (≈4000 members)

BATCH_ATTR=8
MAXTOK_ATTR=192

BATCH_BENCH=8
MAXTOK_BENCH=64

#echo "[Step] DB migrate (idempotent)"
#python apps/shared/src/shared/storage/migrate.py

# echo "[Info] Ensure vLLM is running at ${VLLM_URL} serving ${MODEL}"
# echo "       Example: python -m vllm.entrypoints.openai.api_server --model \"${MODEL}\" --host 0.0.0.0 --port 8000"

# echo "[Step] Attribute generation for dataset ${DS_BAL} (balanced)"
# python apps/benchmark/src/benchmark/cli/run_attr_generation.py \
#   --dataset-id ${DS_BAL} \
#   --llm vllm \
#   --vllm-model "${MODEL}" \
#   --vllm-base-url "${VLLM_URL}" \
#   --batch-size ${BATCH_ATTR} \
#   --max-new-tokens ${MAXTOK_ATTR} \
#   --persist peewee

# echo "[Step] Attribute generation for dataset ${DS_CF} (counterfactuals)"
# python apps/benchmark/src/benchmark/cli/run_attr_generation.py \
#   --dataset-id ${DS_CF} \
#   --llm vllm \
#   --vllm-model "${MODEL}" \
#   --vllm-base-url "${VLLM_URL}" \
#   --batch-size ${BATCH_ATTR} \
#   --max-new-tokens ${MAXTOK_ATTR} \
#   --persist peewee

# echo "[Step] Core benchmark on dataset ${DS_BAL} (with rationale ON)"
# python apps/benchmark/src/benchmark/cli/run_core_benchmark.py \
#   --dataset-id ${DS_BAL} \
#   --llm vllm \
#   --vllm-model "${MODEL}" \
#   --vllm-base-url "${VLLM_URL}" \
#   --batch-size ${BATCH_BENCH} \
#   --max-new-tokens ${MAXTOK_BENCH} \
#   --persist peewee \
#   --with-rational on

echo "[Step] Core benchmark on dataset ${DS_BAL} (with rationale OFF)"
python apps/benchmark/src/benchmark/cli/run_core_benchmark.py \
  --dataset-id ${DS_BAL} \
  --llm vllm \
  --vllm-model "${MODEL}" \
  --vllm-base-url "${VLLM_URL}" \
  --batch-size ${BATCH_BENCH} \
  --max-new-tokens ${MAXTOK_BENCH} \
  --persist peewee \
  --with-rational off

echo "[Step] Core benchmark on dataset ${DS_CF} (with rationale ON)"
python apps/benchmark/src/benchmark/cli/run_core_benchmark.py \
  --dataset-id ${DS_CF} \
  --llm vllm \
  --vllm-model "${MODEL}" \
  --vllm-base-url "${VLLM_URL}" \
  --batch-size ${BATCH_BENCH} \
  --max-new-tokens ${MAXTOK_BENCH} \
  --persist peewee \
  --with-rational on

echo "[Step] Core benchmark on dataset ${DS_CF} (with rationale OFF)"
python apps/benchmark/src/benchmark/cli/run_core_benchmark.py \
  --dataset-id ${DS_CF} \
  --llm vllm \
  --vllm-model "${MODEL}" \
  --vllm-base-url "${VLLM_URL}" \
  --batch-size ${BATCH_BENCH} \
  --max-new-tokens ${MAXTOK_BENCH} \
  --persist peewee \
  --with-rational off

echo "[Done] Runs completed. Analyze with run_benchmark_analysis.py using --dataset-ids ${DS_BAL} or ${DS_CF}."

