#!/usr/bin/env python3
"""Summarize real window-batched LLM Policy Agent runs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-jsonl", type=Path, default=Path("outputs/llm_window_batch/deepseek_high_risk_48.jsonl"))
    parser.add_argument("--latencies", type=Path, default=Path("outputs/latency_tradeoff/main_models.csv"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/llm_window_batch/window_batch_summary.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/llm_window_batch/window_batch_summary.md"))
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.batch_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    slow_rows = [row for row in load_csv(args.latencies) if row["role"] == "slow_agent" and row["segments"] == "48"]
    if not rows:
        raise SystemExit("No batch rows found")
    if not slow_rows:
        raise SystemExit("No 48-window slow_agent latency row found")

    slow_avg = float(slow_rows[0]["avg_latency_sec"])
    successful = [row for row in rows if not row.get("error")]
    call_seconds = [float(row.get("call_seconds") or 0.0) for row in successful]
    patch_decisions = Counter()
    for row in successful:
        for item in row.get("patch_decisions", []):
            patch_decisions[item["decision"]] += 1

    summary = {
        "run": args.batch_jsonl.stem,
        "model": successful[0]["model"] if successful else "",
        "windows": len(rows),
        "successful_windows": len(successful),
        "patches": sum(int(row.get("patch_count") or 0) for row in rows),
        "window_decision_counts": " / ".join(
            f"{key} {value}" for key, value in Counter(row.get("window_decision", "error") for row in rows).items()
        ),
        "patch_decision_counts": " / ".join(f"{key} {patch_decisions[key]}" for key in sorted(patch_decisions)),
        "avg_call_seconds": sum(call_seconds) / len(call_seconds) if call_seconds else 0.0,
        "max_call_seconds": max(call_seconds) if call_seconds else 0.0,
        "slow_avg_latency_seconds": slow_avg,
        "avg_correction_delay_seconds": slow_avg + (sum(call_seconds) / len(call_seconds) if call_seconds else 0.0),
        "max_correction_delay_seconds": slow_avg + (max(call_seconds) if call_seconds else 0.0),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in successful),
    }

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    md = [
        "| Run | Model | Windows | Patches | Window decisions | Patch decisions | Avg call | Avg correction delay | Max correction delay | Tokens |",
        "|---|---|---:|---:|---|---|---:|---:|---:|---:|",
        "| {run} | {model} | {windows} | {patches} | {window_decision_counts} | {patch_decision_counts} | {avg_call_seconds:.2f}s | {avg_correction_delay_seconds:.2f}s | {max_correction_delay_seconds:.2f}s | {total_tokens} |".format(
            **summary
        ),
    ]
    args.output_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
