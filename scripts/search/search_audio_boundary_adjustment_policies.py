#!/usr/bin/env python3
"""Search audio-guided Slow boundary adjustment policies.

Unlike audio-guided sanitization, these policies do not delete whole Slow
segments. They only trim or expand segment boundaries by a small amount using
runtime-safe audio activity masks. DER/GT is used only after materialization for
offline scoring and validation.
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
import csv
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

logging.disable(logging.WARNING)

from search_audio_guided_sanitization_policies import (
    WindowKey,
    as_float,
    average,
    bootstrap_delta,
    build_audio_masks,
    clone_segment,
    duration,
    load_segment_index,
    load_summary,
    percentile,
    recording_holdout,
    score_segments,
    scored_row_key,
    speech_seconds,
    summarize_rows,
)


def speaker_id(segment: dict[str, Any]) -> str:
    for key in ("speaker", "label", "speaker_id"):
        if key in segment and segment[key] is not None:
            return str(segment[key])
    return ""


def cap_same_speaker_overlap(
    proposed_start: float,
    proposed_end: float,
    original_start: float,
    original_end: float,
    current_idx: int,
    segments: list[dict[str, Any]],
) -> tuple[float, float, int]:
    """Keep expansion from creating self-overlap for the same predicted speaker."""
    speaker = speaker_id(segments[current_idx])
    if not speaker:
        return proposed_start, proposed_end, 0

    capped = 0
    for idx, other in enumerate(segments):
        if idx == current_idx or speaker_id(other) != speaker:
            continue
        other_start = as_float(other["start"])
        other_end = as_float(other["end"])
        if other_end <= original_start:
            capped_start = max(proposed_start, other_end)
            capped += int(capped_start > proposed_start)
            proposed_start = capped_start
        elif other_start >= original_end:
            capped_end = min(proposed_end, other_start)
            capped += int(capped_end < proposed_end)
            proposed_end = capped_end
    return proposed_start, proposed_end, capped


def same_speaker_overlap_pairs(segments: list[dict[str, Any]]) -> int:
    count = 0
    by_speaker: dict[str, list[tuple[float, float]]] = {}
    for seg in segments:
        by_speaker.setdefault(speaker_id(seg), []).append((as_float(seg["start"]), as_float(seg["end"])))
    for spans in by_speaker.values():
        spans.sort()
        prev_end = -1.0
        for start, end in spans:
            if start < prev_end:
                count += 1
            prev_end = max(prev_end, end)
    return count


def active_bounds(
    mask_info: dict[str, Any],
    start: float,
    end: float,
    mode: str,
    search_pad: float = 0.0,
) -> tuple[float | None, float | None, float]:
    hop_sec = as_float(mask_info["hop_sec"], default=0.01)
    frame_count = int(mask_info["frame_count"])
    search_start = max(0.0, start - search_pad)
    search_end = min(frame_count * hop_sec, end + search_pad)
    start_idx = max(0, min(frame_count, int(np.floor(search_start / hop_sec))))
    end_idx = max(start_idx + 1, min(frame_count, int(np.ceil(search_end / hop_sec))))
    mask = mask_info[mode][start_idx:end_idx]
    active = np.flatnonzero(mask)
    if active.size == 0:
        return None, None, 0.0
    first_idx = start_idx + int(active[0])
    last_idx = start_idx + int(active[-1])
    active_sec = float(active.size * hop_sec)
    return first_idx * hop_sec, (last_idx + 1) * hop_sec, active_sec


def adjust_segments(
    policy: dict[str, Any],
    key: WindowKey,
    slow: dict[str, Any],
    masks: dict[WindowKey, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    slow_segments = [clone_segment(seg) for seg in slow.get("pred_segments", [])]
    if policy["base"] == "slow":
        return slow_segments, {"slow_base": 1}
    mask_info = masks.get(key)
    if not mask_info:
        return slow_segments, {"missing_audio_mask": 1}

    counters = Counter()
    adjusted = []
    window_end = float(key[1])
    for idx, seg in enumerate(slow_segments):
        original_start = as_float(seg["start"])
        original_end = as_float(seg["end"])
        first_active, last_active, active_sec = active_bounds(
            mask_info,
            original_start,
            original_end,
            policy["mode"],
            policy.get("search_pad", 0.0),
        )
        new_seg = clone_segment(seg)
        if first_active is None or last_active is None or active_sec < policy.get("min_active_sec", 0.0):
            counters["unchanged_no_activity"] += 1
            adjusted.append(new_seg)
            continue

        if policy["base"] == "boundary_trim":
            proposed_start = max(original_start, first_active - policy.get("pad", 0.0))
            proposed_end = min(original_end, last_active + policy.get("pad", 0.0))
            trim_sec = max(0.0, proposed_start - original_start) + max(0.0, original_end - proposed_end)
            if trim_sec <= policy.get("max_total_trim_sec", 0.0) and proposed_end - proposed_start >= policy.get("min_duration", 0.05):
                new_seg["start"] = round(proposed_start, 4)
                new_seg["end"] = round(proposed_end, 4)
                counters["trimmed"] += int(trim_sec > 0)
            else:
                counters["trim_blocked"] += 1
        elif policy["base"] == "boundary_expand":
            proposed_start = max(0.0, min(original_start, first_active - policy.get("pad", 0.0)))
            proposed_end = min(window_end, max(original_end, last_active + policy.get("pad", 0.0)))
            if policy.get("prevent_same_speaker_overlap", True):
                proposed_start, proposed_end, capped = cap_same_speaker_overlap(
                    proposed_start,
                    proposed_end,
                    original_start,
                    original_end,
                    idx,
                    slow_segments,
                )
                counters["same_speaker_overlap_capped"] += capped
            expand_sec = max(0.0, original_start - proposed_start) + max(0.0, proposed_end - original_end)
            if expand_sec <= policy.get("max_total_expand_sec", 0.0) and proposed_end > proposed_start:
                new_seg["start"] = round(proposed_start, 4)
                new_seg["end"] = round(proposed_end, 4)
                counters["expanded"] += int(expand_sec > 0)
            else:
                counters["expand_blocked"] += 1
        adjusted.append(new_seg)
    overlap_pairs = same_speaker_overlap_pairs(adjusted)
    if overlap_pairs and policy.get("prevent_same_speaker_overlap", True):
        counters["same_speaker_overlap_pairs"] += overlap_pairs
        counters["overlap_reverted_windows"] += 1
        return slow_segments, dict(counters)
    counters["same_speaker_overlap_pairs"] += overlap_pairs
    return adjusted, dict(counters)


def policy_id(policy: dict[str, Any]) -> str:
    parts = [policy["base"]]
    for key in [
        "mode",
        "pad",
        "search_pad",
        "max_total_trim_sec",
        "max_total_expand_sec",
        "min_active_sec",
        "prevent_same_speaker_overlap",
    ]:
        if key in policy and policy[key] not in (None, 0, -1):
            parts.append(f"{key}{policy[key]}")
    return "__".join(str(part).replace(".", "p") for part in parts)


def candidate_policies() -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = [{"base": "slow"}]
    for mode in ["mean", "max"]:
        for pad in [0.0, 0.1, 0.2]:
            for max_trim in [0.25, 0.5, 1.0]:
                for min_active in [0.03, 0.05, 0.1]:
                    policies.append(
                        {
                            "base": "boundary_trim",
                            "mode": mode,
                            "pad": pad,
                            "max_total_trim_sec": max_trim,
                            "min_active_sec": min_active,
                        }
                    )
        for pad in [0.0, 0.1]:
            for search_pad in [0.1, 0.25, 0.5]:
                for max_expand in [0.1, 0.25, 0.5]:
                    policies.append(
                        {
                            "base": "boundary_expand",
                            "mode": mode,
                            "pad": pad,
                            "search_pad": search_pad,
                            "max_total_expand_sec": max_expand,
                            "min_active_sec": 0.05,
                            "prevent_same_speaker_overlap": True,
                        }
                    )
    return policies


def evaluate_policy(
    policy: dict[str, Any],
    keys: list[WindowKey],
    slow_by_key: dict[WindowKey, dict[str, Any]],
    masks: dict[WindowKey, dict[str, Any]],
    collar: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    counters = Counter()
    pid = policy_id(policy)
    for key in keys:
        pred, item_counters = adjust_segments(policy, key, slow_by_key[key], masks)
        counters.update(item_counters)
        rows.append(score_segments(key, pid, pred, slow_by_key[key].get("gt_segments", []), collar))
    summary = summarize_rows(policy, pid, rows, dict(counters))
    summary["avg_pred_speech_sec"] = average(rows, "pred_speech_sec")
    return summary, rows


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
        "# Audio Boundary Adjustment Search",
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
        "| Rank | Policy | DER | Miss | FA | Conf | Pred speech | Counters |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for idx, row in enumerate(payload["top_policies"], start=1):
        lines.append(
            f"| {idx} | `{row['policy_id']}` | {row['avg_der']:.2%} | {row['avg_miss_rate']:.2%} | {row['avg_fa_rate']:.2%} | {row['avg_conf_rate']:.2%} | {row['avg_pred_speech_sec']:.2f}s | `{json.dumps(row['counters'], sort_keys=True)}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Policies use only audio activity masks and Slow predicted timelines at runtime.",
            "- They adjust boundaries only; they do not delete complete Slow segments.",
            "- DER/GT is used only after materialization for scoring and validation.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument("--seed-bootstrap", type=int, default=42)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/audio_boundary_adjustment_search"))
    args = parser.parse_args()

    slow_by_key = load_summary(args.slow_summary)
    keys = sorted(slow_by_key)
    segment_index = load_segment_index(args.window_size, args.total_samples, args.seed)
    masks = build_audio_masks(keys, segment_index, args)
    policies = candidate_policies()

    evaluated: dict[str, dict[str, Any]] = {}
    summaries = []
    for idx, policy in enumerate(policies, start=1):
        summary, rows = evaluate_policy(policy, keys, slow_by_key, masks, args.collar)
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
    bootstrap = bootstrap_delta(best_eval["rows_by_key"], slow_eval["rows_by_key"], keys, args.bootstrap_samples, args.seed_bootstrap)
    holdout_final = sum(row["heldout_der"] for row in holdout) / len(holdout)
    holdout_slow = sum(row["heldout_slow_der"] for row in holdout) / len(holdout)
    positive = sum(1 for row in holdout if row["heldout_beats_slow"])
    best_delta = slow_baseline["avg_der"] - summaries[0]["avg_der"]
    status = (
        "robust_audio_boundary_policy_found"
        if best_delta > 0 and bootstrap["delta_ci_low"] > 0 and positive == len(holdout)
        else "no_robust_audio_boundary_policy_found"
    )
    payload = {
        "runtime_contract": "audio_boundary_adjustment_no_live_calls_audio_features_only",
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
    json_path = args.output_dir / "audio_boundary_adjustment_policy_search.json"
    md_path = args.output_dir / "audio_boundary_adjustment_policy_search.md"
    csv_path = args.output_dir / "audio_boundary_adjustment_policy_search.csv"
    holdout_csv = args.output_dir / "audio_boundary_adjustment_policy_holdout.csv"
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
