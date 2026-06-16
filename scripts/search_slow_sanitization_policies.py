#!/usr/bin/env python3
"""Search runtime-safe Slow timeline sanitization policies.

This script explores local post-processing policies that alter the cached Slow
timeline without using DER/GT at runtime. DER is used only after materializing a
candidate timeline to rank and validate policies.
"""

from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[1]
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


def scored_row_key(row: dict[str, Any]) -> WindowKey:
    return (str(row["recording_id"]), int(row["window_size"]), int(row["segment_idx"]))


def load_summary(path: Path) -> dict[WindowKey, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {result_key(row): row for row in data.get("results", []) if row.get("success")}


def duration(seg: dict[str, Any]) -> float:
    return max(0.0, as_float(seg.get("end")) - as_float(seg.get("start")))


def speech_seconds(segments: list[dict[str, Any]]) -> float:
    return sum(duration(seg) for seg in segments)


def overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
    return max(0.0, min(as_float(a["end"]), as_float(b["end"])) - max(as_float(a["start"]), as_float(b["start"])))


def best_fast_support(seg: dict[str, Any], fast_segments: list[dict[str, Any]]) -> tuple[float, float]:
    best = 0.0
    total = 0.0
    for fast in fast_segments:
        value = overlap(seg, fast)
        best = max(best, value)
        total += value
    dur = duration(seg)
    return best, (best / dur if dur else 0.0)


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


def merge_same_speaker(segments: list[dict[str, Any]], gap: float) -> list[dict[str, Any]]:
    by_speaker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for seg in segments:
        by_speaker[str(seg["speaker"])].append(seg)
    merged = []
    for speaker, rows in by_speaker.items():
        ordered = sorted(rows, key=lambda row: (as_float(row["start"]), as_float(row["end"])))
        cur = None
        for seg in ordered:
            if cur is None or as_float(seg["start"]) > as_float(cur["end"]) + gap:
                if cur is not None:
                    merged.append(cur)
                cur = clone_segment(seg)
                cur["speaker"] = speaker
            else:
                cur["end"] = max(as_float(cur["end"]), as_float(seg["end"]))
        if cur is not None:
            merged.append(cur)
    return sorted(merged, key=lambda row: (as_float(row["start"]), as_float(row["end"]), str(row["speaker"])))


def sanitize_segments(
    policy: dict[str, Any],
    fast: dict[str, Any],
    slow: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    window_size = int(slow["window_size"])
    fast_segments = [clone_segment(seg) for seg in fast.get("pred_segments", [])]
    slow_segments = clip_segments(slow.get("pred_segments", []), window_size)
    counters = Counter()

    if policy["base"] == "fast":
        return fast_segments, {"fast_fallback": 1}

    filtered = []
    for seg in slow_segments:
        dur = duration(seg)
        if dur < policy.get("min_duration", 0.0):
            counters["drop_short"] += 1
            continue
        best_sec, best_ratio = best_fast_support(seg, fast_segments)
        if best_sec < policy.get("min_fast_overlap_sec", 0.0):
            counters["drop_low_fast_overlap_sec"] += 1
            continue
        if best_ratio < policy.get("min_fast_overlap_ratio", 0.0):
            counters["drop_low_fast_overlap_ratio"] += 1
            continue
        filtered.append(seg)

    if policy.get("merge_gap", -1.0) >= 0:
        before = len(filtered)
        filtered = merge_same_speaker(filtered, policy["merge_gap"])
        counters["merge_removed"] += max(0, before - len(filtered))

    max_speech_ratio = policy.get("max_speech_ratio")
    if max_speech_ratio is not None and speech_seconds(filtered) > max_speech_ratio * window_size:
        if policy.get("cap_action") == "fast":
            counters["cap_fast_fallback"] += 1
            return fast_segments, dict(counters)
        if policy.get("cap_action") == "drop_unsupported":
            target = max_speech_ratio * window_size
            ranked = sorted(
                filtered,
                key=lambda seg: (
                    best_fast_support(seg, fast_segments)[1],
                    best_fast_support(seg, fast_segments)[0],
                    duration(seg),
                ),
            )
            while speech_seconds(ranked) > target and ranked:
                ranked.pop(0)
                counters["cap_drop"] += 1
            filtered = sorted(ranked, key=lambda row: (as_float(row["start"]), as_float(row["end"]), str(row["speaker"])))

    return filtered, dict(counters)


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
    return sum(values) / len(values) if values else 0.0


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]


def policy_id(policy: dict[str, Any]) -> str:
    parts = [policy["base"]]
    for key in ["min_duration", "min_fast_overlap_sec", "min_fast_overlap_ratio", "merge_gap", "max_speech_ratio", "cap_action"]:
        if key in policy and policy[key] not in (None, -1):
            parts.append(f"{key}{policy[key]}")
    return "__".join(str(part).replace(".", "p") for part in parts)


def summarize_rows(
    policy: dict[str, Any],
    pid: str,
    rows: list[dict[str, Any]],
    counters: dict[str, int] | None = None,
) -> dict[str, Any]:
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


def candidate_policies(policy_set: str) -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = [{"base": "slow"}, {"base": "fast"}]
    if policy_set == "core":
        policies.extend(
            [
                {"base": "slow", "min_duration": 0.2},
                {"base": "slow", "min_duration": 0.4},
                {"base": "slow", "min_fast_overlap_sec": 0.05},
                {"base": "slow", "min_fast_overlap_sec": 0.1},
                {"base": "slow", "min_fast_overlap_ratio": 0.05},
                {"base": "slow", "min_fast_overlap_ratio": 0.1},
                {"base": "slow", "merge_gap": 0.1},
                {"base": "slow", "merge_gap": 0.2},
                {"base": "slow", "max_speech_ratio": 1.2, "cap_action": "fast"},
                {"base": "slow", "max_speech_ratio": 1.4, "cap_action": "fast"},
                {"base": "slow", "max_speech_ratio": 1.2, "cap_action": "drop_unsupported"},
                {"base": "slow", "max_speech_ratio": 1.4, "cap_action": "drop_unsupported"},
            ]
        )
        return policies

    min_durations = [0.1, 0.2, 0.4, 0.6, 1.0]
    overlap_secs = [0.05, 0.1, 0.2, 0.4, 0.8]
    overlap_ratios = [0.05, 0.1, 0.2, 0.4, 0.6]
    merge_gaps = [0.0, 0.1, 0.2, 0.4]
    max_speech_ratios = [1.0, 1.2, 1.4, 1.6, 1.8]

    for value in min_durations:
        policies.append({"base": "slow", "min_duration": value})
    for value in overlap_secs:
        policies.append({"base": "slow", "min_fast_overlap_sec": value})
    for value in overlap_ratios:
        policies.append({"base": "slow", "min_fast_overlap_ratio": value})
    for value in merge_gaps:
        policies.append({"base": "slow", "merge_gap": value})
    for ratio in max_speech_ratios:
        for action in ["fast", "drop_unsupported"]:
            policies.append({"base": "slow", "max_speech_ratio": ratio, "cap_action": action})
    for min_duration in [0.2, 0.4, 0.6]:
        for overlap_sec in [0.05, 0.1, 0.2]:
            policies.append({"base": "slow", "min_duration": min_duration, "min_fast_overlap_sec": overlap_sec})
    for ratio in [1.2, 1.4, 1.6]:
        for overlap_ratio in [0.05, 0.1, 0.2]:
            policies.append(
                {
                    "base": "slow",
                    "min_fast_overlap_ratio": overlap_ratio,
                    "max_speech_ratio": ratio,
                    "cap_action": "drop_unsupported",
                }
            )
    return policies


def evaluate_policy(
    policy: dict[str, Any],
    keys: list[WindowKey],
    fast_by_key: dict[WindowKey, dict[str, Any]],
    slow_by_key: dict[WindowKey, dict[str, Any]],
    collar: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    counters = Counter()
    pid = policy_id(policy)
    for key in keys:
        pred, item_counters = sanitize_segments(policy, fast_by_key[key], slow_by_key[key])
        counters.update(item_counters)
        rows.append(score_segments(key, pid, pred, slow_by_key[key].get("gt_segments", []), collar))
    summary = summarize_rows(policy, pid, rows, dict(counters))
    return summary, rows


def recording_holdout(
    evaluated: dict[str, dict[str, Any]],
    keys: list[WindowKey],
) -> list[dict[str, Any]]:
    out = []
    slow_eval = evaluated["slow"]
    for recording_id in sorted({key[0] for key in keys}):
        train = [key for key in keys if key[0] != recording_id]
        heldout = [key for key in keys if key[0] == recording_id]
        train_summaries = [
            summarize_rows(
                item["policy"],
                policy_id,
                [item["rows_by_key"][key] for key in train],
            )
            for policy_id, item in evaluated.items()
        ]
        best = min(train_summaries, key=lambda row: (row["avg_der"], row["policy_id"]))
        best_eval = evaluated[best["policy_id"]]
        heldout_summary = summarize_rows(
            best_eval["policy"],
            best["policy_id"],
            [best_eval["rows_by_key"][key] for key in heldout],
        )
        slow_summary = summarize_rows(
            slow_eval["policy"],
            "slow",
            [slow_eval["rows_by_key"][key] for key in heldout],
        )
        out.append(
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
    return out


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
        "# Slow Sanitization Policy Search",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Best policy: `{payload['best_policy']['policy_id']}`",
        f"- Best DER: `{payload['best_policy']['avg_der']:.2%}`",
        f"- Slow baseline DER: `{payload['slow_baseline']['avg_der']:.2%}`",
        f"- Delta vs Slow: `{payload['best_delta_vs_slow_pp']:.2f}pp`",
        f"- Bootstrap P(beats Slow): `{payload['bootstrap']['prob_beats_slow']:.1%}`",
        f"- Holdout positive splits: `{payload['holdout_summary']['positive_splits_vs_slow']}/{payload['holdout_summary']['splits']}`",
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
            "- Sanitizers use only predicted Fast/Slow timelines.",
            "- DER/GT is used only after materialization for scoring.",
            "- If the best policy is not robust on bootstrap/holdout, it should not replace the default system path.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast-summary", type=Path, default=Path("outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json"))
    parser.add_argument("--slow-summary", type=Path, default=Path("outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json"))
    parser.add_argument("--collar", type=float, default=0.0)
    parser.add_argument("--bootstrap-samples", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--policy-set", choices=["core", "all"], default="core")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/slow_sanitization_search"))
    args = parser.parse_args()

    fast_by_key = load_summary(args.fast_summary)
    slow_by_key = load_summary(args.slow_summary)
    keys = sorted(set(fast_by_key) & set(slow_by_key))
    policies = candidate_policies(args.policy_set)
    evaluated: dict[str, dict[str, Any]] = {}
    summaries = []
    for idx, policy in enumerate(policies, start=1):
        summary, rows = evaluate_policy(policy, keys, fast_by_key, slow_by_key, args.collar)
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
    holdout = recording_holdout(evaluated, keys)
    best_eval = evaluated[summaries[0]["policy_id"]]
    slow_eval = evaluated["slow"]
    bootstrap = bootstrap_delta(
        best_eval["rows_by_key"],
        slow_eval["rows_by_key"],
        keys,
        args.bootstrap_samples,
        args.seed,
    )
    holdout_final = sum(row["heldout_der"] for row in holdout) / len(holdout)
    holdout_slow = sum(row["heldout_slow_der"] for row in holdout) / len(holdout)
    positive = sum(1 for row in holdout if row["heldout_beats_slow"])
    best_delta = slow_baseline["avg_der"] - summaries[0]["avg_der"]
    status = (
        "robust_sanitizer_found"
        if best_delta > 0 and bootstrap["delta_ci_low"] > 0 and positive == len(holdout)
        else "no_robust_sanitizer_found"
    )
    payload = {
        "runtime_contract": "slow_sanitization_policy_search_no_live_calls_predicted_timeline_features_only",
        "status": status,
        "fast_summary": str(args.fast_summary),
        "slow_summary": str(args.slow_summary),
        "windows": len(keys),
        "policy_set": args.policy_set,
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
    json_path = args.output_dir / "slow_sanitization_policy_search.json"
    md_path = args.output_dir / "slow_sanitization_policy_search.md"
    csv_path = args.output_dir / "slow_sanitization_policy_search.csv"
    holdout_csv = args.output_dir / "slow_sanitization_policy_holdout.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    write_csv(csv_path, summaries)
    write_csv(holdout_csv, holdout)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "status={status} best={best:.2%} slow={slow:.2%} delta={delta:.2f}pp bootstrap_prob={prob:.1%}".format(
            status=status,
            best=summaries[0]["avg_der"],
            slow=slow_baseline["avg_der"],
            delta=best_delta * 100,
            prob=bootstrap["prob_beats_slow"],
        )
    )


if __name__ == "__main__":
    main()
