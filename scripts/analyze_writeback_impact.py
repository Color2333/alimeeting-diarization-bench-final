#!/usr/bin/env python3
"""Estimate offline impact of writeback-gated diarization patches.

This joins deployable gate categories with eval-only patch overlap fields to
quantify what the current writeback policy covers. Ground-truth fields are used
only in this analysis script, never in the runtime Policy Agent prompt.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


WRITEBACK_CATEGORIES = {
    "rule_auto_writeback",
    "rule_label_only_writeback",
    "rule_recover_writeback",
}


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def patch_id(row: dict[str, str]) -> str:
    return (
        f"{row['recording_id']}:{int(float(row['window_size']))}:"
        f"{int(float(row['segment_idx']))}:{row['source']}:{row['segment_id']}"
    )


def load_patch_eval(path: Path) -> dict[str, dict[str, str]]:
    return {patch_id(row): row for row in load_csv(path)}


def load_slow_latency(path: Path) -> float:
    data = json.loads(path.read_text(encoding="utf-8"))
    return float(data.get("avg_latency", 0.0))


def result_key(row: dict[str, Any]) -> tuple[str, int, int]:
    return (str(row["recording_id"]), int(row["window_size"]), int(row["segment_idx"]))


def load_summary_results(path: Path) -> dict[tuple[str, int, int], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {result_key(row): row for row in data.get("results", []) if row.get("success")}


def build_mask(segments: list[dict[str, Any]], window_size: int, frame_sec: float) -> list[bool]:
    frames = int(round(window_size / frame_sec))
    mask = [False] * frames
    for seg in segments:
        start = max(0, int(as_float(seg.get("start")) / frame_sec))
        end = min(frames, int(as_float(seg.get("end")) / frame_sec + 0.999999))
        for idx in range(start, end):
            mask[idx] = True
    return mask


def selected_patch_segments(
    rows: list[dict[str, str]],
    eval_by_patch: dict[str, dict[str, str]],
    category: str,
    patch_type: str,
) -> dict[tuple[str, int, int], list[dict[str, Any]]]:
    selected: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["gate_category"] != category or row["patch_type"] != patch_type:
            continue
        eval_row = eval_by_patch.get(row["patch_id"])
        if eval_row is None:
            continue
        key = (row["recording_id"], int(float(row["window_size"])), int(float(row["segment_idx"])))
        selected[key].append({"start": as_float(eval_row["start"]), "end": as_float(eval_row["end"])})
    return selected


def unique_recovered_miss_seconds(
    gate_rows: list[dict[str, str]],
    eval_by_patch: dict[str, dict[str, str]],
    fast_results: dict[tuple[str, int, int], dict[str, Any]],
    frame_sec: float,
) -> float:
    selected = selected_patch_segments(gate_rows, eval_by_patch, "rule_recover_writeback", "recover_slow_segment")
    total = 0.0
    for key, recover_segments in selected.items():
        fast = fast_results.get(key)
        if fast is None:
            continue
        window_size = int(key[1])
        gt_mask = build_mask(fast.get("gt_segments", []), window_size, frame_sec)
        fast_mask = build_mask(fast.get("pred_segments", []), window_size, frame_sec)
        recover_mask = build_mask(recover_segments, window_size, frame_sec)
        total += sum(
            1
            for gt, fast_speech, recover_speech in zip(gt_mask, fast_mask, recover_mask)
            if gt and not fast_speech and recover_speech
        ) * frame_sec
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-decisions", type=Path, default=Path("outputs/writeback_gate/gate_decisions.csv"))
    parser.add_argument("--patches", type=Path, default=Path("outputs/segment_patches/sortformer_diarizen_48_patches.csv"))
    parser.add_argument("--windows", type=Path, default=Path("outputs/segment_patches/sortformer_diarizen_48_patches_windows.csv"))
    parser.add_argument("--fast-summary", type=Path, default=Path("outputs/sortformer_uv_48/nemo-sortformer-4spk-v1/default__spk_none/summary.json"))
    parser.add_argument("--slow-summary", type=Path, default=Path("outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none/summary.json"))
    parser.add_argument("--frame-sec", type=float, default=0.02)
    parser.add_argument("--true-speech-threshold", type=float, default=0.5)
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/writeback_gate/writeback_impact.csv"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/writeback_gate/writeback_impact_summary.json"))
    parser.add_argument("--summary-md", type=Path, default=Path("outputs/writeback_gate/writeback_impact.md"))
    args = parser.parse_args()

    eval_by_patch = load_patch_eval(args.patches)
    gate_rows = load_csv(args.gate_decisions)
    window_rows = load_csv(args.windows)
    fast_results = load_summary_results(args.fast_summary)
    slow_latency = load_slow_latency(args.slow_summary)
    unique_recover_miss_sec = unique_recovered_miss_seconds(gate_rows, eval_by_patch, fast_results, args.frame_sec)

    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "patches": 0,
            "windows": set(),
            "duration_sec": 0.0,
            "gt_overlap_sec": 0.0,
            "true_supported_patches": 0,
            "recover_gt_overlap_sec": 0.0,
            "label_only_gt_overlap_sec": 0.0,
            "auto_gt_overlap_sec": 0.0,
            "patch_types": Counter(),
        }
    )
    missing_eval = 0
    for row in gate_rows:
        category = row["gate_category"]
        eval_row = eval_by_patch.get(row["patch_id"])
        if eval_row is None:
            missing_eval += 1
            continue
        duration = as_float(eval_row.get("end")) - as_float(eval_row.get("start"))
        gt_overlap = as_float(eval_row.get("gt_overlap_sec"))
        gt_support = as_float(eval_row.get("gt_support_ratio"))
        bucket = buckets[category]
        bucket["patches"] += 1
        bucket["windows"].add(f"{row['recording_id']}:{row['window_size']}:{row['segment_idx']}")
        bucket["duration_sec"] += max(0.0, duration)
        bucket["gt_overlap_sec"] += gt_overlap
        bucket["patch_types"].update([row["patch_type"]])
        if gt_support >= args.true_speech_threshold:
            bucket["true_supported_patches"] += 1
        if category == "rule_recover_writeback":
            bucket["recover_gt_overlap_sec"] += gt_overlap
        elif category == "rule_label_only_writeback":
            bucket["label_only_gt_overlap_sec"] += gt_overlap
        elif category == "rule_auto_writeback":
            bucket["auto_gt_overlap_sec"] += gt_overlap

    fast_miss_sec = sum(as_float(row["fast_miss_sec"]) for row in window_rows)
    slow_recovered_miss_sec = sum(as_float(row["slow_recovers_fast_miss_sec"]) for row in window_rows)
    fast_fa_sec = sum(as_float(row["fast_fa_sec"]) for row in window_rows)
    slow_suppressed_fa_sec = sum(as_float(row["slow_suppresses_fast_fa_sec"]) for row in window_rows)

    output_rows = []
    for category, item in sorted(buckets.items()):
        output_rows.append(
            {
                "gate_category": category,
                "patches": item["patches"],
                "windows": len(item["windows"]),
                "duration_sec": round(item["duration_sec"], 3),
                "gt_overlap_sec": round(item["gt_overlap_sec"], 3),
                "true_supported_patches": item["true_supported_patches"],
                "true_supported_rate": round(item["true_supported_patches"] / item["patches"], 4)
                if item["patches"]
                else 0.0,
                "patch_types": " / ".join(f"{key} {value}" for key, value in sorted(item["patch_types"].items())),
            }
        )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output_rows[0].keys()))
        writer.writeheader()
        writer.writerows(output_rows)

    writeback_patch_count = sum(buckets[category]["patches"] for category in WRITEBACK_CATEGORIES)
    writeback_gt_overlap = sum(buckets[category]["gt_overlap_sec"] for category in WRITEBACK_CATEGORIES)
    recover_overlap = buckets["rule_recover_writeback"]["recover_gt_overlap_sec"]
    label_only_overlap = buckets["rule_label_only_writeback"]["label_only_gt_overlap_sec"]
    auto_overlap = buckets["rule_auto_writeback"]["auto_gt_overlap_sec"]
    summary = {
        "gate_decisions": str(args.gate_decisions),
        "patches": str(args.patches),
        "missing_eval_rows": missing_eval,
        "slow_avg_latency_seconds": slow_latency,
        "writeback_patches": writeback_patch_count,
        "writeback_gt_overlap_sec": round(writeback_gt_overlap, 3),
        "rule_auto_gt_overlap_sec": round(auto_overlap, 3),
        "rule_label_only_gt_overlap_sec": round(label_only_overlap, 3),
        "rule_recover_gt_overlap_sec": round(recover_overlap, 3),
        "rule_recover_unique_fast_miss_sec": round(unique_recover_miss_sec, 3),
        "fast_miss_sec": round(fast_miss_sec, 3),
        "slow_recovered_fast_miss_sec": round(slow_recovered_miss_sec, 3),
        "rule_recover_vs_fast_miss_rate": round(unique_recover_miss_sec / fast_miss_sec, 4) if fast_miss_sec else 0.0,
        "rule_recover_vs_slow_recovered_miss_rate": round(unique_recover_miss_sec / slow_recovered_miss_sec, 4)
        if slow_recovered_miss_sec
        else 0.0,
        "fast_fa_sec": round(fast_fa_sec, 3),
        "slow_suppressed_fast_fa_sec": round(slow_suppressed_fa_sec, 3),
        "category_counts": {category: buckets[category]["patches"] for category in sorted(buckets)},
    }
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "| Category | Patches | Windows | GT overlap sec | True support rate | Patch types |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in output_rows:
        md_lines.append(
            "| {gate_category} | {patches} | {windows} | {gt_overlap_sec:.3f} | {true_supported_rate:.1%} | {patch_types} |".format(
                **row
            )
        )
    md_lines.extend(
        [
            "",
            "| Summary | Value |",
            "|---|---:|",
            f"| Rule writeback patches | {writeback_patch_count} |",
            f"| Rule writeback GT overlap sec | {writeback_gt_overlap:.3f} |",
            f"| Recover writeback GT overlap sec | {recover_overlap:.3f} |",
            f"| Recover unique Fast-miss sec | {unique_recover_miss_sec:.3f} |",
            f"| Recover / Fast miss sec | {summary['rule_recover_vs_fast_miss_rate']:.1%} |",
            f"| Avg Slow correction latency | {slow_latency:.2f}s |",
        ]
    )
    args.summary_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.summary_json}")
    print(f"Wrote {args.summary_md}")


if __name__ == "__main__":
    main()
