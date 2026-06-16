#!/usr/bin/env python3
"""Prototype Fast-to-Slow correction routing for diarization summaries.

This is a window-level prototype:

- Fast Agent: low-latency Sortformer/Streaming Sortformer output.
- Slow Agent: DiariZen-style offline output.
- Correction patch: choose the Fast or Slow timeline for each benchmark window.

The deployable heuristic only looks at Fast/Slow predictions, not ground truth.
Ground truth is used after routing to score the chosen output.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


METRIC_FIELDS = ["der", "miss_rate", "fa_rate", "conf_rate"]


def speech_seconds(segments: list[dict]) -> float:
    return sum(max(0.0, float(seg["end"]) - float(seg["start"])) for seg in segments)


def key_for(result: dict) -> tuple[str, int, int]:
    return (
        str(result["recording_id"]),
        int(result["window_size"]),
        int(result["segment_idx"]),
    )


def load_successful(path: Path) -> tuple[dict, dict[tuple[str, int, int], dict]]:
    data = json.loads(path.read_text())
    return data, {key_for(result): result for result in data.get("results", []) if result.get("success")}


def average(rows: list[dict], field: str) -> float:
    values = [float(row[field]) for row in rows]
    return sum(values) / len(values) if values else 0.0


def summarize(rows: list[dict], prefix: str = "") -> dict[str, float]:
    return {
        f"{prefix}avg_der": average(rows, "der"),
        f"{prefix}avg_miss_rate": average(rows, "miss_rate"),
        f"{prefix}avg_fa_rate": average(rows, "fa_rate"),
        f"{prefix}avg_conf_rate": average(rows, "conf_rate"),
    }


def choose_by_heuristic(fast: dict, slow: dict, args: argparse.Namespace) -> tuple[str, str]:
    fast_speech = speech_seconds(fast.get("pred_segments", []))
    slow_speech = speech_seconds(slow.get("pred_segments", []))
    fast_spk = int(fast["spk_count_pred"])
    slow_spk = int(slow["spk_count_pred"])

    if slow_speech <= 1e-6:
        return "fast", "slow_empty"

    speech_ratio = fast_speech / slow_speech

    # Guard against a pathological Slow output before using it as correction.
    if speech_ratio < args.slow_pathology_ratio and slow_spk >= fast_spk + 2:
        return "fast", "slow_possible_over_speech"

    reasons = []
    if speech_ratio <= args.fast_too_short_ratio:
        reasons.append("recover_miss")
    if speech_ratio >= args.fast_too_long_ratio:
        reasons.append("suppress_fa")
    if fast_spk < slow_spk:
        reasons.append("speaker_count_recover")
    if fast_spk > slow_spk + 1 and speech_ratio >= 1.15:
        reasons.append("speaker_count_suppress")

    if reasons:
        return "slow", "+".join(reasons)
    return "fast", "fast_ok"


def row_from_choice(key: tuple[str, int, int], fast: dict, slow: dict, choice: str, patch_type: str) -> dict:
    chosen = slow if choice == "slow" else fast
    fast_speech = speech_seconds(fast.get("pred_segments", []))
    slow_speech = speech_seconds(slow.get("pred_segments", []))
    return {
        "recording_id": key[0],
        "window_size": key[1],
        "segment_idx": key[2],
        "choice": choice,
        "patch_type": patch_type,
        "fast_der": fast["der"],
        "slow_der": slow["der"],
        "chosen_der": chosen["der"],
        "fast_miss_rate": fast["miss_rate"],
        "slow_miss_rate": slow["miss_rate"],
        "chosen_miss_rate": chosen["miss_rate"],
        "fast_fa_rate": fast["fa_rate"],
        "slow_fa_rate": slow["fa_rate"],
        "chosen_fa_rate": chosen["fa_rate"],
        "fast_conf_rate": fast["conf_rate"],
        "slow_conf_rate": slow["conf_rate"],
        "chosen_conf_rate": chosen["conf_rate"],
        "fast_spk_count_pred": fast["spk_count_pred"],
        "slow_spk_count_pred": slow["spk_count_pred"],
        "gt_spk_count": fast["spk_count_gt"],
        "fast_speech": fast_speech,
        "slow_speech": slow_speech,
        "fast_slow_speech_ratio": fast_speech / slow_speech if slow_speech else 0.0,
        "improved_over_fast": float(chosen["der"]) < float(fast["der"]),
        "regressed_vs_fast": float(chosen["der"]) > float(fast["der"]),
        "slow_better_than_fast": float(slow["der"]) < float(fast["der"]),
        "fast_latency": fast.get("latency", 0.0),
        "slow_latency": slow.get("latency", 0.0),
    }


def make_result_row(result: dict) -> dict:
    return {field: float(result[field]) for field in METRIC_FIELDS}


def print_summary(label: str, rows: list[dict]) -> None:
    metrics = summarize(rows)
    print(
        "%-26s DER=%.2f%% Miss=%.2f%% FA=%.2f%% Conf=%.2f%%"
        % (
            label,
            metrics["avg_der"] * 100,
            metrics["avg_miss_rate"] * 100,
            metrics["avg_fa_rate"] * 100,
            metrics["avg_conf_rate"] * 100,
        )
    )


def prefixed_summary(rows: list[dict], prefix: str) -> dict[str, float]:
    summary = summarize(rows)
    return {f"{prefix}_{key}": value for key, value in summary.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast-summary", required=True, type=Path)
    parser.add_argument("--slow-summary", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/fast_slow_correction/patches.csv"))
    parser.add_argument("--summary-output", type=Path, default=None)
    parser.add_argument("--fast-too-short-ratio", type=float, default=0.72)
    parser.add_argument("--fast-too-long-ratio", type=float, default=1.65)
    parser.add_argument("--slow-pathology-ratio", type=float, default=0.35)
    args = parser.parse_args()

    fast_data, fast_by_key = load_successful(args.fast_summary)
    slow_data, slow_by_key = load_successful(args.slow_summary)
    common_keys = sorted(set(fast_by_key) & set(slow_by_key))
    if not common_keys:
        raise SystemExit("No matching successful windows between fast and slow summaries")

    patch_rows = []
    fast_metric_rows = []
    slow_metric_rows = []
    heuristic_metric_rows = []
    oracle_metric_rows = []
    slow_better_count = 0
    heuristic_selected_slow = 0
    heuristic_covered_better = 0
    heuristic_regressions = 0

    for key in common_keys:
        fast = fast_by_key[key]
        slow = slow_by_key[key]
        fast_metric_rows.append(make_result_row(fast))
        slow_metric_rows.append(make_result_row(slow))

        if float(slow["der"]) < float(fast["der"]):
            slow_better_count += 1

        choice, patch_type = choose_by_heuristic(fast, slow, args)
        if choice == "slow":
            heuristic_selected_slow += 1
            if float(slow["der"]) < float(fast["der"]):
                heuristic_covered_better += 1
            if float(slow["der"]) > float(fast["der"]):
                heuristic_regressions += 1

        patch_row = row_from_choice(key, fast, slow, choice, patch_type)
        patch_rows.append(patch_row)
        heuristic_metric_rows.append(
            {
                "der": float(patch_row["chosen_der"]),
                "miss_rate": float(patch_row["chosen_miss_rate"]),
                "fa_rate": float(patch_row["chosen_fa_rate"]),
                "conf_rate": float(patch_row["chosen_conf_rate"]),
            }
        )

        oracle = slow if float(slow["der"]) < float(fast["der"]) else fast
        oracle_metric_rows.append(make_result_row(oracle))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(patch_rows[0].keys())
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(patch_rows)

    summary_output = args.summary_output or args.output.with_name(args.output.stem + "_summary.json")
    fixable = slow_better_count
    coverage = heuristic_covered_better / fixable if fixable else 0.0
    precision = heuristic_covered_better / heuristic_selected_slow if heuristic_selected_slow else 0.0
    summary = {
        "fast_model": fast_data.get("model_name"),
        "slow_model": slow_data.get("model_name"),
        "windows": len(common_keys),
        "patch_csv": str(args.output),
        "fast_summary": str(args.fast_summary),
        "slow_summary": str(args.slow_summary),
        **prefixed_summary(fast_metric_rows, "fast_only"),
        **prefixed_summary(slow_metric_rows, "slow_only"),
        **prefixed_summary(heuristic_metric_rows, "heuristic"),
        **prefixed_summary(oracle_metric_rows, "oracle_selector"),
        "slow_better_windows": slow_better_count,
        "heuristic_selected_slow": heuristic_selected_slow,
        "heuristic_covered_better": heuristic_covered_better,
        "heuristic_coverage": coverage,
        "heuristic_precision": precision,
        "heuristic_regressions": heuristic_regressions,
        "fast_to_slow_der_improvement": average(fast_metric_rows, "der") - average(slow_metric_rows, "der"),
        "fast_to_heuristic_der_improvement": average(fast_metric_rows, "der") - average(heuristic_metric_rows, "der"),
        "fast_to_oracle_der_improvement": average(fast_metric_rows, "der") - average(oracle_metric_rows, "der"),
    }
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Fast-to-Slow correction prototype")
    print("fast=%s" % fast_data.get("model_name"))
    print("slow=%s" % slow_data.get("model_name"))
    print("windows=%d patch_csv=%s" % (len(common_keys), args.output))
    print_summary("Fast only", fast_metric_rows)
    print_summary("Slow only", slow_metric_rows)
    print_summary("Heuristic Fast+Slow", heuristic_metric_rows)
    print_summary("Oracle selector upper", oracle_metric_rows)

    print(
        "routing selected_slow=%d/%d slow_better=%d coverage=%.1f%% precision=%.1f%% regressions=%d"
        % (
            heuristic_selected_slow,
            len(common_keys),
            slow_better_count,
            coverage * 100,
            precision * 100,
            heuristic_regressions,
        )
    )
    print("summary_json=%s" % summary_output)

    print("\nLargest heuristic regressions")
    regressions = [row for row in patch_rows if row["regressed_vs_fast"]]
    regressions.sort(key=lambda row: float(row["chosen_der"]) - float(row["fast_der"]), reverse=True)
    for row in regressions[:8]:
        print(
            "%s seg=%s %s fast=%.1f%% slow=%.1f%% chosen=%.1f%% ratio=%.2f spk=%s/%s gt=%s"
            % (
                row["recording_id"],
                row["segment_idx"],
                row["patch_type"],
                float(row["fast_der"]) * 100,
                float(row["slow_der"]) * 100,
                float(row["chosen_der"]) * 100,
                float(row["fast_slow_speech_ratio"]),
                row["fast_spk_count_pred"],
                row["slow_spk_count_pred"],
                row["gt_spk_count"],
            )
        )


if __name__ == "__main__":
    main()
