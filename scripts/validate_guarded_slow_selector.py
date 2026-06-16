#!/usr/bin/env python3
"""Validate the guarded Slow selector used by the offline system CLI.

Policy family:
    use Slow by default; fall back to Fast when runtime-safe gate evidence
    reports at least N guard_or_quarantine patches for the window. The default
    validation also blocks Fast fallback when Fast predicts fewer speakers than
    Slow for the same window.

The runtime selector uses only gate categories and cached Fast/Slow outputs.
DER is used here only for offline validation and threshold selection.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


WindowKey = tuple[str, int, int]


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def key_from_row(row: dict[str, Any]) -> WindowKey:
    return (str(row["recording_id"]), int(float(row["window_size"])), int(float(row["segment_idx"])))


def window_id(key: WindowKey) -> str:
    return f"{key[0]}:{key[1]}:{key[2]}"


def load_timeline_results(path: Path) -> dict[WindowKey, dict[str, dict[str, Any]]]:
    by_key: dict[WindowKey, dict[str, dict[str, Any]]] = defaultdict(dict)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = key_from_row(row)
            by_key[key][row["variant"]] = row
    return by_key


def load_guard_counts(path: Path) -> dict[WindowKey, int]:
    counts: Counter[WindowKey] = Counter()
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("gate_category") == "guard_or_quarantine":
                counts[key_from_row(row)] += 1
    return dict(counts)


def metric(row: dict[str, Any], field: str) -> float:
    return as_float(row.get(field), default=float("nan"))


def average(values: list[float]) -> float:
    values = [value for value in values if value == value]
    return sum(values) / len(values) if values else 0.0


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]


def choose_variant(
    key: WindowKey,
    by_key: dict[WindowKey, dict[str, dict[str, Any]]],
    guard_count: int,
    threshold: int,
    speaker_count_safe: bool,
) -> tuple[str, bool]:
    if guard_count < threshold:
        return "slow_base", False
    if speaker_count_safe:
        fast_speaker_count = int(as_float(by_key[key]["fast_base"].get("spk_count_pred")))
        slow_speaker_count = int(as_float(by_key[key]["slow_base"].get("spk_count_pred")))
        if fast_speaker_count < slow_speaker_count:
            return "slow_base", True
    return "fast_base", False


def score_threshold(
    keys: list[WindowKey],
    by_key: dict[WindowKey, dict[str, dict[str, Any]]],
    guard_counts: dict[WindowKey, int],
    threshold: int,
    speaker_count_safe: bool,
) -> dict[str, Any]:
    chosen = []
    source_counts: Counter[str] = Counter()
    fallback_blocked_by_speaker_count = 0
    for key in keys:
        variant, blocked = choose_variant(key, by_key, guard_counts.get(key, 0), threshold, speaker_count_safe)
        chosen.append(by_key[key][variant])
        source_counts[variant] += 1
        fallback_blocked_by_speaker_count += int(blocked)
    slow_rows = [by_key[key]["slow_base"] for key in keys]
    fast_rows = [by_key[key]["fast_base"] for key in keys]
    final_der = average([metric(row, "der") for row in chosen])
    slow_der = average([metric(row, "der") for row in slow_rows])
    fast_der = average([metric(row, "der") for row in fast_rows])
    return {
        "threshold": threshold,
        "windows": len(keys),
        "fast_fallback_windows": source_counts["fast_base"],
        "slow_windows": source_counts["slow_base"],
        "fallback_blocked_by_speaker_count": fallback_blocked_by_speaker_count,
        "fast_der": fast_der,
        "slow_der": slow_der,
        "final_der": final_der,
        "final_miss_rate": average([metric(row, "miss_rate") for row in chosen]),
        "final_fa_rate": average([metric(row, "fa_rate") for row in chosen]),
        "final_conf_rate": average([metric(row, "conf_rate") for row in chosen]),
        "delta_vs_slow": slow_der - final_der,
        "delta_vs_slow_pp": (slow_der - final_der) * 100,
        "beats_slow": final_der < slow_der,
        "delta_vs_fast": fast_der - final_der,
        "delta_vs_fast_pp": (fast_der - final_der) * 100,
        "beats_fast": final_der < fast_der,
    }


def per_recording_rows(
    keys: list[WindowKey],
    by_key: dict[WindowKey, dict[str, dict[str, Any]]],
    guard_counts: dict[WindowKey, int],
    threshold: int,
    speaker_count_safe: bool,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[WindowKey]] = defaultdict(list)
    for key in keys:
        grouped[key[0]].append(key)
    rows = []
    for recording_id, recording_keys in sorted(grouped.items()):
        scored = score_threshold(recording_keys, by_key, guard_counts, threshold, speaker_count_safe)
        rows.append(
            {
                "recording_id": recording_id,
                **scored,
                "positive_vs_slow": scored["delta_vs_slow"] > 0,
            }
        )
    return rows


def recording_holdout(
    keys: list[WindowKey],
    by_key: dict[WindowKey, dict[str, dict[str, Any]]],
    guard_counts: dict[WindowKey, int],
    thresholds: list[int],
    speaker_count_safe: bool,
) -> list[dict[str, Any]]:
    recordings = sorted({key[0] for key in keys})
    rows = []
    for recording_id in recordings:
        train_keys = [key for key in keys if key[0] != recording_id]
        heldout_keys = [key for key in keys if key[0] == recording_id]
        train_scores = [score_threshold(train_keys, by_key, guard_counts, threshold, speaker_count_safe) for threshold in thresholds]
        best_train = min(train_scores, key=lambda row: (row["final_der"], row["threshold"]))
        heldout = score_threshold(heldout_keys, by_key, guard_counts, int(best_train["threshold"]), speaker_count_safe)
        rows.append(
            {
                "heldout_recording_id": recording_id,
                "selected_threshold": best_train["threshold"],
                "train_final_der": best_train["final_der"],
                "train_slow_der": best_train["slow_der"],
                "heldout_windows": heldout["windows"],
                "heldout_fast_fallback_windows": heldout["fast_fallback_windows"],
                "heldout_slow_der": heldout["slow_der"],
                "heldout_final_der": heldout["final_der"],
                "heldout_delta_vs_slow": heldout["delta_vs_slow"],
                "heldout_delta_vs_slow_pp": heldout["delta_vs_slow_pp"],
                "heldout_beats_slow": heldout["beats_slow"],
            }
        )
    return rows


def bootstrap_delta(
    keys: list[WindowKey],
    by_key: dict[WindowKey, dict[str, dict[str, Any]]],
    guard_counts: dict[WindowKey, int],
    threshold: int,
    speaker_count_safe: bool,
    samples: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    deltas = []
    final_ders = []
    slow_ders = []
    for _ in range(samples):
        sample_keys = [rng.choice(keys) for _ in keys]
        scored = score_threshold(sample_keys, by_key, guard_counts, threshold, speaker_count_safe)
        deltas.append(scored["delta_vs_slow"])
        final_ders.append(scored["final_der"])
        slow_ders.append(scored["slow_der"])
    return {
        "samples": samples,
        "seed": seed,
        "threshold": threshold,
        "mean_delta_vs_slow": average(deltas),
        "delta_ci_low": percentile(deltas, 0.025),
        "delta_ci_high": percentile(deltas, 0.975),
        "prob_beats_slow": sum(1 for value in deltas if value > 0) / len(deltas) if deltas else 0.0,
        "mean_final_der": average(final_ders),
        "mean_slow_der": average(slow_ders),
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
    fixed = payload["fixed_policy"]
    bootstrap = payload["bootstrap"]
    lines = [
        "# Guarded Slow Selector Validation",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Fixed policy: `{payload['policy_id']}` with threshold `{fixed['threshold']}`",
        f"- Windows: `{fixed['windows']}`",
        f"- Final DER: `{fixed['final_der']:.2%}`",
        f"- Slow baseline DER: `{fixed['slow_der']:.2%}`",
        f"- Delta vs slow: `{fixed['delta_vs_slow_pp']:.2f}pp`",
        f"- Beats slow: `{fixed['beats_slow']}`",
        f"- Fast fallback windows: `{fixed['fast_fallback_windows']}`",
        f"- Fallback blocked by speaker count: `{fixed.get('fallback_blocked_by_speaker_count', 0)}`",
        f"- Bootstrap P(beats slow): `{bootstrap['prob_beats_slow']:.1%}`",
        f"- Bootstrap delta CI: `{bootstrap['delta_ci_low'] * 100:.2f}pp` to `{bootstrap['delta_ci_high'] * 100:.2f}pp`",
        "",
        "## Threshold Scan",
        "",
        "| Threshold | Final DER | Slow DER | Delta | Fast fallback windows | Speaker blocks | Beats slow |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["threshold_scan"]:
        lines.append(
            f"| {row['threshold']} | {row['final_der']:.2%} | {row['slow_der']:.2%} | {row['delta_vs_slow_pp']:.2f}pp | {row['fast_fallback_windows']} | {row.get('fallback_blocked_by_speaker_count', 0)} | {row['beats_slow']} |"
        )
    lines.extend(
        [
            "",
            "## Recording Holdout",
            "",
            "| Heldout recording | Selected threshold | Final DER | Slow DER | Delta | Beats slow |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["recording_holdout"]:
        lines.append(
            f"| {row['heldout_recording_id']} | {row['selected_threshold']} | {row['heldout_final_der']:.2%} | {row['heldout_slow_der']:.2%} | {row['heldout_delta_vs_slow_pp']:.2f}pp | {row['heldout_beats_slow']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Runtime selection uses only `guard_or_quarantine` counts and predicted Fast/Slow speaker counts.",
            "- DER is used only for offline validation and threshold ranking.",
            "- This is still development-pool validation; true held-out recordings remain a separate blocker.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline-results", type=Path, default=Path("outputs/rule_writeback_timeline_120/rule_writeback_timeline_results.csv"))
    parser.add_argument("--gate-decisions", type=Path, default=Path("outputs/writeback_gate_120/gate_decisions.csv"))
    parser.add_argument("--thresholds", default="1,2,3,5,10,15,20,999")
    parser.add_argument("--fixed-threshold", type=int, default=1)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--disable-speaker-count-safe", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/system_selector_validation"))
    args = parser.parse_args()

    by_key = load_timeline_results(args.timeline_results)
    guard_counts = load_guard_counts(args.gate_decisions)
    keys = sorted(key for key, variants in by_key.items() if {"fast_base", "slow_base"}.issubset(variants))
    thresholds = [int(item.strip()) for item in args.thresholds.split(",") if item.strip()]
    speaker_count_safe = not args.disable_speaker_count_safe
    policy_id = "slow_guarded_fast_fallback_speaker_count_safe" if speaker_count_safe else "slow_guarded_fast_fallback"

    threshold_scan = [score_threshold(keys, by_key, guard_counts, threshold, speaker_count_safe) for threshold in thresholds]
    threshold_scan.sort(key=lambda row: (row["final_der"], row["threshold"]))
    fixed_policy = score_threshold(keys, by_key, guard_counts, args.fixed_threshold, speaker_count_safe)
    recording_rows = per_recording_rows(keys, by_key, guard_counts, args.fixed_threshold, speaker_count_safe)
    holdout_rows = recording_holdout(keys, by_key, guard_counts, thresholds, speaker_count_safe)
    bootstrap = bootstrap_delta(keys, by_key, guard_counts, args.fixed_threshold, speaker_count_safe, args.bootstrap_samples, args.seed)

    weighted_holdout_final = average([row["heldout_final_der"] for row in holdout_rows])
    weighted_holdout_slow = average([row["heldout_slow_der"] for row in holdout_rows])
    if (
        fixed_policy["beats_slow"]
        and bootstrap["delta_ci_low"] > 0
        and bootstrap["prob_beats_slow"] >= 0.95
    ):
        status = "pass_robust_dev_validation"
    elif fixed_policy["beats_slow"]:
        status = "weak_dev_gain_not_robust"
    else:
        status = "fail_does_not_beat_slow"

    payload = {
        "runtime_contract": "guarded_slow_selector_validation_no_live_calls_runtime_features_only",
        "status": status,
        "policy_id": policy_id,
        "timeline_results": str(args.timeline_results),
        "gate_decisions": str(args.gate_decisions),
        "runtime_feature_surface": ["gate_category=guard_or_quarantine", "fast_base.spk_count_pred", "slow_base.spk_count_pred"],
        "no_live_calls_performed": True,
        "no_deepseek_api_calls": True,
        "metric_claim_boundary": "development_pool_validation_not_true_heldout",
        "fixed_policy": fixed_policy,
        "threshold_scan": threshold_scan,
        "per_recording": recording_rows,
        "recording_holdout": holdout_rows,
        "recording_holdout_summary": {
            "splits": len(holdout_rows),
            "positive_splits_vs_slow": sum(1 for row in holdout_rows if row["heldout_beats_slow"]),
            "weighted_heldout_final_der": weighted_holdout_final,
            "weighted_heldout_slow_der": weighted_holdout_slow,
            "weighted_heldout_delta_vs_slow": weighted_holdout_slow - weighted_holdout_final,
            "weighted_heldout_delta_vs_slow_pp": (weighted_holdout_slow - weighted_holdout_final) * 100,
        },
        "bootstrap": bootstrap,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "guarded_slow_selector_validation.json"
    md_path = args.output_dir / "guarded_slow_selector_validation.md"
    threshold_csv = args.output_dir / "guarded_slow_selector_threshold_scan.csv"
    recording_csv = args.output_dir / "guarded_slow_selector_per_recording.csv"
    holdout_csv = args.output_dir / "guarded_slow_selector_recording_holdout.csv"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    write_csv(threshold_csv, threshold_scan)
    write_csv(recording_csv, recording_rows)
    write_csv(holdout_csv, holdout_rows)

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "fixed threshold={threshold} final={final:.2%} slow={slow:.2%} delta={delta:.2f}pp bootstrap_prob={prob:.1%}".format(
            threshold=args.fixed_threshold,
            final=fixed_policy["final_der"],
            slow=fixed_policy["slow_der"],
            delta=fixed_policy["delta_vs_slow_pp"],
            prob=bootstrap["prob_beats_slow"],
        )
    )


if __name__ == "__main__":
    main()
