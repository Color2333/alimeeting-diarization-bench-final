#!/usr/bin/env python3
"""Build a comparison table for real high-risk LLM guard batch runs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


RUNS = [
    {
        "role": "primary_guard",
        "run": "deepseek_high_risk_48",
        "summary_csv": "outputs/llm_window_batch/window_batch_summary.csv",
        "safety_json": "outputs/llm_window_batch/window_batch_safety_summary.json",
        "scope": "full high-risk set",
    },
    {
        "role": "backup_guard_candidate",
        "run": "qwen36_flash_high_risk_48",
        "summary_csv": "outputs/llm_window_batch/qwen36_flash_high_risk_summary.csv",
        "safety_json": "outputs/llm_window_batch/qwen36_flash_high_risk_safety_summary.json",
        "scope": "full high-risk set",
    },
    {
        "role": "offline_second_opinion",
        "run": "qwen37_plus_high_risk_2w_48",
        "summary_csv": "outputs/llm_window_batch/qwen37_plus_high_risk_2w_summary.csv",
        "safety_json": "outputs/llm_window_batch/qwen37_plus_high_risk_2w_safety_summary.json",
        "scope": "top-2 high-risk windows",
    },
]


def first_csv_row(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"No rows in {path}")
    return rows[0]


def load_safety(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/llm_window_batch/guard_model_comparison.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/llm_window_batch/guard_model_comparison.md"))
    args = parser.parse_args()

    rows = []
    for spec in RUNS:
        summary = first_csv_row(Path(spec["summary_csv"]))
        safety = load_safety(Path(spec["safety_json"]))
        row = {
            "role": spec["role"],
            "run": spec["run"],
            "model": summary["model"],
            "scope": spec["scope"],
            "windows": summary["windows"],
            "patches": summary["patches"],
            "window_decisions": summary["window_decision_counts"],
            "patch_decisions": summary["patch_decision_counts"],
            "avg_call_seconds": f"{float(summary['avg_call_seconds']):.2f}",
            "avg_correction_delay_seconds": f"{float(summary['avg_correction_delay_seconds']):.2f}",
            "max_correction_delay_seconds": f"{float(summary['max_correction_delay_seconds']):.2f}",
            "safe_accepts": str(safety.get("safe_accepts", 0)),
            "harmful_accepts": str(safety.get("harmful_accepts", 0)),
            "conservative_blocks": str(safety.get("conservative_blocks", 0)),
            "safe_blocks": str(safety.get("safe_blocks", 0)),
        }
        rows.append(row)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "| Role | Model | Scope | Windows | Patches | Window decisions | Patch decisions | Avg call | Avg correction delay | Max correction delay | Safety |",
        "|---|---|---|---:|---:|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        safety = (
            f"safe {row['safe_accepts']} / harmful {row['harmful_accepts']} / "
            f"conservative {row['conservative_blocks']}"
        )
        lines.append(
            "| {role} | {model} | {scope} | {windows} | {patches} | {window_decisions} | {patch_decisions} | {avg_call_seconds}s | {avg_correction_delay_seconds}s | {max_correction_delay_seconds}s | {safety} |".format(
                **row,
                safety=safety,
            )
        )
    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
