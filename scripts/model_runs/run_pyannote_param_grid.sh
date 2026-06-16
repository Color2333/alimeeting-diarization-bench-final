#!/bin/bash
# Small PyAnnote/Community parameter grid for AliMeeting.

set -euo pipefail

MODEL="${MODEL:-pyannote_community}"
SAMPLES="${SAMPLES:-8}"
COUNT_MODE="${COUNT_MODE:-oracle}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/param_tuning}"
THRESHOLDS="${THRESHOLDS:-0.45 0.50 0.55 0.60 0.65 0.70}"

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

for threshold in $THRESHOLDS; do
  params="{\"clustering\":{\"threshold\":$threshold}}"
  python -m alimeeting_diarization_bench.run \
    "${COMMON_ARGS[@]}" \
    --pipeline-params "$params"
done

python scripts/analysis/summarize_param_tuning.py "$OUTPUT_DIR"
