#!/usr/bin/env python3
"""Select clean high-voiceprint rule-auto windows for LLM audit replay."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_WINDOWS = [
    "R8003_M8001:30:2",
    "R8009_M8018:30:2",
    "R8009_M8018:30:11",
    "R8009_M8019:30:13",
    "R8009_M8020:30:6",
    "R8009_M8020:30:10",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def window_id_from_patch_id(patch_id: str) -> str:
    recording_id, window_size, segment_idx, *_ = patch_id.split(":")
    return f"{recording_id}:{window_size}:{segment_idx}"


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "window_id",
        "patches",
        "recording_id",
        "segment_idx",
        "total_duration",
        "avg_margin",
        "min_margin",
        "max_margin",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-csv", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_candidate_120_audit.csv"))
    parser.add_argument("--window-id", action="append", default=[], help="Optional recording_id:window_size:segment_idx. Can be repeated.")
    parser.add_argument("--max-windows", type=int, default=None, help="Use the largest remaining windows after explicit selection.")
    parser.add_argument("--output-patch-ids", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_expanded_patch_ids.txt"))
    parser.add_argument("--output-window-ids", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_expanded_window_ids.txt"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_expanded_windows.csv"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_expanded_summary.json"))
    args = parser.parse_args()

    rows = [
        row
        for row in load_csv(args.audit_csv)
        if row.get("candidate_class") == "voiceprint_high_rule_auto"
    ]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[window_id_from_patch_id(row["patch_id"])].append(row)

    requested = args.window_id or DEFAULT_WINDOWS
    selected_ids = [window_id for window_id in requested if window_id in grouped]
    missing_ids = [window_id for window_id in requested if window_id not in grouped]
    if args.max_windows is not None and len(selected_ids) < args.max_windows:
        ranked = sorted(
            grouped,
            key=lambda window_id: (
                -len(grouped[window_id]),
                grouped[window_id][0]["recording_id"],
                int(grouped[window_id][0]["segment_idx"]),
            ),
        )
        for window_id in ranked:
            if window_id not in selected_ids:
                selected_ids.append(window_id)
            if len(selected_ids) >= args.max_windows:
                break

    selected_rows = []
    patch_ids = []
    recordings = set()
    for window_id in selected_ids:
        patches = sorted(grouped[window_id], key=lambda row: row["patch_id"])
        margins = [float(row["similarity_margin"]) for row in patches if row.get("similarity_margin")]
        durations = [float(row["duration"]) for row in patches if row.get("duration")]
        recordings.add(patches[0]["recording_id"])
        patch_ids.extend(row["patch_id"] for row in patches)
        selected_rows.append(
            {
                "window_id": window_id,
                "patches": len(patches),
                "recording_id": patches[0]["recording_id"],
                "segment_idx": patches[0]["segment_idx"],
                "total_duration": f"{sum(durations):.2f}",
                "avg_margin": f"{mean(margins):.3f}",
                "min_margin": f"{min(margins):.3f}" if margins else "0.000",
                "max_margin": f"{max(margins):.3f}" if margins else "0.000",
            }
        )

    if not selected_rows:
        raise SystemExit("No high voiceprint rule-auto windows selected")

    args.output_patch_ids.parent.mkdir(parents=True, exist_ok=True)
    args.output_patch_ids.write_text("\n".join(patch_ids) + "\n", encoding="utf-8")
    args.output_window_ids.write_text("\n".join(selected_ids) + "\n", encoding="utf-8")
    write_csv(selected_rows, args.output_csv)
    summary = {
        "audit_csv": str(args.audit_csv),
        "selected_windows": len(selected_ids),
        "selected_patches": len(patch_ids),
        "recordings": sorted(recordings),
        "missing_requested_windows": missing_ids,
        "window_ids": selected_ids,
        "runtime_contract": "clean_high_voiceprint_rule_auto_audit_sample",
    }
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output_patch_ids}")
    print(f"Wrote {args.output_window_ids}")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.summary_json}")


if __name__ == "__main__":
    main()
