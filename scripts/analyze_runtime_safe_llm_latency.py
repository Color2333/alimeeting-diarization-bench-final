#!/usr/bin/env python3
"""Break down runtime-safe LLM guard latency by window decision and patch load."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
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


def counter_text(counter: Counter[str]) -> str:
    return " / ".join(f"{key} {counter[key]}" for key in sorted(counter))


def patch_bucket(count: int) -> str:
    if count <= 2:
        return "01_<=2"
    if count <= 5:
        return "02_3-5"
    if count <= 15:
        return "03_6-15"
    return "04_>15"


def group_stats(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)
    stats = []
    for group_key, items in sorted(groups.items()):
        calls = [float(row["call_seconds"]) for row in items]
        corrections = [float(row["correction_delay_avgslow_seconds"]) for row in items]
        patch_counts = [float(row["patch_count"]) for row in items]
        tokens = [float(row["total_tokens"]) for row in items]
        stats.append(
            {
                key: group_key,
                "windows": len(items),
                "patches": int(sum(patch_counts)),
                "avg_patch_count": round(mean(patch_counts), 2),
                "avg_call_seconds": round(mean(calls), 3),
                "median_call_seconds": round(percentile(calls, 0.5), 3),
                "p95_call_seconds": round(percentile(calls, 0.95), 3),
                "avg_correction_delay_seconds": round(mean(corrections), 3),
                "p95_correction_delay_seconds": round(percentile(corrections, 0.95), 3),
                "avg_total_tokens": round(mean(tokens), 1),
            }
        )
    return stats


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Runtime-Safe LLM Guard Latency Breakdown",
        "",
        "| Windows | Patches | Avg call | Median call | P95 call | Max call | Avg correction | P95 correction | Avg tokens/window |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        (
            "| {windows} | {patches} | {avg_call_seconds:.2f}s | {median_call_seconds:.2f}s | "
            "{p95_call_seconds:.2f}s | {max_call_seconds:.2f}s | "
            "{avg_correction_delay_seconds:.2f}s | {p95_correction_delay_seconds:.2f}s | "
            "{avg_total_tokens:.0f} |"
        ).format(**summary),
        "",
        "## By Window Decision",
        "",
        "| Decision | Windows | Patches | Avg patches/window | Avg call | P95 call | Avg correction | P95 correction |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["by_window_decision"]:
        lines.append(
            "| {window_decision} | {windows} | {patches} | {avg_patch_count:.2f} | "
            "{avg_call_seconds:.2f}s | {p95_call_seconds:.2f}s | "
            "{avg_correction_delay_seconds:.2f}s | {p95_correction_delay_seconds:.2f}s |".format(**row)
        )
    lines.extend(
        [
            "",
            "## By Patch Count Bucket",
            "",
            "| Patch bucket | Windows | Patches | Avg patches/window | Avg call | P95 call | Avg correction | P95 correction |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary["by_patch_bucket"]:
        lines.append(
            "| {patch_bucket} | {windows} | {patches} | {avg_patch_count:.2f} | "
            "{avg_call_seconds:.2f}s | {p95_call_seconds:.2f}s | "
            "{avg_correction_delay_seconds:.2f}s | {p95_correction_delay_seconds:.2f}s |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Slowest Windows",
            "",
            "| Window | Decision | Patches | Call | Correction delay | Tokens | Reason |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in summary["slowest_windows"]:
        lines.append(
            "| {window_id} | {window_decision} | {patch_count} | {call_seconds:.2f}s | "
            "{correction_delay_avgslow_seconds:.2f}s | {total_tokens} | {window_reason} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Correction delay here is estimated as current rule-writeback average delay plus each measured LLM call time.",
            "- The existing safety summary keeps the conservative P95 contract as slow-layer P95 plus LLM-call P95.",
            "- Patch count is a useful but incomplete latency driver; model-side generation and token count still dominate some outliers.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-jsonl", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w.jsonl"))
    parser.add_argument("--system-timeline", type=Path, default=Path("outputs/system_timeline/summary.json"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_latency.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_latency.md"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_latency_summary.json"))
    args = parser.parse_args()

    timeline = load_json(args.system_timeline)
    slow_avg = float(timeline.get("rule_writeback_avg_delay_sec", 0.0))
    batch_rows = load_jsonl(args.batch_jsonl)

    rows: list[dict[str, Any]] = []
    window_decisions: Counter[str] = Counter()
    patch_decisions: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    for row in batch_rows:
        patch_count = int(row.get("patch_count") or len(row.get("patch_decisions", [])))
        call_seconds = float(row.get("call_seconds") or 0.0)
        total_tokens = int(row.get("total_tokens") or 0)
        window_decision = str(row.get("window_decision", "unknown"))
        reason = str(row.get("window_reason", ""))
        window_decisions[window_decision] += 1
        reasons[reason] += 1
        for patch in row.get("patch_decisions", []):
            patch_decisions[str(patch.get("decision", "unknown"))] += 1
        rows.append(
            {
                "window_id": row["window_id"],
                "recording_id": str(row["window_id"]).split(":")[0],
                "segment_idx": str(row["window_id"]).split(":")[-1],
                "window_decision": window_decision,
                "window_reason": reason,
                "patch_count": patch_count,
                "patch_bucket": patch_bucket(patch_count),
                "call_seconds": round(call_seconds, 3),
                "correction_delay_avgslow_seconds": round(slow_avg + call_seconds, 3),
                "prompt_tokens": int(row.get("prompt_tokens") or 0),
                "completion_tokens": int(row.get("completion_tokens") or 0),
                "total_tokens": total_tokens,
                "tokens_per_patch": round(total_tokens / patch_count, 1) if patch_count else 0.0,
                "seconds_per_patch": round(call_seconds / patch_count, 3) if patch_count else 0.0,
                "patch_decision_counts": row.get("patch_decision_counts", ""),
            }
        )

    calls = [float(row["call_seconds"]) for row in rows]
    corrections = [float(row["correction_delay_avgslow_seconds"]) for row in rows]
    patch_counts = [float(row["patch_count"]) for row in rows]
    total_tokens = [float(row["total_tokens"]) for row in rows]
    summary = {
        "windows": len(rows),
        "patches": int(sum(patch_counts)),
        "window_decisions": counter_text(window_decisions),
        "patch_decisions": counter_text(patch_decisions),
        "top_window_reasons": counter_text(Counter(dict(reasons.most_common(8)))),
        "avg_patch_count": round(mean(patch_counts), 2),
        "avg_call_seconds": mean(calls),
        "median_call_seconds": percentile(calls, 0.5),
        "p90_call_seconds": percentile(calls, 0.9),
        "p95_call_seconds": percentile(calls, 0.95),
        "max_call_seconds": max(calls) if calls else 0.0,
        "avg_correction_delay_seconds": mean(corrections),
        "median_correction_delay_seconds": percentile(corrections, 0.5),
        "p90_correction_delay_seconds": percentile(corrections, 0.9),
        "p95_correction_delay_seconds": percentile(corrections, 0.95),
        "max_correction_delay_seconds": max(corrections) if corrections else 0.0,
        "avg_total_tokens": mean(total_tokens),
        "p95_total_tokens": percentile(total_tokens, 0.95),
        "max_total_tokens": max(total_tokens) if total_tokens else 0,
        "by_window_decision": group_stats(rows, "window_decision"),
        "by_patch_bucket": group_stats(rows, "patch_bucket"),
        "slowest_windows": sorted(rows, key=lambda item: float(item["call_seconds"]), reverse=True)[:8],
        "batch_jsonl": str(args.batch_jsonl),
        "system_timeline": str(args.system_timeline),
    }

    write_csv(rows, args.output_csv)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, args.output_md)
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.summary_json}")


if __name__ == "__main__":
    main()
