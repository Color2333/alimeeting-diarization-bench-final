#!/usr/bin/env python3
"""Smoke-test Qwen Omni models as audio guard agents, not diarizers."""

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
import base64
import csv
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alimeeting_diarization_bench.config import APIKeys
from scripts.llm_policy_agent_eval import extract_json


DEFAULT_MODELS = [
    "qwen3.5-omni-flash",
    "qwen3.5-omni-plus",
    "qwen3.5-omni-flash-2026-03-15",
    "qwen3.5-omni-plus-2026-03-15",
]

SYSTEM_PROMPT = """You are an audio guard agent for a real-time speaker diarization system.
You are NOT the diarization model. You only listen to a short meeting audio clip
and return structured safety/evidence signals that may help a downstream
diarization pipeline decide whether a window needs review.

Return only valid JSON:
{
  "transcript_excerpt": "short text or empty if unclear",
  "speaker_count_guess": 0,
  "overlap_or_crosstalk": "none|possible|strong|unknown",
  "speech_activity": "none|low|normal|dense|unknown",
  "diarization_risk": "low|medium|high|unknown",
  "should_quarantine": false,
  "should_defer_to_slow_agent": true,
  "usable_as_direct_diarizer": false,
  "reason": "short_snake_case",
  "confidence": 0.0
}

Hard rules:
- Never invent timestamps.
- Do not claim stable speaker identities from this clip.
- If the audio is unclear, mark risk unknown/high and defer.
- usable_as_direct_diarizer must be false unless you can provide stable,
  timestamped speaker turns, which is not expected in this task.
"""


def make_client(args: argparse.Namespace) -> OpenAI:
    api_keys = APIKeys.from_env()
    api_key = (
        args.api_key
        or os.environ.get("DASHSCOPE_API_KEY")
        or os.environ.get("BAILIAN_API_KEY")
        or os.environ.get("ALIYUN_BAILIAN_API_KEY")
        or api_keys.dashscope_api_key
    )
    base_url = args.base_url or os.environ.get("DASHSCOPE_BASE_URL") or api_keys.dashscope_base_url
    if not api_key:
        raise SystemExit("DashScope/Bailian API key is required")
    return OpenAI(api_key=api_key, base_url=base_url)


def wav_clip_base64(path: Path, start_sec: float, duration_sec: float, channel: int | None) -> tuple[str, dict[str, Any]]:
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    start = int(start_sec * sr)
    end = int((start_sec + duration_sec) * sr)
    clip = audio[start:end]
    if clip.size == 0:
        raise ValueError("Selected audio clip is empty")
    if channel is None:
        mono = np.mean(clip, axis=1)
    else:
        mono = clip[:, channel]
    mono = np.clip(mono, -1.0, 1.0)
    buf = io.BytesIO()
    sf.write(buf, mono, sr, format="WAV", subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode("ascii"), {
        "sample_rate": sr,
        "channels": int(audio.shape[1]),
        "start_sec": start_sec,
        "duration_sec": len(mono) / sr,
        "mixdown": "mean" if channel is None else f"channel_{channel}",
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    for key in [
        "transcript_excerpt",
        "overlap_or_crosstalk",
        "speech_activity",
        "diarization_risk",
        "reason",
    ]:
        payload[key] = str(payload.get(key, ""))
    payload["speaker_count_guess"] = int(float(payload.get("speaker_count_guess") or 0))
    payload["should_quarantine"] = bool(payload.get("should_quarantine", False))
    payload["should_defer_to_slow_agent"] = bool(payload.get("should_defer_to_slow_agent", True))
    payload["usable_as_direct_diarizer"] = bool(payload.get("usable_as_direct_diarizer", False))
    payload["confidence"] = float(payload.get("confidence") or 0.0)
    return payload


def call_model(client: OpenAI, model: str, audio_b64: str, temperature: float) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {"data": f"data:audio/wav;base64,{audio_b64}"},
                    },
                    {
                        "type": "text",
                        "text": "Audit this short meeting clip. Return the JSON object only.",
                    },
                ],
            },
        ],
    )
    content = response.choices[0].message.content or "{}"
    payload = validate(json.loads(extract_json(content)))
    usage = getattr(response, "usage", None)
    payload.update(
        {
            "raw_content": content,
            "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
            "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
            "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
        }
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, default=Path("/Users/haojiang/data/AliMeeting/Eval_Ali/Eval_Ali_far/audio_dir/R8003_M8001_MS801.wav"))
    parser.add_argument("--start-sec", type=float, default=150.0)
    parser.add_argument("--duration-sec", type=float, default=12.0)
    parser.add_argument("--channel", type=int, default=None)
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--output-jsonl", type=Path, default=Path("outputs/omni_guard/omni_audio_guard_smoke.jsonl"))
    parser.add_argument("--output-csv", type=Path, default=None)
    args = parser.parse_args()

    models = args.model or DEFAULT_MODELS
    audio_b64, clip_meta = wav_clip_base64(args.audio, args.start_sec, args.duration_sec, args.channel)
    client = make_client(args)

    rows = []
    for model in models:
        base = {
            "model": model,
            "audio": str(args.audio),
            **clip_meta,
        }
        try:
            started = time.perf_counter()
            payload = call_model(client, model, audio_b64, args.temperature)
            base.update(payload)
            base["call_seconds"] = round(time.perf_counter() - started, 3)
            base["schema_ok"] = True
            base["error"] = ""
        except Exception as exc:
            base.update(
                {
                    "transcript_excerpt": "",
                    "speaker_count_guess": "",
                    "overlap_or_crosstalk": "",
                    "speech_activity": "",
                    "diarization_risk": "",
                    "should_quarantine": "",
                    "should_defer_to_slow_agent": "",
                    "usable_as_direct_diarizer": "",
                    "reason": "call_failed",
                    "confidence": "",
                    "raw_content": "",
                    "prompt_tokens": "",
                    "completion_tokens": "",
                    "total_tokens": "",
                    "call_seconds": "",
                    "schema_ok": False,
                    "error": repr(exc),
                }
            )
        rows.append(base)

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    output_csv = args.output_csv or args.output_jsonl.with_suffix(".csv")
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {args.output_jsonl}")
    print(f"Wrote {output_csv}")
    for row in rows:
        print(
            "{model}: schema={schema_ok} risk={diarization_risk} defer={should_defer_to_slow_agent} latency={call_seconds} error={error}".format(
                **row
            )
        )


if __name__ == "__main__":
    main()
