#!/usr/bin/env python3
"""Summarize real LLM Policy Agent comparison runs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


MODEL_LABELS = {
    "qwen36_flash_48_mixed18": "qwen3.6-flash-2026-04-16",
    "qwen37_plus_48_mixed8": "qwen3.7-plus",
    "deepseek_v4_flash_48_mixed8": "deepseek-v4-flash",
    "glm51_48_mixed8": "glm-5.1",
    "qwen36_35b_a3b_48_mixed8": "qwen3.6-35b-a3b",
}


def fmt_counts(counts: dict[str, int]) -> str:
    order = ["accept", "defer", "reject", "quarantine", "error"]
    parts = [f"{key} {counts[key]}" for key in order if counts.get(key)]
    return " / ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("outputs/llm_policy_agent"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/llm_policy_agent/model_comparison.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/llm_policy_agent/model_comparison.md"))
    args = parser.parse_args()

    rows = []
    for stem, model in MODEL_LABELS.items():
        summary_path = args.input_dir / f"{stem}_summary.json"
        if not summary_path.exists():
            continue
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        rows.append(
            {
                "model": model,
                "samples": data["items"],
                "decision_counts": fmt_counts(data["decision_counts"]),
                "agreement_rate": round(data["agreement_rate"], 4),
                "avg_call_seconds": round(data.get("avg_call_seconds", 0.0), 3),
                "p95_call_seconds": round(data.get("p95_call_seconds", 0.0), 3),
                "total_tokens": data.get("total_tokens", 0),
            }
        )

    if not rows:
        raise SystemExit("No mixed LLM summary files found")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    md_lines = [
        "| Model | Samples | Decisions | Agreement | Avg call | P95 call | Tokens |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        md_lines.append(
            "| {model} | {samples} | {decision_counts} | {agreement_rate:.1%} | "
            "{avg_call_seconds:.2f}s | {p95_call_seconds:.2f}s | {total_tokens} |".format(**row)
        )
    args.output_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
