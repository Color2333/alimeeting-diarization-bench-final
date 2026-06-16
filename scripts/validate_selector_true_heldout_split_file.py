#!/usr/bin/env python3
"""Validate the sealed selector true-heldout split file without scoring metrics."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPLIT = Path("data/selector_true_heldout_split.csv")
OUTPUT_JSON = Path("outputs/research_progress_snapshot/selector_true_heldout_split_validation.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/selector_true_heldout_split_validation.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/selector_true_heldout_split_validation.csv")
REQUIRED_COLUMNS = ["recording_id", "split", "source_manifest", "audio_path"]
OPTIONAL_COLUMNS = ["textgrid_path", "notes"]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def existing_path(value: str) -> bool:
    return bool(value) and Path(value).expanduser().exists()


def build_validation(root: Path, split_file: Path, min_true_heldout: int) -> dict[str, Any]:
    split_path = split_file if split_file.is_absolute() else root / split_file
    rows = read_csv(split_path)
    candidate_scan = read_json(root / "outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.json")
    per_recording = read_csv(root / "outputs/realtime_contract_recording_stability_120/per_recording.csv")
    dev_recordings = sorted({row["group"] for row in per_recording if row.get("group")})

    fieldnames = list(rows[0].keys()) if rows else []
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    extra_columns = [column for column in fieldnames if column not in REQUIRED_COLUMNS + OPTIONAL_COLUMNS]
    valid_roles = {"train", "dev", "true_heldout"}
    true_rows = [row for row in rows if row.get("split") == "true_heldout"]
    true_recordings = sorted({row.get("recording_id", "") for row in true_rows if row.get("recording_id")})
    all_recordings = [row.get("recording_id", "") for row in rows if row.get("recording_id")]
    duplicate_recordings = sorted(recording for recording, count in Counter(all_recordings).items() if count > 1)
    invalid_roles = sorted({row.get("split", "") for row in rows if row.get("split") not in valid_roles})
    overlap_with_dev = sorted(set(true_recordings) & set(dev_recordings))
    missing_audio = [
        {"recording_id": row.get("recording_id", ""), "audio_path": row.get("audio_path", "")}
        for row in true_rows
        if not existing_path(row.get("audio_path", ""))
    ]
    missing_textgrid = [
        {"recording_id": row.get("recording_id", ""), "textgrid_path": row.get("textgrid_path", "")}
        for row in true_rows
        if "textgrid_path" in fieldnames and not existing_path(row.get("textgrid_path", ""))
    ]
    source_counts = Counter(row.get("source_manifest", "") for row in true_rows)

    blockers = []
    if not split_path.exists():
        blockers.append("missing_sealed_split_file")
    if split_path.exists() and missing_columns:
        blockers.append("missing_required_columns")
    if split_path.exists() and invalid_roles:
        blockers.append("invalid_split_roles")
    if len(true_recordings) < min_true_heldout:
        blockers.append("not_enough_true_heldout_recordings")
    if duplicate_recordings:
        blockers.append("duplicate_recording_rows")
    if overlap_with_dev:
        blockers.append("true_heldout_overlaps_development_pool")
    if missing_audio:
        blockers.append("true_heldout_audio_missing")
    if missing_textgrid:
        blockers.append("true_heldout_textgrid_missing")

    gates = [
        {
            "gate_id": "sealed_split_exists",
            "status": "pass" if split_path.exists() else "blocked",
            "evidence": str(split_file),
        },
        {
            "gate_id": "required_columns",
            "status": "pass" if split_path.exists() and not missing_columns else "blocked",
            "evidence": ",".join(missing_columns) if missing_columns else "all required columns present",
        },
        {
            "gate_id": "true_heldout_count",
            "status": "pass" if len(true_recordings) >= min_true_heldout else "blocked",
            "evidence": f"{len(true_recordings)}/{min_true_heldout}",
        },
        {
            "gate_id": "no_development_overlap",
            "status": "pass" if split_path.exists() and not overlap_with_dev else "blocked",
            "evidence": ",".join(overlap_with_dev) if overlap_with_dev else "no overlap" if split_path.exists() else "split missing",
        },
        {
            "gate_id": "audio_paths_exist",
            "status": "pass" if split_path.exists() and not missing_audio else "blocked",
            "evidence": str(len(missing_audio)),
        },
        {
            "gate_id": "textgrid_paths_exist_if_declared",
            "status": "pass" if split_path.exists() and not missing_textgrid else "blocked",
            "evidence": str(len(missing_textgrid)),
        },
        {
            "gate_id": "no_metric_claim",
            "status": "pass",
            "evidence": "validation only; no DER/GT/support scoring",
        },
    ]

    return {
        "runtime_contract": "selector_true_heldout_split_validation_no_metric_claim",
        "status": "ready_for_fixed_policy_scoring" if not blockers else "blocked_waiting_for_valid_sealed_split",
        "split_file": str(split_file),
        "minimum_true_heldout_recordings": min_true_heldout,
        "required_columns": REQUIRED_COLUMNS,
        "optional_columns": OPTIONAL_COLUMNS,
        "summary": {
            "split_exists": split_path.exists(),
            "rows": len(rows),
            "true_heldout_rows": len(true_rows),
            "true_heldout_recordings": len(true_recordings),
            "development_recordings": len(dev_recordings),
            "overlap_with_development": len(overlap_with_dev),
            "missing_required_columns": len(missing_columns),
            "invalid_role_count": len(invalid_roles),
            "duplicate_recordings": len(duplicate_recordings),
            "missing_audio_count": len(missing_audio),
            "missing_textgrid_count": len(missing_textgrid),
            "eligible_local_candidates": candidate_scan.get("summary", {}).get("eligible_true_heldout_recordings", 0),
            "missing_new_recordings_to_minimum": max(min_true_heldout - len(true_recordings), 0),
            "no_metric_claim": True,
            "sealed_split_written_by_validator": False,
        },
        "blockers": blockers,
        "gates": gates,
        "fieldnames": fieldnames,
        "missing_columns": missing_columns,
        "extra_columns": extra_columns,
        "invalid_roles": invalid_roles,
        "duplicate_recordings": duplicate_recordings,
        "true_heldout_recordings": true_recordings,
        "overlap_with_development_recordings": overlap_with_dev,
        "missing_audio": missing_audio[:20],
        "missing_textgrid": missing_textgrid[:20],
        "source_manifest_counts": dict(source_counts),
    }


def write_csv(validation: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["gate_id", "status", "evidence"])
        writer.writeheader()
        writer.writerows(validation["gates"])


def write_markdown(validation: dict[str, Any], path: Path) -> None:
    summary = validation["summary"]
    lines = [
        "# Selector True-Heldout Split Validation",
        "",
        f"- Runtime contract: `{validation['runtime_contract']}`",
        f"- Status: `{validation['status']}`",
        f"- Split file: `{validation['split_file']}`",
        f"- Minimum true-heldout recordings: `{validation['minimum_true_heldout_recordings']}`",
        f"- Split exists: `{summary['split_exists']}`",
        f"- Rows: `{summary['rows']}`",
        f"- True-heldout recordings: `{summary['true_heldout_recordings']}`",
        f"- Overlap with development: `{summary['overlap_with_development']}`",
        f"- Missing audio: `{summary['missing_audio_count']}`",
        f"- Missing TextGrid: `{summary['missing_textgrid_count']}`",
        f"- Missing required columns: `{summary['missing_required_columns']}`",
        f"- No metric claim: `{summary['no_metric_claim']}`",
        f"- Blockers: `{', '.join(validation['blockers']) if validation['blockers'] else 'none'}`",
        "",
        "## Gates",
        "",
        "| Gate | Status | Evidence |",
        "|---|---|---|",
    ]
    for gate in validation["gates"]:
        evidence = str(gate["evidence"]).replace("|", "/")
        lines.append(f"| `{gate['gate_id']}` | `{gate['status']}` | {evidence} |")
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This validator only checks the sealed split contract; it does not compute DER, GT support, or selector metrics.",
            "- A valid true-heldout split must use recordings outside the 120-window development/selector pool.",
            "- `textgrid_path` is optional in the schema, but if declared, every true-heldout row must point to an existing file.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--min-true-heldout", type=int, default=8)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    validation = build_validation(ROOT, args.split_file, args.min_true_heldout)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(validation, args.output_md)
    write_csv(validation, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
