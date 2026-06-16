#!/usr/bin/env python3
"""Simulate splitting large runtime-safe LLM guard windows into smaller batches.

This is an offline planning model, not a replacement for real LLM calls. It uses
the measured 104-window latency table to estimate whether max-patch sub-batching
is worth validating with live calls.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    frac = pos - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def fit_linear(xs: list[float], ys: list[float]) -> tuple[float, float]:
    x_mean = mean(xs)
    y_mean = mean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return y_mean, 0.0
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
    intercept = y_mean - slope * x_mean
    return intercept, slope


def chunk_sizes(patch_count: int, max_patches: int) -> list[int]:
    chunks = math.ceil(patch_count / max_patches)
    if chunks <= 1:
        return [patch_count]
    base = patch_count // chunks
    remainder = patch_count % chunks
    return [base + (1 if idx < remainder else 0) for idx in range(chunks)]


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Runtime-Safe LLM Guard Split Simulation",
        "",
        "This is an offline latency planning model. It estimates parallel sub-batching from measured 104-window calls; it is not a live-call result.",
        "",
        "## Fitted Model",
        "",
        "| Relationship | Intercept | Slope |",
        "|---|---:|---:|",
        f"| total_tokens ~ patch_count | {summary['token_intercept']:.2f} | {summary['token_per_patch']:.2f} |",
        f"| call_seconds ~ total_tokens | {summary['call_intercept']:.2f} | {summary['call_per_token']:.6f} |",
        "",
        "## Policy Summary",
        "",
        "| Max patches/subcall | Split windows | Calls | Added calls | Avg call | P95 call | Max call | Avg correction | P95 correction | Token multiplier |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["policies"]:
        lines.append(
            "| {max_patches_per_call} | {split_windows} | {calls} | {added_calls} | "
            "{avg_call_seconds:.2f}s | {p95_call_seconds:.2f}s | {max_call_seconds:.2f}s | "
            "{avg_correction_delay_seconds:.2f}s | {p95_correction_delay_seconds:.2f}s | "
            "{token_multiplier:.2f}x |".format(**row)
        )
    best = summary["recommended_policy"]
    lines.extend(
        [
            "",
            "## Recommended Next Test",
            "",
            (
                f"- Validate `max_patches_per_call={best['max_patches_per_call']}` with live calls on the slowest windows first: "
                f"estimated P95 call {best['p95_call_seconds']:.2f}s vs observed {summary['observed_p95_call_seconds']:.2f}s, "
                f"added calls {best['added_calls']}, token multiplier {best['token_multiplier']:.2f}x."
            ),
            "- Treat the numbers as a routing budget, not as claimed model performance, until the split prompt is actually called.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latency-csv", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_latency.csv"))
    parser.add_argument("--system-timeline", type=Path, default=Path("outputs/system_timeline/summary.json"))
    parser.add_argument("--max-patches", nargs="+", type=int, default=[20, 15, 12, 10, 8])
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation.md"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation_summary.json"))
    args = parser.parse_args()

    rows = load_csv(args.latency_csv)
    timeline = load_json(args.system_timeline)
    slow_avg = float(timeline.get("rule_writeback_avg_delay_sec", 0.0))
    patch_counts = [float(row["patch_count"]) for row in rows]
    total_tokens = [float(row["total_tokens"]) for row in rows]
    call_seconds = [float(row["call_seconds"]) for row in rows]

    token_intercept, token_per_patch = fit_linear(patch_counts, total_tokens)
    token_intercept = max(0.0, token_intercept)
    call_intercept, call_per_token = fit_linear(total_tokens, call_seconds)
    call_intercept = max(0.0, call_intercept)

    observed_total_tokens = sum(total_tokens)
    observed_avg_call = mean(call_seconds)
    observed_p95_call = percentile(call_seconds, 0.95)

    policy_rows = []
    detail_rows: list[dict[str, Any]] = []
    for max_patches in args.max_patches:
        simulated_calls = []
        simulated_corrections = []
        simulated_tokens_total = 0.0
        calls = 0
        split_windows = 0
        max_subcalls = 0
        for row in rows:
            patch_count = int(row["patch_count"])
            sizes = chunk_sizes(patch_count, max_patches)
            if len(sizes) > 1:
                split_windows += 1
            max_subcalls = max(max_subcalls, len(sizes))
            calls += len(sizes)
            per_patch_tokens = max(token_per_patch, (float(row["total_tokens"]) - token_intercept) / patch_count)
            chunk_tokens = [token_intercept + per_patch_tokens * size for size in sizes]
            chunk_calls = [call_intercept + call_per_token * tokens for tokens in chunk_tokens]
            window_call = max(chunk_calls)
            simulated_tokens_total += sum(chunk_tokens)
            simulated_calls.append(window_call)
            simulated_corrections.append(slow_avg + window_call)
            detail_rows.append(
                {
                    "max_patches_per_call": max_patches,
                    "window_id": row["window_id"],
                    "patch_count": patch_count,
                    "subcalls": len(sizes),
                    "largest_subcall_patch_count": max(sizes),
                    "observed_call_seconds": row["call_seconds"],
                    "simulated_parallel_call_seconds": round(window_call, 3),
                    "observed_total_tokens": row["total_tokens"],
                    "simulated_total_tokens": round(sum(chunk_tokens), 1),
                    "window_decision": row["window_decision"],
                }
            )
        policy_rows.append(
            {
                "max_patches_per_call": max_patches,
                "split_windows": split_windows,
                "calls": calls,
                "added_calls": calls - len(rows),
                "max_parallel_subcalls": max_subcalls,
                "avg_call_seconds": round(mean(simulated_calls), 3),
                "p95_call_seconds": round(percentile(simulated_calls, 0.95), 3),
                "max_call_seconds": round(max(simulated_calls), 3),
                "avg_correction_delay_seconds": round(mean(simulated_corrections), 3),
                "p95_correction_delay_seconds": round(percentile(simulated_corrections, 0.95), 3),
                "token_multiplier": round(simulated_tokens_total / observed_total_tokens, 3) if observed_total_tokens else 0.0,
                "p95_call_reduction_seconds": round(observed_p95_call - percentile(simulated_calls, 0.95), 3),
            }
        )

    recommended = min(
        policy_rows,
        key=lambda row: (
            0 if row["p95_call_seconds"] <= 25.0 else 1,
            row["token_multiplier"],
            row["added_calls"],
        ),
    )
    summary = {
        "windows": len(rows),
        "observed_calls": len(rows),
        "observed_avg_call_seconds": observed_avg_call,
        "observed_p95_call_seconds": observed_p95_call,
        "observed_max_call_seconds": max(call_seconds) if call_seconds else 0.0,
        "token_intercept": token_intercept,
        "token_per_patch": token_per_patch,
        "call_intercept": call_intercept,
        "call_per_token": call_per_token,
        "policies": policy_rows,
        "recommended_policy": recommended,
        "latency_csv": str(args.latency_csv),
        "system_timeline": str(args.system_timeline),
    }

    write_csv(detail_rows, args.output_csv)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, args.output_md)
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.summary_json}")


if __name__ == "__main__":
    main()
