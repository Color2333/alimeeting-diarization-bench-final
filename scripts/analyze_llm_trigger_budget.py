#!/usr/bin/env python3
"""Estimate LLM trigger volume and async latency budgets for Policy Agent patches."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Callable, Any


Row = dict[str, Any]


def load_jsonl(path: Path) -> list[Row]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_model_latencies(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def has_high_error_flag(row: Row) -> bool:
    return any("high_der" in flag or "high_fa" in flag for flag in row.get("abnormal_flags", []))


def has_slow_quarantine_flag(row: Row) -> bool:
    return any(flag.startswith("slow_high_der") or flag.startswith("slow_high_fa") for flag in row.get("abnormal_flags", []))


def build_policies() -> list[tuple[str, str, Callable[[Row], bool]]]:
    return [
        (
            "all_patch_audit",
            "Call LLM for every Fast/Slow patch. Diagnostic upper bound only.",
            lambda row: True,
        ),
        (
            "non_accept_review",
            "Only review rule-agent defer/quarantine patches.",
            lambda row: row["decision"] != "accept",
        ),
        (
            "semantic_label_smoothing",
            "Review memory-low relabel deferrals plus short recover/suppress conflicts.",
            lambda row: row["reason"]
            in {
                "memory_low_confidence_relabel_deferred",
                "recover_segment_too_short",
                "do_not_suppress_without_strong_evidence",
            },
        ),
        (
            "writeback_guard",
            "Review risky writebacks: non-accept patches, suppressions, and recovered slow segments.",
            lambda row: row["decision"] != "accept"
            or row["patch_type"] in {"suppress_fast_candidate", "recover_slow_segment"},
        ),
        (
            "high_risk_quarantine",
            "Review only high-DER/high-FA windows, slow quarantine flags, or suppress candidates.",
            lambda row: has_high_error_flag(row)
            or has_slow_quarantine_flag(row)
            or row["decision"] == "quarantine"
            or row["patch_type"] == "suppress_fast_candidate",
        ),
        (
            "minimal_live_escalation",
            "Smallest live-safe trigger: high-error windows or suppress candidates only.",
            lambda row: has_high_error_flag(row) or row["patch_type"] == "suppress_fast_candidate",
        ),
    ]


def summarize_policy(rows: list[Row], policy_name: str, description: str, predicate: Callable[[Row], bool]) -> dict[str, Any]:
    selected = [row for row in rows if predicate(row)]
    unique_windows = {(row["recording_id"], row["window_size"], row["segment_idx"]) for row in selected}
    high_error = sum(1 for row in selected if has_high_error_flag(row))
    non_accept = sum(1 for row in selected if row["decision"] != "accept")
    suppress = sum(1 for row in selected if row["patch_type"] == "suppress_fast_candidate")
    return {
        "policy": policy_name,
        "description": description,
        "calls": len(selected),
        "call_rate": len(selected) / len(rows) if rows else 0.0,
        "windows_touched": len(unique_windows),
        "non_accept_calls": non_accept,
        "high_error_calls": high_error,
        "suppress_calls": suppress,
    }


def add_latency_budget(
    policy_rows: list[dict[str, Any]],
    model_rows: list[dict[str, str]],
    audio_seconds: float,
) -> list[dict[str, Any]]:
    output = []
    for policy in policy_rows:
        for model in model_rows:
            avg = float(model["avg_call_seconds"])
            p95 = float(model["p95_call_seconds"])
            total_avg = policy["calls"] * avg
            total_p95 = policy["calls"] * p95
            output.append(
                {
                    **policy,
                    "model": model["model"],
                    "avg_call_seconds": avg,
                    "p95_call_seconds": p95,
                    "total_avg_seconds": total_avg,
                    "total_p95_seconds": total_p95,
                    "async_rtf_avg": total_avg / audio_seconds if audio_seconds else 0.0,
                    "async_rtf_p95": total_p95 / audio_seconds if audio_seconds else 0.0,
                    "workers_for_realtime_avg": max(1, math.ceil(total_avg / audio_seconds)) if policy["calls"] else 0,
                    "workers_for_realtime_p95": max(1, math.ceil(total_p95 / audio_seconds)) if policy["calls"] else 0,
                }
            )
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, policy_rows: list[dict[str, Any]], budget_rows: list[dict[str, Any]]) -> None:
    lines = [
        "## LLM Trigger Policies",
        "",
        "| Policy | Calls | Rate | Windows | Non-accept | High-error | Suppress |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in policy_rows:
        lines.append(
            "| {policy} | {calls} | {call_rate:.1%} | {windows_touched} | {non_accept_calls} | {high_error_calls} | {suppress_calls} |".format(
                **row
            )
        )

    preferred = [row for row in budget_rows if row["model"] == "deepseek-v4-flash"]
    lines.extend(
        [
            "",
            "## Async Budget With deepseek-v4-flash",
            "",
            "| Policy | Calls | Total avg | Async RTF | Workers avg |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in preferred:
        lines.append(
            "| {policy} | {calls} | {total_avg_seconds:.1f}s | {async_rtf_avg:.3f} | {workers_for_realtime_avg} |".format(
                **row
            )
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, default=Path("outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl"))
    parser.add_argument("--model-comparison", type=Path, default=Path("outputs/llm_policy_agent/model_comparison.csv"))
    parser.add_argument("--window-seconds", type=float, default=30.0)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/llm_trigger_budget"))
    args = parser.parse_args()

    rows = load_jsonl(args.decisions)
    if not rows:
        raise SystemExit("No policy decisions found")
    model_rows = load_model_latencies(args.model_comparison)
    if not model_rows:
        raise SystemExit("No model comparison rows found")

    windows = {(row["recording_id"], row["window_size"], row["segment_idx"]) for row in rows}
    audio_seconds = len(windows) * args.window_seconds
    policy_rows = [summarize_policy(rows, name, desc, pred) for name, desc, pred in build_policies()]
    budget_rows = add_latency_budget(policy_rows, model_rows, audio_seconds)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "trigger_policies.csv", policy_rows)
    write_csv(args.output_dir / "latency_budget_by_model.csv", budget_rows)
    write_markdown(args.output_dir / "trigger_budget.md", policy_rows, budget_rows)

    summary = {
        "patches": len(rows),
        "windows": len(windows),
        "audio_seconds": audio_seconds,
        "trigger_policies_csv": str(args.output_dir / "trigger_policies.csv"),
        "latency_budget_csv": str(args.output_dir / "latency_budget_by_model.csv"),
        "markdown": str(args.output_dir / "trigger_budget.md"),
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
