#!/usr/bin/env python3
"""Analyze segment-level Fast-to-Slow correction patches.

The patch table is production-facing: it uses only Fast and Slow predictions.
The window metrics are evaluation-facing: ground truth is used only to quantify
how much Fast miss/FA/confusion can be corrected by the Slow output.
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
from collections import Counter, defaultdict
from pathlib import Path


def overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def duration(seg: dict) -> float:
    return max(0.0, float(seg["end"]) - float(seg["start"]))


def key_for(result: dict) -> tuple[str, int, int]:
    return (
        str(result["recording_id"]),
        int(result["window_size"]),
        int(result["segment_idx"]),
    )


def load_successful(path: Path) -> tuple[dict, dict[tuple[str, int, int], dict]]:
    data = json.loads(path.read_text())
    return data, {key_for(result): result for result in data.get("results", []) if result.get("success")}


def speech_seconds(segments: list[dict]) -> float:
    return sum(duration(seg) for seg in segments)


def best_overlap(seg: dict, candidates: list[dict]) -> tuple[dict | None, float]:
    best = None
    best_value = 0.0
    for candidate in candidates:
        value = overlap(float(seg["start"]), float(seg["end"]), float(candidate["start"]), float(candidate["end"]))
        if value > best_value:
            best = candidate
            best_value = value
    return best, best_value


def segment_gt_overlap(seg: dict, gt_segments: list[dict]) -> float:
    return sum(
        overlap(float(seg["start"]), float(seg["end"]), float(gt["start"]), float(gt["end"]))
        for gt in gt_segments
    )


def build_speech_mask(segments: list[dict], window_size: int, frame_sec: float) -> list[bool]:
    n = int(round(window_size / frame_sec))
    mask = [False] * n
    for seg in segments:
        start = max(0, int(float(seg["start"]) / frame_sec))
        end = min(n, int(float(seg["end"]) / frame_sec + 0.999999))
        for idx in range(start, end):
            mask[idx] = True
    return mask


def mask_seconds(mask: list[bool], frame_sec: float) -> float:
    return sum(1 for value in mask if value) * frame_sec


def greedy_speaker_mapping(pred_segments: list[dict], gt_segments: list[dict]) -> dict[str, str]:
    scores: dict[tuple[str, str], float] = defaultdict(float)
    for pred in pred_segments:
        p_spk = str(pred["speaker"])
        for gt in gt_segments:
            value = overlap(float(pred["start"]), float(pred["end"]), float(gt["start"]), float(gt["end"]))
            if value > 0:
                scores[(p_spk, str(gt["speaker"]))] += value

    mapping = {}
    used_pred = set()
    used_gt = set()
    for (pred_spk, gt_spk), value in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        if value <= 0 or pred_spk in used_pred or gt_spk in used_gt:
            continue
        mapping[pred_spk] = gt_spk
        used_pred.add(pred_spk)
        used_gt.add(gt_spk)
    return mapping


def mapped_correct_overlap(pred_segments: list[dict], gt_segments: list[dict]) -> float:
    mapping = greedy_speaker_mapping(pred_segments, gt_segments)
    correct = 0.0
    for pred in pred_segments:
        mapped = mapping.get(str(pred["speaker"]))
        if mapped is None:
            continue
        for gt in gt_segments:
            if mapped != str(gt["speaker"]):
                continue
            correct += overlap(float(pred["start"]), float(pred["end"]), float(gt["start"]), float(gt["end"]))
    return correct


def analyze_window(
    key: tuple[str, int, int],
    fast: dict,
    slow: dict,
    args: argparse.Namespace,
) -> tuple[list[dict], dict]:
    fast_segments = fast.get("pred_segments", [])
    slow_segments = slow.get("pred_segments", [])
    gt_segments = fast.get("gt_segments", [])
    window_size = int(fast["window_size"])

    patch_rows = []
    patch_counts = Counter()

    for idx, fast_seg in enumerate(fast_segments):
        best_slow, best_sec = best_overlap(fast_seg, slow_segments)
        fast_dur = duration(fast_seg)
        support = best_sec / fast_dur if fast_dur else 0.0
        gt_sec = segment_gt_overlap(fast_seg, gt_segments)
        gt_support = min(1.0, gt_sec / fast_dur) if fast_dur else 0.0
        if support < args.support_threshold:
            patch_type = "suppress_fast_candidate"
        else:
            boundary_delta = 0.0
            if best_slow is not None:
                boundary_delta = abs(float(fast_seg["start"]) - float(best_slow["start"])) + abs(
                    float(fast_seg["end"]) - float(best_slow["end"])
                )
            patch_type = "boundary_fix_or_relabel" if boundary_delta >= args.boundary_delta else "keep_fast_supported"
        patch_counts[patch_type] += 1
        patch_rows.append(
            {
                "recording_id": key[0],
                "window_size": key[1],
                "segment_idx": key[2],
                "source": "fast",
                "patch_type": patch_type,
                "segment_id": f"fast_{idx}",
                "start": fast_seg["start"],
                "end": fast_seg["end"],
                "speaker": fast_seg["speaker"],
                "matched_source": "slow" if best_slow is not None else "",
                "matched_speaker": "" if best_slow is None else best_slow["speaker"],
                "overlap_sec": round(best_sec, 4),
                "support_ratio": round(support, 4),
                "gt_overlap_sec": round(gt_sec, 4),
                "gt_support_ratio": round(gt_support, 4),
            }
        )

    for idx, slow_seg in enumerate(slow_segments):
        best_fast, best_sec = best_overlap(slow_seg, fast_segments)
        slow_dur = duration(slow_seg)
        support = best_sec / slow_dur if slow_dur else 0.0
        gt_sec = segment_gt_overlap(slow_seg, gt_segments)
        gt_support = min(1.0, gt_sec / slow_dur) if slow_dur else 0.0
        patch_type = "recover_slow_segment" if support < args.support_threshold else "align_slow_segment"
        patch_counts[patch_type] += 1
        patch_rows.append(
            {
                "recording_id": key[0],
                "window_size": key[1],
                "segment_idx": key[2],
                "source": "slow",
                "patch_type": patch_type,
                "segment_id": f"slow_{idx}",
                "start": slow_seg["start"],
                "end": slow_seg["end"],
                "speaker": slow_seg["speaker"],
                "matched_source": "fast" if best_fast is not None else "",
                "matched_speaker": "" if best_fast is None else best_fast["speaker"],
                "overlap_sec": round(best_sec, 4),
                "support_ratio": round(support, 4),
                "gt_overlap_sec": round(gt_sec, 4),
                "gt_support_ratio": round(gt_support, 4),
            }
        )

    frame_sec = args.frame_sec
    gt_mask = build_speech_mask(gt_segments, window_size, frame_sec)
    fast_mask = build_speech_mask(fast_segments, window_size, frame_sec)
    slow_mask = build_speech_mask(slow_segments, window_size, frame_sec)

    gt_speech = mask_seconds(gt_mask, frame_sec)
    fast_miss = [gt and not fast_value for gt, fast_value in zip(gt_mask, fast_mask)]
    slow_recovers_miss = [
        gt and not fast_value and slow_value
        for gt, fast_value, slow_value in zip(gt_mask, fast_mask, slow_mask)
    ]
    fast_fa = [fast_value and not gt for gt, fast_value in zip(gt_mask, fast_mask)]
    slow_suppresses_fa = [
        fast_value and not gt and not slow_value
        for gt, fast_value, slow_value in zip(gt_mask, fast_mask, slow_mask)
    ]
    slow_added_fa = [
        slow_value and not gt and not fast_value
        for gt, fast_value, slow_value in zip(gt_mask, fast_mask, slow_mask)
    ]
    disagreement = [fast_value != slow_value for fast_value, slow_value in zip(fast_mask, slow_mask)]

    fast_miss_sec = mask_seconds(fast_miss, frame_sec)
    fast_fa_sec = mask_seconds(fast_fa, frame_sec)
    recovered_sec = mask_seconds(slow_recovers_miss, frame_sec)
    suppressed_sec = mask_seconds(slow_suppresses_fa, frame_sec)
    added_fa_sec = mask_seconds(slow_added_fa, frame_sec)
    disagreement_sec = mask_seconds(disagreement, frame_sec)
    fast_correct = mapped_correct_overlap(fast_segments, gt_segments)
    slow_correct = mapped_correct_overlap(slow_segments, gt_segments)

    window_row = {
        "recording_id": key[0],
        "window_size": key[1],
        "segment_idx": key[2],
        "fast_der": fast["der"],
        "slow_der": slow["der"],
        "fast_spk_count_pred": fast["spk_count_pred"],
        "slow_spk_count_pred": slow["spk_count_pred"],
        "gt_spk_count": fast["spk_count_gt"],
        "fast_segments": len(fast_segments),
        "slow_segments": len(slow_segments),
        "fast_speech": speech_seconds(fast_segments),
        "slow_speech": speech_seconds(slow_segments),
        "gt_speech": gt_speech,
        "fast_miss_sec": fast_miss_sec,
        "slow_recovers_fast_miss_sec": recovered_sec,
        "fast_miss_recovery_rate": recovered_sec / fast_miss_sec if fast_miss_sec else 0.0,
        "fast_fa_sec": fast_fa_sec,
        "slow_suppresses_fast_fa_sec": suppressed_sec,
        "fast_fa_suppression_rate": suppressed_sec / fast_fa_sec if fast_fa_sec else 0.0,
        "slow_added_fa_sec": added_fa_sec,
        "fast_slow_disagreement_sec": disagreement_sec,
        "fast_label_correct_overlap": fast_correct,
        "slow_label_correct_overlap": slow_correct,
        "label_correct_gain_sec": slow_correct - fast_correct,
        "keep_fast_supported": patch_counts["keep_fast_supported"],
        "boundary_fix_or_relabel": patch_counts["boundary_fix_or_relabel"],
        "suppress_fast_candidate": patch_counts["suppress_fast_candidate"],
        "recover_slow_segment": patch_counts["recover_slow_segment"],
        "align_slow_segment": patch_counts["align_slow_segment"],
    }
    return patch_rows, window_row


def weighted_rate(rows: list[dict], numerator: str, denominator: str) -> float:
    num = sum(float(row[numerator]) for row in rows)
    den = sum(float(row[denominator]) for row in rows)
    return num / den if den else 0.0


def average(rows: list[dict], field: str) -> float:
    return sum(float(row[field]) for row in rows) / len(rows) if rows else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast-summary", required=True, type=Path)
    parser.add_argument("--slow-summary", required=True, type=Path)
    parser.add_argument("--patch-output", type=Path, default=Path("outputs/segment_patches/patches.csv"))
    parser.add_argument("--window-output", type=Path, default=None)
    parser.add_argument("--summary-output", type=Path, default=None)
    parser.add_argument("--support-threshold", type=float, default=0.35)
    parser.add_argument("--boundary-delta", type=float, default=0.5)
    parser.add_argument("--frame-sec", type=float, default=0.02)
    parser.add_argument("--true-speech-threshold", type=float, default=0.5)
    parser.add_argument("--true-fa-threshold", type=float, default=0.2)
    args = parser.parse_args()

    fast_data, fast_by_key = load_successful(args.fast_summary)
    slow_data, slow_by_key = load_successful(args.slow_summary)
    common_keys = sorted(set(fast_by_key) & set(slow_by_key))
    if not common_keys:
        raise SystemExit("No matching successful windows between fast and slow summaries")

    patch_rows = []
    window_rows = []
    for key in common_keys:
        patches, window = analyze_window(key, fast_by_key[key], slow_by_key[key], args)
        patch_rows.extend(patches)
        window_rows.append(window)

    args.patch_output.parent.mkdir(parents=True, exist_ok=True)
    window_output = args.window_output or args.patch_output.with_name(args.patch_output.stem + "_windows.csv")
    summary_output = args.summary_output or args.patch_output.with_name(args.patch_output.stem + "_summary.json")

    with args.patch_output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(patch_rows[0].keys()))
        writer.writeheader()
        writer.writerows(patch_rows)

    with window_output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(window_rows[0].keys()))
        writer.writeheader()
        writer.writerows(window_rows)

    patch_counts = Counter(row["patch_type"] for row in patch_rows)
    true_recover_segments = sum(
        1
        for row in patch_rows
        if row["patch_type"] == "recover_slow_segment"
        and float(row["gt_support_ratio"]) >= args.true_speech_threshold
    )
    true_suppress_segments = sum(
        1
        for row in patch_rows
        if row["patch_type"] == "suppress_fast_candidate"
        and float(row["gt_support_ratio"]) <= args.true_fa_threshold
    )
    summary = {
        "fast_model": fast_data.get("model_name"),
        "slow_model": slow_data.get("model_name"),
        "windows": len(common_keys),
        "patch_rows": len(patch_rows),
        "patch_csv": str(args.patch_output),
        "window_csv": str(window_output),
        "avg_fast_der": average(window_rows, "fast_der"),
        "avg_slow_der": average(window_rows, "slow_der"),
        "total_fast_miss_sec": sum(float(row["fast_miss_sec"]) for row in window_rows),
        "total_slow_recovers_fast_miss_sec": sum(float(row["slow_recovers_fast_miss_sec"]) for row in window_rows),
        "fast_miss_recovery_rate": weighted_rate(window_rows, "slow_recovers_fast_miss_sec", "fast_miss_sec"),
        "total_fast_fa_sec": sum(float(row["fast_fa_sec"]) for row in window_rows),
        "total_slow_suppresses_fast_fa_sec": sum(float(row["slow_suppresses_fast_fa_sec"]) for row in window_rows),
        "fast_fa_suppression_rate": weighted_rate(window_rows, "slow_suppresses_fast_fa_sec", "fast_fa_sec"),
        "total_slow_added_fa_sec": sum(float(row["slow_added_fa_sec"]) for row in window_rows),
        "total_label_correct_gain_sec": sum(float(row["label_correct_gain_sec"]) for row in window_rows),
        "avg_disagreement_sec": average(window_rows, "fast_slow_disagreement_sec"),
        "patch_counts": dict(patch_counts),
        "true_recover_slow_segments": true_recover_segments,
        "true_recover_slow_segment_rate": true_recover_segments / patch_counts["recover_slow_segment"]
        if patch_counts["recover_slow_segment"]
        else 0.0,
        "true_suppress_fast_segments": true_suppress_segments,
        "true_suppress_fast_segment_rate": true_suppress_segments / patch_counts["suppress_fast_candidate"]
        if patch_counts["suppress_fast_candidate"]
        else 0.0,
    }
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Segment-level Fast-to-Slow patches")
    print("fast=%s" % summary["fast_model"])
    print("slow=%s" % summary["slow_model"])
    print("windows=%d patches=%d" % (summary["windows"], summary["patch_rows"]))
    print("patch_csv=%s" % args.patch_output)
    print("window_csv=%s" % window_output)
    print("summary_json=%s" % summary_output)
    print(
        "Fast miss recovered by Slow: %.1f%% (%.2fs / %.2fs)"
        % (
            summary["fast_miss_recovery_rate"] * 100,
            summary["total_slow_recovers_fast_miss_sec"],
            summary["total_fast_miss_sec"],
        )
    )
    print(
        "Fast FA suppressible by Slow: %.1f%% (%.2fs / %.2fs), slow_added_fa=%.2fs"
        % (
            summary["fast_fa_suppression_rate"] * 100,
            summary["total_slow_suppresses_fast_fa_sec"],
            summary["total_fast_fa_sec"],
            summary["total_slow_added_fa_sec"],
        )
    )
    print("Patch counts:", dict(patch_counts))
    print(
        "True recover segments=%d, true suppress segments=%d"
        % (true_recover_segments, true_suppress_segments)
    )


if __name__ == "__main__":
    main()
