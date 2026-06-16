#!/usr/bin/env python3
"""Summarize Omni audio guard smoke results."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.llm_policy_agent_eval import extract_json


NON_REALTIME_INPUTS = [
    Path("outputs/omni_guard/omni_flash_plus_audio_guard_8s.csv"),
    Path("outputs/omni_guard/omni_dated_audio_guard_8s.csv"),
]
REALTIME_INPUTS = [
    Path("outputs/omni_guard/qwen35_omni_flash_realtime_guard_8s.jsonl"),
]


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_text_json(text: str) -> dict:
    json_text = extract_json(text)
    if not json_text.strip():
        json_text = text
    if "{" in json_text and "}" in json_text:
        json_text = json_text[json_text.find("{") : json_text.rfind("}") + 1]
    return json.loads(json_text)


def summarize_non_realtime() -> list[dict[str, str]]:
    rows = []
    for path in NON_REALTIME_INPUTS:
        for row in load_csv(path):
            rows.append(
                {
                    "model": row["model"],
                    "interface": "openai_compatible_audio",
                    "duration_sec": row["duration_sec"],
                    "call_seconds": f"{float(row['call_seconds']):.3f}" if row.get("call_seconds") else "",
                    "first_text_seconds": "",
                    "schema_ok": row["schema_ok"],
                    "speaker_count_guess": row["speaker_count_guess"],
                    "diarization_risk": row["diarization_risk"],
                    "should_quarantine": row["should_quarantine"],
                    "should_defer_to_slow_agent": row["should_defer_to_slow_agent"],
                    "usable_as_direct_diarizer": row["usable_as_direct_diarizer"],
                    "reason": row["reason"],
                    "confidence": row["confidence"],
                    "note": "structured audio guard",
                }
            )
    return rows


def summarize_realtime() -> list[dict[str, str]]:
    rows = []
    for path in REALTIME_INPUTS:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            parsed = {}
            schema_ok = False
            try:
                parsed = parse_text_json(row.get("text", ""))
                schema_ok = True
            except Exception:
                pass
            rows.append(
                {
                    "model": row["model"],
                    "interface": "dashscope_realtime_websocket",
                    "duration_sec": str(row["duration_sec"]),
                    "call_seconds": f"{float(row['call_seconds']):.3f}",
                    "first_text_seconds": str(row.get("first_text_seconds", "")),
                    "schema_ok": str(schema_ok),
                    "speaker_count_guess": str(parsed.get("speaker_count_guess", "")),
                    "diarization_risk": str(parsed.get("diarization_risk", "")),
                    "should_quarantine": str(parsed.get("should_quarantine", "")),
                    "should_defer_to_slow_agent": str(parsed.get("should_defer_to_slow_agent", "")),
                    "usable_as_direct_diarizer": str(parsed.get("usable_as_direct_diarizer", "")),
                    "reason": str(parsed.get("reason", "")),
                    "confidence": str(parsed.get("confidence", "")),
                    "note": f"{row.get('event_count', 0)} events; response_done={row.get('response_done')}",
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/omni_guard/omni_guard_summary.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/omni_guard/omni_guard_summary.md"))
    args = parser.parse_args()

    rows = summarize_non_realtime() + summarize_realtime()
    if not rows:
        raise SystemExit("No Omni guard smoke rows found")
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "| Model | Interface | Clip | Call | First text | Schema | Risk | Quarantine | Defer | Direct diarizer | Reason |",
        "|---|---|---:|---:|---:|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {model} | {interface} | {duration_sec}s | {call_seconds}s | {first_text_seconds} | {schema_ok} | {diarization_risk} | {should_quarantine} | {should_defer_to_slow_agent} | {usable_as_direct_diarizer} | {reason} |".format(
                **row
            )
        )
    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
