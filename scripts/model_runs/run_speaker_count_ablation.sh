#!/bin/bash
# Speaker-count hint ablation for PyAnnote pipelines.

set -euo pipefail

MODEL="${1:-pyannote}"
SAMPLES="${SAMPLES:-120}"
OUTPUT_DIR="${OUTPUT_DIR:-}"

COMMON_ARGS=(
  --model "$MODEL"
  --window-size 30
  --sampling-mode stratified
  --total-samples "$SAMPLES"
  --seed 42
  --collar 0.0
)

if [ -n "$OUTPUT_DIR" ]; then
  COMMON_ARGS+=(--output-dir "$OUTPUT_DIR")
fi

python -m alimeeting_diarization_bench.run "${COMMON_ARGS[@]}" --speaker-count-mode oracle
python -m alimeeting_diarization_bench.run "${COMMON_ARGS[@]}" --speaker-count-mode none
python -m alimeeting_diarization_bench.run "${COMMON_ARGS[@]}" --speaker-count-mode bounds --min-speakers 1 --max-speakers 8
