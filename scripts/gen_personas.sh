#!/bin/bash
set -euo pipefail

# Standardwerte, können per Env oder CLI überschrieben werden
MODEL_NAME=${MODEL_NAME:-openai/gpt-oss-20b}
MIXED_PRECISION=${MIXED_PRECISION:-bf16}   # fp16 | bf16 | no
QUANT_MODE=${QUANT_MODE:-4bit}             # 4bit | 8bit | none
RUN_ID=${RUN_ID:-}

if [ -z "$RUN_ID" ]; then
	TS=$(date -u +%Y%m%dT%H%M%SZ)
	RAND=$(head -c4 /dev/urandom | LC_ALL=C tr -dc 'a-z0-9' | head -c4 || echo rnd)
	RUN_ID="local_${TS}_${RAND}"
	export RUN_ID
fi

usage() {
	cat <<EOF
Usage: $0 [OPTIONS]

Options:
	-m, --model NAME           HuggingFace Model (default: $MODEL_NAME)
	-p, --precision MODE       Mixed precision: bf16|fp16|no (default: $MIXED_PRECISION)
	-q, --quant MODE           Quantization: 4bit|8bit|none (default: $QUANT_MODE)
	-h, --help                 Show this help

Environment overrides (same precedence as CLI if not set via CLI):
	MODEL_NAME, MIXED_PRECISION, QUANT_MODE
EOF
}

# CLI Argumente parsen
while [[ $# -gt 0 ]]; do
	case "$1" in
		-m|--model)
			[[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
			MODEL_NAME="$2"; shift 2 ;;
		-p|--precision)
			[[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
			MIXED_PRECISION="$2"; shift 2 ;;
		-q|--quant)
			[[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
			QUANT_MODE="$2"; shift 2 ;;
		-h|--help)
			usage; exit 0 ;;
		--) shift; break ;;
		*)
			echo "Unknown argument: $1" >&2
			usage
			exit 1 ;;
	esac
done

case "${QUANT_MODE}" in
	4bit) QUANT_FLAGS=(--load_in_4bit) ;;
	8bit) QUANT_FLAGS=(--load_in_8bit) ;;
	none) QUANT_FLAGS=(--no_quantization) ;;
	*) echo "Unbekannter QUANT_MODE: ${QUANT_MODE}" >&2; exit 1 ;;
esac

echo "[gen_personas] RUN_ID: ${RUN_ID} | Modell: ${MODEL_NAME} | Precision: ${MIXED_PRECISION} | Quantisierung: ${QUANT_MODE}" >&2

python apps/benchmark/src/benchmark/cli/run_preprocessing.py \
	--model_name "${MODEL_NAME}" \
	--mixed_precision "${MIXED_PRECISION}" \
	"${QUANT_FLAGS[@]}"