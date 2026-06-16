#!/usr/bin/env python3
"""Run Omni audio guard on selected diarization windows."""

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
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.omni_audio_guard_smoke import call_model, make_client, wav_clip_base64


def load_results(path: Path) -> dict[tuple[str, int, int], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        (row["recording_id"], int(row["window_size"]), int(row["segment_idx"])): row
        for row in data["results"]
        if row.get("success")
    }


def audio_path(audio_dir: Path, recording_id: str) -> Path:
    matches = sorted(audio_dir.glob(f"{recording_id}_*.wav"))
    if not matches:
        raise FileNotFoundError(f"No audio wav found for {recording_id} under {audio_dir}")
    return matches[0]


def select_windows(
    fast: dict[tuple[str, int, int], dict[str, Any]],
    slow: dict[tuple[str, int, int], dict[str, Any]],
    per_bucket: int,
) -> list[dict[str, Any]]:
    shared = []
    for key, f in fast.items():
        if key not in slow:
            continue
        s = slow[key]
        combined = max(float(f["der"]), float(s["der"]))
        shared.append(
            {
                "recording_id": key[0],
                "window_size": key[1],
                "segment_idx": key[2],
                "fast_der": float(f["der"]),
                "slow_der": float(s["der"]),
                "combined_der": combined,
                "gt_spk_count": int(f.get("spk_count_gt") or 0),
            }
        )
    high = sorted(shared, key=lambda r: r["combined_der"], reverse=True)[:per_bucket]
    clean_candidates = [r for r in shared if r["fast_der"] < 0.12 and r["slow_der"] < 0.08]
    clean = sorted(clean_candidates, key=lambda r: r["combined_der"])[:per_bucket]
    medium_candidates = [
        r
        for r in shared
        if 0.18 <= r["combined_der"] <= 0.35
        and (r["recording_id"], r["window_size"], r["segment_idx"])
        not in {(x["recording_id"], x["window_size"], x["segment_idx"]) for x in high + clean}
    ]
    medium = sorted(medium_candidates, key=lambda r: abs(r["combined_der"] - 0.25))[:per_bucket]
    selected = []
    for bucket, rows in [("high", high), ("medium", medium), ("clean", clean)]:
        for row in rows:
            item = dict(row)
            item["bucket"] = bucket
            selected.append(item)
    return selected


def load_input_windows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    windows = []
    for row in rows:
        windows.append(
            {
                "recording_id": row["recording_id"],
                "window_size": int(row["window_size"]),
                "segment_idx": int(row["segment_idx"]),
                "bucket": row.get("prior_bucket", row.get("bucket", "runtime_proxy")),
                "manifest_role": row.get("expansion_role", ""),
                "proxy_reasons": row.get("proxy_reasons", ""),
                "proxy_score": row.get("proxy_score", ""),
            }
        )
    return windows


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def omni_call_id(row: dict[str, Any], model: str | None = None) -> str:
    return "{recording_id}:{window_size}:{segment_idx}:{model}".format(
        recording_id=row.get("recording_id"),
        window_size=row.get("window_size"),
        segment_idx=row.get("segment_idx"),
        model=model or row.get("model"),
    )


def existing_successful_rows_by_id(path: Path) -> dict[str, dict[str, Any]]:
    successful: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        call_id = str(row.get("call_id") or omni_call_id(row))
        if row.get("error") or row.get("schema_ok") is False:
            continue
        successful.setdefault(call_id, row)
    return successful


def csv_fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "call_id",
        "recording_id",
        "window_size",
        "segment_idx",
        "bucket",
        "manifest_role",
        "proxy_reasons",
        "proxy_score",
        "audio",
        "clip_start_sec",
        "sample_rate",
        "channels",
        "start_sec",
        "duration_sec",
        "mixdown",
        "model",
        "transcript_excerpt",
        "speaker_count_guess",
        "overlap_or_crosstalk",
        "speech_activity",
        "diarization_risk",
        "should_quarantine",
        "should_defer_to_slow_agent",
        "usable_as_direct_diarizer",
        "reason",
        "confidence",
        "raw_content",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "call_seconds",
        "call_attempts",
        "max_call_attempts",
        "retry_backoff_seconds",
        "schema_ok",
        "error",
    ]
    seen = {key for row in rows for key in row}
    return [key for key in preferred if key in seen] + sorted(seen - set(preferred))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-windows-csv", type=Path, default=None, help="Use an explicit window manifest instead of DER-based bucket selection.")
    parser.add_argument("--fast-summary", type=Path, default=Path("outputs/sortformer_uv_48/nemo-sortformer-4spk-v1/default__spk_none/summary.json"))
    parser.add_argument("--slow-summary", type=Path, default=Path("outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none/summary.json"))
    parser.add_argument("--audio-dir", type=Path, default=Path("/Users/haojiang/data/AliMeeting/Eval_Ali/Eval_Ali_far/audio_dir"))
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--per-bucket", type=int, default=2)
    parser.add_argument("--clip-sec", type=float, default=8.0)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--output-jsonl", type=Path, default=Path("outputs/omni_guard/omni_window_batch.jsonl"))
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--max-call-attempts", type=int, default=1, help="Bounded attempts per live API call; failed rows still persist after final attempt.")
    parser.add_argument("--retry-backoff-seconds", type=float, default=0.0, help="Sleep between failed call attempts.")
    parser.add_argument(
        "--skip-existing-output",
        action="store_true",
        help="Reuse successful rows already present in --output-jsonl and only call missing/failed window-model ids.",
    )
    args = parser.parse_args()

    if not args.model:
        args.model = ["qwen3.5-omni-flash"]
    if args.input_windows_csv:
        windows = load_input_windows(args.input_windows_csv)
    else:
        fast = load_results(args.fast_summary)
        slow = load_results(args.slow_summary)
        windows = select_windows(fast, slow, args.per_bucket)
    existing_success = existing_successful_rows_by_id(args.output_jsonl) if args.skip_existing_output else {}
    targets = [(window, model, omni_call_id(window, model)) for window in windows for model in args.model]
    pending_targets = [(window, model, call_id) for window, model, call_id in targets if call_id not in existing_success]
    skipped_existing_calls = len(targets) - len(pending_targets)

    client = make_client(args) if pending_targets else None
    new_rows_by_id: dict[str, dict[str, Any]] = {}
    for window, model, call_id in pending_targets:
        path = audio_path(args.audio_dir, window["recording_id"])
        start_sec = float(window["segment_idx"] * window["window_size"])
        audio_b64, meta = wav_clip_base64(path, start_sec, args.clip_sec, channel=None)
        row = {
            **window,
            "call_id": call_id,
            "audio": str(path),
            "clip_start_sec": start_sec,
            **meta,
            "model": model,
            "max_call_attempts": max(1, int(args.max_call_attempts)),
            "retry_backoff_seconds": float(args.retry_backoff_seconds),
        }
        started = time.perf_counter()
        last_exc: Exception | None = None
        for attempt in range(1, max(1, int(args.max_call_attempts)) + 1):
            try:
                payload = call_model(client, model, audio_b64, args.temperature)
                row.update(payload)
                row["call_seconds"] = round(time.perf_counter() - started, 3)
                row["call_attempts"] = attempt
                row["schema_ok"] = True
                row["error"] = ""
                break
            except Exception as exc:
                last_exc = exc
                if attempt < max(1, int(args.max_call_attempts)) and float(args.retry_backoff_seconds) > 0:
                    time.sleep(float(args.retry_backoff_seconds))
        if "schema_ok" not in row:
            row.update(
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
                    "call_seconds": round(time.perf_counter() - started, 3),
                    "call_attempts": max(1, int(args.max_call_attempts)),
                    "schema_ok": False,
                    "error": repr(last_exc),
                }
            )
        new_rows_by_id[call_id] = row
    rows = []
    for _, _, call_id in targets:
        if call_id in existing_success:
            row = dict(existing_success[call_id])
            row.setdefault("call_id", call_id)
            row.setdefault("bucket", row.get("prior_bucket", ""))
            rows.append(row)
        elif call_id in new_rows_by_id:
            rows.append(new_rows_by_id[call_id])

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    output_csv = args.output_csv or args.output_jsonl.with_suffix(".csv")
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fieldnames(rows))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {args.output_jsonl}")
    print(f"Wrote {output_csv}")
    print(f"skipped_existing_calls={skipped_existing_calls} newly_requested_calls={len(pending_targets)}")
    for row in rows:
        printable = {
            **row,
            "bucket": row.get("bucket", row.get("prior_bucket", "")),
            "diarization_risk": row.get("diarization_risk", ""),
            "should_quarantine": row.get("should_quarantine", ""),
            "should_defer_to_slow_agent": row.get("should_defer_to_slow_agent", ""),
            "call_seconds": row.get("call_seconds", ""),
        }
        print(
            "{bucket} {recording_id}:{segment_idx} {model} risk={diarization_risk} quarantine={should_quarantine} defer={should_defer_to_slow_agent} latency={call_seconds}".format(
                **printable
            )
        )


if __name__ == "__main__":
    main()
