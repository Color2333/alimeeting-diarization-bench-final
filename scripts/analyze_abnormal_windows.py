#!/usr/bin/env python3
"""Find abnormal diarization windows from benchmark summary files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def speech_seconds(segments: list[dict]) -> float:
    return sum(max(0.0, float(seg["end"]) - float(seg["start"])) for seg in segments)


def reason_for(row: dict, der_threshold: float, fa_threshold: float, miss_threshold: float) -> str:
    reasons = []
    if row["der"] >= der_threshold:
        reasons.append("high_der")
    if row["fa_rate"] >= fa_threshold:
        reasons.append("high_fa")
    if row["miss_rate"] >= miss_threshold:
        reasons.append("high_miss")
    if row["speech_ratio"] >= 2.0:
        reasons.append("pred_speech_too_long")
    if row["speech_ratio"] <= 0.5:
        reasons.append("pred_speech_too_short")
    if row["spk_count_pred"] != row["spk_count_gt"]:
        reasons.append("speaker_count_mismatch")
    return ",".join(reasons)


def analyze_summary(path: Path, args: argparse.Namespace) -> list[dict]:
    data = json.loads(path.read_text())
    rows = []
    for result in data.get("results", []):
        if not result.get("success"):
            continue
        pred_speech = speech_seconds(result.get("pred_segments", []))
        gt_speech = speech_seconds(result.get("gt_segments", []))
        speech_ratio = pred_speech / gt_speech if gt_speech else 0.0
        row = {
            "summary": str(path),
            "model_name": data.get("model_name", ""),
            "recording_id": result["recording_id"],
            "window_size": int(result["window_size"]),
            "segment_idx": int(result["segment_idx"]),
            "der": float(result["der"]),
            "miss_rate": float(result["miss_rate"]),
            "fa_rate": float(result["fa_rate"]),
            "conf_rate": float(result["conf_rate"]),
            "spk_count_pred": int(result["spk_count_pred"]),
            "spk_count_gt": int(result["spk_count_gt"]),
            "pred_speech": pred_speech,
            "gt_speech": gt_speech,
            "speech_ratio": speech_ratio,
        }
        row["reason"] = reason_for(row, args.der_threshold, args.fa_threshold, args.miss_threshold)
        if row["reason"]:
            rows.append(row)
    rows.sort(key=lambda item: item["der"], reverse=True)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", nargs="+", type=Path)
    parser.add_argument("--der-threshold", type=float, default=1.0)
    parser.add_argument("--fa-threshold", type=float, default=0.5)
    parser.add_argument("--miss-threshold", type=float, default=0.5)
    parser.add_argument("--output", type=Path, default=Path("outputs/abnormal_windows/results.csv"))
    args = parser.parse_args()

    rows = []
    for summary_path in args.summary:
        rows.extend(analyze_summary(summary_path, args))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model_name",
        "recording_id",
        "window_size",
        "segment_idx",
        "der",
        "miss_rate",
        "fa_rate",
        "conf_rate",
        "spk_count_pred",
        "spk_count_gt",
        "pred_speech",
        "gt_speech",
        "speech_ratio",
        "reason",
        "summary",
    ]
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("Abnormal diarization windows")
    print("count=%d csv=%s" % (len(rows), args.output))
    for row in rows[:20]:
        print(
            "%-24s %s seg=%s DER=%.1f%% Miss=%.1f%% FA=%.1f%% Conf=%.1f%% spk=%d/%d speech_ratio=%.2f %s"
            % (
                row["model_name"],
                row["recording_id"],
                row["segment_idx"],
                row["der"] * 100,
                row["miss_rate"] * 100,
                row["fa_rate"] * 100,
                row["conf_rate"] * 100,
                row["spk_count_pred"],
                row["spk_count_gt"],
                row["speech_ratio"],
                row["reason"],
            )
        )


if __name__ == "__main__":
    main()
