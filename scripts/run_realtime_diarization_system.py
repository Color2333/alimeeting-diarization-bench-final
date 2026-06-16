#!/usr/bin/env python3
"""Offline runnable realtime diarization enhancement pipeline.

The system path is intentionally offline:

1. Use cached fast diarization output as the first timeline.
2. Use cached slow diarization output as correction evidence.
3. Apply conservative rule writeback for recover patches only.
4. Keep risky/guarded patches out of the final timeline.
5. Write timelines, correction logs, RTTM/CSV/JSON, and metrics.

No DeepSeek, Qwen, Omni, or other online API calls are made by this script.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import logging
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alimeeting_diarization_bench.data.manifests import generate_stratified_segments, load_manifests
from alimeeting_diarization_bench.metrics.der import calc_der

from evaluate_rule_writeback_timeline import (
    WRITEBACK_CATEGORIES,
    grouped_gate_rows,
    load_csv,
    load_summary,
    materialize_variant,
    patch_id,
)


DEFAULT_FAST_SUMMARY = ROOT / "outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json"
DEFAULT_SLOW_SUMMARY = ROOT / "outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json"
DEFAULT_GATE_DECISIONS = ROOT / "outputs/writeback_gate_120/gate_decisions.csv"
DEFAULT_PATCHES = ROOT / "outputs/segment_patches/sortformer_diarizen_120_patches.csv"
DEFAULT_GUARD_SUMMARY = ROOT / "outputs/runtime_safe_llm_window_batch/llm_guard_tuning_104w_summary.json"
DEFAULT_TIMELINE_RESULTS = ROOT / "outputs/rule_writeback_timeline_120/rule_writeback_timeline_results.csv"
DEFAULT_SELECTOR_VALIDATION = ROOT / "outputs/system_selector_validation/guarded_slow_selector_validation.json"
DEFAULT_SELECTOR_SEARCH = ROOT / "outputs/system_selector_search/system_selector_policy_search.json"
DEFAULT_SLOW_SANITIZATION_SEARCH = ROOT / "outputs/slow_sanitization_search/slow_sanitization_policy_search.json"
DEFAULT_AUDIO_FEATURES = ROOT / "outputs/audio_window_features/audio_window_features_120.csv"
DEFAULT_WINDOW_FEATURES = ROOT / "outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv"
DEFAULT_EXTERNAL_CANDIDATE_SUMMARY = ROOT / "outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none/summary.json"
DEFAULT_VARIANT = "slow_guarded_fast_fallback_rare_audio_rule_recover"
DEFAULT_GUARD_QUARANTINE_THRESHOLD = 1
DEFAULT_RARE_AUDIO_SPEECH_SEC_THRESHOLD = 18.605
DEFAULT_RARE_SLOW_SEGMENTS_MAX = 3
DEFAULT_BALANCED_ALIGN_SLOW_SEGMENT_MIN = 18
DEFAULT_BALANCED_KEEP_FAST_SUPPORTED_MIN = 6
DEFAULT_CONTEXT_AUDIO_P50_DB_MIN = -36.6753
DEFAULT_CONTEXT_PREV_AUDIO_DYNAMIC_RANGE_DB_MAX = 10.1179
DEFAULT_EXTERNAL_FAST_AUDIO_SPEECH_RATIO_MAX = 1.64195
DEFAULT_EXTERNAL_FAST_SPEECH_MAX = 19.52

logging.getLogger().setLevel(logging.ERROR)
logging.disable(logging.WARNING)


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def infer_recording_id(audio: Path) -> str | None:
    match = re.search(r"(R\d+_M\d+)", audio.name)
    return match.group(1) if match else None


def result_key(row: dict[str, Any]) -> tuple[str, int, int]:
    return (str(row["recording_id"]), int(row["window_size"]), int(row["segment_idx"]))


def window_id(key: tuple[str, int, int]) -> str:
    return f"{key[0]}:{key[1]}:{key[2]}"


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]


def average(values: list[float]) -> float | None:
    values = [v for v in values if v == v]
    return sum(values) / len(values) if values else None


def load_segment_index(window_size: int, total_samples: int, seed: int) -> dict[tuple[str, int, int], dict[str, Any]]:
    try:
        recordings, supervisions = load_manifests()
        segments = generate_stratified_segments(
            recordings,
            supervisions,
            window_size=window_size,
            total_samples=total_samples,
            seed=seed,
        )
        return {(seg["recording_id"], int(seg["window_size"]), int(seg["segment_idx"])): seg for seg in segments}
    except Exception:
        return {}


def with_global_times(
    segments: list[dict[str, Any]],
    key: tuple[str, int, int],
    offset: float,
    source: str,
) -> list[dict[str, Any]]:
    out = []
    for idx, seg in enumerate(segments):
        start = round(offset + as_float(seg.get("start")), 4)
        end = round(offset + as_float(seg.get("end")), 4)
        if end <= start:
            continue
        out.append(
            {
                "recording_id": key[0],
                "window_size": key[1],
                "segment_idx": key[2],
                "window_id": window_id(key),
                "segment_id": f"{source}_{idx}",
                "source": source,
                "start": start,
                "end": end,
                "speaker": str(seg.get("speaker", "unknown")),
                "local_start": round(as_float(seg.get("start")), 4),
                "local_end": round(as_float(seg.get("end")), 4),
            }
        )
    return out


def clip_segments_to_window(
    segments: list[dict[str, Any]],
    window_size: float,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    clipped_segments = []
    counters: Counter[str] = Counter()
    for seg in segments:
        start = as_float(seg.get("start"))
        end = as_float(seg.get("end"))
        clipped_start = min(max(start, 0.0), window_size)
        clipped_end = min(max(end, 0.0), window_size)
        if clipped_end <= clipped_start:
            counters["window_clip_dropped_segments"] += 1
            continue
        if abs(clipped_start - start) > 1e-9 or abs(clipped_end - end) > 1e-9:
            counters["window_clip_adjusted_segments"] += 1
            counters["window_clip_trimmed_ms"] += int(round(((end - start) - (clipped_end - clipped_start)) * 1000))
        new_seg = dict(seg)
        new_seg["start"] = round(clipped_start, 4)
        new_seg["end"] = round(clipped_end, 4)
        clipped_segments.append(new_seg)
    return clipped_segments, dict(counters)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def timeline_rows_to_rttm_string(rows: list[dict[str, Any]], fallback_session_id: str) -> str:
    lines = []
    for row in rows:
        dur = as_float(row["end"]) - as_float(row["start"])
        if dur <= 0:
            continue
        session_id = str(row.get("recording_id") or fallback_session_id)
        lines.append(
            f"SPEAKER {session_id} 1 {as_float(row['start']):.3f} {dur:.3f} "
            f"<NA> <NA> {row['speaker']} <NA> <NA>"
        )
    return "\n".join(lines)


def write_timeline_files(output_dir: Path, stem: str, rows: list[dict[str, Any]], session_id: str) -> None:
    write_json(output_dir / f"{stem}_timeline.json", rows)
    write_csv(
        output_dir / f"{stem}_timeline.csv",
        rows,
        [
            "recording_id",
            "window_size",
            "segment_idx",
            "window_id",
            "segment_id",
            "source",
            "start",
            "end",
            "speaker",
            "local_start",
            "local_end",
        ],
    )
    (output_dir / f"{stem}_timeline.rttm").write_text(
        timeline_rows_to_rttm_string(rows, session_id) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def score_window(
    key: tuple[str, int, int],
    label: str,
    pred_segments: list[dict[str, Any]],
    gt_segments: list[dict[str, Any]],
    collar: float,
) -> dict[str, Any]:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        metrics = calc_der(gt_segments, pred_segments, f"{key[0]}_ws{key[1]}_seg{key[2]}_{label}", collar=collar)
    row = {
        "window_id": window_id(key),
        "recording_id": key[0],
        "window_size": key[1],
        "segment_idx": key[2],
        "variant": label,
        "success": metrics is not None,
        "der": None,
        "miss_rate": None,
        "fa_rate": None,
        "conf_rate": None,
        "scored_time": None,
        "pred_segments": len(pred_segments),
    }
    if metrics:
        row.update(metrics)
    return row


def load_precomputed_scores(path: Path) -> dict[tuple[tuple[str, int, int], str], dict[str, Any]]:
    if not path.exists():
        return {}
    scores = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (str(row["recording_id"]), int(float(row["window_size"])), int(float(row["segment_idx"])))
            variant = str(row["variant"])
            scores[(key, variant)] = {
                "window_id": window_id(key),
                "recording_id": key[0],
                "window_size": key[1],
                "segment_idx": key[2],
                "variant": variant,
                "success": str(row.get("success", "")).lower() == "true",
                "der": as_float(row.get("der"), default=float("nan")),
                "miss_rate": as_float(row.get("miss_rate"), default=float("nan")),
                "fa_rate": as_float(row.get("fa_rate"), default=float("nan")),
                "conf_rate": as_float(row.get("conf_rate"), default=float("nan")),
                "scored_time": as_float(row.get("scored_time"), default=float("nan")),
                "pred_segments": int(as_float(row.get("pred_segments"), default=0)),
            }
    return scores


def load_audio_features(path: Path) -> dict[tuple[str, int, int], dict[str, float]]:
    if not path.exists():
        return {}
    out = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = result_key(row)
            out[key] = {
                name: as_float(value)
                for name, value in row.items()
                if name.startswith("audio_") and name not in {"audio_path", "audio_exists"}
            }
    return out


def load_window_features(path: Path) -> dict[tuple[str, int, int], dict[str, float]]:
    if not path.exists():
        return {}
    out = {}
    feature_names = {
        "fast_spk_count_pred",
        "slow_spk_count_pred",
        "fast_segments",
        "slow_segments",
        "fast_speech",
        "slow_speech",
        "fast_slow_disagreement_sec",
        "keep_fast_supported",
        "boundary_fix_or_relabel",
        "suppress_fast_candidate",
        "recover_slow_segment",
        "align_slow_segment",
    }
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = result_key(row)
            out[key] = {name: as_float(row.get(name)) for name in feature_names if name in row}
    return out


def build_context_features(
    keys: list[tuple[str, int, int]],
    audio_features_by_key: dict[tuple[str, int, int], dict[str, float]],
    window_features_by_key: dict[tuple[str, int, int], dict[str, float]],
) -> dict[tuple[str, int, int], dict[str, float]]:
    base_by_key = {}
    for key in keys:
        row = {}
        row.update(window_features_by_key.get(key, {}))
        row.update(audio_features_by_key.get(key, {}))
        base_by_key[key] = row

    by_recording_idx = {(key[0], key[2]): key for key in keys}
    out = {}
    for key in keys:
        row = dict(base_by_key.get(key, {}))
        prev_key = by_recording_idx.get((key[0], key[2] - 1))
        row["has_prev_window"] = 1.0 if prev_key is not None else 0.0
        if prev_key is not None:
            for name, value in base_by_key.get(prev_key, {}).items():
                row[f"prev_{name}"] = value
        out[key] = row
    return out


def aggregate_metric(rows: list[dict[str, Any]], field: str) -> float | None:
    return average([as_float(row.get(field), default=float("nan")) for row in rows if row.get(field) is not None])


def summarize_window_rows_by_recording(window_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in window_rows:
        grouped[str(row["recording_id"])].append(row)

    out = []
    for recording_id, rows in sorted(grouped.items()):
        fast_der = average([as_float(row.get("fast_der"), default=float("nan")) for row in rows])
        final_der = average([as_float(row.get("final_der"), default=float("nan")) for row in rows])
        fast_latencies = [as_float(row.get("fast_latency")) for row in rows]
        slow_latencies = [as_float(row.get("slow_latency")) for row in rows]
        out.append(
            {
                "recording_id": recording_id,
                "windows": len(rows),
                "fast_der": fast_der,
                "final_der": final_der,
                "der_delta_vs_fast_pp": (fast_der - final_der) * 100 if fast_der is not None and final_der is not None else None,
                "first_output_latency_proxy_avg_sec": average(fast_latencies) or 0.0,
                "first_output_latency_proxy_p95_sec": percentile(fast_latencies, 0.95),
                "rule_writeback_latency_proxy_avg_sec": average(slow_latencies) or 0.0,
                "rule_writeback_latency_proxy_p95_sec": percentile(slow_latencies, 0.95),
            }
        )
    return out


def summarize_precomputed_variant(
    keys: list[tuple[str, int, int]],
    precomputed_scores: dict[tuple[tuple[str, int, int], str], dict[str, Any]],
    variant: str,
) -> dict[str, Any] | None:
    rows = [precomputed_scores[(key, variant)] for key in keys if (key, variant) in precomputed_scores]
    if not rows:
        return None
    return {
        "baseline_id": variant,
        "windows": len(rows),
        "der": aggregate_metric(rows, "der"),
        "miss_rate": aggregate_metric(rows, "miss_rate"),
        "fa_rate": aggregate_metric(rows, "fa_rate"),
        "conf_rate": aggregate_metric(rows, "conf_rate"),
    }


def source_artifact_status(paths: dict[str, Path]) -> dict[str, bool]:
    return {name: path.exists() for name, path in paths.items()}


def read_selector_validation(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "status": "missing_selector_validation",
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    fixed = data.get("fixed_policy", {})
    bootstrap = data.get("bootstrap", {})
    holdout = data.get("recording_holdout_summary", {})
    return {
        "path": str(path),
        "exists": True,
        "status": data.get("status"),
        "metric_claim_boundary": data.get("metric_claim_boundary"),
        "fixed_delta_vs_slow_pp": fixed.get("delta_vs_slow_pp"),
        "fixed_beats_slow": fixed.get("beats_slow"),
        "bootstrap_prob_beats_slow": bootstrap.get("prob_beats_slow"),
        "bootstrap_delta_ci_low": bootstrap.get("delta_ci_low"),
        "bootstrap_delta_ci_high": bootstrap.get("delta_ci_high"),
        "holdout_positive_splits_vs_slow": holdout.get("positive_splits_vs_slow"),
        "holdout_splits": holdout.get("splits"),
    }


def read_selector_search(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "status": "missing_selector_policy_search",
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    best = data.get("best_full_policy", {})
    holdout = data.get("holdout_summary", {})
    return {
        "path": str(path),
        "exists": True,
        "status": data.get("status"),
        "best_policy_id": best.get("policy_id"),
        "best_final_der": best.get("final_der"),
        "best_delta_vs_slow_pp": best.get("delta_vs_slow_pp"),
        "holdout_positive_splits_vs_slow": holdout.get("positive_splits_vs_slow"),
        "holdout_splits": holdout.get("splits"),
        "holdout_weighted_delta_vs_slow_pp": holdout.get("weighted_delta_vs_slow_pp"),
        "metric_claim_boundary": data.get("metric_claim_boundary"),
    }


def read_slow_sanitization_search(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "status": "missing_slow_sanitization_search",
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    best = data.get("best_policy", {})
    slow = data.get("slow_baseline", {})
    bootstrap = data.get("bootstrap", {})
    holdout = data.get("holdout_summary", {})
    return {
        "path": str(path),
        "exists": True,
        "status": data.get("status"),
        "policy_set": data.get("policy_set"),
        "candidate_policies": data.get("candidate_policies"),
        "best_policy_id": best.get("policy_id"),
        "best_der": best.get("avg_der"),
        "slow_der": slow.get("avg_der"),
        "best_delta_vs_slow_pp": data.get("best_delta_vs_slow_pp"),
        "bootstrap_prob_beats_slow": bootstrap.get("prob_beats_slow"),
        "bootstrap_delta_ci_low": bootstrap.get("delta_ci_low"),
        "bootstrap_delta_ci_high": bootstrap.get("delta_ci_high"),
        "holdout_positive_splits_vs_slow": holdout.get("positive_splits_vs_slow"),
        "holdout_splits": holdout.get("splits"),
        "holdout_weighted_delta_vs_slow_pp": holdout.get("weighted_delta_vs_slow_pp"),
        "metric_claim_boundary": data.get("metric_claim_boundary"),
    }


def build_correction_rows(
    key: tuple[str, int, int],
    rows_by_patch: dict[str, dict[str, str]],
    variant: str,
    final_source: str,
) -> list[dict[str, Any]]:
    rows = []
    for pid, row in sorted(rows_by_patch.items()):
        category = row.get("gate_category", "")
        patch_type = row.get("patch_type", "")
        if category == "guard_or_quarantine":
            action = "blocked_by_runtime_safe_guard"
        elif category == "rule_recover_writeback" and patch_type == "recover_slow_segment":
            action = "accepted_writeback"
        elif category in WRITEBACK_CATEGORIES:
            action = "accepted_by_gate_not_applied_by_conservative_variant"
        else:
            action = "blocked_or_deferred"
        rows.append(
            {
                "window_id": window_id(key),
                "patch_id": pid,
                "recording_id": key[0],
                "window_size": key[1],
                "segment_idx": key[2],
                "patch_type": patch_type,
                "gate_category": category,
                "action": action,
                "variant": variant,
                "final_source": final_source,
                "duration": row.get("duration", ""),
                "support_ratio": row.get("support_ratio", ""),
                "gate_blockers": row.get("gate_blockers", ""),
                "abnormal_flags": row.get("abnormal_flags", ""),
                "decision": row.get("decision", ""),
                "reason": row.get("reason", ""),
            }
        )
    return rows


def materialize_system_variant(
    variant: str,
    key: tuple[str, int, int],
    fast: dict[str, Any],
    slow: dict[str, Any],
    gate_by_patch: dict[str, dict[str, str]],
    patch_eval_by_id: dict[str, dict[str, str]],
    audio_features: dict[str, float],
    window_features: dict[str, float],
    external_candidate: dict[str, Any] | None,
    guard_quarantine_threshold: int,
    rare_audio_speech_sec_threshold: float,
    rare_slow_segments_max: int,
    balanced_align_slow_segment_min: int,
    balanced_keep_fast_supported_min: int,
    context_audio_p50_db_min: float,
    context_prev_audio_dynamic_range_db_max: float,
    external_fast_audio_speech_ratio_max: float,
    external_fast_speech_max: float,
) -> tuple[list[dict[str, Any]], dict[str, int], str]:
    if variant in {
        "slow_guarded_fast_fallback",
        "slow_guarded_fast_fallback_speaker_count_safe",
        "slow_guarded_fast_fallback_rare_audio_rule_recover",
        "slow_guarded_fast_fallback_rare_audio_rule_recover_external_diarizen_overlay",
    }:
        guard_count = sum(1 for row in gate_by_patch.values() if row.get("gate_category") == "guard_or_quarantine")
        fast_speaker_count = len({str(seg.get("speaker")) for seg in fast.get("pred_segments", [])})
        slow_speaker_count = len({str(seg.get("speaker")) for seg in slow.get("pred_segments", [])})

        if variant in {
            "slow_guarded_fast_fallback_rare_audio_rule_recover",
            "slow_guarded_fast_fallback_rare_audio_rule_recover_external_diarizen_overlay",
        }:
            audio_speech_sec = audio_features.get("audio_speech_sec")
            fast_speech = window_features.get("fast_speech")
            fast_audio_speech_ratio = (
                fast_speech / audio_speech_sec
                if fast_speech is not None and audio_speech_sec
                else 999.0
            )
            if (
                variant == "slow_guarded_fast_fallback_rare_audio_rule_recover_external_diarizen_overlay"
                and external_candidate is not None
                and fast_speech is not None
                and fast_audio_speech_ratio <= external_fast_audio_speech_ratio_max
                and fast_speech <= external_fast_speech_max
            ):
                return (
                    [dict(seg) for seg in external_candidate.get("pred_segments", [])],
                    {
                        "external_diarizen_overlay_windows": 1,
                        "external_fast_audio_speech_ratio_x100000": int(round(fast_audio_speech_ratio * 100000)),
                        "external_fast_speech_x100": int(round(fast_speech * 100)),
                        "rare_audio_rule_recover_windows": 0,
                        "rare_short_slow_rule_recover_windows": 0,
                        "recording_balanced_fast_overlay_windows": 0,
                        "recording_context_fast_overlay_windows": 0,
                        "slow_windows_selected": 0,
                        "fast_guard_fallback_windows": 0,
                        "guard_or_quarantine_patches": guard_count,
                        "fallback_blocked_by_speaker_count": 0,
                        "fast_speaker_count": fast_speaker_count,
                        "slow_speaker_count": slow_speaker_count,
                    },
                    "external_diarizen_overlay",
                )

            audio_speech_sec = audio_features.get("audio_speech_sec")
            if (
                audio_speech_sec is not None
                and audio_speech_sec >= rare_audio_speech_sec_threshold
                and guard_count < guard_quarantine_threshold
            ):
                final_segments, counters = materialize_variant(
                    "rule_recover_uncovered_only",
                    key,
                    fast,
                    slow,
                    gate_by_patch,
                    patch_eval_by_id,
                )
                counters.update(
                    {
                        "rare_audio_rule_recover_windows": 1,
                        "rare_audio_speech_sec_x100": int(round(audio_speech_sec * 100)),
                        "slow_windows_selected": 0,
                        "fast_guard_fallback_windows": 0,
                        "guard_or_quarantine_patches": guard_count,
                        "fallback_blocked_by_speaker_count": 0,
                        "fast_speaker_count": fast_speaker_count,
                        "slow_speaker_count": slow_speaker_count,
                    }
                )
                return final_segments, counters, "rare_audio_rule_recover"
            if len(slow.get("pred_segments", [])) <= rare_slow_segments_max and guard_count < guard_quarantine_threshold:
                final_segments, counters = materialize_variant(
                    "rule_recover_uncovered_only",
                    key,
                    fast,
                    slow,
                    gate_by_patch,
                    patch_eval_by_id,
                )
                counters.update(
                    {
                        "rare_audio_rule_recover_windows": 0,
                        "rare_short_slow_rule_recover_windows": 1,
                        "slow_windows_selected": 0,
                        "fast_guard_fallback_windows": 0,
                        "guard_or_quarantine_patches": guard_count,
                        "fallback_blocked_by_speaker_count": 0,
                        "fast_speaker_count": fast_speaker_count,
                        "slow_speaker_count": slow_speaker_count,
                    }
                )
                return final_segments, counters, "rare_short_slow_rule_recover"
            if (
                guard_count < guard_quarantine_threshold
                and fast_speaker_count >= slow_speaker_count
                and window_features.get("align_slow_segment", 0.0) >= balanced_align_slow_segment_min
                and window_features.get("keep_fast_supported", 0.0) >= balanced_keep_fast_supported_min
            ):
                return (
                    [dict(seg) for seg in fast.get("pred_segments", [])],
                    {
                        "rare_audio_rule_recover_windows": 0,
                        "rare_short_slow_rule_recover_windows": 0,
                        "recording_balanced_fast_overlay_windows": 1,
                        "slow_windows_selected": 0,
                        "fast_guard_fallback_windows": 0,
                        "guard_or_quarantine_patches": guard_count,
                        "fallback_blocked_by_speaker_count": 0,
                        "fast_speaker_count": fast_speaker_count,
                        "slow_speaker_count": slow_speaker_count,
                    },
                    "recording_balanced_fast_overlay",
                )

            if (
                guard_count < guard_quarantine_threshold
                and window_features.get("has_prev_window", 0.0) >= 1.0
                and window_features.get("audio_p50_db", -999.0) >= context_audio_p50_db_min
                and window_features.get("prev_audio_dynamic_range_db", 999.0)
                <= context_prev_audio_dynamic_range_db_max
            ):
                return (
                    [dict(seg) for seg in fast.get("pred_segments", [])],
                    {
                        "rare_audio_rule_recover_windows": 0,
                        "rare_short_slow_rule_recover_windows": 0,
                        "recording_balanced_fast_overlay_windows": 0,
                        "recording_context_fast_overlay_windows": 1,
                        "slow_windows_selected": 0,
                        "fast_guard_fallback_windows": 0,
                        "guard_or_quarantine_patches": guard_count,
                        "fallback_blocked_by_speaker_count": 0,
                        "fast_speaker_count": fast_speaker_count,
                        "slow_speaker_count": slow_speaker_count,
                    },
                    "recording_context_fast_overlay",
                )

        if guard_count >= guard_quarantine_threshold:
            if variant in {
                "slow_guarded_fast_fallback_speaker_count_safe",
                "slow_guarded_fast_fallback_rare_audio_rule_recover",
            } and fast_speaker_count < slow_speaker_count:
                return (
                    [dict(seg) for seg in slow.get("pred_segments", [])],
                    {
                        "rare_audio_rule_recover_windows": 0,
                        "rare_short_slow_rule_recover_windows": 0,
                        "slow_windows_selected": 1,
                        "fast_guard_fallback_windows": 0,
                        "guard_or_quarantine_patches": guard_count,
                        "fallback_blocked_by_speaker_count": 1,
                        "fast_speaker_count": fast_speaker_count,
                        "slow_speaker_count": slow_speaker_count,
                    },
                    "slow",
                )
            return (
                [dict(seg) for seg in fast.get("pred_segments", [])],
                {
                    "rare_audio_rule_recover_windows": 0,
                    "rare_short_slow_rule_recover_windows": 0,
                    "slow_windows_selected": 0,
                    "fast_guard_fallback_windows": 1,
                    "guard_or_quarantine_patches": guard_count,
                    "fallback_blocked_by_speaker_count": 0,
                    "fast_speaker_count": fast_speaker_count,
                    "slow_speaker_count": slow_speaker_count,
                },
                "fast_guard_fallback",
            )
        return (
            [dict(seg) for seg in slow.get("pred_segments", [])],
            {
                "rare_audio_rule_recover_windows": 0,
                "rare_short_slow_rule_recover_windows": 0,
                "slow_windows_selected": 1,
                "fast_guard_fallback_windows": 0,
                "guard_or_quarantine_patches": guard_count,
                "fallback_blocked_by_speaker_count": 0,
                "fast_speaker_count": fast_speaker_count,
                "slow_speaker_count": slow_speaker_count,
            },
            "slow",
        )

    final_segments, counters = materialize_variant(
        variant,
        key,
        fast,
        slow,
        gate_by_patch,
        patch_eval_by_id,
    )
    counters["slow_windows_selected"] = 0
    counters["fast_guard_fallback_windows"] = 0
    return final_segments, counters, "rule_writeback"


def selected_keys(
    fast_by_key: dict[tuple[str, int, int], dict[str, Any]],
    slow_by_key: dict[tuple[str, int, int], dict[str, Any]],
    recording_id: str | None,
    window_size: int | None,
    segment_idx: int | None,
) -> list[tuple[str, int, int]]:
    keys = sorted(set(fast_by_key) & set(slow_by_key))
    if recording_id:
        keys = [key for key in keys if key[0] == recording_id]
    if window_size is not None:
        keys = [key for key in keys if key[1] == window_size]
    if segment_idx is not None:
        keys = [key for key in keys if key[2] == segment_idx]
    return keys


def write_metrics_md(path: Path, metrics: dict[str, Any]) -> None:
    m = metrics["metrics"]
    baseline_win_summary = metrics.get("baseline_win_summary", {})
    lines = [
        "# Realtime Diarization System Metrics",
        "",
        f"- Execution mode: `{metrics['execution_mode']}`",
        f"- Run scope: `{metrics['run_scope']}`",
        f"- Evaluation status: `{metrics['evaluation_status']}`",
        f"- Selector validation status: `{metrics.get('selector_validation', {}).get('status', 'missing')}`",
        f"- Recording: `{metrics['recording_id']}`",
        f"- Recordings processed: `{metrics['recordings_processed']}`",
        f"- Windows processed: `{metrics['windows_processed']}`",
        f"- Cached window coverage: `{metrics['windows_processed']}/{metrics['cached_windows_available']}` (`{metrics['cached_window_coverage']:.1%}`)",
        f"- API calls: DeepSeek `{m['deepseek_api_calls']}`, Qwen `{m['qwen_api_calls']}`, Omni `{m['omni_api_calls']}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Fast DER | {m['fast_der']:.2%} |" if m["fast_der"] is not None else "| Fast DER | n/a |",
        f"| Final DER | {m['final_der']:.2%} |" if m["final_der"] is not None else "| Final DER | n/a |",
        f"| DER delta vs fast | {m['der_delta_vs_fast_pp']:.2f} pp |" if m["der_delta_vs_fast_pp"] is not None else "| DER delta vs fast | n/a |",
        f"| Best baseline | {metrics['best_baseline']['baseline_id']} / {metrics['best_baseline']['der']:.2%} |" if metrics.get("best_baseline") else "| Best baseline | n/a |",
        f"| DER delta vs best baseline | {m['der_delta_vs_best_baseline_pp']:.2f} pp |" if m.get("der_delta_vs_best_baseline_pp") is not None else "| DER delta vs best baseline | n/a |",
        f"| Beats best baseline | {m.get('beats_best_baseline')} |",
        f"| Beats all baselines | {baseline_win_summary.get('beats_all_baselines')} ({baseline_win_summary.get('beaten_baselines')}/{baseline_win_summary.get('baseline_count')}) |",
        f"| Final Miss | {m['final_miss_rate']:.2%} |" if m["final_miss_rate"] is not None else "| Final Miss | n/a |",
        f"| Final FA | {m['final_fa_rate']:.2%} |" if m["final_fa_rate"] is not None else "| Final FA | n/a |",
        f"| Final Confusion | {m['final_conf_rate']:.2%} |" if m["final_conf_rate"] is not None else "| Final Confusion | n/a |",
        f"| Correction rows | {m['correction_count']} |",
        f"| Accepted writebacks | {m['accepted_correction_count']} |",
        f"| Accepted window corrections | {m.get('accepted_window_correction_count', 0)} |",
        f"| Guard fallback windows | {m.get('guard_fallback_window_count', 0)} |",
        f"| Blocked/deferred/quarantined | {m['blocked_or_quarantined_correction_count']} |",
        f"| First output latency proxy avg / P95 | {m['first_output_latency_proxy_avg_sec']:.3f}s / {m['first_output_latency_proxy_p95_sec']:.3f}s |",
        f"| Rule writeback latency proxy avg / P95 | {m['rule_writeback_latency_proxy_avg_sec']:.3f}s / {m['rule_writeback_latency_proxy_p95_sec']:.3f}s |",
        f"| Processed audio seconds | {m.get('processed_audio_sec', 0.0):.1f}s |",
        f"| Total CLI wall time | {m['total_processing_wall_time_sec']:.3f}s |",
        f"| Offline replay RTF | {m.get('offline_replay_rtf', 0.0):.6f} |",
        "",
        "## Reading",
        "",
        "- DER/Miss/FA/Conf are scored only when cached AliMeeting reference segments are available.",
        "- Latency values are proxies from existing model runs, not fresh online inference timings.",
        "- Offline replay RTF is CLI wall time divided by processed cached-window audio seconds.",
        "- The final timeline uses conservative rule recover writeback; guard/quarantine rows do not enter the timeline.",
        "- This run performs zero live LLM/API calls.",
    ]
    validation = metrics.get("selector_validation", {})
    if validation:
        lines.extend(
            [
                "",
                "## Selector Validation",
                "",
                "| Check | Value |",
                "|---|---:|",
                f"| Status | {validation.get('status')} |",
                f"| Boundary | {validation.get('metric_claim_boundary')} |",
                f"| Fixed delta vs slow | {as_float(validation.get('fixed_delta_vs_slow_pp')):.2f} pp |",
                f"| Bootstrap P(beats slow) | {as_float(validation.get('bootstrap_prob_beats_slow')):.1%} |",
                f"| Bootstrap delta CI low/high | {as_float(validation.get('bootstrap_delta_ci_low')) * 100:.2f} pp / {as_float(validation.get('bootstrap_delta_ci_high')) * 100:.2f} pp |",
                f"| Holdout positive splits | {validation.get('holdout_positive_splits_vs_slow')}/{validation.get('holdout_splits')} |",
            ]
        )
    search = metrics.get("selector_policy_search", {})
    if search:
        lines.extend(
            [
                "",
                "## Selector Policy Search",
                "",
                "| Check | Value |",
                "|---|---:|",
                f"| Status | {search.get('status')} |",
                f"| Best policy | {search.get('best_policy_id')} |",
                f"| Best delta vs slow | {as_float(search.get('best_delta_vs_slow_pp')):.2f} pp |",
                f"| Holdout weighted delta vs slow | {as_float(search.get('holdout_weighted_delta_vs_slow_pp')):.2f} pp |",
                f"| Holdout positive splits | {search.get('holdout_positive_splits_vs_slow')}/{search.get('holdout_splits')} |",
            ]
        )
    sanitizer = metrics.get("slow_sanitization_search", {})
    if sanitizer:
        lines.extend(
            [
                "",
                "## Slow Sanitization Search",
                "",
                "| Check | Value |",
                "|---|---:|",
                f"| Status | {sanitizer.get('status')} |",
                f"| Policy set / candidates | {sanitizer.get('policy_set')} / {sanitizer.get('candidate_policies')} |",
                f"| Best policy | {sanitizer.get('best_policy_id')} |",
                f"| Best delta vs slow | {as_float(sanitizer.get('best_delta_vs_slow_pp')):.2f} pp |",
                f"| Bootstrap P(beats slow) | {as_float(sanitizer.get('bootstrap_prob_beats_slow')):.1%} |",
                f"| Holdout weighted delta vs slow | {as_float(sanitizer.get('holdout_weighted_delta_vs_slow_pp')):.2f} pp |",
                f"| Holdout positive splits | {sanitizer.get('holdout_positive_splits_vs_slow')}/{sanitizer.get('holdout_splits')} |",
            ]
        )
    if metrics.get("recording_metrics"):
        lines.extend(
            [
                "",
                "## Recording Summary",
                "",
                "| Recording | Windows | Fast DER | Final DER | Delta |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in metrics["recording_metrics"]:
            fast_der = row["fast_der"]
            final_der = row["final_der"]
            delta = row["der_delta_vs_fast_pp"]
            lines.append(
                "| {recording_id} | {windows} | {fast} | {final} | {delta} |".format(
                    recording_id=row["recording_id"],
                    windows=row["windows"],
                    fast=f"{fast_der:.2%}" if fast_der is not None else "n/a",
                    final=f"{final_der:.2%}" if final_der is not None else "n/a",
                    delta=f"{delta:.2f} pp" if delta is not None else "n/a",
                )
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, default=None, help="Meeting audio path. Basename can carry Rxxxx_Mxxxx.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--all-cached-recordings", action="store_true", help="Run every cached Fast/Slow window instead of one inferred recording.")
    parser.add_argument("--recording-id", default=None, help="Override inferred AliMeeting recording id.")
    parser.add_argument("--window-size", type=int, default=30)
    parser.add_argument("--segment-idx", type=int, default=None, help="Optional single cached segment index. Default: all cached windows for recording.")
    parser.add_argument("--fast-summary", type=Path, default=DEFAULT_FAST_SUMMARY)
    parser.add_argument("--slow-summary", type=Path, default=DEFAULT_SLOW_SUMMARY)
    parser.add_argument("--gate-decisions", type=Path, default=DEFAULT_GATE_DECISIONS)
    parser.add_argument("--patches", type=Path, default=DEFAULT_PATCHES)
    parser.add_argument("--guard-summary", type=Path, default=DEFAULT_GUARD_SUMMARY)
    parser.add_argument("--timeline-results", type=Path, default=DEFAULT_TIMELINE_RESULTS)
    parser.add_argument("--audio-features", type=Path, default=DEFAULT_AUDIO_FEATURES)
    parser.add_argument("--window-features", type=Path, default=DEFAULT_WINDOW_FEATURES)
    parser.add_argument("--external-candidate-summary", type=Path, default=DEFAULT_EXTERNAL_CANDIDATE_SUMMARY)
    parser.add_argument("--selector-validation", type=Path, default=DEFAULT_SELECTOR_VALIDATION)
    parser.add_argument("--selector-search", type=Path, default=DEFAULT_SELECTOR_SEARCH)
    parser.add_argument("--slow-sanitization-search", type=Path, default=DEFAULT_SLOW_SANITIZATION_SEARCH)
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    parser.add_argument("--guard-quarantine-threshold", type=int, default=DEFAULT_GUARD_QUARANTINE_THRESHOLD)
    parser.add_argument("--rare-audio-speech-sec-threshold", type=float, default=DEFAULT_RARE_AUDIO_SPEECH_SEC_THRESHOLD)
    parser.add_argument("--rare-slow-segments-max", type=int, default=DEFAULT_RARE_SLOW_SEGMENTS_MAX)
    parser.add_argument("--balanced-align-slow-segment-min", type=int, default=DEFAULT_BALANCED_ALIGN_SLOW_SEGMENT_MIN)
    parser.add_argument("--balanced-keep-fast-supported-min", type=int, default=DEFAULT_BALANCED_KEEP_FAST_SUPPORTED_MIN)
    parser.add_argument("--context-audio-p50-db-min", type=float, default=DEFAULT_CONTEXT_AUDIO_P50_DB_MIN)
    parser.add_argument(
        "--context-prev-audio-dynamic-range-db-max",
        type=float,
        default=DEFAULT_CONTEXT_PREV_AUDIO_DYNAMIC_RANGE_DB_MAX,
    )
    parser.add_argument("--external-fast-audio-speech-ratio-max", type=float, default=DEFAULT_EXTERNAL_FAST_AUDIO_SPEECH_RATIO_MAX)
    parser.add_argument("--external-fast-speech-max", type=float, default=DEFAULT_EXTERNAL_FAST_SPEECH_MAX)
    parser.add_argument("--collar", type=float, default=0.0)
    parser.add_argument("--total-samples", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.all_cached_recordings and args.audio is None and not args.recording_id:
        parser.error("--audio or --recording-id is required unless --all-cached-recordings is set")

    started = time.time()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    recording_id = args.recording_id or (infer_recording_id(args.audio) if args.audio else None)
    fast_data, fast_by_key = load_summary(args.fast_summary)
    slow_data, slow_by_key = load_summary(args.slow_summary)
    external_candidate_data, external_candidate_by_key = load_summary(args.external_candidate_summary) if args.external_candidate_summary.exists() else ({}, {})
    gate_by_window = grouped_gate_rows(load_csv(args.gate_decisions))
    patch_eval_by_id = {patch_id(row): row for row in load_csv(args.patches)}
    precomputed_scores = load_precomputed_scores(args.timeline_results)
    audio_features_by_key = load_audio_features(args.audio_features)
    window_features_by_key = load_window_features(args.window_features)
    segment_index = load_segment_index(args.window_size, args.total_samples, args.seed)

    available_keys = selected_keys(fast_by_key, slow_by_key, None, args.window_size, None)
    context_features_by_key = build_context_features(available_keys, audio_features_by_key, window_features_by_key)
    if args.all_cached_recordings:
        keys = selected_keys(fast_by_key, slow_by_key, None, args.window_size, args.segment_idx)
    else:
        keys = (
            selected_keys(fast_by_key, slow_by_key, recording_id, args.window_size, args.segment_idx)
            if recording_id
            else []
        )

    guard_summary = {}
    if args.guard_summary.exists():
        guard_summary = json.loads(args.guard_summary.read_text(encoding="utf-8"))
    selector_validation = read_selector_validation(args.selector_validation)
    selector_search = read_selector_search(args.selector_search)
    slow_sanitization_search = read_slow_sanitization_search(args.slow_sanitization_search)

    fast_timeline: list[dict[str, Any]] = []
    slow_timeline: list[dict[str, Any]] = []
    final_timeline: list[dict[str, Any]] = []
    correction_rows: list[dict[str, Any]] = []
    fast_scores: list[dict[str, Any]] = []
    final_scores: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    counter_totals: Counter[str] = Counter()

    for key in keys:
        fast = fast_by_key[key]
        slow = slow_by_key[key]
        seg_meta = segment_index.get(key, {})
        offset = as_float(seg_meta.get("offset"), default=float(key[2] * key[1]))

        gate_rows = gate_by_window.get(key, {})
        final_segments, counters, final_source = materialize_system_variant(
            args.variant,
            key,
            fast,
            slow,
            gate_rows,
            patch_eval_by_id,
            audio_features_by_key.get(key, {}),
            context_features_by_key.get(key, {}),
            external_candidate_by_key.get(key),
            args.guard_quarantine_threshold,
            args.rare_audio_speech_sec_threshold,
            args.rare_slow_segments_max,
            args.balanced_align_slow_segment_min,
            args.balanced_keep_fast_supported_min,
            args.context_audio_p50_db_min,
            args.context_prev_audio_dynamic_range_db_max,
            args.external_fast_audio_speech_ratio_max,
            args.external_fast_speech_max,
        )
        final_segments, clip_counters = clip_segments_to_window(final_segments, args.window_size)
        counters.update(clip_counters)
        counter_totals.update(counters)

        gt_segments = fast.get("gt_segments", [])
        fast_score = precomputed_scores.get((key, "fast_base")) or score_window(
            key, "fast_base", fast.get("pred_segments", []), gt_segments, args.collar
        )
        final_score = score_window(key, args.variant, final_segments, gt_segments, args.collar)
        fast_scores.append(fast_score)
        final_scores.append(final_score)

        fast_timeline.extend(with_global_times(fast.get("pred_segments", []), key, offset, "fast"))
        slow_timeline.extend(with_global_times(slow.get("pred_segments", []), key, offset, "slow"))
        final_timeline.extend(with_global_times(final_segments, key, offset, "final"))
        correction_rows.extend(build_correction_rows(key, gate_rows, args.variant, final_source))

        window_rows.append(
            {
                "window_id": window_id(key),
                "recording_id": key[0],
                "window_size": key[1],
                "segment_idx": key[2],
                "offset": offset,
                "fast_der": fast_score.get("der"),
                "final_der": final_score.get("der"),
                "fast_latency": fast.get("latency"),
                "slow_latency": slow.get("latency"),
                "final_source": final_source,
                "final_segments": len(final_segments),
                **{f"counter_{name}": value for name, value in counters.items()},
            }
        )

    fast_timeline.sort(key=lambda row: (row["start"], row["end"], row["speaker"]))
    slow_timeline.sort(key=lambda row: (row["start"], row["end"], row["speaker"]))
    final_timeline.sort(key=lambda row: (row["start"], row["end"], row["speaker"]))

    session_id = recording_id or ("all_cached_recordings" if args.all_cached_recordings else "unknown_recording")
    write_timeline_files(args.output_dir, "fast", fast_timeline, session_id)
    write_timeline_files(args.output_dir, "slow", slow_timeline, session_id)
    write_timeline_files(args.output_dir, "final", final_timeline, session_id)
    write_json(args.output_dir / "correction_log.json", correction_rows)
    write_csv(
        args.output_dir / "correction_log.csv",
        correction_rows,
        [
            "window_id",
            "patch_id",
            "recording_id",
            "window_size",
            "segment_idx",
            "patch_type",
            "gate_category",
            "action",
            "variant",
            "final_source",
            "duration",
            "support_ratio",
            "gate_blockers",
            "abnormal_flags",
            "decision",
            "reason",
        ],
    )
    write_json(args.output_dir / "window_metrics.json", window_rows)
    write_csv(
        args.output_dir / "window_metrics.csv",
        window_rows,
        sorted({key for row in window_rows for key in row.keys()}),
    )
    recording_metrics = summarize_window_rows_by_recording(window_rows)
    write_json(args.output_dir / "recording_metrics.json", recording_metrics)
    write_csv(
        args.output_dir / "recording_metrics.csv",
        recording_metrics,
        [
            "recording_id",
            "windows",
            "fast_der",
            "final_der",
            "der_delta_vs_fast_pp",
            "first_output_latency_proxy_avg_sec",
            "first_output_latency_proxy_p95_sec",
            "rule_writeback_latency_proxy_avg_sec",
            "rule_writeback_latency_proxy_p95_sec",
        ],
    )
    baseline_variants = [
        "fast_base",
        "slow_base",
        "rule_recover_policy_sweep_best",
        "rule_recover_matched_label",
        "rule_recover_uncovered_only",
    ]
    baseline_comparison = [
        row
        for row in (
            summarize_precomputed_variant(keys, precomputed_scores, variant)
            for variant in baseline_variants
        )
        if row is not None
    ]
    best_baseline = min(
        (row for row in baseline_comparison if row.get("der") is not None),
        key=lambda row: float(row["der"]),
        default=None,
    )
    write_json(args.output_dir / "baseline_comparison.json", baseline_comparison)
    write_csv(
        args.output_dir / "baseline_comparison.csv",
        baseline_comparison,
        ["baseline_id", "windows", "der", "miss_rate", "fa_rate", "conf_rate"],
    )

    fast_der = aggregate_metric(fast_scores, "der")
    final_der = aggregate_metric(final_scores, "der")
    baseline_deltas = []
    if final_der is not None:
        for row in baseline_comparison:
            baseline_der = row.get("der")
            if baseline_der is None:
                continue
            delta = float(baseline_der) - final_der
            baseline_deltas.append(
                {
                    "baseline_id": row.get("baseline_id"),
                    "baseline_der": baseline_der,
                    "final_der": final_der,
                    "delta_vs_baseline": delta,
                    "delta_vs_baseline_pp": delta * 100,
                    "beats_baseline": final_der < float(baseline_der),
                }
            )
    baseline_win_summary = {
        "baseline_count": len(baseline_deltas),
        "beaten_baselines": sum(1 for row in baseline_deltas if row["beats_baseline"]),
        "beats_all_baselines": bool(baseline_deltas) and all(row["beats_baseline"] for row in baseline_deltas),
        "deltas": baseline_deltas,
    }
    fast_latencies = [as_float(fast_by_key[key].get("latency")) for key in keys]
    slow_latencies = [as_float(slow_by_key[key].get("latency")) for key in keys]
    correction_action_counts = Counter(row["action"] for row in correction_rows)
    gate_category_counts = Counter(row["gate_category"] for row in correction_rows)
    final_source_counts = Counter(row.get("final_source", "") for row in window_rows)
    wall_time = time.time() - started
    processed_audio_sec = float(sum(key[1] for key in keys))
    offline_replay_rtf = wall_time / processed_audio_sec if processed_audio_sec > 0 else 0.0

    evaluation_status = "scored_with_cached_reference" if keys and all(row.get("success") for row in final_scores) else "no_reference"
    if not keys:
        evaluation_status = "no_cached_model_outputs"

    metrics = {
        "runtime_contract": "offline_realtime_diarization_system_no_live_calls",
        "execution_mode": "offline_replay_existing_fast_slow_outputs_with_rule_writeback",
        "run_scope": "all_cached_recordings" if args.all_cached_recordings else "single_recording_or_audio",
        "audio": {
            "path": str(args.audio) if args.audio else None,
            "exists": args.audio.exists() if args.audio else False,
        },
        "recording_id": recording_id,
        "recording_ids": sorted({key[0] for key in keys}),
        "window_size": args.window_size,
        "segment_idx": args.segment_idx,
        "windows_processed": len(keys),
        "cached_windows_available": len(available_keys),
        "cached_window_coverage": round(len(keys) / len(available_keys), 4) if available_keys else 0.0,
        "recordings_processed": len({key[0] for key in keys}),
        "selected_window_ids": [window_id(key) for key in keys],
        "evaluation_status": evaluation_status,
        "fast_summary": str(args.fast_summary),
        "slow_summary": str(args.slow_summary),
        "gate_decisions": str(args.gate_decisions),
        "patches": str(args.patches),
        "timeline_results": str(args.timeline_results),
        "audio_features": str(args.audio_features),
        "window_features": str(args.window_features),
        "external_candidate_summary": str(args.external_candidate_summary),
        "variant": args.variant,
        "guard_quarantine_threshold": args.guard_quarantine_threshold,
        "rare_audio_speech_sec_threshold": args.rare_audio_speech_sec_threshold,
        "rare_slow_segments_max": args.rare_slow_segments_max,
        "balanced_align_slow_segment_min": args.balanced_align_slow_segment_min,
        "balanced_keep_fast_supported_min": args.balanced_keep_fast_supported_min,
        "context_audio_p50_db_min": args.context_audio_p50_db_min,
        "context_prev_audio_dynamic_range_db_max": args.context_prev_audio_dynamic_range_db_max,
        "external_fast_audio_speech_ratio_max": args.external_fast_audio_speech_ratio_max,
        "external_fast_speech_max": args.external_fast_speech_max,
        "fast_model": fast_data.get("model_name"),
        "slow_model": slow_data.get("model_name"),
        "external_candidate_model": external_candidate_data.get("model_name"),
        "baseline_comparison": baseline_comparison,
        "best_baseline": best_baseline,
        "baseline_win_summary": baseline_win_summary,
        "selector_validation": selector_validation,
        "selector_policy_search": selector_search,
        "slow_sanitization_search": slow_sanitization_search,
        "source_artifacts_exist": source_artifact_status(
            {
                "fast_summary": args.fast_summary,
                "slow_summary": args.slow_summary,
                "gate_decisions": args.gate_decisions,
                "patches": args.patches,
                "timeline_results": args.timeline_results,
                "window_features": args.window_features,
                "external_candidate_summary": args.external_candidate_summary,
                "guard_summary": args.guard_summary,
                "selector_validation": args.selector_validation,
                "selector_search": args.selector_search,
                "slow_sanitization_search": args.slow_sanitization_search,
            }
        ),
        "recording_metrics": recording_metrics,
        "metrics": {
            "fast_der": fast_der,
            "fast_miss_rate": aggregate_metric(fast_scores, "miss_rate"),
            "fast_fa_rate": aggregate_metric(fast_scores, "fa_rate"),
            "fast_conf_rate": aggregate_metric(fast_scores, "conf_rate"),
            "final_der": final_der,
            "final_miss_rate": aggregate_metric(final_scores, "miss_rate"),
            "final_fa_rate": aggregate_metric(final_scores, "fa_rate"),
            "final_conf_rate": aggregate_metric(final_scores, "conf_rate"),
            "der_delta_vs_fast": (fast_der - final_der) if fast_der is not None and final_der is not None else None,
            "der_delta_vs_fast_pp": (fast_der - final_der) * 100 if fast_der is not None and final_der is not None else None,
            "der_delta_vs_best_baseline": (best_baseline["der"] - final_der) if best_baseline and final_der is not None else None,
            "der_delta_vs_best_baseline_pp": (best_baseline["der"] - final_der) * 100 if best_baseline and final_der is not None else None,
            "beats_best_baseline": bool(best_baseline and final_der is not None and final_der < best_baseline["der"]),
            "correction_count": len(correction_rows),
            "accepted_correction_count": correction_action_counts.get("accepted_writeback", 0),
            "blocked_or_quarantined_correction_count": sum(
                count for action, count in correction_action_counts.items() if action != "accepted_writeback"
            ),
            "gate_category_counts": dict(gate_category_counts),
            "correction_action_counts": dict(correction_action_counts),
            "final_source_counts": dict(final_source_counts),
            "accepted_window_correction_count": final_source_counts.get("slow", 0),
            "guard_fallback_window_count": final_source_counts.get("fast_guard_fallback", 0),
            "materialization_counters": dict(counter_totals),
            "guard_status": "active_offline_runtime_safe_gate",
            "guard_harmful_accepts": guard_summary.get("best_zero_harm_harmful_accepts"),
            "guard_safe_accepts": guard_summary.get("best_zero_harm_safe_accepts_after"),
            "guard_conservative_blocks": guard_summary.get("best_zero_harm_conservative_blocks_after"),
            "first_output_latency_proxy_avg_sec": average(fast_latencies) or 0.0,
            "first_output_latency_proxy_p95_sec": percentile(fast_latencies, 0.95),
            "rule_writeback_latency_proxy_avg_sec": average(slow_latencies) or 0.0,
            "rule_writeback_latency_proxy_p95_sec": percentile(slow_latencies, 0.95),
            "processed_audio_sec": processed_audio_sec,
            "total_processing_wall_time_sec": wall_time,
            "offline_replay_rtf": offline_replay_rtf,
            "deepseek_api_calls": 0,
            "qwen_api_calls": 0,
            "omni_api_calls": 0,
        },
        "outputs": {
            "fast_timeline_json": str(args.output_dir / "fast_timeline.json"),
            "fast_timeline_csv": str(args.output_dir / "fast_timeline.csv"),
            "fast_timeline_rttm": str(args.output_dir / "fast_timeline.rttm"),
            "final_timeline_json": str(args.output_dir / "final_timeline.json"),
            "final_timeline_csv": str(args.output_dir / "final_timeline.csv"),
            "final_timeline_rttm": str(args.output_dir / "final_timeline.rttm"),
            "correction_log_json": str(args.output_dir / "correction_log.json"),
            "correction_log_csv": str(args.output_dir / "correction_log.csv"),
            "recording_metrics_json": str(args.output_dir / "recording_metrics.json"),
            "recording_metrics_csv": str(args.output_dir / "recording_metrics.csv"),
            "baseline_comparison_json": str(args.output_dir / "baseline_comparison.json"),
            "baseline_comparison_csv": str(args.output_dir / "baseline_comparison.csv"),
            "metrics_json": str(args.output_dir / "metrics.json"),
            "metrics_md": str(args.output_dir / "metrics.md"),
        },
        "notes": [
            "This command uses cached local model outputs; it does not rerun acoustic models or live LLM APIs.",
            "DeepSeek is not used and remains excluded from the system path.",
            "If evaluation_status is no_reference/no_cached_model_outputs, DER fields are not trustworthy and runtime outputs should be treated as surface validation only.",
        ],
    }

    write_json(args.output_dir / "metrics.json", metrics)
    write_metrics_md(args.output_dir / "metrics.md", metrics)

    print(f"Wrote system demo outputs to {args.output_dir}")
    print(f"scope={metrics['run_scope']} recordings={metrics['recordings_processed']} windows={len(keys)} evaluation_status={evaluation_status}")
    if fast_der is not None and final_der is not None:
        print(f"DER fast={fast_der:.2%} final={final_der:.2%} delta={(fast_der - final_der) * 100:.2f}pp")
    print(f"metrics={args.output_dir / 'metrics.json'}")


if __name__ == "__main__":
    main()
