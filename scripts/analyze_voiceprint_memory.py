#!/usr/bin/env python3
"""Prototype voiceprint-memory relabeling for diarization summaries.

This script evaluates the core Slow-Agent idea without requiring a camera:

1. Reconstruct benchmark windows from the AliMeeting manifests.
2. For each predicted local speaker in each window, extract a speaker embedding
   from the original audio.
3. Initialize global speaker memory from the first N windows.
4. Assign later local speakers to memory by cosine similarity, optionally
   creating new speakers.
5. Use ground truth only at the end to score global identity consistency.

Run with the DiariZen uv environment because it already has SpeechBrain:

    .venv_diarizen/bin/python scripts/analyze_voiceprint_memory.py \
      outputs/diarizen_uv_24/diarizen-large-v2/default__spk_none/summary.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
import torch

from alimeeting_diarization_bench.config import Paths
from alimeeting_diarization_bench.data.audio import slice_audio
from alimeeting_diarization_bench.data.manifests import (
    generate_segments,
    generate_stratified_segments,
    load_manifests,
)


def patch_torch_amp_compat() -> None:
    """Bridge SpeechBrain's torch>=2.4 autocast API on the local torch 2.1 env."""
    if hasattr(torch.amp, "custom_fwd") and hasattr(torch.amp, "custom_bwd"):
        return

    def custom_fwd(fwd=None, *, device_type: str | None = None, cast_inputs=None):
        del device_type
        return torch.cuda.amp.custom_fwd(fwd=fwd, cast_inputs=cast_inputs)

    def custom_bwd(bwd=None, *, device_type: str | None = None):
        del device_type
        return torch.cuda.amp.custom_bwd(bwd=bwd)

    if not hasattr(torch.amp, "custom_fwd"):
        torch.amp.custom_fwd = custom_fwd
    if not hasattr(torch.amp, "custom_bwd"):
        torch.amp.custom_bwd = custom_bwd


def overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-8:
        return vector
    return vector / norm


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def build_segment_index(
    sampling_mode: str,
    window_size: int,
    total_samples: int,
    seed: int,
    segments_per_meeting: int,
) -> dict[tuple[str, int, int], dict]:
    recordings, supervisions = load_manifests()
    if sampling_mode == "stratified":
        segments = generate_stratified_segments(
            recordings,
            supervisions,
            window_size=window_size,
            total_samples=total_samples,
            seed=seed,
        )
    else:
        segments = generate_segments(
            recordings,
            window_sizes=[window_size],
            segments_per_meeting=segments_per_meeting,
        )
    return {
        (seg["recording_id"], int(seg["window_size"]), int(seg["segment_idx"])): seg
        for seg in segments
    }


def infer_segment_args(summary: dict, fallback_window_size: int | None) -> tuple[int, int]:
    results = [r for r in summary.get("results", []) if r.get("success")]
    if not results:
        raise ValueError("summary has no successful results")
    window_size = fallback_window_size or int(results[0]["window_size"])
    total_samples = int(summary.get("total_segments") or len(results))
    return window_size, total_samples


class SpeechBrainEmbedder:
    def __init__(self, source: str, savedir: Path):
        patch_torch_amp_compat()
        from speechbrain.inference.speaker import EncoderClassifier

        self.classifier = EncoderClassifier.from_hparams(
            source=source,
            savedir=str(savedir),
            run_opts={"device": "cuda" if torch.cuda.is_available() else "cpu"},
        )

    def encode(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        if sample_rate != 16000:
            raise ValueError("Expected 16 kHz audio")
        wav = torch.from_numpy(audio.astype("float32")).unsqueeze(0)
        with torch.no_grad():
            embedding = self.classifier.encode_batch(wav).squeeze().detach().cpu().numpy()
        return l2_normalize(np.asarray(embedding, dtype=np.float32))


def collect_local_speaker_audio(
    segment_meta: dict,
    pred_segments: list[dict],
    local_speaker: str,
    min_segment_sec: float,
    max_audio_sec: float,
) -> np.ndarray | None:
    pieces = []
    total = 0.0
    for pred in pred_segments:
        if str(pred["speaker"]) != local_speaker:
            continue
        start = float(pred["start"])
        end = float(pred["end"])
        dur = end - start
        if dur < min_segment_sec:
            continue
        remaining = max_audio_sec - total
        if remaining <= 0:
            break
        use_dur = min(dur, remaining)
        audio, _ = slice_audio(
            segment_meta["audio_path"],
            offset=float(segment_meta["offset"]) + start,
            duration=use_dur,
        )
        if audio.size:
            pieces.append(audio)
            total += use_dur
    if not pieces:
        return None
    return np.concatenate(pieces)


def best_gt_for_global(results: Iterable[dict], assigned_key: str = "global_speaker") -> dict[str, str]:
    scores: dict[tuple[str, str], float] = defaultdict(float)
    for result in results:
        for pred in result.get("memory_segments", []):
            if pred.get(assigned_key) is None:
                continue
            p_start = float(pred["start"])
            p_end = float(pred["end"])
            global_id = str(pred[assigned_key])
            for gt in result.get("gt_segments", []):
                duration = overlap(p_start, p_end, float(gt["start"]), float(gt["end"]))
                if duration > 0:
                    scores[(global_id, str(gt["speaker"]))] += duration

    mapping = {}
    used_global = set()
    used_gt = set()
    for (global_id, gt_id), value in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        if global_id in used_global or gt_id in used_gt:
            continue
        mapping[global_id] = gt_id
        used_global.add(global_id)
        used_gt.add(gt_id)
    return mapping


def score_global_identity(results: Iterable[dict], global_to_gt: dict[str, str]) -> dict[str, float]:
    total_overlap = 0.0
    correct_overlap = 0.0
    pred_speech = 0.0
    assigned_speech = 0.0
    for result in results:
        for pred in result.get("memory_segments", []):
            p_start = float(pred["start"])
            p_end = float(pred["end"])
            p_dur = max(0.0, p_end - p_start)
            pred_speech += p_dur
            if pred.get("global_speaker") is not None:
                assigned_speech += p_dur
            mapped_gt = global_to_gt.get(str(pred.get("global_speaker")))
            for gt in result.get("gt_segments", []):
                duration = overlap(p_start, p_end, float(gt["start"]), float(gt["end"]))
                if duration <= 0:
                    continue
                total_overlap += duration
                if mapped_gt == str(gt["speaker"]):
                    correct_overlap += duration
    return {
        "global_identity_accuracy": correct_overlap / total_overlap if total_overlap else 0.0,
        "assigned_speech_rate": assigned_speech / pred_speech if pred_speech else 0.0,
        "overlap_seconds": total_overlap,
    }


def process_recording(
    recording_id: str,
    results: list[dict],
    segment_index: dict[tuple[str, int, int], dict],
    embedder: SpeechBrainEmbedder,
    enrollment_windows: int,
    match_threshold: float,
    update_threshold: float,
    min_segment_sec: float,
    max_audio_sec: float,
) -> dict:
    memories: dict[str, np.ndarray] = {}
    memory_counts: dict[str, int] = defaultdict(int)
    next_global = 0
    processed = []

    for window_idx, result in enumerate(results):
        key = (result["recording_id"], int(result["window_size"]), int(result["segment_idx"]))
        segment_meta = segment_index.get(key)
        if segment_meta is None:
            raise KeyError(f"Cannot reconstruct segment metadata for {key}")

        pred_segments = result.get("pred_segments", [])
        local_speakers = sorted({str(s["speaker"]) for s in pred_segments})
        local_embeddings = {}
        for local_speaker in local_speakers:
            audio = collect_local_speaker_audio(
                segment_meta,
                pred_segments,
                local_speaker,
                min_segment_sec=min_segment_sec,
                max_audio_sec=max_audio_sec,
            )
            if audio is None or len(audio) < int(16000 * min_segment_sec):
                continue
            local_embeddings[local_speaker] = embedder.encode(audio, 16000)

        local_to_global = {}
        for local_speaker, embedding in local_embeddings.items():
            if window_idx == 0 or not memories:
                global_id = f"G{next_global:02d}"
                next_global += 1
                memories[global_id] = embedding
                memory_counts[global_id] = 1
                local_to_global[local_speaker] = global_id
                continue

            best_id = None
            best_score = -math.inf
            for global_id, centroid in memories.items():
                score = cosine(embedding, centroid)
                if score > best_score:
                    best_id = global_id
                    best_score = score

            if best_id is not None and best_score >= match_threshold:
                local_to_global[local_speaker] = best_id
                if best_score >= update_threshold:
                    count = memory_counts[best_id]
                    memories[best_id] = l2_normalize((memories[best_id] * count + embedding) / (count + 1))
                    memory_counts[best_id] = count + 1
            else:
                global_id = f"G{next_global:02d}"
                next_global += 1
                memories[global_id] = embedding
                memory_counts[global_id] = 1
                local_to_global[local_speaker] = global_id

        memory_segments = []
        for pred in pred_segments:
            local_speaker = str(pred["speaker"])
            global_id = local_to_global.get(local_speaker)
            memory_segments.append(
                {
                    **pred,
                    "local_speaker": local_speaker,
                    "global_speaker": global_id,
                }
            )
        processed.append({**result, "memory_segments": memory_segments})

    eval_processed = processed[enrollment_windows:] if len(processed) > enrollment_windows else processed
    global_to_gt = best_gt_for_global(eval_processed)
    score = score_global_identity(eval_processed, global_to_gt)
    return {
        "recording_id": recording_id,
        "windows": len(results),
        "eval_windows": len(eval_processed),
        "global_speakers": len(memories),
        "global_to_gt": json.dumps(global_to_gt, ensure_ascii=False, sort_keys=True),
        **score,
    }


def analyze_summary(
    summary_path: Path,
    args: argparse.Namespace,
    embedder: SpeechBrainEmbedder,
) -> list[dict]:
    summary = json.loads(summary_path.read_text())
    window_size, total_samples = infer_segment_args(summary, args.window_size)
    segment_index = build_segment_index(
        sampling_mode=args.sampling_mode,
        window_size=window_size,
        total_samples=args.total_samples or total_samples,
        seed=args.seed,
        segments_per_meeting=args.segments_per_meeting,
    )

    by_recording: dict[str, list[dict]] = defaultdict(list)
    for result in summary.get("results", []):
        if result.get("success"):
            by_recording[result["recording_id"]].append(result)

    rows = []
    for recording_id, results in sorted(by_recording.items()):
        results.sort(key=lambda r: (int(r.get("segment_idx", 0)), int(r.get("window_size", 0))))
        row = process_recording(
            recording_id,
            results,
            segment_index,
            embedder,
            enrollment_windows=args.enrollment_windows,
            match_threshold=args.match_threshold,
            update_threshold=args.update_threshold,
            min_segment_sec=args.min_segment_sec,
            max_audio_sec=args.max_audio_sec,
        )
        row["summary"] = str(summary_path)
        row["model_name"] = summary.get("model_name", "")
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", nargs="+", type=Path)
    parser.add_argument("--sampling-mode", choices=["stratified", "uniform"], default="stratified")
    parser.add_argument("--window-size", type=int, default=None)
    parser.add_argument("--total-samples", type=int, default=None)
    parser.add_argument("--segments-per-meeting", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--enrollment-windows", type=int, default=1)
    parser.add_argument("--match-threshold", type=float, default=0.35)
    parser.add_argument("--update-threshold", type=float, default=0.55)
    parser.add_argument("--min-segment-sec", type=float, default=0.6)
    parser.add_argument("--max-audio-sec", type=float, default=8.0)
    parser.add_argument("--embedding-model", default="speechbrain/spkrec-ecapa-voxceleb")
    parser.add_argument("--embedding-cache", type=Path, default=Path("outputs/voiceprint_memory/speechbrain_ecapa"))
    parser.add_argument("--output", type=Path, default=Path("outputs/voiceprint_memory/results.csv"))
    args = parser.parse_args()

    Paths.from_env()
    embedder = SpeechBrainEmbedder(args.embedding_model, args.embedding_cache)

    rows = []
    for summary in args.summary:
        rows.extend(analyze_summary(summary, args, embedder))

    if not rows:
        raise SystemExit("No rows produced")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("Voiceprint memory relabeling")
    by_model: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_model[row["model_name"]].append(row)
        print(
            "%s %-24s acc=%.1f%% assigned=%.1f%% global_spk=%d map=%s"
            % (
                row["recording_id"],
                row["model_name"],
                row["global_identity_accuracy"] * 100,
                row["assigned_speech_rate"] * 100,
                row["global_speakers"],
                row["global_to_gt"],
            )
        )
    print("\nAverages by model")
    for model_name, model_rows in sorted(by_model.items()):
        acc = sum(r["global_identity_accuracy"] for r in model_rows) / len(model_rows)
        assigned = sum(r["assigned_speech_rate"] for r in model_rows) / len(model_rows)
        speakers = sum(r["global_speakers"] for r in model_rows) / len(model_rows)
        print(
            "%-24s acc=%.1f%% assigned=%.1f%% avg_global_spk=%.1f"
            % (model_name, acc * 100, assigned * 100, speakers)
        )
    print("CSV:", args.output)


if __name__ == "__main__":
    main()
