#!/usr/bin/env python3
"""Generate real patch-level voiceprint evidence from diarization summaries.

This uses the same ECAPA embedding path as analyze_voiceprint_memory.py, but
emits deployable patch evidence for the LLM Policy Agent:
top1/top2 global speaker, cosine similarities, and confidence margin.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.analyze_voiceprint_memory import (  # noqa: E402
    SpeechBrainEmbedder,
    build_segment_index,
    collect_local_speaker_audio,
    cosine,
    infer_segment_args,
)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_summary_results(path: Path) -> tuple[dict[str, Any], dict[tuple[str, int, int], dict[str, Any]]]:
    summary = json.loads(path.read_text(encoding="utf-8"))
    by_key = {}
    for row in summary.get("results", []):
        if row.get("success"):
            by_key[(row["recording_id"], int(row["window_size"]), int(row["segment_idx"]))] = row
    return summary, by_key


def load_patch_ids_from_prompt(path: Path | None) -> set[str]:
    if path is None:
        return set()
    patch_ids = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            for message in row.get("messages", []):
                if message.get("role") != "user":
                    continue
                payload = json.loads(message.get("content", "{}"))
                for patch in payload.get("patches", []):
                    patch_ids.add(patch["patch_id"])
    return patch_ids


def load_patch_ids_from_file(path: Path | None) -> set[str]:
    if path is None:
        return set()
    patch_ids = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            value = line.strip()
            if value and not value.startswith("#"):
                patch_ids.add(value)
    return patch_ids


def trigger_selected(row: dict[str, str], trigger_policy: str) -> bool:
    if trigger_policy == "all":
        return True
    if trigger_policy == "semantic_label_smoothing":
        return row["reason"] in {
            "memory_low_confidence_relabel_deferred",
            "recover_segment_too_short",
            "do_not_suppress_without_strong_evidence",
        }
    if trigger_policy == "non_accept_review":
        return row["decision"] != "accept"
    raise ValueError(f"Unsupported trigger policy: {trigger_policy}")


def confidence_bucket(confidence: float, margin: float) -> str:
    if confidence >= 0.75 and margin >= 0.12:
        return "high"
    if confidence >= 0.55 and margin >= 0.06:
        return "medium"
    return "low"


def local_speaker_embedding(
    result: dict[str, Any],
    segment_index: dict[tuple[str, int, int], dict[str, Any]],
    embedder: SpeechBrainEmbedder,
    local_speaker: str,
    min_segment_sec: float,
    max_audio_sec: float,
) -> np.ndarray | None:
    key = (result["recording_id"], int(result["window_size"]), int(result["segment_idx"]))
    segment_meta = segment_index.get(key)
    if segment_meta is None:
        return None
    audio = collect_local_speaker_audio(
        segment_meta,
        result.get("pred_segments", []),
        local_speaker,
        min_segment_sec=min_segment_sec,
        max_audio_sec=max_audio_sec,
    )
    if audio is None or len(audio) < int(16000 * min_segment_sec):
        return None
    return embedder.encode(audio, 16000)


def build_initial_memory(
    results_by_key: dict[tuple[str, int, int], dict[str, Any]],
    segment_index: dict[tuple[str, int, int], dict[str, Any]],
    embedder: SpeechBrainEmbedder,
    enrollment_windows: int,
    min_segment_sec: float,
    max_audio_sec: float,
) -> dict[str, dict[str, np.ndarray]]:
    by_recording: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results_by_key.values():
        by_recording[result["recording_id"]].append(result)

    memories: dict[str, dict[str, np.ndarray]] = {}
    for recording_id, results in by_recording.items():
        results.sort(key=lambda row: int(row["segment_idx"]))
        recording_memory: dict[str, np.ndarray] = {}
        next_global = 0
        for result in results[:enrollment_windows]:
            local_speakers = sorted({str(seg["speaker"]) for seg in result.get("pred_segments", [])})
            for local_speaker in local_speakers:
                embedding = local_speaker_embedding(
                    result,
                    segment_index,
                    embedder,
                    local_speaker,
                    min_segment_sec=min_segment_sec,
                    max_audio_sec=max_audio_sec,
                )
                if embedding is None:
                    continue
                global_id = f"G{next_global:02d}"
                next_global += 1
                recording_memory[global_id] = embedding
        memories[recording_id] = recording_memory
    return memories


def rank_memory(embedding: np.ndarray, memory: dict[str, np.ndarray]) -> list[tuple[str, float]]:
    scores = [(global_id, cosine(embedding, centroid)) for global_id, centroid in memory.items()]
    scores.sort(key=lambda item: item[1], reverse=True)
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patches", type=Path, default=Path("outputs/policy_agent/sortformer_diarizen_48_decisions.csv"))
    parser.add_argument("--fast-summary", type=Path, default=Path("outputs/sortformer_uv_48/nemo-sortformer-4spk-v1/default__spk_none/summary.json"))
    parser.add_argument("--slow-summary", type=Path, default=Path("outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none/summary.json"))
    parser.add_argument("--memory-summary", type=Path, default=None)
    parser.add_argument("--trigger-policy", choices=["all", "semantic_label_smoothing", "non_accept_review"], default="semantic_label_smoothing")
    parser.add_argument("--patch-ids-from-prompt", type=Path, default=None)
    parser.add_argument("--patch-id-file", type=Path, default=None)
    parser.add_argument("--max-patches", type=int, default=24)
    parser.add_argument("--enrollment-windows", type=int, default=1)
    parser.add_argument("--min-segment-sec", type=float, default=0.6)
    parser.add_argument("--max-audio-sec", type=float, default=8.0)
    parser.add_argument("--embedding-model", default="speechbrain/spkrec-ecapa-voxceleb")
    parser.add_argument("--embedding-cache", type=Path, default=Path("outputs/voiceprint_memory/speechbrain_ecapa"))
    parser.add_argument("--output", type=Path, default=Path("outputs/voiceprint_patch_evidence/real_patch_evidence.csv"))
    args = parser.parse_args()

    memory_summary_path = args.memory_summary or args.fast_summary
    memory_summary, memory_results = load_summary_results(memory_summary_path)
    fast_summary, fast_results = load_summary_results(args.fast_summary)
    slow_summary, slow_results = load_summary_results(args.slow_summary)
    window_size, total_samples = infer_segment_args(memory_summary, None)
    segment_index = build_segment_index(
        sampling_mode="stratified",
        window_size=window_size,
        total_samples=total_samples,
        seed=42,
        segments_per_meeting=3,
    )

    embedder = SpeechBrainEmbedder(args.embedding_model, args.embedding_cache)
    memories = build_initial_memory(
        memory_results,
        segment_index,
        embedder,
        enrollment_windows=args.enrollment_windows,
        min_segment_sec=args.min_segment_sec,
        max_audio_sec=args.max_audio_sec,
    )

    patch_id_filter = load_patch_ids_from_prompt(args.patch_ids_from_prompt)
    patch_id_filter.update(load_patch_ids_from_file(args.patch_id_file))
    patch_rows = [row for row in load_csv(args.patches) if trigger_selected(row, args.trigger_policy)]
    if patch_id_filter:
        patch_rows = [row for row in patch_rows if row["patch_id"] in patch_id_filter]
    patch_rows.sort(key=lambda row: (row["recording_id"], int(row["segment_idx"]), int(float(row["start"])), row["patch_id"]))
    if args.max_patches:
        patch_rows = patch_rows[: args.max_patches]

    summary_by_source = {
        "fast": (fast_summary, fast_results),
        "slow": (slow_summary, slow_results),
    }
    output_rows = []
    embedding_cache: dict[tuple[str, str, str, int, int], np.ndarray | None] = {}
    for row in patch_rows:
        source = row["source"]
        _, source_results = summary_by_source.get(source, (fast_summary, fast_results))
        key = (row["recording_id"], int(row["window_size"]), int(row["segment_idx"]))
        result = source_results.get(key)
        memory = memories.get(row["recording_id"], {})
        base = {
            "patch_id": row["patch_id"],
            "top1_global_speaker": "",
            "top1_similarity": "",
            "top2_global_speaker": "",
            "top2_similarity": "",
            "similarity_margin": "",
            "memory_confidence": "",
            "confidence_bucket": "missing",
            "enrollment_source": "first_window_ecapa",
            "evidence_status": "",
        }
        if result is None:
            base["evidence_status"] = "missing_source_result"
            output_rows.append(base)
            continue
        if not memory:
            base["evidence_status"] = "missing_memory"
            output_rows.append(base)
            continue
        cache_key = (source, row["recording_id"], str(row["speaker"]), int(row["window_size"]), int(row["segment_idx"]))
        if cache_key not in embedding_cache:
            embedding_cache[cache_key] = local_speaker_embedding(
                result,
                segment_index,
                embedder,
                str(row["speaker"]),
                min_segment_sec=args.min_segment_sec,
                max_audio_sec=args.max_audio_sec,
            )
        embedding = embedding_cache[cache_key]
        if embedding is None:
            base["evidence_status"] = "missing_patch_embedding"
            output_rows.append(base)
            continue
        ranked = rank_memory(embedding, memory)
        if not ranked:
            base["evidence_status"] = "missing_memory_scores"
            output_rows.append(base)
            continue
        top1_id, top1 = ranked[0]
        top2_id, top2 = ranked[1] if len(ranked) > 1 else ("", -math.inf)
        margin = top1 - top2 if math.isfinite(top2) else top1
        confidence = max(0.0, min(1.0, top1))
        base.update(
            {
                "top1_global_speaker": top1_id,
                "top1_similarity": round(top1, 4),
                "top2_global_speaker": top2_id,
                "top2_similarity": round(top2, 4) if math.isfinite(top2) else "",
                "similarity_margin": round(margin, 4),
                "memory_confidence": round(confidence, 4),
                "confidence_bucket": confidence_bucket(confidence, margin),
                "evidence_status": "ok",
            }
        )
        output_rows.append(base)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output_rows[0].keys()))
        writer.writeheader()
        writer.writerows(output_rows)

    ok = sum(1 for row in output_rows if row["evidence_status"] == "ok")
    print(f"Generated patch voiceprint evidence rows={len(output_rows)} ok={ok} output={args.output}")
    print(f"memory_model={memory_summary.get('model_name')} fast_model={fast_summary.get('model_name')} slow_model={slow_summary.get('model_name')}")


if __name__ == "__main__":
    main()
