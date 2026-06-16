#!/usr/bin/env python3
"""Analyze one-shot identity enrollment from diarization summary files.

This script simulates visual one-shot enrollment without requiring a camera:
the first N evaluated windows of each recording are treated as identity
registration windows. Predicted local speaker labels are mapped to ground-truth
speaker IDs by temporal overlap in those enrollment windows, then the fixed
mapping is applied to later windows.

The goal is not to recompute DER. It measures whether a diarization model keeps
local speaker labels stable enough for one-shot enrollment to work. If this
score is low while per-window oracle mapping is high, the next module should be
voiceprint memory / global relabeling.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def speaker_overlaps(pred_segments: list[dict], gt_segments: list[dict]) -> dict[tuple[str, str], float]:
    scores: dict[tuple[str, str], float] = defaultdict(float)
    for pred in pred_segments:
        p_start = float(pred["start"])
        p_end = float(pred["end"])
        p_spk = str(pred["speaker"])
        for gt in gt_segments:
            duration = overlap(p_start, p_end, float(gt["start"]), float(gt["end"]))
            if duration > 0:
                scores[(p_spk, str(gt["speaker"]))] += duration
    return scores


def build_mapping(results: list[dict], enrollment_windows: int, min_overlap: float) -> dict[str, str]:
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for result in results[:enrollment_windows]:
        for key, value in speaker_overlaps(result.get("pred_segments", []), result.get("gt_segments", [])).items():
            totals[key] += value

    mapping: dict[str, str] = {}
    used_pred: set[str] = set()
    used_gt: set[str] = set()
    candidates = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    for (pred_spk, gt_spk), value in candidates:
        if value < min_overlap or pred_spk in used_pred or gt_spk in used_gt:
            continue
        mapping[pred_spk] = gt_spk
        used_pred.add(pred_spk)
        used_gt.add(gt_spk)
    return mapping


def evaluate_fixed_mapping(results: Iterable[dict], mapping: dict[str, str]) -> dict[str, float]:
    total_overlap = 0.0
    correct_overlap = 0.0
    mapped_pred_speech = 0.0
    total_pred_speech = 0.0

    for result in results:
        pred_segments = result.get("pred_segments", [])
        gt_segments = result.get("gt_segments", [])
        for pred in pred_segments:
            p_start = float(pred["start"])
            p_end = float(pred["end"])
            p_dur = max(0.0, p_end - p_start)
            total_pred_speech += p_dur
            mapped_gt = mapping.get(str(pred["speaker"]))
            if mapped_gt is not None:
                mapped_pred_speech += p_dur
            for gt in gt_segments:
                duration = overlap(p_start, p_end, float(gt["start"]), float(gt["end"]))
                if duration <= 0:
                    continue
                total_overlap += duration
                if mapped_gt == str(gt["speaker"]):
                    correct_overlap += duration

    return {
        "fixed_label_accuracy": correct_overlap / total_overlap if total_overlap else 0.0,
        "mapped_pred_speech_rate": mapped_pred_speech / total_pred_speech if total_pred_speech else 0.0,
        "overlap_seconds": total_overlap,
        "correct_overlap_seconds": correct_overlap,
    }


def evaluate_per_window_oracle(results: Iterable[dict], min_overlap: float) -> dict[str, float]:
    total_overlap = 0.0
    correct_overlap = 0.0
    for result in results:
        mapping = build_mapping([result], enrollment_windows=1, min_overlap=min_overlap)
        stats = evaluate_fixed_mapping([result], mapping)
        total_overlap += stats["overlap_seconds"]
        correct_overlap += stats["correct_overlap_seconds"]
    return {
        "per_window_oracle_accuracy": correct_overlap / total_overlap if total_overlap else 0.0,
    }


def analyze_summary(path: Path, enrollment_windows: int, min_overlap: float) -> list[dict]:
    data = json.loads(path.read_text())
    successful = [r for r in data.get("results", []) if r.get("success")]
    by_recording: dict[str, list[dict]] = defaultdict(list)
    for result in successful:
        by_recording[result["recording_id"]].append(result)

    rows = []
    for recording_id, results in sorted(by_recording.items()):
        results.sort(key=lambda r: (r.get("segment_idx", 0), r.get("window_size", 0)))
        mapping = build_mapping(results, enrollment_windows, min_overlap)
        eval_results = results[enrollment_windows:] if len(results) > enrollment_windows else results
        fixed = evaluate_fixed_mapping(eval_results, mapping)
        oracle = evaluate_per_window_oracle(eval_results, min_overlap)
        rows.append(
            {
                "summary": str(path),
                "model_name": data.get("model_name", ""),
                "recording_id": recording_id,
                "windows": len(results),
                "enrollment_windows": min(enrollment_windows, len(results)),
                "mapped_speakers": len(mapping),
                "fixed_label_accuracy": fixed["fixed_label_accuracy"],
                "mapped_pred_speech_rate": fixed["mapped_pred_speech_rate"],
                "per_window_oracle_accuracy": oracle["per_window_oracle_accuracy"],
                "stability_gap": oracle["per_window_oracle_accuracy"] - fixed["fixed_label_accuracy"],
                "mapping": json.dumps(mapping, ensure_ascii=False, sort_keys=True),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", nargs="+", type=Path, help="summary.json files")
    parser.add_argument("--enrollment-windows", type=int, default=1)
    parser.add_argument("--min-overlap", type=float, default=0.2)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    rows = []
    for path in args.summary:
        rows.extend(analyze_summary(path, args.enrollment_windows, args.min_overlap))

    if not rows:
        raise SystemExit("No successful results with pred_segments/gt_segments found.")

    fieldnames = list(rows[0].keys())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print("One-shot identity memory simulation")
    print("summary_count=%d recording_count=%d" % (len(args.summary), len(rows)))
    by_model: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_model[row["model_name"]].append(row)
        print(
            "%s %-22s fixed=%.1f%% oracle=%.1f%% gap=%.1f%% mapped=%d/%s"
            % (
                row["recording_id"],
                row["model_name"],
                row["fixed_label_accuracy"] * 100,
                row["per_window_oracle_accuracy"] * 100,
                row["stability_gap"] * 100,
                row["mapped_speakers"],
                row["mapping"],
            )
        )
    print("\nAverages by model")
    for model_name, model_rows in sorted(by_model.items()):
        fixed = sum(row["fixed_label_accuracy"] for row in model_rows) / len(model_rows)
        oracle = sum(row["per_window_oracle_accuracy"] for row in model_rows) / len(model_rows)
        mapped = sum(row["mapped_pred_speech_rate"] for row in model_rows) / len(model_rows)
        print(
            "%-22s fixed=%.1f%% oracle=%.1f%% gap=%.1f%% mapped_speech=%.1f%%"
            % (model_name, fixed * 100, oracle * 100, (oracle - fixed) * 100, mapped * 100)
        )
    if args.output:
        print("CSV:", args.output)


if __name__ == "__main__":
    main()
