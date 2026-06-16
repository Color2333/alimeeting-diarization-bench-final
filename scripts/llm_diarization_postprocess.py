#!/usr/bin/env python
"""Export or run LLM-based diarization label post-processing.

The script consumes new benchmark summary.json files that include
pred_segments/gt_segments. It can either export compact prompts for inspection or
call an OpenAI-compatible chat model to relabel predicted diarization segments.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alimeeting_diarization_bench.metrics.der import calc_der


SYSTEM_PROMPT = """You correct speaker diarization labels for a short meeting clip.
Use the transcript text and speaker-turn context to fix inconsistent speaker IDs.
Do not invent speech. Keep timestamps unchanged unless a boundary is clearly invalid.
Return only valid JSON with this shape:
{"segments":[{"start":0.0,"end":1.2,"speaker":"SPEAKER_00"}]}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary_json", help="Benchmark summary.json with segments")
    parser.add_argument("--mode", choices=["export", "openai"], default="export")
    parser.add_argument("--output", default=None)
    parser.add_argument("--model", default=os.environ.get("LLM_POSTPROCESS_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--api-key", default=os.environ.get("GPT_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"))
    parser.add_argument("--max-items", type=int, default=None)
    args = parser.parse_args()

    summary_path = Path(args.summary_json)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = [
        r
        for r in summary.get("results", [])
        if r.get("success") and r.get("pred_segments") and r.get("gt_segments")
    ]
    if args.max_items is not None:
        rows = rows[: args.max_items]

    if not rows:
        raise SystemExit(
            "No post-processable rows found. Re-run the benchmark after the "
            "pred_segments/gt_segments fields were added."
        )

    output = Path(args.output) if args.output else _default_output(summary_path, args.mode)
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.mode == "export":
        _export_prompts(rows, output)
        print(f"Exported {len(rows)} LLM post-processing prompts to {output}")
        return

    if not args.api_key:
        raise SystemExit("GPT_API_KEY or OPENAI_API_KEY is required for --mode openai")

    client_kwargs = {"api_key": args.api_key}
    if args.base_url:
        client_kwargs["base_url"] = args.base_url
    client = OpenAI(**client_kwargs)

    processed = []
    for row in rows:
        corrected = _call_llm(client, args.model, row)
        der = calc_der(
            row["gt_segments"],
            corrected,
            session_id=f"{row['recording_id']}_{row['segment_idx']}",
            collar=summary.get("collar", 0.0) or 0.0,
        )
        processed.append(
            {
                "recording_id": row["recording_id"],
                "segment_idx": row["segment_idx"],
                "original_der": row.get("der"),
                "post_der": der["der"] if der else None,
                "original_segments": row["pred_segments"],
                "post_segments": corrected,
            }
        )

    payload = {
        "source": str(summary_path),
        "model": args.model,
        "items": processed,
        "avg_original_der": _avg([p["original_der"] for p in processed]),
        "avg_post_der": _avg([p["post_der"] for p in processed]),
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote post-processed results to {output}")
    print(
        "DER: %.2f%% -> %.2f%%"
        % ((payload["avg_original_der"] or 0) * 100, (payload["avg_post_der"] or 0) * 100)
    )


def _default_output(summary_path: Path, mode: str) -> Path:
    suffix = "prompts.jsonl" if mode == "export" else "llm_postprocess.json"
    return summary_path.parent / suffix


def _export_prompts(rows: list[dict[str, Any]], output: Path) -> None:
    with output.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_prompt_payload(row), ensure_ascii=False) + "\n")


def _prompt_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"{row['recording_id']}_{row['segment_idx']}",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(row)},
        ],
        "has_transcript_text": bool(row.get("pred_text")),
    }


def _user_prompt(row: dict[str, Any]) -> str:
    compact_segments = [
        {
            "start": round(float(s["start"]), 3),
            "end": round(float(s["end"]), 3),
            "speaker": str(s["speaker"]),
            "text": s.get("text", ""),
        }
        for s in row["pred_segments"]
    ]
    return json.dumps(
        {
            "clip": {
                "recording_id": row["recording_id"],
                "segment_idx": row["segment_idx"],
                "duration_sec": row["window_size"],
                "predicted_speaker_count": row.get("spk_count_pred"),
            },
            "transcript_text": row.get("pred_text", ""),
            "diarization_segments": compact_segments,
            "task": "Return corrected diarization_segments as JSON. Prefer changing speaker labels over changing timestamps.",
        },
        ensure_ascii=False,
    )


def _call_llm(client: OpenAI, model: str, row: dict[str, Any]) -> list[dict[str, Any]]:
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(row)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    payload = json.loads(_extract_json(content))
    return [
        {"start": float(s["start"]), "end": float(s["end"]), "speaker": str(s["speaker"])}
        for s in payload.get("segments", [])
        if float(s["end"]) > float(s["start"])
    ]


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _avg(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return round(sum(clean) / len(clean), 4) if clean else None


if __name__ == "__main__":
    main()
