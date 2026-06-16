#!/usr/bin/env python3
"""Run the shortest offline reproduction path and print the key metrics."""

from __future__ import annotations

# Keep final modules import-compatible when executed with python -m.
import sys as _sys
from pathlib import Path as _Path
_SCRIPT_ROOT = _Path(__file__).resolve().parent
_REPO_ROOT = _Path(__file__).resolve().parents[2]
for _candidate in [_REPO_ROOT, _SCRIPT_ROOT, *_SCRIPT_ROOT.iterdir()]:
    if _candidate.is_dir():
        _value = str(_candidate)
        if _value not in _sys.path:
            _sys.path.insert(0, _value)

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = Path("outputs/quick_start/all_cached_recordings")
EXPECTED_FINAL_DER = 0.16492333333333334


def run(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def assert_close(name: str, value: float, expected: float, tolerance: float = 1e-9) -> None:
    if abs(value - expected) > tolerance:
        raise SystemExit(f"{name} mismatch: got {value}, expected {expected}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for regenerated quick-start outputs.",
    )
    parser.add_argument(
        "--no-assert",
        action="store_true",
        help="Print metrics without enforcing expected submission values.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    run(
        [
            sys.executable,
            "-m", "alimeeting_diarization_bench.final.realtime_system",
            "--all-cached-recordings",
            "--output-dir",
            str(output_dir),
        ]
    )

    metrics_path = ROOT / output_dir / "metrics.json"
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics = payload["metrics"]
    baseline_summary = payload["baseline_win_summary"]

    if not args.no_assert:
        if payload["windows_processed"] != 120:
            raise SystemExit(f"windows_processed mismatch: {payload['windows_processed']}")
        if payload["recordings_processed"] != 8:
            raise SystemExit(f"recordings_processed mismatch: {payload['recordings_processed']}")
        assert_close("metrics.final_der", float(metrics["final_der"]), EXPECTED_FINAL_DER)
        if not bool(baseline_summary["beats_all_baselines"]):
            raise SystemExit("beats_all_baselines mismatch: got false")
        for key in ("deepseek_api_calls", "qwen_api_calls", "omni_api_calls"):
            if int(metrics[key]) != 0:
                raise SystemExit(f"{key} mismatch: got {metrics[key]}")

    print("\nQuick start complete")
    print(f"- metrics: {output_dir / 'metrics.json'}")
    print(f"- final DER: {float(metrics['final_der']) * 100:.4f}%")
    print(f"- margin vs best baseline: {float(metrics['der_delta_vs_best_baseline_pp']):.4f}pp")
    print(f"- beats all tracked baselines: {baseline_summary['beats_all_baselines']}")
    print(f"- processed audio: {float(metrics['processed_audio_sec']):.1f}s")
    print(f"- offline replay RTF: {float(metrics['offline_replay_rtf']):.6f}")
    print(
        "- live API calls: "
        f"DeepSeek={metrics['deepseek_api_calls']}, "
        f"Qwen={metrics['qwen_api_calls']}, "
        f"Omni={metrics['omni_api_calls']}"
    )


if __name__ == "__main__":
    main()
