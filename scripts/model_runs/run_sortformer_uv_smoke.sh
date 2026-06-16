#!/bin/bash
# Run NVIDIA NeMo Sortformer in its isolated uv environment.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SAMPLES="${SAMPLES:-8}"
WINDOW_SIZE="${WINDOW_SIZE:-90}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/sortformer_uv_8_90s}"

cd "$ROOT_DIR"

MPLCONFIGDIR=/private/tmp/matplotlib \
.venv_sortformer/bin/python -m alimeeting_diarization_bench.run \
  --model sortformer \
  --window-size "$WINDOW_SIZE" \
  --sampling-mode stratified \
  --total-samples "$SAMPLES" \
  --seed 42 \
  --collar 0.0 \
  --speaker-count-mode none \
  --output-dir "$OUTPUT_DIR"
