#!/usr/bin/env python3
"""Build runtime-safe audio energy features for cached AliMeeting windows.

The features are intentionally simple and offline-runnable:
- no model/API calls;
- no DER, GT speech, or oracle speaker labels;
- only audio path, offset, duration, and frame-level RMS statistics.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alimeeting_diarization_bench.data.manifests import generate_stratified_segments, load_manifests


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def key_from_segment(seg: dict[str, Any]) -> tuple[str, int, int]:
    return (str(seg["recording_id"]), int(seg["window_size"]), int(seg["segment_idx"]))


def frame_rms(audio: np.ndarray, sr: int, frame_ms: float, hop_ms: float) -> np.ndarray:
    frame = max(1, int(sr * frame_ms / 1000.0))
    hop = max(1, int(sr * hop_ms / 1000.0))
    if len(audio) < frame:
        return np.array([], dtype=np.float32)
    values = []
    for start in range(0, len(audio) - frame + 1, hop):
        chunk = audio[start : start + frame]
        if chunk.ndim == 1:
            values.append(float(np.sqrt(np.mean(chunk * chunk) + 1e-12)))
        else:
            values.append(np.sqrt(np.mean(chunk * chunk, axis=0) + 1e-12))
    return np.asarray(values, dtype=np.float32)


def rms_to_db(rms: np.ndarray) -> np.ndarray:
    return 20 * np.log10(rms + 1e-12)


def threshold_stats(db: np.ndarray, args: argparse.Namespace) -> tuple[float, float, float, float]:
    noise = float(np.percentile(db, args.noise_percentile))
    threshold = max(noise + args.threshold_margin_db, args.min_threshold_db)
    hop_sec = args.hop_ms / 1000.0
    speech_sec = float(np.sum(db > threshold) * hop_sec)
    return noise, threshold, hop_sec, speech_sec


def audio_features(seg: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    audio_path = Path(seg["audio_path"])
    row = {
        "recording_id": seg["recording_id"],
        "window_size": int(seg["window_size"]),
        "segment_idx": int(seg["segment_idx"]),
        "audio_path": str(audio_path),
        "audio_exists": audio_path.exists(),
        "offset": as_float(seg.get("offset")),
        "duration": as_float(seg.get("duration")),
        "sample_rate": None,
        "channels": None,
        "audio_speech_sec": 0.0,
        "audio_speech_ratio": 0.0,
        "audio_mean_db": None,
        "audio_p20_db": None,
        "audio_p50_db": None,
        "audio_p90_db": None,
        "audio_p95_db": None,
        "audio_threshold_db": None,
        "audio_dynamic_range_db": None,
        "audio_high_energy_ratio": 0.0,
        "audio_low_energy_ratio": 0.0,
        "audio_max_speech_sec": 0.0,
        "audio_max_speech_ratio": 0.0,
        "audio_max_mean_db": None,
        "audio_max_p90_db": None,
        "audio_max_threshold_db": None,
        "audio_max_minus_mean_p90_db": None,
        "audio_channel_activity_mean": None,
        "audio_channel_activity_p90": None,
        "audio_channel_activity_ratio": None,
        "audio_frame_count": 0,
        "feature_status": "missing_audio",
    }
    if not audio_path.exists():
        return row

    info = sf.info(audio_path)
    sr = info.samplerate
    start = int(as_float(seg.get("offset")) * sr)
    frames = int(as_float(seg.get("duration")) * sr)
    raw_audio, _ = sf.read(audio_path, start=start, frames=frames, dtype="float32")
    if raw_audio.ndim > 1:
        row["channels"] = int(raw_audio.shape[1])
        if args.mixdown == "mean":
            audio = raw_audio.mean(axis=1)
        else:
            audio = raw_audio[:, int(args.channel)]
    else:
        row["channels"] = 1
        raw_audio = raw_audio.reshape(-1, 1)
        audio = raw_audio[:, 0]
    row["sample_rate"] = sr

    db = rms_to_db(frame_rms(audio, sr, args.frame_ms, args.hop_ms))
    if db.size == 0:
        row["feature_status"] = "too_short"
        return row

    _, threshold, hop_sec, speech_sec = threshold_stats(db, args)
    channel_rms = frame_rms(raw_audio, sr, args.frame_ms, args.hop_ms)
    if channel_rms.ndim == 1:
        channel_rms = channel_rms.reshape(-1, 1)
    channel_db = rms_to_db(channel_rms)
    max_db = np.max(channel_db, axis=1)
    _, max_threshold, _, max_speech_sec = threshold_stats(max_db, args)
    active_channels = np.sum(channel_db > max_threshold, axis=1)
    channels = max(1, int(row["channels"] or 1))
    duration = as_float(seg.get("duration"))
    row.update(
        {
            "audio_speech_sec": round(speech_sec, 4),
            "audio_speech_ratio": round(speech_sec / duration if duration else 0.0, 4),
            "audio_mean_db": round(float(np.mean(db)), 4),
            "audio_p20_db": round(float(np.percentile(db, 20)), 4),
            "audio_p50_db": round(float(np.percentile(db, 50)), 4),
            "audio_p90_db": round(float(np.percentile(db, 90)), 4),
            "audio_p95_db": round(float(np.percentile(db, 95)), 4),
            "audio_threshold_db": round(threshold, 4),
            "audio_dynamic_range_db": round(float(np.percentile(db, 90) - np.percentile(db, 20)), 4),
            "audio_high_energy_ratio": round(float(np.mean(db > np.percentile(db, 90))), 4),
            "audio_low_energy_ratio": round(float(np.mean(db < np.percentile(db, 20))), 4),
            "audio_max_speech_sec": round(max_speech_sec, 4),
            "audio_max_speech_ratio": round(max_speech_sec / duration if duration else 0.0, 4),
            "audio_max_mean_db": round(float(np.mean(max_db)), 4),
            "audio_max_p90_db": round(float(np.percentile(max_db, 90)), 4),
            "audio_max_threshold_db": round(max_threshold, 4),
            "audio_max_minus_mean_p90_db": round(float(np.percentile(max_db, 90) - np.percentile(db, 90)), 4),
            "audio_channel_activity_mean": round(float(np.mean(active_channels)), 4),
            "audio_channel_activity_p90": round(float(np.percentile(active_channels, 90)), 4),
            "audio_channel_activity_ratio": round(float(np.mean(active_channels) / channels), 4),
            "audio_frame_count": int(db.size),
            "feature_status": "ok",
        }
    )
    return row


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "recording_id",
        "window_size",
        "segment_idx",
        "audio_path",
        "audio_exists",
        "offset",
        "duration",
        "sample_rate",
        "channels",
        "audio_speech_sec",
        "audio_speech_ratio",
        "audio_mean_db",
        "audio_p20_db",
        "audio_p50_db",
        "audio_p90_db",
        "audio_p95_db",
        "audio_threshold_db",
        "audio_dynamic_range_db",
        "audio_high_energy_ratio",
        "audio_low_energy_ratio",
        "audio_max_speech_sec",
        "audio_max_speech_ratio",
        "audio_max_mean_db",
        "audio_max_p90_db",
        "audio_max_threshold_db",
        "audio_max_minus_mean_p90_db",
        "audio_channel_activity_mean",
        "audio_channel_activity_p90",
        "audio_channel_activity_ratio",
        "audio_frame_count",
        "feature_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Audio Window Runtime Features",
        "",
        f"- Runtime contract: `{summary['runtime_contract']}`",
        f"- Status: `{summary['status']}`",
        f"- Windows: `{summary['windows']}`",
        f"- OK rows: `{summary['ok_rows']}`",
        f"- Missing audio rows: `{summary['missing_audio_rows']}`",
        f"- Mean audio speech ratio: `{summary['mean_audio_speech_ratio']:.3f}`",
        f"- Mean max-channel speech ratio: `{summary['mean_audio_max_speech_ratio']:.3f}`",
        f"- Mean channel activity ratio: `{summary['mean_audio_channel_activity_ratio']:.3f}`",
        "",
        "## Reading",
        "",
        "- These are lightweight energy and multichannel activity proxies, not calibrated VAD.",
        "- It can be used as a runtime feature, but DER/GT scoring must happen only after the selector decision.",
        "- Far-field overlapping speech can make the proxy undercount true overlapped speaker time.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-size", type=int, default=30)
    parser.add_argument("--total-samples", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--frame-ms", type=float, default=30.0)
    parser.add_argument("--hop-ms", type=float, default=10.0)
    parser.add_argument("--noise-percentile", type=float, default=20.0)
    parser.add_argument("--threshold-margin-db", type=float, default=8.0)
    parser.add_argument("--min-threshold-db", type=float, default=-45.0)
    parser.add_argument("--mixdown", choices=["mean", "channel"], default="mean")
    parser.add_argument("--channel", type=int, default=0)
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/audio_window_features/audio_window_features_120.csv"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/audio_window_features/summary.json"))
    parser.add_argument("--summary-md", type=Path, default=Path("outputs/audio_window_features/audio_window_features.md"))
    args = parser.parse_args()

    recordings, supervisions = load_manifests()
    segments = generate_stratified_segments(
        recordings,
        supervisions,
        window_size=args.window_size,
        total_samples=args.total_samples,
        seed=args.seed,
    )
    rows = [audio_features(seg, args) for seg in segments]
    ok_rows = [row for row in rows if row["feature_status"] == "ok"]
    summary = {
        "runtime_contract": "audio_window_energy_features_no_live_calls_no_gt_metrics",
        "status": "pass" if len(ok_rows) == len(rows) else "partial",
        "windows": len(rows),
        "ok_rows": len(ok_rows),
        "missing_audio_rows": sum(1 for row in rows if row["feature_status"] == "missing_audio"),
        "mean_audio_speech_ratio": float(np.mean([row["audio_speech_ratio"] for row in ok_rows])) if ok_rows else 0.0,
        "mean_audio_max_speech_ratio": float(np.mean([row["audio_max_speech_ratio"] for row in ok_rows])) if ok_rows else 0.0,
        "mean_audio_channel_activity_ratio": float(np.mean([row["audio_channel_activity_ratio"] for row in ok_rows])) if ok_rows else 0.0,
        "output_csv": str(args.output_csv),
        "summary_md": str(args.summary_md),
        "feature_params": {
            "frame_ms": args.frame_ms,
            "hop_ms": args.hop_ms,
            "noise_percentile": args.noise_percentile,
            "threshold_margin_db": args.threshold_margin_db,
            "min_threshold_db": args.min_threshold_db,
            "mixdown": args.mixdown,
            "channel": args.channel,
        },
    }
    write_csv(args.output_csv, rows)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.summary_md, summary)
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.summary_json}")
    print(f"Wrote {args.summary_md}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
