#!/bin/bash
set -euo pipefail

# Konfigurierbare Umgebungsvariablen (können von außen überschrieben werden)
MODEL_NAME=${MODEL_NAME:-openai/gpt-oss-20b}
MIXED_PRECISION=${MIXED_PRECISION:-bf16}  # Optionen: fp16, bf16, no
QUANT_MODE=${QUANT_MODE:-4bit}            # Optionen: 4bit, 8bit, none

case "${QUANT_MODE}" in
	4bit) QUANT_FLAGS=(--load_in_4bit) ;;
	8bit) QUANT_FLAGS=(--load_in_8bit) ;;
	none) QUANT_FLAGS=(--no_quantization) ;;
	*) echo "Unbekannter QUANT_MODE: ${QUANT_MODE}" >&2; exit 1 ;;
esac

echo "[gen_personas] Modell: ${MODEL_NAME} | Precision: ${MIXED_PRECISION} | Quantisierung: ${QUANT_MODE}" >&2

python apps/benchmark/src/benchmark/cli/run_preprocessing.py \
	--model_name "${MODEL_NAME}" \
	--mixed_precision "${MIXED_PRECISION}" \
	"${QUANT_FLAGS[@]}"