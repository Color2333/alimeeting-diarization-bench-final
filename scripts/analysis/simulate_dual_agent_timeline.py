#!/usr/bin/env python3
"""Simulate correction arrival latency for the Fast/Slow/LLM agent pipeline."""

from __future__ import annotations

# Keep categorized scripts import-compatible when executed by file path.
import sys as _sys
from pathlib import Path as _Path
_SCRIPT_ROOT = _Path(__file__).resolve().parents[1]
_REPO_ROOT = _SCRIPT_ROOT.parent
for _candidate in [_REPO_ROOT, _SCRIPT_ROOT, *_SCRIPT_ROOT.iterdir()]:
    if _candidate.is_dir():
        _value = str(_candidate)
        if _value not in _sys.path:
            _sys.path.insert(0, _value)

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any, Callable


Row = dict[str, Any]


def load_jsonl(path: Path) -> list[Row]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = round((len(ordered) - 1) * q)
    return ordered[idx]


def has_high_error(row: Row) -> bool:
    return any("high_der" in flag or "high_fa" in flag for flag in row.get("abnormal_flags", []))


def has_slow_quarantine_flag(row: Row) -> bool:
    return any(flag.startswith("slow_high_der") or flag.startswith("slow_high_fa") for flag in row.get("abnormal_flags", []))


def policy_predicate(name: str) -> Callable[[Row], bool]:
    if name == "none":
        return lambda row: False
    if name == "high_risk_quarantine":
        return (
            lambda row: has_high_error(row)
            or has_slow_quarantine_flag(row)
            or row["decision"] == "quarantine"
            or row["patch_type"] == "suppress_fast_candidate"
        )
    if name == "semantic_label_smoothing":
        return lambda row: row["reason"] in {
            "memory_low_confidence_relabel_deferred",
            "recover_segment_too_short",
            "do_not_suppress_without_strong_evidence",
        }
    if name == "non_accept_review":
        return lambda row: row["decision"] != "accept"
    if name == "manual_only":
        return lambda row: False
    raise ValueError(f"Unsupported trigger policy: {name}")


def find_latency(latency_rows: list[dict[str, str]], role: str) -> dict[str, float]:
    candidates = [row for row in latency_rows if row["role"] == role and row["segments"] == "48"]
    if not candidates:
        raise ValueError(f"Cannot find latency row for role={role}")
    row = candidates[0]
    return {
        "avg": float(row["avg_latency_sec"]),
        "p95": float(row["p95_latency_sec"]),
    }


def simulate_route(
    decisions: list[Row],
    route: dict[str, str],
    window_seconds: float,
    slow_latency: float,
    batch_mode: str,
    window_batch_multiplier: float,
) -> dict[str, Any]:
    pred = policy_predicate(route["trigger_policy"])
    selected = [row for row in decisions if pred(row)]
    window_keys = []
    seen = set()
    for row in decisions:
        key = (row["recording_id"], row["segment_idx"])
        if key not in seen:
            seen.add(key)
            window_keys.append(key)
    window_index = {key: idx for idx, key in enumerate(window_keys)}

    workers = max(1, int(float(route["workers_avg"] or 1))) if selected else 0
    service_seconds = float(route["avg_call_seconds"])
    if batch_mode == "window":
        service_seconds *= window_batch_multiplier
    worker_available = [0.0 for _ in range(workers)]
    call_records = []
    if batch_mode == "patch":
        call_items = [
            {
                "window": (row["recording_id"], row["segment_idx"]),
                "decision_index": row["decision_index"],
                "patch_count": 1,
            }
            for row in selected
        ]
    elif batch_mode == "window":
        grouped: dict[tuple[str, int], int] = {}
        for row in selected:
            key = (row["recording_id"], row["segment_idx"])
            grouped[key] = grouped.get(key, 0) + 1
        call_items = [
            {
                "window": key,
                "decision_index": 0,
                "patch_count": count,
            }
            for key, count in grouped.items()
        ]
    else:
        raise ValueError(f"Unsupported batch mode: {batch_mode}")

    for item in sorted(call_items, key=lambda call: (window_index[call["window"]], call["decision_index"])):
        key = item["window"]
        window_end = (window_index[key] + 1) * window_seconds
        arrival = window_end + slow_latency
        worker_id = min(range(workers), key=lambda idx: worker_available[idx])
        start = max(arrival, worker_available[worker_id])
        finish = start + service_seconds
        worker_available[worker_id] = finish
        call_records.append(
            {
                "window": key,
                "patch_count": item["patch_count"],
                "arrival": arrival,
                "start": start,
                "finish": finish,
                "queue_wait": start - arrival,
                "delay_from_window_end": finish - window_end,
                "delay_after_slow": finish - arrival,
            }
        )

    delays = [record["delay_from_window_end"] for record in call_records]
    waits = [record["queue_wait"] for record in call_records]
    touched = {record["window"] for record in call_records}
    return {
        "route": route["route"],
        "batch_mode": batch_mode,
        "trigger_policy": route["trigger_policy"],
        "model": route["model"],
        "workers": workers,
        "calls": len(call_records),
        "patches_covered": len(selected),
        "windows_touched": len(touched),
        "service_seconds": service_seconds,
        "avg_queue_wait_seconds": mean(waits) if waits else 0.0,
        "p95_queue_wait_seconds": percentile(waits, 0.95),
        "avg_correction_delay_seconds": mean(delays) if delays else 0.0,
        "p95_correction_delay_seconds": percentile(delays, 0.95),
        "max_correction_delay_seconds": max(delays) if delays else 0.0,
        "last_finish_at_seconds": max((record["finish"] for record in call_records), default=0.0),
    }


def write_outputs(output_dir: Path, rows: list[dict[str, Any]], fast_latency: dict[str, float], slow_latency: dict[str, float]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "timeline_simulation.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "## Dual-Agent Timeline Simulation",
        "",
        f"- Fast provisional latency: avg {fast_latency['avg']:.2f}s, p95 {fast_latency['p95']:.2f}s after each 30s window.",
        f"- Slow mature patch latency: avg {slow_latency['avg']:.2f}s, p95 {slow_latency['p95']:.2f}s after each 30s window.",
        "",
        "| Route | Mode | Model | Workers | Calls | Patches | Windows | Avg correction delay | P95 correction delay | Max correction delay | Avg queue wait |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {route} | {batch_mode} | {model} | {workers} | {calls} | {patches_covered} | {windows_touched} | {avg_correction_delay_seconds:.1f}s | {p95_correction_delay_seconds:.1f}s | {max_correction_delay_seconds:.1f}s | {avg_queue_wait_seconds:.1f}s |".format(
                **row
            )
        )
    (output_dir / "timeline_simulation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = {
        "fast_avg_latency_seconds": fast_latency["avg"],
        "slow_avg_latency_seconds": slow_latency["avg"],
        "output_csv": str(csv_path),
        "output_md": str(output_dir / "timeline_simulation.md"),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, default=Path("outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl"))
    parser.add_argument("--routing-plan", type=Path, default=Path("outputs/llm_policy_agent/routing_plan.csv"))
    parser.add_argument("--latencies", type=Path, default=Path("outputs/latency_tradeoff/main_models.csv"))
    parser.add_argument("--window-seconds", type=float, default=30.0)
    parser.add_argument("--window-batch-multiplier", type=float, default=1.25)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/dual_agent_timeline"))
    args = parser.parse_args()

    decisions = load_jsonl(args.decisions)
    routes = load_csv(args.routing_plan)
    latency_rows = load_csv(args.latencies)
    fast_latency = find_latency(latency_rows, "fast_agent")
    slow_latency = find_latency(latency_rows, "slow_agent")

    rows = []
    for route in routes:
        if route["route"] not in {"high_risk_guard", "limited_writeback", "offline_cross_check"}:
            continue
        for batch_mode in ["patch", "window"]:
            rows.append(
                simulate_route(
                    decisions,
                    route,
                    args.window_seconds,
                    slow_latency["avg"],
                    batch_mode=batch_mode,
                    window_batch_multiplier=args.window_batch_multiplier,
                )
            )
    write_outputs(args.output_dir, rows, fast_latency, slow_latency)
    print((args.output_dir / "timeline_simulation.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
