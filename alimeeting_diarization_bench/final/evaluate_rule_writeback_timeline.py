#!/usr/bin/env python3
"""Materialize rule-gated writeback patches and score merged timelines.

This script turns the current writeback policy from patch-level evidence into
window-level diarization hypotheses. It is intentionally conservative: runtime
gate outputs decide which patches may alter the Fast timeline; ground truth is
used only after materialization for scoring.
"""

from __future__ import annotations

# Keep final modules import-compatible when executed with python -m.
import sys as _sys
from pathlib import Path as _Path
_SCRIPT_ROOT = _Path(__file__).resolve().parent
_REPO_ROOT = _Path(__file__).resolve().parents[2]
for _candidate in [_REPO_ROOT, _SCRIPT_ROOT, *_SCRIPT_ROOT.iterdir()]:
    if _candidate.is_dir():
        _value = str(_candidate)
        if _value not in _sys.path:
            _sys.path.insert(0, _value)

import argparse
import csv
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alimeeting_diarization_bench.metrics.der import calc_der

logging.getLogger().setLevel(logging.ERROR)


WRITEBACK_CATEGORIES = {
    "rule_auto_writeback",
    "rule_label_only_writeback",
    "rule_recover_writeback",
}


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def result_key(row: dict[str, Any]) -> tuple[str, int, int]:
    return (str(row["recording_id"]), int(row["window_size"]), int(row["segment_idx"]))


def patch_id(row: dict[str, str]) -> str:
    return (
        f"{row['recording_id']}:{int(float(row['window_size']))}:"
        f"{int(float(row['segment_idx']))}:{row['source']}:{row['segment_id']}"
    )


def load_summary(path: Path) -> tuple[dict[str, Any], dict[tuple[str, int, int], dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, {result_key(row): row for row in data.get("results", []) if row.get("success")}


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def segment_id_map(segments: list[dict[str, Any]], source: str) -> dict[str, dict[str, Any]]:
    return {f"{source}_{idx}": seg for idx, seg in enumerate(segments)}


def duration(seg: dict[str, Any]) -> float:
    return max(0.0, as_float(seg.get("end")) - as_float(seg.get("start")))


def overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
    return max(0.0, min(as_float(a["end"]), as_float(b["end"])) - max(as_float(a["start"]), as_float(b["start"])))


def best_overlap(seg: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    best = None
    best_value = 0.0
    for candidate in candidates:
        value = overlap(seg, candidate)
        if value > best_value:
            best = candidate
            best_value = value
    return best, best_value


def clone_segment(seg: dict[str, Any], speaker: str | None = None) -> dict[str, Any]:
    return {
        "start": float(seg["start"]),
        "end": float(seg["end"]),
        "speaker": str(seg["speaker"] if speaker is None else speaker),
        "text": seg.get("text", ""),
    }


def interval_subtract(start: float, end: float, blockers: list[tuple[float, float]], min_duration: float = 0.04) -> list[tuple[float, float]]:
    pieces = [(start, end)]
    for block_start, block_end in sorted(blockers):
        next_pieces = []
        for piece_start, piece_end in pieces:
            if block_end <= piece_start or block_start >= piece_end:
                next_pieces.append((piece_start, piece_end))
                continue
            if block_start > piece_start:
                next_pieces.append((piece_start, min(block_start, piece_end)))
            if block_end < piece_end:
                next_pieces.append((max(block_end, piece_start), piece_end))
        pieces = next_pieces
    return [(s, e) for s, e in pieces if e - s >= min_duration]


def blocker_intervals(segments: list[dict[str, Any]], speaker: str | None = None) -> list[tuple[float, float]]:
    intervals = []
    for seg in segments:
        if speaker is not None and str(seg["speaker"]) != str(speaker):
            continue
        intervals.append((float(seg["start"]), float(seg["end"])))
    return intervals


def add_segment_with_subtraction(
    merged: list[dict[str, Any]],
    segment: dict[str, Any],
    speaker: str,
    mode: str,
) -> int:
    if mode == "none":
        merged.append(clone_segment(segment, speaker=speaker))
        return 1
    blockers = blocker_intervals(merged, speaker=speaker if mode == "same_speaker" else None)
    pieces = interval_subtract(float(segment["start"]), float(segment["end"]), blockers)
    for start, end in pieces:
        new_seg = clone_segment(segment, speaker=speaker)
        new_seg["start"] = start
        new_seg["end"] = end
        merged.append(new_seg)
    return len(pieces)


def merge_same_speaker_overlaps(segments: list[dict[str, Any]], gap_tolerance: float = 0.0) -> list[dict[str, Any]]:
    by_speaker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for seg in segments:
        by_speaker[str(seg["speaker"])].append(seg)

    merged: list[dict[str, Any]] = []
    for speaker, speaker_segments in by_speaker.items():
        ordered = sorted(speaker_segments, key=lambda item: (float(item["start"]), float(item["end"])))
        for seg in ordered:
            start = float(seg["start"])
            end = float(seg["end"])
            if not merged or str(merged[-1]["speaker"]) != speaker or start > float(merged[-1]["end"]) + gap_tolerance:
                merged.append({"start": start, "end": end, "speaker": speaker, "text": seg.get("text", "")})
            else:
                merged[-1]["end"] = max(float(merged[-1]["end"]), end)
    return sorted(merged, key=lambda item: (float(item["start"]), float(item["end"]), str(item["speaker"])))


def safe_session_id(key: tuple[str, int, int], variant: str) -> str:
    return f"{key[0]}_ws{key[1]}_seg{key[2]}_{variant}".replace(":", "_").replace("|", "_")


def grouped_gate_rows(rows: list[dict[str, str]]) -> dict[tuple[str, int, int], dict[str, dict[str, str]]]:
    grouped: dict[tuple[str, int, int], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        key = (row["recording_id"], int(float(row["window_size"])), int(float(row["segment_idx"])))
        grouped[key][row["patch_id"]] = row
    return grouped


def materialize_variant(
    variant: str,
    key: tuple[str, int, int],
    fast: dict[str, Any],
    slow: dict[str, Any],
    gate_by_patch: dict[str, dict[str, str]],
    patch_eval_by_id: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if variant.endswith("_speaker_union"):
        base_variant = variant.removesuffix("_speaker_union")
        base_segments, counters = materialize_variant(base_variant, key, fast, slow, gate_by_patch, patch_eval_by_id)
        union_segments = merge_same_speaker_overlaps(base_segments)
        counters["speaker_union_removed_segments"] = max(0, len(base_segments) - len(union_segments))
        return union_segments, counters

    fast_segments = fast.get("pred_segments", [])
    slow_segments = slow.get("pred_segments", [])
    fast_by_id = segment_id_map(fast_segments, "fast")
    slow_by_id = segment_id_map(slow_segments, "slow")

    counters = {
        "fast_kept": 0,
        "fast_boundary_replaced": 0,
        "recover_added": 0,
        "recover_label_matched": 0,
        "recover_label_new": 0,
        "recover_split_segments": 0,
        "speaker_union_removed_segments": 0,
    }

    if variant == "fast_base":
        return [clone_segment(seg) for seg in fast_segments], counters
    if variant == "slow_base":
        return [clone_segment(seg) for seg in slow_segments], counters

    merged: list[dict[str, Any]] = []

    for seg_id, fast_seg in fast_by_id.items():
        pid = f"{key[0]}:{key[1]}:{key[2]}:fast:{seg_id}"
        gate = gate_by_patch.get(pid, {})
        patch_type = gate.get("patch_type", "")
        category = gate.get("gate_category", "")

        boundary_variants = {"rule_boundary_recover", "rule_boundary_recover_no_same_overlap"}
        if variant in boundary_variants and category in WRITEBACK_CATEGORIES and patch_type == "boundary_fix_or_relabel":
            best_slow, best_sec = best_overlap(fast_seg, slow_segments)
            if best_slow is not None and best_sec > 0:
                patched = clone_segment(best_slow, speaker=str(fast_seg["speaker"]))
                if variant == "rule_boundary_recover_no_same_overlap":
                    add_segment_with_subtraction(merged, patched, str(fast_seg["speaker"]), "same_speaker")
                else:
                    merged.append(patched)
                counters["fast_boundary_replaced"] += 1
                continue

        merged.append(clone_segment(fast_seg))
        counters["fast_kept"] += 1

    recover_variants = {
        "rule_recover_new_label",
        "rule_recover_matched_label",
        "rule_recover_matched_no_same_overlap",
        "rule_recover_uncovered_only",
        "rule_recover_identity_selector",
        "rule_recover_policy_sweep_best",
        "rule_boundary_recover",
        "rule_boundary_recover_no_same_overlap",
    }
    if variant in recover_variants:
        for seg_id, slow_seg in slow_by_id.items():
            pid = f"{key[0]}:{key[1]}:{key[2]}:slow:{seg_id}"
            gate = gate_by_patch.get(pid, {})
            if gate.get("gate_category") != "rule_recover_writeback" or gate.get("patch_type") != "recover_slow_segment":
                continue
            eval_row = patch_eval_by_id.get(pid, {})
            matched = eval_row.get("matched_speaker") or gate.get("matched_speaker") or ""
            support = as_float(eval_row.get("support_ratio") or gate.get("support_ratio"))
            matched_label_variants = {
                "rule_recover_matched_label",
                "rule_recover_matched_no_same_overlap",
                "rule_recover_uncovered_only",
                "rule_recover_identity_selector",
                "rule_recover_policy_sweep_best",
                "rule_boundary_recover",
                "rule_boundary_recover_no_same_overlap",
            }
            if variant in matched_label_variants and matched and support > 0.0:
                speaker = matched
                counters["recover_label_matched"] += 1
            else:
                speaker = f"slow_recover_{slow_seg['speaker']}"
                counters["recover_label_new"] += 1
            subtract_mode = "none"
            if variant in {"rule_recover_matched_no_same_overlap", "rule_boundary_recover_no_same_overlap"}:
                subtract_mode = "same_speaker"
            elif variant == "rule_recover_uncovered_only":
                subtract_mode = "any_speaker"
            elif variant == "rule_recover_identity_selector":
                fast_spk = int(fast.get("spk_count_pred", 0))
                slow_spk = int(slow.get("spk_count_pred", 0))
                subtract_mode = "none" if slow_spk > fast_spk else "any_speaker"
            elif variant == "rule_recover_policy_sweep_best":
                fast_spk = int(fast.get("spk_count_pred", 0))
                slow_spk = int(slow.get("spk_count_pred", 0))
                fast_speech = sum(duration(seg) for seg in fast_segments)
                slow_speech = sum(duration(seg) for seg in slow_segments)
                speech_ratio = fast_speech / slow_speech if slow_speech else 0.0
                subtract_mode = "none" if slow_spk > fast_spk or speech_ratio <= 0.60 else "any_speaker"
            added = add_segment_with_subtraction(merged, slow_seg, str(speaker), subtract_mode)
            counters["recover_added"] += 1 if added else 0
            counters["recover_split_segments"] += added

    merged.sort(key=lambda item: (float(item["start"]), float(item["end"]), str(item["speaker"])))
    return merged, counters


def score_segments(
    key: tuple[str, int, int],
    variant: str,
    pred_segments: list[dict[str, Any]],
    gt_segments: list[dict[str, Any]],
    collar: float,
) -> dict[str, Any]:
    metrics = calc_der(gt_segments, pred_segments, safe_session_id(key, variant), collar=collar)
    pred_speakers = {str(seg["speaker"]) for seg in pred_segments}
    gt_speakers = {str(seg["speaker"]) for seg in gt_segments}
    row: dict[str, Any] = {
        "recording_id": key[0],
        "window_size": key[1],
        "segment_idx": key[2],
        "variant": variant,
        "success": metrics is not None,
        "der": None,
        "miss_rate": None,
        "fa_rate": None,
        "conf_rate": None,
        "scored_time": None,
        "spk_count_pred": len(pred_speakers),
        "spk_count_gt": len(gt_speakers),
        "spk_match": len(pred_speakers) == len(gt_speakers),
        "pred_segments": len(pred_segments),
        "pred_speech_sec": round(sum(duration(seg) for seg in pred_segments), 4),
    }
    if metrics:
        row.update(metrics)
    return row


def average(rows: list[dict[str, Any]], field: str) -> float:
    values = [as_float(row.get(field), default=float("nan")) for row in rows if row.get(field) is not None]
    values = [value for value in values if value == value]
    return sum(values) / len(values) if values else 0.0


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]


def summarize(rows: list[dict[str, Any]], counters_by_variant: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_variant[str(row["variant"])].append(row)

    summaries = []
    for variant, items in sorted(by_variant.items()):
        ders = [as_float(row["der"]) for row in items if row.get("der") is not None]
        counters = counters_by_variant.get(variant, {})
        summaries.append(
            {
                "variant": variant,
                "windows": len(items),
                "successful": sum(1 for row in items if row.get("success")),
                "avg_der": round(average(items, "der"), 4),
                "median_der": round(percentile(ders, 0.5), 4),
                "avg_miss_rate": round(average(items, "miss_rate"), 4),
                "avg_fa_rate": round(average(items, "fa_rate"), 4),
                "avg_conf_rate": round(average(items, "conf_rate"), 4),
                "spk_match_rate": round(sum(1 for row in items if row.get("spk_match")) / len(items), 4) if items else 0.0,
                "avg_pred_segments": round(average(items, "pred_segments"), 2),
                "avg_pred_speech_sec": round(average(items, "pred_speech_sec"), 3),
                "fast_boundary_replaced": counters.get("fast_boundary_replaced", 0),
                "recover_added": counters.get("recover_added", 0),
                "recover_label_matched": counters.get("recover_label_matched", 0),
                "recover_label_new": counters.get("recover_label_new", 0),
                "recover_split_segments": counters.get("recover_split_segments", 0),
                "speaker_union_removed_segments": counters.get("speaker_union_removed_segments", 0),
            }
        )
    return summaries


def write_markdown(summary_rows: list[dict[str, Any]], output: Path) -> None:
    lines = [
        "# Rule Writeback Timeline Evaluation",
        "",
        "| Variant | Windows | DER | Median DER | Miss | FA | Conf | Spk match | Boundary replaced | Recover added | Interpretation |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    interpretations = {
        "fast_base": "Original realtime first-pass baseline.",
        "slow_base": "Full DiariZen mature-window replacement baseline.",
        "rule_recover_new_label": "Adds accepted recover segments with new slow labels; tests speech recovery without identity linking.",
        "rule_recover_matched_label": "Adds accepted recover segments with matched Fast labels when available.",
        "rule_recover_matched_no_same_overlap": "Matched-label recover, subtracting same-speaker overlap before insertion.",
        "rule_recover_uncovered_only": "Matched-label recover only where Fast has no predicted speech; lowest-risk miss patch.",
        "rule_recover_identity_selector": "Matched-label recover; allow overlap only when Slow predicts more speakers than Fast.",
        "rule_recover_policy_sweep_best": "Policy-search best: matched recover if slow_spk > fast_spk or fast/slow speech ratio <= 0.60.",
        "fast_base_speaker_union": "Fast baseline after merging overlapping same-speaker fragments.",
        "rule_recover_matched_label_speaker_union": "Matched-label recover plus same-speaker union sanitizer.",
        "rule_recover_uncovered_only_speaker_union": "Uncovered-only recover plus same-speaker union sanitizer.",
        "rule_boundary_recover": "Also applies accepted boundary replacements; closest current conservative merged timeline.",
        "rule_boundary_recover_no_same_overlap": "Boundary+recover with same-speaker overlap subtraction.",
        "rule_boundary_recover_speaker_union": "Boundary+recover plus same-speaker union sanitizer.",
    }
    for row in summary_rows:
        lines.append(
            "| {variant} | {windows} | {avg_der:.2%} | {median_der:.2%} | {avg_miss_rate:.2%} | {avg_fa_rate:.2%} | {avg_conf_rate:.2%} | {spk_match_rate:.1%} | {fast_boundary_replaced} | {recover_added} | {interp} |".format(
                interp=interpretations.get(str(row["variant"]), ""),
                **row,
            )
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This is a timeline-level score, not just patch coverage.",
            "- Ground truth is used only after materializing predictions for DER scoring.",
            "- If recover variants lower Miss but raise Conf/FA, the next bottleneck is identity assignment and overlap-aware insertion, not acoustic detection.",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast-summary", type=Path, default=Path("outputs/sortformer_uv_48/nemo-sortformer-4spk-v1/default__spk_none/summary.json"))
    parser.add_argument("--slow-summary", type=Path, default=Path("outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none/summary.json"))
    parser.add_argument("--gate-decisions", type=Path, default=Path("outputs/writeback_gate/gate_decisions.csv"))
    parser.add_argument("--patches", type=Path, default=Path("outputs/segment_patches/sortformer_diarizen_48_patches.csv"))
    parser.add_argument("--collar", type=float, default=0.0)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/rule_writeback_timeline"))
    args = parser.parse_args()

    fast_data, fast_by_key = load_summary(args.fast_summary)
    slow_data, slow_by_key = load_summary(args.slow_summary)
    gate_by_window = grouped_gate_rows(load_csv(args.gate_decisions))
    patch_eval_by_id = {patch_id(row): row for row in load_csv(args.patches)}

    common_keys = sorted(set(fast_by_key) & set(slow_by_key))
    if not common_keys:
        raise SystemExit("No common successful Fast/Slow windows")

    variants = [
        "fast_base",
        "fast_base_speaker_union",
        "slow_base",
        "rule_recover_new_label",
        "rule_recover_matched_label",
        "rule_recover_matched_label_speaker_union",
        "rule_recover_matched_no_same_overlap",
        "rule_recover_uncovered_only",
        "rule_recover_uncovered_only_speaker_union",
        "rule_recover_identity_selector",
        "rule_recover_policy_sweep_best",
        "rule_boundary_recover",
        "rule_boundary_recover_speaker_union",
        "rule_boundary_recover_no_same_overlap",
    ]
    result_rows: list[dict[str, Any]] = []
    merged_examples: dict[str, Any] = {}
    counters_by_variant: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for key in common_keys:
        fast = fast_by_key[key]
        slow = slow_by_key[key]
        gt_segments = fast.get("gt_segments", [])
        for variant in variants:
            pred_segments, counters = materialize_variant(
                variant,
                key,
                fast,
                slow,
                gate_by_window.get(key, {}),
                patch_eval_by_id,
            )
            for name, value in counters.items():
                counters_by_variant[variant][name] += value
            row = score_segments(key, variant, pred_segments, gt_segments, args.collar)
            result_rows.append(row)
            if variant.startswith("rule_") and variant not in merged_examples:
                merged_examples[variant] = {
                    "key": key,
                    "pred_segments": pred_segments[:20],
                    "gt_segments": gt_segments[:20],
                }

    summary_rows = summarize(result_rows, counters_by_variant)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_csv = args.output_dir / "rule_writeback_timeline_results.csv"
    summary_csv = args.output_dir / "rule_writeback_timeline_summary.csv"
    summary_json = args.output_dir / "rule_writeback_timeline_summary.json"
    summary_md = args.output_dir / "rule_writeback_timeline_summary.md"
    examples_json = args.output_dir / "rule_writeback_timeline_examples.json"

    with results_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result_rows[0].keys()))
        writer.writeheader()
        writer.writerows(result_rows)

    with summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    summary_payload = {
        "fast_summary": str(args.fast_summary),
        "slow_summary": str(args.slow_summary),
        "gate_decisions": str(args.gate_decisions),
        "patches": str(args.patches),
        "fast_model": fast_data.get("model_name"),
        "slow_model": slow_data.get("model_name"),
        "collar": args.collar,
        "summary": summary_rows,
    }
    summary_json.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    examples_json.write_text(json.dumps(merged_examples, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary_rows, summary_md)

    print(f"Wrote {results_csv}")
    print(f"Wrote {summary_csv}")
    print(f"Wrote {summary_json}")
    print(f"Wrote {summary_md}")


if __name__ == "__main__":
    main()
