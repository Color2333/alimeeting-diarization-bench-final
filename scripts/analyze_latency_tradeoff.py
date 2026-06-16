#!/usr/bin/env python3
"""Summarize latency/RTF tradeoffs from benchmark summary files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    frac = pos - lo
    return values[lo] * (1 - frac) + values[hi] * frac


def infer_model_role(model_name: str) -> str:
    lowered = model_name.lower()
    if "streaming" in lowered:
        return "fast_streaming_candidate"
    if "sortformer" in lowered:
        return "fast_agent"
    if "diarizen" in lowered:
        return "slow_agent"
    if "pyannote" in lowered:
        return "baseline"
    return "other"


def summarize(path: Path) -> dict:
    data = json.loads(path.read_text())
    results = [row for row in data.get("results", []) if row.get("success")]
    latencies = [float(row.get("latency") or 0.0) for row in results]
    window_sizes = [float(row.get("window_size") or 0.0) for row in results]
    rtfs = [lat / win for lat, win in zip(latencies, window_sizes) if win > 0]
    model_name = data.get("model_name", "")
    return {
        "summary": str(path),
        "model_name": model_name,
        "role": infer_model_role(model_name),
        "segments": len(results),
        "window_size_sec": window_sizes[0] if window_sizes else 0.0,
        "avg_der": float(data.get("avg_der") or 0.0),
        "avg_miss_rate": float(data.get("avg_miss_rate") or 0.0),
        "avg_fa_rate": float(data.get("avg_fa_rate") or 0.0),
        "avg_conf_rate": float(data.get("avg_conf_rate") or 0.0),
        "avg_latency_sec": sum(latencies) / len(latencies) if latencies else 0.0,
        "p50_latency_sec": percentile(latencies, 0.50),
        "p90_latency_sec": percentile(latencies, 0.90),
        "p95_latency_sec": percentile(latencies, 0.95),
        "max_latency_sec": max(latencies) if latencies else 0.0,
        "avg_rtf": sum(rtfs) / len(rtfs) if rtfs else 0.0,
        "p95_rtf": percentile(rtfs, 0.95),
        "throughput_x_realtime": (1.0 / (sum(rtfs) / len(rtfs))) if rtfs and sum(rtfs) > 0 else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/latency_tradeoff/summary.csv"))
    parser.add_argument("--json-output", type=Path, default=None)
    args = parser.parse_args()

    rows = [summarize(path) for path in args.summary]
    rows.sort(key=lambda row: (row["role"], row["avg_rtf"], row["avg_der"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    json_output = args.json_output or args.output.with_suffix(".json")
    json_output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Latency / DER tradeoff")
    print("csv=%s json=%s" % (args.output, json_output))
    for row in rows:
        print(
            "%-30s %-24s n=%d win=%.0fs DER=%.2f%% avg=%.2fs p95=%.2fs RTF=%.3f xRT=%.1f"
            % (
                row["role"],
                row["model_name"],
                row["segments"],
                row["window_size_sec"],
                row["avg_der"] * 100,
                row["avg_latency_sec"],
                row["p95_latency_sec"],
                row["avg_rtf"],
                row["throughput_x_realtime"],
            )
        )


if __name__ == "__main__":
    main()
