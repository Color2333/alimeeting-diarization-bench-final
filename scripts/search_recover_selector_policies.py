#!/usr/bin/env python3
"""Search deployable recover writeback selector policies.

The policy chooses, per window, among already materialized timeline variants:

- fast_base: do not write back recover patches;
- rule_recover_matched_label: add recover patches with matched Fast labels;
- rule_recover_uncovered_only: add recover patches only where Fast has no speech.

Ground truth is used only to score candidate policies after the choice is made.
Policy features are deployable Fast/Slow prediction statistics.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable


MetricRow = dict[str, str]
WindowKey = tuple[str, int, int]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def key_from_row(row: dict[str, str]) -> WindowKey:
    return (row["recording_id"], int(float(row["window_size"])), int(float(row["segment_idx"])))


def as_float(value: str | float | int | None, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def index_results(rows: list[dict[str, str]]) -> dict[WindowKey, dict[str, dict[str, str]]]:
    by_key: dict[WindowKey, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        by_key[key_from_row(row)][row["variant"]] = row
    return by_key


def recover_windows(gate_rows: list[dict[str, str]]) -> dict[WindowKey, list[dict[str, str]]]:
    grouped: dict[WindowKey, list[dict[str, str]]] = defaultdict(list)
    for row in gate_rows:
        if row.get("gate_category") != "rule_recover_writeback":
            continue
        grouped[key_from_row(row)].append(row)
    return grouped


def window_features(window_rows: list[dict[str, str]], recover_by_key: dict[WindowKey, list[dict[str, str]]]) -> dict[WindowKey, dict[str, float]]:
    features = {}
    for row in window_rows:
        key = key_from_row(row)
        recover_rows = recover_by_key.get(key, [])
        fast_speech = as_float(row.get("fast_speech"))
        slow_speech = as_float(row.get("slow_speech"))
        total_recover_duration = sum(as_float(item.get("duration")) for item in recover_rows)
        max_recover_duration = max([as_float(item.get("duration")) for item in recover_rows] or [0.0])
        avg_recover_support = (
            sum(as_float(item.get("support_ratio")) for item in recover_rows) / len(recover_rows)
            if recover_rows
            else 0.0
        )
        features[key] = {
            "fast_spk": as_float(row.get("fast_spk_count_pred")),
            "slow_spk": as_float(row.get("slow_spk_count_pred")),
            "fast_speech": fast_speech,
            "slow_speech": slow_speech,
            "speech_ratio": fast_speech / slow_speech if slow_speech else 0.0,
            "speech_diff": slow_speech - fast_speech,
            "recover_patches": float(len(recover_rows)),
            "total_recover_duration": total_recover_duration,
            "max_recover_duration": max_recover_duration,
            "avg_recover_support": avg_recover_support,
        }
    return features


def policy_functions() -> list[tuple[str, Callable[[dict[str, float]], str]]]:
    policies: list[tuple[str, Callable[[dict[str, float]], str]]] = [
        ("all_matched", lambda f: "rule_recover_matched_label"),
        ("all_uncovered", lambda f: "rule_recover_uncovered_only"),
        ("spk_gt", lambda f: "rule_recover_matched_label" if f["slow_spk"] > f["fast_spk"] else "rule_recover_uncovered_only"),
        ("spk_ge", lambda f: "rule_recover_matched_label" if f["slow_spk"] >= f["fast_spk"] else "rule_recover_uncovered_only"),
        ("spk_gt_else_fast", lambda f: "rule_recover_matched_label" if f["slow_spk"] > f["fast_spk"] else "fast_base"),
    ]
    thresholds = [round(value / 100, 2) for value in range(25, 111, 5)]
    durations = [0.2, 0.6, 1.0, 2.0, 4.0]
    for threshold in thresholds:
        policies.append(
            (
                f"ratio_le_{threshold:.2f}_else_uncovered",
                lambda f, threshold=threshold: "rule_recover_matched_label"
                if f["speech_ratio"] <= threshold
                else "rule_recover_uncovered_only",
            )
        )
        policies.append(
            (
                f"spk_gt_or_ratio_le_{threshold:.2f}",
                lambda f, threshold=threshold: "rule_recover_matched_label"
                if f["slow_spk"] > f["fast_spk"] or f["speech_ratio"] <= threshold
                else "rule_recover_uncovered_only",
            )
        )
        policies.append(
            (
                f"spk_ge_or_ratio_le_{threshold:.2f}",
                lambda f, threshold=threshold: "rule_recover_matched_label"
                if f["slow_spk"] >= f["fast_spk"] or f["speech_ratio"] <= threshold
                else "rule_recover_uncovered_only",
            )
        )
        policies.append(
            (
                f"spk_gt_and_ratio_le_{threshold:.2f}",
                lambda f, threshold=threshold: "rule_recover_matched_label"
                if f["slow_spk"] > f["fast_spk"] and f["speech_ratio"] <= threshold
                else "rule_recover_uncovered_only",
            )
        )
    for min_duration in durations:
        policies.append(
            (
                f"spk_gt_min_recover_{min_duration:.1f}",
                lambda f, min_duration=min_duration: (
                    "fast_base"
                    if f["total_recover_duration"] < min_duration
                    else (
                        "rule_recover_matched_label"
                        if f["slow_spk"] > f["fast_spk"]
                        else "rule_recover_uncovered_only"
                    )
                ),
            )
        )
    return policies


def average(rows: list[dict[str, str]], field: str) -> float:
    values = [as_float(row.get(field)) for row in rows if row.get(field) not in (None, "")]
    return sum(values) / len(values) if values else 0.0


def score_policy(
    name: str,
    policy: Callable[[dict[str, float]], str],
    by_key: dict[WindowKey, dict[str, dict[str, str]]],
    features: dict[WindowKey, dict[str, float]],
    recover_by_key: dict[WindowKey, list[dict[str, str]]],
) -> dict[str, str]:
    chosen_rows = []
    choices: Counter[str] = Counter()
    for key, variants in by_key.items():
        if key not in recover_by_key:
            choice = "fast_base"
        else:
            choice = policy(features[key])
        if choice not in variants:
            raise RuntimeError(f"Missing materialized variant {choice} for {key}")
        choices[choice] += 1
        chosen_rows.append(variants[choice])
    return {
        "policy": name,
        "windows": str(len(chosen_rows)),
        "recover_windows": str(len(recover_by_key)),
        "avg_der": f"{average(chosen_rows, 'der'):.4f}",
        "avg_miss_rate": f"{average(chosen_rows, 'miss_rate'):.4f}",
        "avg_fa_rate": f"{average(chosen_rows, 'fa_rate'):.4f}",
        "avg_conf_rate": f"{average(chosen_rows, 'conf_rate'):.4f}",
        "matched_windows": str(choices["rule_recover_matched_label"]),
        "uncovered_windows": str(choices["rule_recover_uncovered_only"]),
        "fast_windows": str(choices["fast_base"]),
        "choice_counts": " / ".join(f"{key} {value}" for key, value in sorted(choices.items())),
    }


def write_markdown(rows: list[dict[str, str]], output: Path, top_n: int) -> None:
    lines = [
        "# Recover Selector Policy Search",
        "",
        "| Rank | Policy | DER | Miss | FA | Conf | Matched | Uncovered | Fast |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(rows[:top_n], start=1):
        lines.append(
            "| {rank} | {policy} | {der:.2%} | {miss:.2%} | {fa:.2%} | {conf:.2%} | {matched} | {uncovered} | {fast} |".format(
                rank=idx,
                policy=row["policy"],
                der=float(row["avg_der"]),
                miss=float(row["avg_miss_rate"]),
                fa=float(row["avg_fa_rate"]),
                conf=float(row["avg_conf_rate"]),
                matched=row["matched_windows"],
                uncovered=row["uncovered_windows"],
                fast=row["fast_windows"],
            )
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Policies use only deployable Fast/Slow prediction features.",
            "- Ground truth is used only to rank policies after materialized timeline scoring.",
            "- The selected policy should be validated on a larger held-out sample before being treated as final.",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline-results", type=Path, default=Path("outputs/rule_writeback_timeline/rule_writeback_timeline_results.csv"))
    parser.add_argument("--window-features", type=Path, default=Path("outputs/segment_patches/sortformer_diarizen_48_patches_windows.csv"))
    parser.add_argument("--gate-decisions", type=Path, default=Path("outputs/writeback_gate/gate_decisions.csv"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/rule_writeback_timeline/recover_selector_policy_search.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/rule_writeback_timeline/recover_selector_policy_search.md"))
    parser.add_argument("--top-n", type=int, default=15)
    args = parser.parse_args()

    by_key = index_results(load_csv(args.timeline_results))
    recover_by_key = recover_windows(load_csv(args.gate_decisions))
    features = window_features(load_csv(args.window_features), recover_by_key)

    rows = [
        score_policy(name, policy, by_key, features, recover_by_key)
        for name, policy in policy_functions()
    ]
    rows.sort(key=lambda row: (float(row["avg_der"]), float(row["avg_fa_rate"]), float(row["avg_conf_rate"])))

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    write_markdown(rows, args.output_md, args.top_n)

    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")
    print("best", rows[0])


if __name__ == "__main__":
    main()
