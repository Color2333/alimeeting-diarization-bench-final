#!/usr/bin/env python3
"""Normalize patch-level voiceprint evidence for LLM Policy Agent prompts.

Input CSV schema:
patch_id,top1_global_speaker,top1_similarity,top2_global_speaker,top2_similarity,
memory_confidence[,enrollment_source]

The output is deployable evidence only: it contains similarity/margin signals
from a speaker memory system, not ground-truth speaker labels.
"""

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


REQUIRED_FIELDS = {
    "patch_id",
    "top1_global_speaker",
    "top1_similarity",
    "top2_global_speaker",
    "top2_similarity",
    "memory_confidence",
}


def confidence_bucket(confidence: float, margin: float) -> str:
    if confidence >= 0.75 and margin >= 0.12:
        return "high"
    if confidence >= 0.55 and margin >= 0.06:
        return "medium"
    return "low"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/voiceprint_patch_evidence/patch_evidence.csv"))
    args = parser.parse_args()

    with args.input.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_FIELDS - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Missing required fields: {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise SystemExit("No voiceprint evidence rows found")

    output_rows = []
    for row in rows:
        top1 = float(row["top1_similarity"])
        top2 = float(row["top2_similarity"])
        confidence = float(row["memory_confidence"])
        margin = top1 - top2
        output_rows.append(
            {
                "patch_id": row["patch_id"],
                "top1_global_speaker": row["top1_global_speaker"],
                "top1_similarity": round(top1, 4),
                "top2_global_speaker": row["top2_global_speaker"],
                "top2_similarity": round(top2, 4),
                "similarity_margin": round(margin, 4),
                "memory_confidence": round(confidence, 4),
                "confidence_bucket": confidence_bucket(confidence, margin),
                "enrollment_source": row.get("enrollment_source", ""),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output_rows[0].keys()))
        writer.writeheader()
        writer.writerows(output_rows)

    schema = {
        "input_schema": ",".join(
            [
                "patch_id",
                "top1_global_speaker",
                "top1_similarity",
                "top2_global_speaker",
                "top2_similarity",
                "memory_confidence",
                "[enrollment_source]",
            ]
        ),
        "output": str(args.output),
        "rows": len(output_rows),
        "notes": [
            "No ground-truth speaker labels are used.",
            "similarity_margin = top1_similarity - top2_similarity.",
            "confidence_bucket is a prompt-friendly coarse confidence label.",
        ],
    }
    schema_path = args.output.with_name(args.output.stem + "_schema.json")
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {schema_path}")


if __name__ == "__main__":
    main()
