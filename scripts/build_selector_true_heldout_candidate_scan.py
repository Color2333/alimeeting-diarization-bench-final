#!/usr/bin/env python3
"""Scan local AliMeeting recordings for selector true-heldout candidates."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FAR_AUDIO_DIR = Path("/Users/haojiang/data/AliMeeting/Eval_Ali/Eval_Ali_far/audio_dir")
DEFAULT_FAR_TEXTGRID_DIR = Path("/Users/haojiang/data/AliMeeting/Eval_Ali/Eval_Ali_far/textgrid_dir")
DEFAULT_NEAR_AUDIO_DIR = Path("/Users/haojiang/data/AliMeeting/Eval_Ali/Eval_Ali_near/audio_dir")
OUTPUT_JSON = Path("outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.csv")
OUTPUT_TEMPLATE = Path("outputs/research_progress_snapshot/selector_true_heldout_split_template.csv")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def recording_id_from_far_audio(path: Path) -> str:
    parts = path.stem.split("_")
    return "_".join(parts[:2])


def recording_id_from_near_audio(path: Path) -> str:
    parts = path.stem.split("_")
    return "_".join(parts[:2])


def build_scan(
    root: Path,
    far_audio_dir: Path,
    far_textgrid_dir: Path,
    near_audio_dir: Path,
    min_new_recordings: int,
) -> dict[str, Any]:
    per_recording = read_csv(root / "outputs/realtime_contract_recording_stability_120/per_recording.csv")
    dev_recordings = sorted({row["group"] for row in per_recording if row.get("group")})

    far_audio_by_recording: dict[str, Path] = {}
    for path in sorted(far_audio_dir.glob("*.wav")):
        far_audio_by_recording.setdefault(recording_id_from_far_audio(path), path)
    far_textgrid_by_recording = {path.stem: path for path in sorted(far_textgrid_dir.glob("*.TextGrid"))}
    near_counts: dict[str, int] = {}
    for path in sorted(near_audio_dir.glob("*.wav")):
        near_counts[recording_id_from_near_audio(path)] = near_counts.get(recording_id_from_near_audio(path), 0) + 1

    all_recordings = sorted(set(far_audio_by_recording) | set(far_textgrid_by_recording) | set(near_counts))
    rows = []
    for recording_id in all_recordings:
        has_far_audio = recording_id in far_audio_by_recording
        has_far_textgrid = recording_id in far_textgrid_by_recording
        is_dev = recording_id in dev_recordings
        blockers = []
        if is_dev:
            blockers.append("already_in_120_window_development_pool")
        if not has_far_audio:
            blockers.append("missing_far_audio")
        if not has_far_textgrid:
            blockers.append("missing_far_textgrid")
        rows.append(
            {
                "recording_id": recording_id,
                "eligible_true_heldout": not blockers,
                "blockers": blockers,
                "far_audio_path": str(far_audio_by_recording.get(recording_id, "")),
                "far_textgrid_path": str(far_textgrid_by_recording.get(recording_id, "")),
                "near_channel_count": near_counts.get(recording_id, 0),
                "source_manifest": "local_eval_ali_scan",
            }
        )

    eligible = [row for row in rows if row["eligible_true_heldout"]]
    local_dev_overlap = sorted(set(all_recordings) & set(dev_recordings))
    missing_needed = max(min_new_recordings - len(eligible), 0)
    status = "ready_to_create_sealed_split_template" if len(eligible) >= min_new_recordings else "not_enough_new_local_recordings"
    return {
        "runtime_contract": "selector_true_heldout_candidate_scan_no_metric_claim",
        "status": status,
        "minimum_true_heldout_recordings": min_new_recordings,
        "scan_roots": {
            "far_audio_dir": str(far_audio_dir),
            "far_textgrid_dir": str(far_textgrid_dir),
            "near_audio_dir": str(near_audio_dir),
        },
        "summary": {
            "local_recordings": len(all_recordings),
            "development_recordings": len(dev_recordings),
            "local_dev_overlap": len(local_dev_overlap),
            "eligible_true_heldout_recordings": len(eligible),
            "missing_new_recordings_to_minimum": missing_needed,
            "far_audio_count": len(far_audio_by_recording),
            "far_textgrid_count": len(far_textgrid_by_recording),
            "near_recording_count": len(near_counts),
            "no_metric_claim": True,
            "sealed_split_written": False,
        },
        "development_recordings": dev_recordings,
        "eligible_recordings": [row["recording_id"] for row in eligible],
        "rows": rows,
        "recommendation": (
            f"Need {missing_needed} new recordings outside the current development pool before creating "
            "data/selector_true_heldout_split.csv."
            if missing_needed
            else "Enough local candidates exist; create a sealed split CSV before scoring."
        ),
    }


def write_csv(scan: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "recording_id",
        "eligible_true_heldout",
        "blockers",
        "far_audio_path",
        "far_textgrid_path",
        "near_channel_count",
        "source_manifest",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in scan["rows"]:
            item = dict(row)
            item["blockers"] = ";".join(item["blockers"])
            writer.writerow(item)


def write_template(scan: dict[str, Any], path: Path) -> None:
    fieldnames = ["recording_id", "split", "source_manifest", "audio_path", "textgrid_path"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for recording_id in scan["eligible_recordings"]:
            row = next(item for item in scan["rows"] if item["recording_id"] == recording_id)
            writer.writerow(
                {
                    "recording_id": recording_id,
                    "split": "true_heldout",
                    "source_manifest": row["source_manifest"],
                    "audio_path": row["far_audio_path"],
                    "textgrid_path": row["far_textgrid_path"],
                }
            )


def write_markdown(scan: dict[str, Any], path: Path) -> None:
    summary = scan["summary"]
    lines = [
        "# Selector True-Heldout Candidate Scan",
        "",
        f"- Runtime contract: `{scan['runtime_contract']}`",
        f"- Status: `{scan['status']}`",
        f"- Local recordings scanned: `{summary['local_recordings']}`",
        f"- Development recordings: `{summary['development_recordings']}`",
        f"- Eligible true-heldout recordings: `{summary['eligible_true_heldout_recordings']}`",
        f"- Missing new recordings to minimum: `{summary['missing_new_recordings_to_minimum']}`",
        f"- No metric claim: `{summary['no_metric_claim']}`",
        f"- Sealed split written: `{summary['sealed_split_written']}`",
        f"- Recommendation: {scan['recommendation']}",
        "",
        "## Recording Scan",
        "",
        "| Recording | Eligible | Blockers | Far audio | Far TextGrid | Near channels |",
        "|---|---|---|---|---|---:|",
    ]
    for row in scan["rows"]:
        blockers = "; ".join(row["blockers"]) if row["blockers"] else "none"
        lines.append(
            f"| `{row['recording_id']}` | `{row['eligible_true_heldout']}` | {blockers} | "
            f"`{bool(row['far_audio_path'])}` | `{bool(row['far_textgrid_path'])}` | {row['near_channel_count']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This scan only inspects local recording availability; it does not create the sealed split used for scoring.",
            "- Near-channel files for the same meeting are not counted as new true-heldout recordings.",
            "- Every local Eval_Ali meeting currently overlaps the 120-window development/selector pool, so true-heldout scoring remains blocked.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--far-audio-dir", type=Path, default=DEFAULT_FAR_AUDIO_DIR)
    parser.add_argument("--far-textgrid-dir", type=Path, default=DEFAULT_FAR_TEXTGRID_DIR)
    parser.add_argument("--near-audio-dir", type=Path, default=DEFAULT_NEAR_AUDIO_DIR)
    parser.add_argument("--min-new-recordings", type=int, default=8)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--output-template", type=Path, default=OUTPUT_TEMPLATE)
    args = parser.parse_args()

    scan = build_scan(ROOT, args.far_audio_dir, args.far_textgrid_dir, args.near_audio_dir, args.min_new_recordings)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(scan, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(scan, args.output_md)
    write_csv(scan, args.output_csv)
    write_template(scan, args.output_template)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_template}")


if __name__ == "__main__":
    main()
