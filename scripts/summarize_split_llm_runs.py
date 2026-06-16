#!/usr/bin/env python3
"""Summarize split-window LLM runs against original unsplit window calls."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Split LLM Run Summary",
        "",
        "| Parent window | Patches | Original call | Split calls | Split max call | Token multiplier | Reduction |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["parents"]:
        lines.append(
            "| {parent_window_id} | {patches} | {original_call_seconds:.2f}s | {split_calls} | "
            "{split_max_call_seconds:.2f}s | {token_multiplier:.2f}x | {parallel_reduction_rate:.1%} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            "| Parents | Patches | Split calls | Original avg | Split parent avg max | Original max | Split max | Token multiplier | Harmful accepts |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            (
                "| {parent_windows} | {patches} | {split_calls} | {original_avg_call_seconds:.2f}s | "
                "{split_parent_avg_max_call_seconds:.2f}s | {original_max_call_seconds:.2f}s | "
                "{split_max_call_seconds:.2f}s | {token_multiplier:.2f}x | {harmful_accepts} |"
            ).format(**summary),
            "",
            "## Run Batches",
            "",
            "| Run | Calls | Successful calls | Wall | Workers | Harmful accepts |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary["runs"]:
        lines.append(
            "| {run} | {calls} | {successful_calls} | {wall_seconds:.2f}s | {parallel_workers} | {harmful_accepts} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- `Split max call` is the parent-window wall-clock estimate if that parent's subcalls run concurrently.",
            "- Batch `Wall` is the measured wall-clock for that script invocation, including local scheduling and API round trip.",
            "- If multiple batches are provided, their walls are measured separately and should not be treated as one all-at-once topN wall-clock.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-jsonl", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w.jsonl"))
    parser.add_argument("--split-csv", type=Path, action="append", required=True)
    parser.add_argument("--run-summary", type=Path, action="append", required=True)
    parser.add_argument("--safety-summary", type=Path, action="append", required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()

    original = {row["window_id"]: row for row in load_jsonl(args.original_jsonl)}
    split_rows = []
    for path in args.split_csv:
        split_rows.extend(load_csv(path))
    by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in split_rows:
        by_parent[row["parent_window_id"]].append(row)

    parent_rows = []
    for parent_id, rows in sorted(
        by_parent.items(),
        key=lambda item: -float(original[item[0]]["call_seconds"]),
    ):
        orig = original[parent_id]
        split_calls = [float(row["call_seconds"]) for row in rows]
        split_tokens = sum(int(row["total_tokens"]) for row in rows if row.get("total_tokens"))
        original_tokens = int(orig["total_tokens"])
        split_max = max(split_calls)
        original_call = float(orig["call_seconds"])
        parent_rows.append(
            {
                "parent_window_id": parent_id,
                "patches": int(orig["patch_count"]),
                "original_call_seconds": original_call,
                "original_total_tokens": original_tokens,
                "split_calls": len(rows),
                "split_max_call_seconds": split_max,
                "split_total_tokens": split_tokens,
                "token_multiplier": split_tokens / original_tokens if original_tokens else 0.0,
                "parallel_reduction_rate": 1.0 - split_max / original_call if original_call else 0.0,
            }
        )

    run_rows = []
    for run_path, safety_path in zip(args.run_summary, args.safety_summary):
        run = load_json(run_path)
        safety = load_json(safety_path)
        run_rows.append(
            {
                "run": run_path.stem,
                "calls": int(run.get("calls", 0)),
                "successful_calls": int(run.get("successful_calls", 0)),
                "wall_seconds": float(run.get("wall_seconds") or 0.0),
                "parallel_workers": int(run.get("parallel_workers") or 1),
                "harmful_accepts": int(safety.get("harmful_accepts", 0)),
            }
        )

    safety_rows = [load_json(path) for path in args.safety_summary]
    summary = {
        "parent_windows": len(parent_rows),
        "patches": sum(row["patches"] for row in parent_rows),
        "split_calls": sum(row["split_calls"] for row in parent_rows),
        "original_avg_call_seconds": sum(row["original_call_seconds"] for row in parent_rows) / len(parent_rows),
        "split_parent_avg_max_call_seconds": sum(row["split_max_call_seconds"] for row in parent_rows) / len(parent_rows),
        "original_max_call_seconds": max(row["original_call_seconds"] for row in parent_rows),
        "split_max_call_seconds": max(row["split_max_call_seconds"] for row in parent_rows),
        "token_multiplier": (
            sum(row["split_total_tokens"] for row in parent_rows)
            / sum(row["original_total_tokens"] for row in parent_rows)
        ),
        "harmful_accepts": sum(int(row.get("harmful_accepts", 0)) for row in safety_rows),
        "conservative_blocks": sum(int(row.get("conservative_blocks", 0)) for row in safety_rows),
        "parent_window_decision_override": all(bool(row.get("parent_window_decision_override")) for row in safety_rows),
        "parents": parent_rows,
        "runs": run_rows,
        "runtime_contract": "split_llm_run_summary; parent_window_quarantine_override",
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
