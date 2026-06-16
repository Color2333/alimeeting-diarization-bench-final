#!/bin/bash
# Run all experiments sequentially
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Running Round 1: ASR-Flash + Omni-Plus Baseline ==="
bash "$SCRIPT_DIR/run_round1.sh"

echo "=== Running Round 2: Prompt Variants ==="
bash "$SCRIPT_DIR/run_round2.sh"

echo "=== Running Round 3: Two-Stage Agent ==="
bash "$SCRIPT_DIR/run_round3.sh"

echo "=== Running P0: Fun-ASR ==="
bash "$SCRIPT_DIR/run_p0_funasr.sh"

echo "=== Running P0 Extended: Paraformer-v2 + GPT-4o ==="
bash "$SCRIPT_DIR/run_p0_ext.sh"

echo "=== Running P1: PyAnnote 3.1 ==="
bash "$SCRIPT_DIR/run_pyannote.sh"

echo "=== Running Collar Comparison ==="
bash "$SCRIPT_DIR/run_collar.sh"

echo "=== All experiments complete ==="
