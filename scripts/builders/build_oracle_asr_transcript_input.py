#!/usr/bin/env python3
"""Export oracle transcript rows from benchmark summaries for ASR evidence tests.

This is an upper-bound control, not deployable ASR. It reuses the `gt_text`
already stored in benchmark summary.json files and aligns rows by
recording_id/window_size/segment_idx.
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
from typing import Any


def parse_window_id(window_id: str) -> tuple[str, int, int]:
    parts = window_id.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"window_id must be recording_id:window_size:segment_idx, got {window_id!r}"
        )
    return parts[0], int(parts[1]), int(parts[2])


def load_results(summary: Path) -> list[dict[str, Any]]:
    data = json.loads(summary.read_text(encoding="utf-8"))
    return list(data.get("results", []))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("outputs/sortformer_uv_48/nemo-sortformer-4spk-v1/default__spk_none/summary.json"),
        help="Benchmark summary.json containing gt_text.",
    )
    parser.add_argument(
        "--window-id",
        action="append",
        default=[],
        help="Optional recording_id:window_size:segment_idx filter. Can be repeated.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/asr_semantic_evidence/oracle_transcript_input.csv"),
    )
    args = parser.parse_args()

    selected = {parse_window_id(item) for item in args.window_id}
    output_rows = []
    for row in load_results(args.summary):
        key = (row["recording_id"], int(row["window_size"]), int(row["segment_idx"]))
        if selected and key not in selected:
            continue
        text = (row.get("gt_text") or "").strip()
        if not text:
            continue
        output_rows.append(
            {
                "recording_id": key[0],
                "window_size": key[1],
                "segment_idx": key[2],
                "start": 0.0,
                "end": float(key[1]),
                "text": text,
                "asr_speaker": "",
                "evidence_source": "oracle_transcript_upper_bound_not_deployable",
            }
        )

    if not output_rows:
        raise SystemExit("No oracle transcript rows selected")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output_rows[0].keys()))
        writer.writeheader()
        writer.writerows(output_rows)

    manifest = {
        "summary": str(args.summary),
        "output": str(args.output),
        "rows": len(output_rows),
        "window_ids": [":".join(map(str, key)) for key in sorted(selected)] if selected else "all",
        "evidence_source": "oracle_transcript_upper_bound_not_deployable",
        "notes": [
            "Uses benchmark gt_text, so this is an upper-bound control only.",
            "Does not expose ground-truth speaker labels to the LLM prompt.",
        ],
    }
    args.output.with_name(args.output.stem + "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {args.output}")
    print(f"Rows {len(output_rows)}")


if __name__ == "__main__":
    main()
