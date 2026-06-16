#!/bin/bash
# Targeted PyAnnote Community-1 Fa/Fb grid.

set -euo pipefail

MODEL="${MODEL:-pyannote_community}"
SAMPLES="${SAMPLES:-8}"
COUNT_MODE="${COUNT_MODE:-oracle}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/param_tuning_fafb}"

COMMON_ARGS=(
  --model "$MODEL"
  --window-size 30
  --sampling-mode stratified
  --total-samples "$SAMPLES"
  --seed 42
  --collar 0.0
  --speaker-count-mode "$COUNT_MODE"
  --output-dir "$OUTPUT_DIR"
)

PARAMS=(
  '{"clustering":{"Fa":0.03,"Fb":0.8}}'
  '{"clustering":{"Fa":0.07,"Fb":0.8}}'
  '{"clustering":{"Fa":0.12,"Fb":0.8}}'
  '{"clustering":{"Fa":0.07,"Fb":0.6}}'
  '{"clustering":{"Fa":0.07,"Fb":1.0}}'
)

for params in "${PARAMS[@]}"; do
  python -m alimeeting_diarization_bench.run \
    "${COMMON_ARGS[@]}" \
    --pipeline-params "$params"
done

python scripts/summarize_param_tuning.py "$OUTPUT_DIR"
