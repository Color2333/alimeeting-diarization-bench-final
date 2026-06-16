#!/bin/bash
# Sweep NVIDIA Streaming Sortformer latency presets in the isolated uv env.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SAMPLES="${SAMPLES:-8}"
WINDOW_SIZE="${WINDOW_SIZE:-90}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/streaming_sortformer_latency_sweep}"
PRESETS="${PRESETS:-ultra_low_latency low_latency high_latency very_high_latency}"
MODEL_ID="${MODEL_ID:-nvidia/diar_streaming_sortformer_4spk-v2}"

cd "$ROOT_DIR"

for preset in $PRESETS; do
  echo "=== Streaming Sortformer preset: $preset ==="
  MPLCONFIGDIR=/private/tmp/matplotlib \
  .venv_sortformer/bin/python -m alimeeting_diarization_bench.run \
    --model sortformer \
    --window-size "$WINDOW_SIZE" \
    --sampling-mode stratified \
    --total-samples "$SAMPLES" \
    --seed 42 \
    --collar 0.0 \
    --speaker-count-mode none \
    --pipeline-params "{\"streaming\":true,\"model_id\":\"$MODEL_ID\",\"latency_preset\":\"$preset\"}" \
    --output-dir "$OUTPUT_DIR"
done
