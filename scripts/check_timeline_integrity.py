#!/usr/bin/env python3
"""Check generated timeline artifacts for runtime integrity.

This validates the output surface itself: JSON/CSV/RTTM consistency, positive
durations, local/global timing consistency, window segment counts, and
same-speaker self-overlap. It does not use ground truth or DER.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def rttm_line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def issue(severity: str, code: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "detail": detail or {},
    }


def same_speaker_overlaps(rows: list[dict[str, Any]], tolerance: float) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("recording_id", "")), str(row.get("speaker", "")))].append(row)

    overlaps = []
    for (recording_id, speaker), items in grouped.items():
        items.sort(key=lambda row: (as_float(row.get("start")), as_float(row.get("end"))))
        prev: dict[str, Any] | None = None
        for row in items:
            if prev and as_float(row.get("start")) < as_float(prev.get("end")) - tolerance:
                overlaps.append(
                    {
                        "recording_id": recording_id,
                        "speaker": speaker,
                        "prev_window_id": prev.get("window_id"),
                        "window_id": row.get("window_id"),
                        "prev_start": prev.get("start"),
                        "prev_end": prev.get("end"),
                        "start": row.get("start"),
                        "end": row.get("end"),
                    }
                )
            if prev is None or as_float(row.get("end")) > as_float(prev.get("end")):
                prev = row
    return overlaps


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Timeline Integrity Check",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Timeline rows: `{payload['summary']['timeline_rows']}`",
        f"- Window rows: `{payload['summary']['window_rows']}`",
        f"- Issues: `{payload['summary']['fail_count']}` fail, `{payload['summary']['warn_count']}` warn",
        "",
        "## Checks",
        "",
        "| Severity | Code | Message |",
        "|---|---|---|",
    ]
    for row in payload["issues"]:
        lines.append(f"| `{row['severity']}` | `{row['code']}` | {row['message']} |")
    if not payload["issues"]:
        lines.append("| `pass` | `no_issues` | no timeline integrity issues detected |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline-json", type=Path, default=Path("outputs/system_demo/all_cached_recordings/final_timeline.json"))
    parser.add_argument("--timeline-csv", type=Path, default=Path("outputs/system_demo/all_cached_recordings/final_timeline.csv"))
    parser.add_argument("--timeline-rttm", type=Path, default=Path("outputs/system_demo/all_cached_recordings/final_timeline.rttm"))
    parser.add_argument("--window-metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/window_metrics.json"))
    parser.add_argument("--time-tolerance", type=float, default=1e-3)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/timeline_integrity"))
    args = parser.parse_args()

    rows = read_json_list(args.timeline_json)
    csv_rows = read_csv_rows(args.timeline_csv)
    window_rows = read_json_list(args.window_metrics)
    rttm_rows = rttm_line_count(args.timeline_rttm)
    issues: list[dict[str, Any]] = []

    if not rows:
        issues.append(issue("fail", "timeline_json_nonempty", "final timeline JSON is missing or empty", {"path": str(args.timeline_json)}))
    if len(csv_rows) != len(rows):
        issues.append(issue("fail", "csv_json_row_count_match", "final timeline CSV row count differs from JSON", {"json": len(rows), "csv": len(csv_rows)}))
    if rttm_rows != len(rows):
        issues.append(issue("fail", "rttm_json_row_count_match", "final timeline RTTM line count differs from JSON", {"json": len(rows), "rttm": rttm_rows}))

    nonpositive = []
    bad_local_global = []
    for row in rows:
        start = as_float(row.get("start"))
        end = as_float(row.get("end"))
        local_start = as_float(row.get("local_start"))
        local_end = as_float(row.get("local_end"))
        offset = start - local_start
        if end <= start:
            nonpositive.append(row.get("segment_id"))
        if abs((end - local_end) - offset) > args.time_tolerance:
            bad_local_global.append(row.get("segment_id"))
    if nonpositive:
        issues.append(issue("fail", "positive_durations", "timeline contains non-positive duration segments", {"count": len(nonpositive), "examples": nonpositive[:10]}))
    if bad_local_global:
        issues.append(issue("fail", "local_global_time_consistency", "local/global start-end offsets are inconsistent", {"count": len(bad_local_global), "examples": bad_local_global[:10]}))

    expected_by_window = {
        str(row.get("window_id")): int(as_float(row.get("final_segments")))
        for row in window_rows
        if row.get("window_id") is not None
    }
    actual_by_window: dict[str, int] = defaultdict(int)
    for row in rows:
        actual_by_window[str(row.get("window_id"))] += 1
    mismatched_windows = [
        {"window_id": window_id, "expected": expected, "actual": actual_by_window.get(window_id, 0)}
        for window_id, expected in expected_by_window.items()
        if actual_by_window.get(window_id, 0) != expected
    ]
    if mismatched_windows:
        issues.append(issue("fail", "window_final_segment_counts_match", "final timeline row counts do not match window_metrics final_segments", {"count": len(mismatched_windows), "examples": mismatched_windows[:10]}))

    overlaps = same_speaker_overlaps(rows, args.time_tolerance)
    if overlaps:
        issues.append(issue("fail", "no_same_speaker_self_overlap", "same recording/speaker has overlapping final timeline segments", {"count": len(overlaps), "examples": overlaps[:10]}))

    fail_count = sum(1 for row in issues if row["severity"] == "fail")
    warn_count = sum(1 for row in issues if row["severity"] == "warn")
    payload = {
        "runtime_contract": "timeline_integrity_no_gt_no_live_calls",
        "status": "fail" if fail_count else ("warn" if warn_count else "pass"),
        "summary": {
            "timeline_rows": len(rows),
            "csv_rows": len(csv_rows),
            "rttm_rows": rttm_rows,
            "window_rows": len(window_rows),
            "window_segments_total": sum(expected_by_window.values()),
            "same_speaker_overlap_count": len(overlaps),
            "fail_count": fail_count,
            "warn_count": warn_count,
        },
        "inputs": {
            "timeline_json": str(args.timeline_json),
            "timeline_csv": str(args.timeline_csv),
            "timeline_rttm": str(args.timeline_rttm),
            "window_metrics": str(args.window_metrics),
        },
        "issues": issues,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "final_timeline_integrity.json"
    md_path = args.output_dir / "final_timeline_integrity.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"status={payload['status']} rows={len(rows)} fail={fail_count} warn={warn_count}")
    raise SystemExit(1 if fail_count else 0)


if __name__ == "__main__":
    main()
