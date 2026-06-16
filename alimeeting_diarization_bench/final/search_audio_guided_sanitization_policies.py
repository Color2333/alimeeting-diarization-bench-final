#!/usr/bin/env python3
"""Search audio-guided runtime-safe Slow segment sanitizers.

The policies use only cached Slow/Fast predictions plus audio-derived activity
masks at runtime. DER/GT is used only after materializing candidate timelines to
score and validate policies.
"""

from __future__ import annotations

# Keep final modules import-compatible when executed with python -m.
import sys as _sys
from pathlib import Path as _Path
_SCRIPT_ROOT = _Path(__file__).resolve().parent
_REPO_ROOT = _Path(__file__).resolve().parents[2]
for _candidate in [_REPO_ROOT, _SCRIPT_ROOT, *_SCRIPT_ROOT.iterdir()]:
    if _candidate.is_dir():
        _value = str(_candidate)
        if _value not in _sys.path:
            _sys.path.insert(0, _value)

import argparse
import contextlib
import csv
import io
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alimeeting_diarization_bench.data.manifests import generate_stratified_segments, load_manifests
from alimeeting_diarization_bench.metrics.der import calc_der


WindowKey = tuple[str, int, int]


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def result_key(row: dict[str, Any]) -> WindowKey:
    return (str(row["recording_id"]), int(row["window_size"]), int(row["segment_idx"]))


def scored_row_key(row: dict[str, Any]) -> WindowKey:
    return (str(row["recording_id"]), int(row["window_size"]), int(row["segment_idx"]))


def load_summary(path: Path) -> dict[WindowKey, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {result_key(row): row for row in data.get("results", []) if row.get("success")}


def load_segment_index(window_size: int, total_samples: int, seed: int) -> dict[WindowKey, dict[str, Any]]:
    recordings, supervisions = load_manifests()
    segments = generate_stratified_segments(
        recordings,
        supervisions,
        window_size=window_size,
        total_samples=total_samples,
        seed=seed,
    )
    return {result_key(seg): seg for seg in segments}


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


def activity_mask(db: np.ndarray, noise_percentile: float, margin_db: float, min_threshold_db: float) -> tuple[np.ndarray, float]:
    threshold = max(float(np.percentile(db, noise_percentile)) + margin_db, min_threshold_db)
    return db > threshold, threshold


def build_audio_masks(
    keys: list[WindowKey],
    segment_index: dict[WindowKey, dict[str, Any]],
    args: argparse.Namespace,
) -> dict[WindowKey, dict[str, Any]]:
    masks = {}
    for key in keys:
        seg = segment_index[key]
        path = Path(seg["audio_path"])
        if not path.exists():
            continue
        info = sf.info(path)
        sr = info.samplerate
        start = int(as_float(seg.get("offset")) * sr)
        frames = int(as_float(seg.get("duration")) * sr)
        audio, _ = sf.read(path, start=start, frames=frames, dtype="float32")
        if audio.ndim == 1:
            audio = audio.reshape(-1, 1)
        channel_db = rms_to_db(frame_rms(audio, sr, args.frame_ms, args.hop_ms))
        if channel_db.ndim == 1:
            channel_db = channel_db.reshape(-1, 1)
        mean_db = rms_to_db(frame_rms(audio.mean(axis=1), sr, args.frame_ms, args.hop_ms))
        max_db = np.max(channel_db, axis=1)
        mean_mask, mean_threshold = activity_mask(mean_db, args.noise_percentile, args.threshold_margin_db, args.min_threshold_db)
        max_mask, max_threshold = activity_mask(max_db, args.noise_percentile, args.threshold_margin_db, args.min_threshold_db)
        active_channels = np.sum(channel_db > max_threshold, axis=1)
        masks[key] = {
            "mean": mean_mask,
            "max": max_mask,
            "active_channels": active_channels,
            "frame_count": int(len(max_mask)),
            "hop_sec": args.hop_ms / 1000.0,
            "mean_threshold_db": mean_threshold,
            "max_threshold_db": max_threshold,
        }
    return masks


def duration(seg: dict[str, Any]) -> float:
    return max(0.0, as_float(seg.get("end")) - as_float(seg.get("start")))


def speech_seconds(segments: list[dict[str, Any]]) -> float:
    return sum(duration(seg) for seg in segments)


def clone_segment(seg: dict[str, Any]) -> dict[str, Any]:
    return {
        "start": as_float(seg.get("start")),
        "end": as_float(seg.get("end")),
        "speaker": str(seg.get("speaker", "unknown")),
        "text": seg.get("text", ""),
    }


def segment_support(mask_info: dict[str, Any], seg: dict[str, Any], mode: str) -> tuple[float, float, float]:
    mask = mask_info[mode]
    hop_sec = as_float(mask_info["hop_sec"], default=0.01)
    frame_count = int(mask_info["frame_count"])
    start_idx = max(0, min(frame_count, int(np.floor(as_float(seg["start"]) / hop_sec))))
    end_idx = max(start_idx + 1, min(frame_count, int(np.ceil(as_float(seg["end"]) / hop_sec))))
    segment_mask = mask[start_idx:end_idx]
    active = float(np.sum(segment_mask) * hop_sec)
    total = max(hop_sec, float(len(segment_mask) * hop_sec))
    active_channels = mask_info["active_channels"][start_idx:end_idx]
    return active, active / total if total else 0.0, float(np.mean(active_channels)) if len(active_channels) else 0.0


def sanitize_segments(
    policy: dict[str, Any],
    key: WindowKey,
    fast: dict[str, Any],
    slow: dict[str, Any],
    masks: dict[WindowKey, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if policy["base"] == "fast":
        return [clone_segment(seg) for seg in fast.get("pred_segments", [])], {"fast_base": 1}
    slow_segments = [clone_segment(seg) for seg in slow.get("pred_segments", [])]
    if policy["base"] == "slow":
        return slow_segments, {"slow_base": 1}
    mask_info = masks.get(key)
    if not mask_info:
        return slow_segments, {"missing_audio_mask": 1}

    counters = Counter()
    kept = []
    for seg in slow_segments:
        support_sec, support_ratio, active_channel_mean = segment_support(mask_info, seg, policy["mode"])
        if duration(seg) < policy.get("min_segment_duration", 0.0):
            counters["drop_short"] += 1
            continue
        if support_sec < policy.get("min_support_sec", 0.0):
            counters["drop_low_support_sec"] += 1
            continue
        if support_ratio < policy.get("min_support_ratio", 0.0):
            counters["drop_low_support_ratio"] += 1
            continue
        if active_channel_mean < policy.get("min_active_channels", 0.0):
            counters["drop_low_active_channels"] += 1
            continue
        kept.append(seg)
    return kept, dict(counters)


def score_segments(key: WindowKey, policy_id: str, pred: list[dict[str, Any]], gt: list[dict[str, Any]], collar: float) -> dict[str, Any]:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        metrics = calc_der(gt, pred, f"{key[0]}_ws{key[1]}_seg{key[2]}_{policy_id}", collar=collar)
    row = {
        "recording_id": key[0],
        "window_size": key[1],
        "segment_idx": key[2],
        "policy_id": policy_id,
        "success": metrics is not None,
        "der": None,
        "miss_rate": None,
        "fa_rate": None,
        "conf_rate": None,
        "pred_segments": len(pred),
        "pred_speech_sec": speech_seconds(pred),
    }
    if metrics:
        row.update(metrics)
    return row


def average(rows: list[dict[str, Any]], field: str) -> float:
    values = [as_float(row.get(field), default=float("nan")) for row in rows]
    values = [value for value in values if value == value]
    return sum(values) / len(values) if values else 999.0


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]


def policy_id(policy: dict[str, Any]) -> str:
    parts = [policy["base"]]
    for key in ["mode", "min_support_ratio", "min_support_sec", "min_active_channels", "min_segment_duration"]:
        if key in policy and policy[key] not in (None, 0, -1):
            parts.append(f"{key}{policy[key]}")
    return "__".join(str(part).replace(".", "p") for part in parts)


def candidate_policies() -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = [{"base": "slow"}, {"base": "fast"}]
    for mode in ["mean", "max"]:
        for ratio in [0.05, 0.1, 0.2, 0.35, 0.5, 0.7]:
            policies.append({"base": "audio_support_filter", "mode": mode, "min_support_ratio": ratio})
        for sec in [0.05, 0.1, 0.2, 0.5, 1.0]:
            policies.append({"base": "audio_support_filter", "mode": mode, "min_support_sec": sec})
        for active_channels in [0.25, 0.5, 1.0, 2.0]:
            policies.append({"base": "audio_support_filter", "mode": mode, "min_active_channels": active_channels})
        for ratio in [0.1, 0.2, 0.35]:
            for sec in [0.1, 0.2, 0.5]:
                policies.append({"base": "audio_support_filter", "mode": mode, "min_support_ratio": ratio, "min_support_sec": sec})
        for ratio in [0.1, 0.2, 0.35]:
            policies.append({"base": "audio_support_filter", "mode": mode, "min_support_ratio": ratio, "min_segment_duration": 0.2})
    return policies


def summarize_rows(policy: dict[str, Any], pid: str, rows: list[dict[str, Any]], counters: dict[str, int] | None = None) -> dict[str, Any]:
    return {
        "policy_id": pid,
        "policy": json.dumps(policy, sort_keys=True),
        "windows": len(rows),
        "success_windows": sum(1 for row in rows if row.get("success")),
        "avg_der": average(rows, "der"),
        "avg_miss_rate": average(rows, "miss_rate"),
        "avg_fa_rate": average(rows, "fa_rate"),
        "avg_conf_rate": average(rows, "conf_rate"),
        "avg_pred_segments": average(rows, "pred_segments"),
        "avg_pred_speech_sec": average(rows, "pred_speech_sec"),
        "counters": counters or {},
    }


def evaluate_policy(
    policy: dict[str, Any],
    keys: list[WindowKey],
    fast_by_key: dict[WindowKey, dict[str, Any]],
    slow_by_key: dict[WindowKey, dict[str, Any]],
    masks: dict[WindowKey, dict[str, Any]],
    collar: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    counters = Counter()
    pid = policy_id(policy)
    for key in keys:
        pred, item_counters = sanitize_segments(policy, key, fast_by_key[key], slow_by_key[key], masks)
        counters.update(item_counters)
        rows.append(score_segments(key, pid, pred, slow_by_key[key].get("gt_segments", []), collar))
    return summarize_rows(policy, pid, rows, dict(counters)), rows


def recording_holdout(evaluated: dict[str, dict[str, Any]], keys: list[WindowKey]) -> list[dict[str, Any]]:
    rows = []
    slow_eval = evaluated["slow"]
    for recording_id in sorted({key[0] for key in keys}):
        train = [key for key in keys if key[0] != recording_id]
        heldout = [key for key in keys if key[0] == recording_id]
        train_summaries = [
            summarize_rows(item["policy"], policy_id, [item["rows_by_key"][key] for key in train])
            for policy_id, item in evaluated.items()
        ]
        best = min(train_summaries, key=lambda row: (row["avg_der"], row["policy_id"]))
        best_eval = evaluated[best["policy_id"]]
        heldout_summary = summarize_rows(best_eval["policy"], best["policy_id"], [best_eval["rows_by_key"][key] for key in heldout])
        slow_summary = summarize_rows(slow_eval["policy"], "slow", [slow_eval["rows_by_key"][key] for key in heldout])
        rows.append(
            {
                "heldout_recording_id": recording_id,
                "selected_policy_id": best["policy_id"],
                "train_der": best["avg_der"],
                "heldout_der": heldout_summary["avg_der"],
                "heldout_slow_der": slow_summary["avg_der"],
                "heldout_delta_vs_slow": slow_summary["avg_der"] - heldout_summary["avg_der"],
                "heldout_delta_vs_slow_pp": (slow_summary["avg_der"] - heldout_summary["avg_der"]) * 100,
                "heldout_beats_slow": heldout_summary["avg_der"] < slow_summary["avg_der"],
            }
        )
    return rows


def bootstrap_delta(
    policy_rows_by_key: dict[WindowKey, dict[str, Any]],
    slow_rows_by_key: dict[WindowKey, dict[str, Any]],
    keys: list[WindowKey],
    samples: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        sample_keys = [rng.choice(keys) for _ in keys]
        policy_der = average([policy_rows_by_key[key] for key in sample_keys], "der")
        slow_der = average([slow_rows_by_key[key] for key in sample_keys], "der")
        deltas.append(slow_der - policy_der)
    return {
        "samples": samples,
        "seed": seed,
        "mean_delta_vs_slow": average([{"v": value} for value in deltas], "v"),
        "delta_ci_low": percentile(deltas, 0.025),
        "delta_ci_high": percentile(deltas, 0.975),
        "prob_beats_slow": sum(1 for value in deltas if value > 0) / len(deltas) if deltas else 0.0,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Audio-Guided Slow Sanitization Search",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Windows: `{payload['windows']}`",
        f"- Candidate policies: `{payload['candidate_policies']}`",
        f"- Best policy: `{payload['best_policy']['policy_id']}`",
        f"- Best DER: `{payload['best_policy']['avg_der']:.2%}`",
        f"- Slow baseline DER: `{payload['slow_baseline']['avg_der']:.2%}`",
        f"- Delta vs Slow: `{payload['best_delta_vs_slow_pp']:.2f}pp`",
        f"- Bootstrap P(beats Slow): `{payload['bootstrap']['prob_beats_slow']:.1%}`",
        f"- Holdout positive splits: `{payload['holdout_summary']['positive_splits_vs_slow']}/{payload['holdout_summary']['splits']}`",
        f"- Holdout weighted delta vs Slow: `{payload['holdout_summary']['weighted_delta_vs_slow_pp']:.2f}pp`",
        "",
        "## Top Policies",
        "",
        "| Rank | Policy | DER | Miss | FA | Conf | Counters |",
        "|---:|---|---:|---:|---:|---:|---|",
    ]
    for idx, row in enumerate(payload["top_policies"], start=1):
        lines.append(
            f"| {idx} | `{row['policy_id']}` | {row['avg_der']:.2%} | {row['avg_miss_rate']:.2%} | {row['avg_fa_rate']:.2%} | {row['avg_conf_rate']:.2%} | `{json.dumps(row['counters'], sort_keys=True)}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Policies use only audio activity masks and predicted Fast/Slow timelines at runtime.",
            "- DER/GT is used only after materialization for scoring.",
            "- If holdout/bootstrap is weak, this should remain an analysis artifact rather than a default runtime path.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast-summary", type=Path, default=Path("outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json"))
    parser.add_argument("--slow-summary", type=Path, default=Path("outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json"))
    parser.add_argument("--window-size", type=int, default=30)
    parser.add_argument("--total-samples", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--frame-ms", type=float, default=30.0)
    parser.add_argument("--hop-ms", type=float, default=10.0)
    parser.add_argument("--noise-percentile", type=float, default=20.0)
    parser.add_argument("--threshold-margin-db", type=float, default=8.0)
    parser.add_argument("--min-threshold-db", type=float, default=-45.0)
    parser.add_argument("--collar", type=float, default=0.0)
    parser.add_argument("--bootstrap-samples", type=int, default=500)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/audio_guided_sanitization_search"))
    args = parser.parse_args()

    fast_by_key = load_summary(args.fast_summary)
    slow_by_key = load_summary(args.slow_summary)
    keys = sorted(set(fast_by_key) & set(slow_by_key))
    segment_index = load_segment_index(args.window_size, args.total_samples, args.seed)
    masks = build_audio_masks(keys, segment_index, args)
    policies = candidate_policies()

    evaluated: dict[str, dict[str, Any]] = {}
    summaries = []
    for idx, policy in enumerate(policies, start=1):
        summary, rows = evaluate_policy(policy, keys, fast_by_key, slow_by_key, masks, args.collar)
        pid = summary["policy_id"]
        evaluated[pid] = {
            "policy": policy,
            "summary": summary,
            "rows": rows,
            "rows_by_key": {scored_row_key(row): row for row in rows},
        }
        summaries.append(summary)
        print(f"[{idx}/{len(policies)}] {pid}: DER={summary['avg_der']:.2%}", flush=True)

    summaries.sort(key=lambda row: (row["avg_der"], row["avg_fa_rate"], row["policy_id"]))
    slow_baseline = next(row for row in summaries if row["policy_id"] == "slow")
    best_eval = evaluated[summaries[0]["policy_id"]]
    slow_eval = evaluated["slow"]
    holdout = recording_holdout(evaluated, keys)
    bootstrap = bootstrap_delta(best_eval["rows_by_key"], slow_eval["rows_by_key"], keys, args.bootstrap_samples, args.seed)
    holdout_final = sum(row["heldout_der"] for row in holdout) / len(holdout)
    holdout_slow = sum(row["heldout_slow_der"] for row in holdout) / len(holdout)
    positive = sum(1 for row in holdout if row["heldout_beats_slow"])
    best_delta = slow_baseline["avg_der"] - summaries[0]["avg_der"]
    status = (
        "robust_audio_sanitizer_found"
        if best_delta > 0 and bootstrap["delta_ci_low"] > 0 and positive == len(holdout)
        else "no_robust_audio_sanitizer_found"
    )
    payload = {
        "runtime_contract": "audio_guided_slow_sanitization_no_live_calls_audio_features_only",
        "status": status,
        "windows": len(keys),
        "audio_mask_coverage": f"{len(masks)}/{len(keys)}",
        "candidate_policies": len(policies),
        "no_live_calls_performed": True,
        "no_deepseek_api_calls": True,
        "metric_claim_boundary": "development_pool_search_not_true_heldout",
        "best_policy": summaries[0],
        "slow_baseline": slow_baseline,
        "best_delta_vs_slow": best_delta,
        "best_delta_vs_slow_pp": best_delta * 100,
        "top_policies": summaries[: args.top_n],
        "holdout": holdout,
        "holdout_summary": {
            "splits": len(holdout),
            "positive_splits_vs_slow": positive,
            "weighted_holdout_final_der": holdout_final,
            "weighted_holdout_slow_der": holdout_slow,
            "weighted_delta_vs_slow": holdout_slow - holdout_final,
            "weighted_delta_vs_slow_pp": (holdout_slow - holdout_final) * 100,
        },
        "bootstrap": bootstrap,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "audio_guided_sanitization_policy_search.json"
    md_path = args.output_dir / "audio_guided_sanitization_policy_search.md"
    csv_path = args.output_dir / "audio_guided_sanitization_policy_search.csv"
    holdout_csv = args.output_dir / "audio_guided_sanitization_policy_holdout.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    write_csv(csv_path, summaries)
    write_csv(holdout_csv, holdout)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "status={status} best={best:.2%} slow={slow:.2%} delta={delta:.2f}pp holdout_delta={holdout:.2f}pp".format(
            status=status,
            best=summaries[0]["avg_der"],
            slow=slow_baseline["avg_der"],
            delta=best_delta * 100,
            holdout=(holdout_slow - holdout_final) * 100,
        )
    )


if __name__ == "__main__":
    main()
