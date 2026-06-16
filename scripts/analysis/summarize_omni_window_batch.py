#!/usr/bin/env python3
"""Summarize Omni guard window batch outputs."""

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
from collections import Counter, defaultdict
from pathlib import Path


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def is_positive(row: dict[str, str]) -> bool:
    return row.get("diarization_risk") in {"medium", "high"} or str(row.get("should_quarantine")) == "True"


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", nargs="+", type=Path)
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/omni_guard/omni_window_batch_summary.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/omni_guard/omni_window_batch_summary.md"))
    args = parser.parse_args()

    rows = []
    for path in args.input_csv:
        rows.extend(load_csv(path))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["model"]].append(row)

    summary_rows = []
    for model, model_rows in grouped.items():
        buckets = Counter(row["bucket"] for row in model_rows)
        risks = Counter(row["diarization_risk"] for row in model_rows)
        positives_by_bucket = Counter(row["bucket"] for row in model_rows if is_positive(row))
        quarantines = sum(1 for row in model_rows if str(row["should_quarantine"]) == "True")
        defers = sum(1 for row in model_rows if str(row["should_defer_to_slow_agent"]) == "True")
        latencies = [float(row["call_seconds"]) for row in model_rows if row.get("call_seconds")]
        high_total = buckets["high"]
        high_positive = positives_by_bucket["high"]
        clean_total = buckets["clean"]
        clean_positive = positives_by_bucket["clean"]
        summary_rows.append(
            {
                "model": model,
                "windows": str(len(model_rows)),
                "risk_counts": " / ".join(f"{key} {risks[key]}" for key in sorted(risks)),
                "high_positive_rate": f"{high_positive}/{high_total}" if high_total else "n/a",
                "clean_false_positive_rate": f"{clean_positive}/{clean_total}" if clean_total else "n/a",
                "quarantines": str(quarantines),
                "defers": str(defers),
                "avg_call_seconds": f"{sum(latencies) / len(latencies):.3f}" if latencies else "",
                "p95_call_seconds": f"{percentile(latencies, 0.95):.3f}" if latencies else "",
                "max_call_seconds": f"{max(latencies):.3f}" if latencies else "",
                "verdict": (
                    "fast risk hint, weak recall"
                    if "flash" in model and "plus" not in model
                    else "conservative high-risk sentinel"
                ),
            }
        )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    lines = [
        "| Model | Windows | Risk counts | High positive | Clean false positive | Quarantine | Defer | Avg call | P95 call | Max call | Verdict |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary_rows:
        lines.append(
            "| {model} | {windows} | {risk_counts} | {high_positive_rate} | {clean_false_positive_rate} | {quarantines} | {defers} | {avg_call_seconds}s | {p95_call_seconds}s | {max_call_seconds}s | {verdict} |".format(
                **row
            )
        )
    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
