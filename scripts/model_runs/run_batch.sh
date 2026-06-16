#!/usr/bin/env bash
# Batch run all 6 models with stratified sampling (120 segments)
# Results saved to ~/data/AliMeeting/batch_results_v2/{model}/
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUTPUT_DIR="${1:-$HOME/data/AliMeeting/batch_results_v2}"
SAMPLES="${2:-120}"
SEED="${3:-42}"
WINDOW=30

MODELS=(fun_asr paraformer_v2 asr_flash omni_plus gpt4o_audio pyannote)

echo "============================================"
echo "  AliMeeting Batch Benchmark"
echo "  Output: $OUTPUT_DIR"
echo "  Samples: $SAMPLES | Window: ${WINDOW}s | Seed: $SEED"
echo "  Models: ${MODELS[*]}"
echo "============================================"

for model in "${MODELS[@]}"; do
    echo ""
    echo ">>> Running model: $model"
    echo ">>> Started at: $(date '+%Y-%m-%d %H:%M:%S')"

    python3 -m alimeeting_diarization_bench.run \
        --model "$model" \
        --sampling-mode stratified \
        --window-size "$WINDOW" \
        --total-samples "$SAMPLES" \
        --seed "$SEED" \
        --output-dir "$OUTPUT_DIR" \
        --verbose 2>&1 | tee "$OUTPUT_DIR/${model}_log.txt"

    echo ">>> Finished $model at: $(date '+%Y-%m-%d %H:%M:%S')"
done

echo ""
echo "============================================"
echo "  All models complete!"
echo "  Results in: $OUTPUT_DIR"
echo ""

python3 "$REPO_ROOT/scripts/analysis/analyze_results.py" "$OUTPUT_DIR"
