#!/usr/bin/env python3
"""Build window-level ASR semantic evidence for LLM Policy Agent prompts.

Input CSV schema:
recording_id,window_size,segment_idx,start,end,text[,asr_speaker]

The output is intentionally compact and deployable: it contains transcript
snippets and simple semantic cues, not diarization ground truth.
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


QUESTION_MARKERS = ("?", "？", "吗", "是不是", "能不能", "为什么", "怎么", "如何")
ADDRESS_MARKERS = ("老师", "同学", "主持", "大家", "你", "您")
SELF_MARKERS = ("我", "我们", "我的", "我们这边")


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def summarize_texts(rows: list[dict[str, str]], max_chars: int) -> str:
    snippets = []
    for row in rows:
        text = row.get("text", "").strip()
        if not text:
            continue
        snippets.append(f"[{float(row['start']):.1f}-{float(row['end']):.1f}] {text}")
    joined = " ".join(snippets)
    if len(joined) <= max_chars:
        return joined
    return joined[: max_chars - 1] + "…"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/asr_semantic_evidence/window_evidence.csv"))
    parser.add_argument("--max-chars", type=int, default=420)
    args = parser.parse_args()

    rows = load_rows(args.input)
    if not rows:
        raise SystemExit("No ASR transcript rows found")

    grouped: dict[tuple[str, int, int], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["recording_id"], int(row["window_size"]), int(row["segment_idx"])), []).append(row)

    output_rows = []
    for (recording_id, window_size, segment_idx), utterances in sorted(grouped.items()):
        utterances.sort(key=lambda row: (float(row["start"]), float(row["end"])))
        texts = [row.get("text", "").strip() for row in utterances if row.get("text", "").strip()]
        full_text = " ".join(texts)
        output_rows.append(
            {
                "recording_id": recording_id,
                "window_size": window_size,
                "segment_idx": segment_idx,
                "evidence_source": next(
                    (
                        row.get("evidence_source", "")
                        for row in utterances
                        if row.get("evidence_source", "")
                    ),
                    "asr_transcript",
                ),
                "utterance_count": len(texts),
                "char_count": len(full_text),
                "has_question": int(has_any(full_text, QUESTION_MARKERS)),
                "has_addressing": int(has_any(full_text, ADDRESS_MARKERS)),
                "has_self_reference": int(has_any(full_text, SELF_MARKERS)),
                "asr_speaker_count": len({row.get("asr_speaker", "") for row in utterances if row.get("asr_speaker", "")}),
                "transcript_excerpt": summarize_texts(utterances, args.max_chars),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output_rows[0].keys()))
        writer.writeheader()
        writer.writerows(output_rows)

    schema = {
        "input_schema": "recording_id,window_size,segment_idx,start,end,text[,asr_speaker]",
        "output": str(args.output),
        "rows": len(output_rows),
        "notes": [
            "No ground-truth diarization fields are used.",
            "transcript_excerpt is capped to keep LLM prompts bounded.",
            "asr_speaker is optional and only used as weak ASR-side evidence.",
        ],
    }
    schema_path = args.output.with_name(args.output.stem + "_schema.json")
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {schema_path}")


if __name__ == "__main__":
    main()
