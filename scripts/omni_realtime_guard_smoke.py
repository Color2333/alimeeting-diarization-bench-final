#!/usr/bin/env python3
"""Smoke-test Qwen Omni realtime models on a short audio guard task."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

import dashscope
from dashscope.audio.qwen_omni import AudioFormat, MultiModality, OmniRealtimeCallback, OmniRealtimeConversation

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alimeeting_diarization_bench.config import APIKeys
from scripts.llm_policy_agent_eval import extract_json


DEFAULT_INSTRUCTIONS = """You are an audio guard agent for a real-time speaker diarization system.
Listen to the short meeting clip and return concise JSON only:
{"speaker_count_guess":0,"overlap_or_crosstalk":"none|possible|strong|unknown","diarization_risk":"low|medium|high|unknown","should_quarantine":false,"should_defer_to_slow_agent":true,"usable_as_direct_diarizer":false,"reason":"short_snake_case","confidence":0.0}
Never invent timestamps. Do not claim stable speaker identities.
"""


class CollectCallback(OmniRealtimeCallback):
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.done = threading.Event()
        self.opened_at = 0.0
        self.first_text_at: float | None = None
        self.text_parts: list[str] = []
        self.final_text: str = ""
        self.errors: list[str] = []

    def on_open(self) -> None:
        self.opened_at = time.perf_counter()

    def on_close(self, close_status_code, close_msg) -> None:
        self.events.append({"type": "client.close", "code": close_status_code, "message": close_msg})
        self.done.set()

    def on_event(self, message: dict) -> None:
        self.events.append(message)
        event_type = str(message.get("type", ""))
        if event_type == "response.text.done" and isinstance(message.get("text"), str):
            self.final_text = str(message["text"])
        delta = message.get("delta")
        if isinstance(delta, str) and event_type == "response.text.delta":
            if self.first_text_at is None:
                self.first_text_at = time.perf_counter()
            self.text_parts.append(delta)
        if event_type in {"response.done", "session.finished"}:
            self.done.set()
        if event_type == "error":
            self.errors.append(json.dumps(message, ensure_ascii=False))
            self.done.set()


def pcm_clip_chunks(path: Path, start_sec: float, duration_sec: float, chunk_ms: int, channel: int | None) -> tuple[list[str], dict[str, Any]]:
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if sr != 16000:
        raise ValueError(f"Expected 16 kHz audio for realtime smoke, got {sr}")
    start = int(start_sec * sr)
    end = int((start_sec + duration_sec) * sr)
    clip = audio[start:end]
    if clip.size == 0:
        raise ValueError("Selected audio clip is empty")
    mono = np.mean(clip, axis=1) if channel is None else clip[:, channel]
    pcm = (np.clip(mono, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    chunk_bytes = int(sr * chunk_ms / 1000) * 2
    chunks = [base64.b64encode(pcm[i : i + chunk_bytes]).decode("ascii") for i in range(0, len(pcm), chunk_bytes)]
    return chunks, {
        "sample_rate": sr,
        "channels": int(audio.shape[1]),
        "start_sec": start_sec,
        "duration_sec": len(mono) / sr,
        "chunk_ms": chunk_ms,
        "chunks": len(chunks),
        "mixdown": "mean" if channel is None else f"channel_{channel}",
    }


def run_model(args: argparse.Namespace, model: str, chunks: list[str]) -> dict[str, Any]:
    api_keys = APIKeys.from_env()
    api_key = (
        args.api_key
        or os.environ.get("DASHSCOPE_API_KEY")
        or os.environ.get("BAILIAN_API_KEY")
        or os.environ.get("ALIYUN_BAILIAN_API_KEY")
        or api_keys.dashscope_api_key
    )
    dashscope.api_key = api_key
    callback = CollectCallback()
    conv = OmniRealtimeConversation(
        model=model,
        callback=callback,
        api_key=api_key,
        url=args.ws_url,
    )
    started = time.perf_counter()
    try:
        conv.connect()
        conv.update_session(
            output_modalities=[MultiModality.TEXT],
            voice=args.voice,
            input_audio_format=AudioFormat.PCM_16000HZ_MONO_16BIT,
            enable_input_audio_transcription=True,
            input_audio_transcription_model=args.transcription_model,
            enable_turn_detection=False,
        )
        # Give the session.update event a small chance to reach the server.
        time.sleep(0.2)
        for chunk in chunks:
            conv.append_audio(chunk)
            if args.realtime_sleep:
                time.sleep(args.chunk_ms / 1000)
        conv.commit()
        conv.create_response(instructions=args.instructions, output_modalities=[MultiModality.TEXT])
        callback.done.wait(args.timeout_sec)
        try:
            conv.close()
        except Exception:
            pass
    except Exception as exc:
        callback.errors.append(repr(exc))
    elapsed = time.perf_counter() - started
    text = callback.final_text or "".join(callback.text_parts)
    try:
        json_text = extract_json(text)
        if "{" in json_text and "}" in json_text:
            json_text = json_text[json_text.find("{") : json_text.rfind("}") + 1]
        parsed = json.loads(json_text)
        schema_maybe = isinstance(parsed, dict)
        parsed_json = json.dumps(parsed, ensure_ascii=False)
    except Exception:
        schema_maybe = False
        parsed_json = ""
    return {
        "model": model,
        "call_seconds": round(elapsed, 3),
        "first_text_seconds": round(callback.first_text_at - started, 3) if callback.first_text_at else "",
        "event_count": len(callback.events),
        "text": text,
        "parsed_json": parsed_json,
        "response_done": any(event.get("type") == "response.done" for event in callback.events),
        "schema_maybe": schema_maybe,
        "errors": " | ".join(callback.errors),
        "events_json": json.dumps(callback.events, ensure_ascii=False),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, default=Path("/Users/haojiang/data/AliMeeting/Eval_Ali/Eval_Ali_far/audio_dir/R8003_M8001_MS801.wav"))
    parser.add_argument("--start-sec", type=float, default=150.0)
    parser.add_argument("--duration-sec", type=float, default=8.0)
    parser.add_argument("--channel", type=int, default=None)
    parser.add_argument("--chunk-ms", type=int, default=200)
    parser.add_argument("--realtime-sleep", action="store_true")
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--instructions", default=DEFAULT_INSTRUCTIONS)
    parser.add_argument("--voice", default="Tina")
    parser.add_argument("--transcription-model", default="qwen3-asr-flash-realtime")
    parser.add_argument("--ws-url", default="wss://dashscope.aliyuncs.com/api-ws/v1/realtime")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--timeout-sec", type=float, default=30.0)
    parser.add_argument("--output-jsonl", type=Path, default=Path("outputs/omni_guard/omni_realtime_guard_smoke.jsonl"))
    parser.add_argument("--output-csv", type=Path, default=None)
    args = parser.parse_args()

    if not args.model:
        args.model = ["qwen3.5-omni-flash-realtime"]
    chunks, meta = pcm_clip_chunks(args.audio, args.start_sec, args.duration_sec, args.chunk_ms, args.channel)
    rows = []
    for model in args.model:
        row = {"audio": str(args.audio), **meta, **run_model(args, model, chunks)}
        rows.append(row)

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    output_csv = args.output_csv or args.output_jsonl.with_suffix(".csv")
    csv_fields = [key for key in rows[0].keys() if key != "events_json"]
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in csv_fields})
    print(f"Wrote {args.output_jsonl}")
    print(f"Wrote {output_csv}")
    for row in rows:
        print(
            "{model}: done={response_done} first_text={first_text_seconds} total={call_seconds} schema={schema_maybe} errors={errors}".format(
                **row
            )
        )


if __name__ == "__main__":
    main()
