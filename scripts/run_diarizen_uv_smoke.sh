#!/bin/bash
# Run DiariZen in its isolated uv environment on a small AliMeeting sample.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SAMPLES="${SAMPLES:-8}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/diarizen_uv_8}"

cd "$ROOT_DIR"

MPLCONFIGDIR=/private/tmp/matplotlib \
.venv_diarizen/bin/python -m alimeeting_diarization_bench.run \
  --model diarizen \
  --window-size 30 \
  --sampling-mode stratified \
  --total-samples "$SAMPLES" \
  --seed 42 \
  --collar 0.0 \
  --speaker-count-mode none \
  --output-dir "$OUTPUT_DIR"
