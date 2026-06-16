#!/usr/bin/env python3
"""Build a synthetic writeback gate from materialized tuned LLM guard decisions."""

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
from pathlib import Path


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(rows: list[dict[str, str]], path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-gate", type=Path, default=Path("outputs/writeback_gate_120/gate_decisions.csv"))
    parser.add_argument("--tuned-safety", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_passthrough_safety.csv"))
    parser.add_argument("--runtime-decisions", type=Path, default=Path("outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.csv"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/tuned_v2_writeback_gate_decisions.csv"))
    args = parser.parse_args()

    gate_rows = load_csv(args.base_gate)
    runtime_by_patch = {row["patch_id"]: row for row in load_csv(args.runtime_decisions)}
    tuned_accepts = {
        row["patch_id"]: row
        for row in load_csv(args.tuned_safety)
        if row.get("effective_decision") == "accept" and row.get("patch_type") == "boundary_fix_or_relabel"
    }

    rows_by_patch = {row["patch_id"]: dict(row) for row in gate_rows}
    added = 0
    upgraded = 0
    for patch_id in sorted(tuned_accepts):
        runtime = runtime_by_patch.get(patch_id)
        if not runtime:
            continue
        row = rows_by_patch.get(patch_id)
        if row is None:
            row = {
                "patch_id": patch_id,
                "recording_id": runtime["recording_id"],
                "window_size": runtime["window_size"],
                "segment_idx": runtime["segment_idx"],
                "patch_type": runtime["patch_type"],
                "decision": "accept",
                "reason": runtime.get("reason", ""),
                "duration": runtime.get("duration", ""),
                "support_ratio": runtime.get("support_ratio", ""),
                "abnormal_flags": runtime.get("abnormal_flags", ""),
                "voiceprint_bucket": "",
                "voiceprint_status": "",
                "gate_category": "rule_auto_writeback",
                "gate_blockers": "llm_guard_tuned_passthrough_v2",
            }
            rows_by_patch[patch_id] = row
            added += 1
        elif row.get("gate_category") not in {"rule_auto_writeback", "rule_label_only_writeback", "rule_recover_writeback"}:
            row["gate_category"] = "rule_auto_writeback"
            row["gate_blockers"] = "llm_guard_tuned_passthrough_v2"
            upgraded += 1

    output_rows = list(rows_by_patch.values())
    fieldnames = list(gate_rows[0].keys())
    write_csv(output_rows, args.output_csv, fieldnames)
    print(
        {
            "base_rows": len(gate_rows),
            "output_rows": len(output_rows),
            "tuned_boundary_accepts": len(tuned_accepts),
            "added": added,
            "upgraded": upgraded,
            "output_csv": str(args.output_csv),
        }
    )


if __name__ == "__main__":
    main()
