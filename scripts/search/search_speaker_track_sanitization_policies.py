#!/usr/bin/env python3
"""Search runtime-safe speaker-track sanitization policies for Slow outputs.

The policies remove entire low-evidence speaker tracks from cached Slow
diarization windows. Runtime features come only from Fast/Slow predictions;
DER/GT is used after materialization for offline ranking and validation.
"""

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
import contextlib
import csv
import hashlib
import io
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


def load_summary(path: Path) -> dict[WindowKey, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {result_key(row): row for row in data.get("results", []) if row.get("success")}


def duration(seg: dict[str, Any]) -> float:
    return max(0.0, as_float(seg.get("end")) - as_float(seg.get("start")))


def clone_segment(seg: dict[str, Any]) -> dict[str, Any]:
    return {
        "start": as_float(seg.get("start")),
        "end": as_float(seg.get("end")),
        "speaker": str(seg.get("speaker", "unknown")),
        "text": seg.get("text", ""),
    }


def clip_segments(segments: list[dict[str, Any]], window_size: int) -> list[dict[str, Any]]:
    out = []
    for seg in segments:
        new_seg = clone_segment(seg)
        new_seg["start"] = max(0.0, min(float(window_size), new_seg["start"]))
        new_seg["end"] = max(0.0, min(float(window_size), new_seg["end"]))
        if duration(new_seg) > 0:
            out.append(new_seg)
    return out


def overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
    return max(0.0, min(as_float(a["end"]), as_float(b["end"])) - max(as_float(a["start"]), as_float(b["start"])))


def speech_seconds(segments: list[dict[str, Any]]) -> float:
    return sum(duration(seg) for seg in segments)


def track_features(
    slow_segments: list[dict[str, Any]],
    fast_segments: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    tracks: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "segments": 0.0,
            "total_sec": 0.0,
            "max_segment_sec": 0.0,
            "fast_overlap_sec": 0.0,
        }
    )
    for seg in slow_segments:
        speaker = str(seg.get("speaker", "unknown"))
        dur = duration(seg)
        tracks[speaker]["segments"] += 1
        tracks[speaker]["total_sec"] += dur
        tracks[speaker]["max_segment_sec"] = max(tracks[speaker]["max_segment_sec"], dur)
        tracks[speaker]["fast_overlap_sec"] += sum(overlap(seg, fast) for fast in fast_segments)
    for row in tracks.values():
        row["fast_overlap_ratio"] = row["fast_overlap_sec"] / row["total_sec"] if row["total_sec"] else 0.0
    return tracks


def should_drop_track(features: dict[str, float], policy: dict[str, Any]) -> bool:
    if features["total_sec"] < policy.get("min_track_total_sec", 0.0):
        return True
    if features["segments"] < policy.get("min_track_segments", 0.0):
        return True
    if features["max_segment_sec"] < policy.get("min_track_max_segment_sec", 0.0):
        return True
    if features["fast_overlap_sec"] < policy.get("min_track_fast_overlap_sec", 0.0):
        return True
    if features["fast_overlap_ratio"] < policy.get("min_track_fast_overlap_ratio", 0.0):
        return True
    return False


def sanitize_segments(
    policy: dict[str, Any],
    fast: dict[str, Any],
    slow: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    window_size = int(slow["window_size"])
    fast_segments = clip_segments(fast.get("pred_segments", []), window_size)
    slow_segments = clip_segments(slow.get("pred_segments", []), window_size)
    if policy["base"] == "slow":
        return slow_segments, {"slow_base": 1}
    if policy["base"] == "fast":
        return fast_segments, {"fast_base": 1}

    tracks = track_features(slow_segments, fast_segments)
    drop_speakers = {speaker for speaker, row in tracks.items() if should_drop_track(row, policy)}
    if policy.get("require_remaining_speakers", 1) and len(set(tracks) - drop_speakers) < int(policy["require_remaining_speakers"]):
        return slow_segments, {"blocked_min_remaining_speakers": 1}

    kept = [seg for seg in slow_segments if str(seg.get("speaker", "unknown")) not in drop_speakers]
    counters = {
        "dropped_speaker_tracks": len(drop_speakers),
        "dropped_segments": len(slow_segments) - len(kept),
    }
    return kept, counters


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


def segment_signature(segments: list[dict[str, Any]]) -> str:
    payload = [
        {
            "start": round(as_float(seg.get("start")), 4),
            "end": round(as_float(seg.get("end")), 4),
            "speaker": str(seg.get("speaker", "unknown")),
        }
        for seg in segments
    ]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def cache_key(row: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        str(row["policy_id"]),
        str(row["recording_id"]),
        str(int(float(row["window_size"]))),
        str(int(float(row["segment_idx"]))),
        str(row["collar"]),
        str(row["pred_signature"]),
    )


def load_score_cache(path: Path) -> dict[tuple[str, str, str, str, str, str], dict[str, Any]]:
    if not path.exists():
        return {}
    out = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            out[cache_key(row)] = {
                "recording_id": row["recording_id"],
                "window_size": int(float(row["window_size"])),
                "segment_idx": int(float(row["segment_idx"])),
                "policy_id": row["policy_id"],
                "success": str(row.get("success", "")).lower() == "true",
                "der": as_float(row.get("der"), default=float("nan")),
                "miss_rate": as_float(row.get("miss_rate"), default=float("nan")),
                "fa_rate": as_float(row.get("fa_rate"), default=float("nan")),
                "conf_rate": as_float(row.get("conf_rate"), default=float("nan")),
                "pred_segments": int(as_float(row.get("pred_segments"), default=0)),
                "pred_speech_sec": as_float(row.get("pred_speech_sec"), default=0.0),
                "collar": row["collar"],
                "pred_signature": row["pred_signature"],
            }
    return out


def cacheable_row(row: dict[str, Any], collar: float, pred_signature: str) -> dict[str, Any]:
    cached = dict(row)
    cached["collar"] = f"{collar:.6f}"
    cached["pred_signature"] = pred_signature
    return cached


def score_segments_cached(
    key: WindowKey,
    policy_id_value: str,
    pred: list[dict[str, Any]],
    gt: list[dict[str, Any]],
    collar: float,
    score_cache: dict[tuple[str, str, str, str, str, str], dict[str, Any]],
    cache_updates: dict[tuple[str, str, str, str, str, str], dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    pred_sig = segment_signature(pred)
    lookup = {
        "policy_id": policy_id_value,
        "recording_id": key[0],
        "window_size": key[1],
        "segment_idx": key[2],
        "collar": f"{collar:.6f}",
        "pred_signature": pred_sig,
    }
    key_tuple = cache_key(lookup)
    cached = score_cache.get(key_tuple)
    if cached is not None:
        row = dict(cached)
        row.pop("collar", None)
        row.pop("pred_signature", None)
        return row, True
    row = score_segments(key, policy_id_value, pred, gt, collar)
    cache_updates[key_tuple] = cacheable_row(row, collar, pred_sig)
    return row, False


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
    for key in [
        "min_track_total_sec",
        "min_track_segments",
        "min_track_max_segment_sec",
        "min_track_fast_overlap_sec",
        "min_track_fast_overlap_ratio",
        "require_remaining_speakers",
    ]:
        if key in policy and policy[key] not in (None, 0, -1):
            parts.append(f"{key}{policy[key]}")
    return "__".join(str(part).replace(".", "p") for part in parts)


def candidate_policies(policy_set: str) -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = [{"base": "slow"}, {"base": "fast"}]
    totals = [0.2, 0.5, 1.0, 1.5, 2.0, 3.0]
    segments = [2, 3, 4]
    max_segments = [0.2, 0.5, 1.0, 1.5]
    overlap_secs = [0.05, 0.1, 0.2, 0.5, 1.0]
    overlap_ratios = [0.02, 0.05, 0.1, 0.2]
    if policy_set == "core":
        totals = [0.5, 1.0, 2.0]
        segments = [2, 3]
        max_segments = [0.5, 1.0]
        overlap_secs = [0.1, 0.5]
        overlap_ratios = [0.05, 0.1]

    for value in totals:
        policies.append({"base": "speaker_track_filter", "min_track_total_sec": value, "require_remaining_speakers": 1})
    for value in segments:
        policies.append({"base": "speaker_track_filter", "min_track_segments": value, "require_remaining_speakers": 1})
    for value in max_segments:
        policies.append({"base": "speaker_track_filter", "min_track_max_segment_sec": value, "require_remaining_speakers": 1})
    for value in overlap_secs:
        policies.append({"base": "speaker_track_filter", "min_track_fast_overlap_sec": value, "require_remaining_speakers": 1})
    for value in overlap_ratios:
        policies.append({"base": "speaker_track_filter", "min_track_fast_overlap_ratio": value, "require_remaining_speakers": 1})
    for total in totals:
        for seg_count in segments:
            policies.append(
                {
                    "base": "speaker_track_filter",
                    "min_track_total_sec": total,
                    "min_track_segments": seg_count,
                    "require_remaining_speakers": 1,
                }
            )
    for total in totals:
        for overlap_ratio in overlap_ratios:
            policies.append(
                {
                    "base": "speaker_track_filter",
                    "min_track_total_sec": total,
                    "min_track_fast_overlap_ratio": overlap_ratio,
                    "require_remaining_speakers": 1,
                }
            )
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
    collar: float,
    score_cache: dict[tuple[str, str, str, str, str, str], dict[str, Any]],
    cache_updates: dict[tuple[str, str, str, str, str, str], dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    counters = Counter()
    cache_hits = 0
    cache_misses = 0
    pid = policy_id(policy)
    for key in keys:
        pred, item_counters = sanitize_segments(policy, fast_by_key[key], slow_by_key[key])
        counters.update(item_counters)
        row, cache_hit = score_segments_cached(
            key,
            pid,
            pred,
            slow_by_key[key].get("gt_segments", []),
            collar,
            score_cache,
            cache_updates,
        )
        cache_hits += int(cache_hit)
        cache_misses += int(not cache_hit)
        rows.append(row)
    counters["score_cache_hits"] += cache_hits
    counters["score_cache_misses"] += cache_misses
    return summarize_rows(policy, pid, rows, dict(counters)), rows


def recording_holdout(evaluated: dict[str, dict[str, Any]], keys: list[WindowKey]) -> list[dict[str, Any]]:
    rows = []
    slow_eval = evaluated["slow"]
    for recording_id in sorted({key[0] for key in keys}):
        train = [key for key in keys if key[0] != recording_id]
        heldout = [key for key in keys if key[0] == recording_id]
        train_summaries = [
            summarize_rows(item["policy"], pid, [item["rows_by_key"][key] for key in train])
            for pid, item in evaluated.items()
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
        "mean_delta_vs_slow": sum(deltas) / len(deltas) if deltas else 0.0,
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


def write_score_cache(path: Path, rows: dict[tuple[str, str, str, str, str, str], dict[str, Any]]) -> None:
    fieldnames = [
        "policy_id",
        "recording_id",
        "window_size",
        "segment_idx",
        "collar",
        "pred_signature",
        "success",
        "der",
        "miss_rate",
        "fa_rate",
        "conf_rate",
        "pred_segments",
        "pred_speech_sec",
    ]
    write_csv(path, [{name: row.get(name) for name in fieldnames} for row in rows.values()], fieldnames)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    best = payload["best_policy"]
    bootstrap = payload["bootstrap"]
    holdout = payload["holdout_summary"]
    lines = [
        "# Speaker-Track Sanitization Search",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Policy set: `{payload['policy_set']}`",
        f"- Candidate policies: `{payload['candidate_policies']}`",
        f"- Best policy: `{best['policy_id']}`",
        f"- Best DER: `{best['avg_der']:.2%}`",
        f"- Slow DER: `{payload['slow_baseline']['avg_der']:.2%}`",
        f"- Delta vs Slow: `{payload['best_delta_vs_slow_pp']:.3f}pp`",
        f"- Bootstrap P(beats Slow): `{bootstrap['prob_beats_slow']:.1%}`",
        f"- Bootstrap CI: `{bootstrap['delta_ci_low'] * 100:.3f}pp` to `{bootstrap['delta_ci_high'] * 100:.3f}pp`",
        f"- Holdout positive splits: `{holdout['positive_splits_vs_slow']}/{holdout['splits']}`",
        f"- Holdout weighted delta: `{holdout['weighted_delta_vs_slow_pp']:.3f}pp`",
        f"- Score cache hits/misses: `{payload['score_cache']['hits']}/{payload['score_cache']['misses']}`",
        "",
        "## Top Policies",
        "",
        "| Rank | Policy | DER | Delta vs Slow | Pred segs | Counters |",
        "|---:|---|---:|---:|---:|---|",
    ]
    for idx, row in enumerate(payload["top_policies"], start=1):
        lines.append(
            f"| {idx} | `{row['policy_id']}` | {row['avg_der']:.2%} | {row['delta_vs_slow_pp']:.3f}pp | "
            f"{row['avg_pred_segments']:.2f} | `{json.dumps(row['counters'], sort_keys=True)}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Policies remove entire low-evidence Slow speaker tracks using only prediction-derived features.",
            "- `no_robust_speaker_track_sanitizer_found` means this new candidate surface should not be promoted yet.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast-summary", type=Path, default=Path("outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json"))
    parser.add_argument("--slow-summary", type=Path, default=Path("outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json"))
    parser.add_argument("--policy-set", choices=["core", "expanded"], default="core")
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--collar", type=float, default=0.0)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--score-cache", type=Path, default=None, help="Per-policy/window score cache. Default: <output-dir>/speaker_track_sanitization_score_cache.csv")
    parser.add_argument("--no-score-cache", action="store_true", help="Disable reading and writing the score cache.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/speaker_track_sanitization_search"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    score_cache_path = args.score_cache or (args.output_dir / "speaker_track_sanitization_score_cache.csv")
    score_cache = {} if args.no_score_cache else load_score_cache(score_cache_path)
    cache_updates: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}

    fast_by_key = load_summary(args.fast_summary)
    slow_by_key = load_summary(args.slow_summary)
    keys = sorted(set(fast_by_key) & set(slow_by_key))
    policies = candidate_policies(args.policy_set)
    evaluated = {}
    summaries = []
    for policy in policies:
        summary, rows = evaluate_policy(policy, keys, fast_by_key, slow_by_key, args.collar, score_cache, cache_updates)
        rows_by_key = {result_key(row): row for row in rows}
        evaluated[summary["policy_id"]] = {"policy": policy, "summary": summary, "rows": rows, "rows_by_key": rows_by_key}
        summaries.append(summary)

    slow_summary = evaluated["slow"]["summary"]
    for row in summaries:
        row["delta_vs_slow"] = slow_summary["avg_der"] - row["avg_der"]
        row["delta_vs_slow_pp"] = row["delta_vs_slow"] * 100
        row["beats_slow"] = row["avg_der"] < slow_summary["avg_der"]
    summaries.sort(key=lambda row: (row["avg_der"], row["policy_id"]))
    best = summaries[0]
    best_eval = evaluated[best["policy_id"]]
    holdout_rows = recording_holdout(evaluated, keys)
    weighted_delta = sum(row["heldout_delta_vs_slow"] * len([key for key in keys if key[0] == row["heldout_recording_id"]]) for row in holdout_rows) / len(keys)
    holdout_summary = {
        "splits": len(holdout_rows),
        "positive_splits_vs_slow": sum(1 for row in holdout_rows if row["heldout_beats_slow"]),
        "weighted_delta_vs_slow": weighted_delta,
        "weighted_delta_vs_slow_pp": weighted_delta * 100,
    }
    bootstrap = bootstrap_delta(
        best_eval["rows_by_key"],
        evaluated["slow"]["rows_by_key"],
        keys,
        args.bootstrap_samples,
        args.seed,
    )
    robust = (
        best["avg_der"] < slow_summary["avg_der"]
        and bootstrap["delta_ci_low"] > 0
        and bootstrap["prob_beats_slow"] >= 0.95
        and holdout_summary["positive_splits_vs_slow"] >= max(1, holdout_summary["splits"] - 1)
        and holdout_summary["weighted_delta_vs_slow"] > 0
    )
    status = "robust_speaker_track_sanitizer_found" if robust else "no_robust_speaker_track_sanitizer_found"
    payload = {
        "runtime_contract": "speaker_track_sanitization_no_live_calls_prediction_features_only",
        "status": status,
        "policy_set": args.policy_set,
        "windows": len(keys),
        "recordings": len({key[0] for key in keys}),
        "candidate_policies": len(policies),
        "slow_baseline": slow_summary,
        "best_policy": best,
        "best_delta_vs_slow_pp": best["delta_vs_slow_pp"],
        "bootstrap": bootstrap,
        "holdout_summary": holdout_summary,
        "holdout_rows": holdout_rows,
        "top_policies": summaries[: args.top_n],
        "score_cache": {
            "enabled": not args.no_score_cache,
            "path": str(score_cache_path),
            "loaded_entries": len(score_cache),
            "new_entries": len(cache_updates),
            "hits": sum(as_float(row["counters"].get("score_cache_hits")) for row in summaries),
            "misses": sum(as_float(row["counters"].get("score_cache_misses")) for row in summaries),
        },
        "metric_claim_boundary": "development_pool_search_not_true_heldout",
    }

    json_path = args.output_dir / "speaker_track_sanitization_policy_search.json"
    md_path = args.output_dir / "speaker_track_sanitization_policy_search.md"
    csv_path = args.output_dir / "speaker_track_sanitization_policy_search.csv"
    holdout_csv = args.output_dir / "speaker_track_sanitization_policy_holdout.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    write_csv(csv_path, summaries)
    write_csv(holdout_csv, holdout_rows)
    if not args.no_score_cache:
        merged_cache = dict(score_cache)
        merged_cache.update(cache_updates)
        write_score_cache(score_cache_path, merged_cache)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {holdout_csv}")
    if not args.no_score_cache:
        print(f"Wrote {score_cache_path}")
    print(
        "status={status} best={best} best_der={best_der:.2%} slow={slow:.2%} delta={delta:.3f}pp holdout={pos}/{splits}".format(
            status=status,
            best=best["policy_id"],
            best_der=best["avg_der"],
            slow=slow_summary["avg_der"],
            delta=best["delta_vs_slow_pp"],
            pos=holdout_summary["positive_splits_vs_slow"],
            splits=holdout_summary["splits"],
        )
    )


if __name__ == "__main__":
    main()
