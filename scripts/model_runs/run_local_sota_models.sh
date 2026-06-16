#!/bin/bash
# Compare local/open diarization candidates on the same stratified sample.

set -euo pipefail

SAMPLES="${SAMPLES:-120}"
COUNT_MODE="${COUNT_MODE:-oracle}"
OUTPUT_DIR="${OUTPUT_DIR:-}"

MODELS=(
  pyannote
  pyannote_community
  diarizen
)

COMMON_ARGS=(
  --window-size 30
  --sampling-mode stratified
  --total-samples "$SAMPLES"
  --seed 42
  --collar 0.0
  --speaker-count-mode "$COUNT_MODE"
)

if [ -n "$OUTPUT_DIR" ]; then
  COMMON_ARGS+=(--output-dir "$OUTPUT_DIR")
fi

for model in "${MODELS[@]}"; do
  python -m alimeeting_diarization_bench.run --model "$model" "${COMMON_ARGS[@]}"
done
