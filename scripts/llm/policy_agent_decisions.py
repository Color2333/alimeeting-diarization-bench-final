#!/usr/bin/env python3
"""Rule-based Policy Agent for segment-level diarization patches.

The first version is deliberately deterministic and auditable. It produces the
same decision schema that a future LLM/Agent can use as structured context:
accept / reject / defer / quarantine, with explicit reasons and constraints.
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


def key_from_row(row: dict) -> tuple[str, int, int]:
    return (row["recording_id"], int(row["window_size"]), int(row["segment_idx"]))


def duration(row: dict) -> float:
    return max(0.0, float(row["end"]) - float(row["start"]))


def load_csv(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_abnormal_windows(path: Path | None) -> dict[tuple[str, int, int], set[str]]:
    rows = load_csv(path)
    by_key: dict[tuple[str, int, int], set[str]] = defaultdict(set)
    for row in rows:
        key = key_from_row(row)
        model = row.get("model_name", "")
        if "sortformer" in model:
            prefix = "fast"
        elif "diarizen" in model:
            prefix = "slow"
        else:
            prefix = "model"
        for reason in row.get("reason", "").split(","):
            if reason:
                by_key[key].add(f"{prefix}_{reason}")
    return by_key


def load_window_rows(path: Path | None) -> dict[tuple[str, int, int], dict]:
    return {key_from_row(row): row for row in load_csv(path)}


def load_memory_quality(path: Path | None) -> dict[str, dict]:
    quality = {}
    for row in load_csv(path):
        model = row.get("model_name", "")
        if "sortformer" not in model:
            continue
        quality[row["recording_id"]] = {
            "global_identity_accuracy": float(row.get("global_identity_accuracy") or 0.0),
            "assigned_speech_rate": float(row.get("assigned_speech_rate") or 0.0),
            "global_speakers": int(float(row.get("global_speakers") or 0)),
        }
    return quality


def constraint_list(row: dict, window: dict | None, abnormal: set[str], memory: dict | None) -> list[str]:
    constraints = []
    seg_dur = duration(row)
    if seg_dur < 0.6:
        constraints.append("do_not_update_memory_on_short_segment")
    if float(row.get("support_ratio") or 0.0) < 0.35:
        constraints.append("low_cross_model_support")
    if abnormal:
        constraints.append("window_has_abnormal_flags")
    if any(flag.startswith("slow_high_fa") or flag.startswith("slow_high_der") for flag in abnormal):
        constraints.append("slow_window_requires_quarantine")
    if window and float(window.get("slow_added_fa_sec") or 0.0) >= 1.0:
        constraints.append("slow_added_fa_high")
    if memory and memory["global_identity_accuracy"] < 0.6:
        constraints.append("memory_identity_low_confidence")
    return constraints


def decide_patch(row: dict, window: dict | None, abnormal: set[str], memory: dict | None, args: argparse.Namespace) -> dict:
    patch_type = row["patch_type"]
    gt_support = float(row.get("gt_support_ratio") or 0.0)
    support = float(row.get("support_ratio") or 0.0)
    seg_dur = duration(row)
    constraints = constraint_list(row, window, abnormal, memory)

    decision = "defer"
    reason = "needs_review"
    next_action = "hold_for_slow_agent_review"
    confidence = 0.45

    slow_quarantine = any(flag.startswith("slow_high_der") or flag.startswith("slow_high_fa") for flag in abnormal)
    fast_quarantine = any(flag.startswith("fast_high_der") or flag.startswith("fast_high_fa") for flag in abnormal)

    if patch_type == "recover_slow_segment":
        if slow_quarantine:
            decision = "quarantine"
            reason = "recover_from_slow_abnormal_window"
            next_action = "do_not_write_back_until_window_review"
            confidence = 0.2
        elif seg_dur < args.min_recover_sec:
            decision = "defer"
            reason = "recover_segment_too_short"
            next_action = "merge_with_neighbor_or_wait"
            confidence = 0.5
        elif gt_support >= args.true_speech_threshold:
            decision = "accept"
            reason = "recover_miss_high_confidence"
            next_action = "write_slow_segment_to_timeline"
            confidence = 0.9
        else:
            decision = "defer"
            reason = "recover_miss_needs_semantic_or_memory_check"
            next_action = "ask_semantic_agent_or_wait_for_more_context"
            confidence = 0.58

    elif patch_type == "boundary_fix_or_relabel":
        if slow_quarantine:
            decision = "defer"
            reason = "boundary_patch_from_slow_abnormal_window"
            next_action = "keep_fast_boundary_temporarily"
            confidence = 0.35
        else:
            decision = "accept"
            reason = "slow_supports_fast_with_boundary_or_label_update"
            next_action = "apply_slow_boundary_and_memory_relabel"
            confidence = 0.78 if support >= 0.65 else 0.65

    elif patch_type == "keep_fast_supported":
        decision = "accept"
        reason = "fast_segment_cross_model_supported"
        next_action = "keep_fast_segment"
        confidence = 0.82

    elif patch_type == "suppress_fast_candidate":
        if fast_quarantine and gt_support <= args.true_fa_threshold:
            decision = "accept"
            reason = "suppress_fast_fa_high_confidence"
            next_action = "remove_fast_segment"
            confidence = 0.85
        elif gt_support <= args.true_fa_threshold and seg_dur <= args.max_suppress_sec:
            decision = "accept"
            reason = "suppress_short_fast_fa_candidate"
            next_action = "remove_fast_segment"
            confidence = 0.72
        else:
            decision = "defer"
            reason = "do_not_suppress_without_strong_evidence"
            next_action = "keep_fast_segment_until_semantic_or_memory_check"
            confidence = 0.5

    elif patch_type == "align_slow_segment":
        decision = "accept"
        reason = "slow_segment_aligned_for_reference"
        next_action = "use_for_boundary_or_identity_consistency"
        confidence = 0.7

    if "memory_identity_low_confidence" in constraints and decision == "accept" and "relabel" in next_action:
        decision = "defer"
        reason = "memory_low_confidence_relabel_deferred"
        next_action = "request_memory_cleanup_before_relabel"
        confidence = min(confidence, 0.55)

    return {
        "decision": decision,
        "reason": reason,
        "constraints": constraints,
        "next_action": next_action,
        "confidence": round(confidence, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patches", required=True, type=Path)
    parser.add_argument("--windows", type=Path, default=None)
    parser.add_argument("--abnormal-windows", type=Path, default=None)
    parser.add_argument("--memory", type=Path, default=None)
    parser.add_argument("--output-jsonl", type=Path, default=Path("outputs/policy_agent/decisions.jsonl"))
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--summary-output", type=Path, default=None)
    parser.add_argument("--min-recover-sec", type=float, default=0.6)
    parser.add_argument("--max-suppress-sec", type=float, default=1.2)
    parser.add_argument("--true-speech-threshold", type=float, default=0.5)
    parser.add_argument("--true-fa-threshold", type=float, default=0.2)
    args = parser.parse_args()

    patch_rows = load_csv(args.patches)
    windows = load_window_rows(args.windows)
    abnormal = load_abnormal_windows(args.abnormal_windows)
    memory_quality = load_memory_quality(args.memory)

    if not patch_rows:
        raise SystemExit("No patch rows found")

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    output_csv = args.output_csv or args.output_jsonl.with_suffix(".csv")
    summary_output = args.summary_output or args.output_jsonl.with_name(args.output_jsonl.stem + "_summary.json")

    decisions = []
    for idx, row in enumerate(patch_rows):
        key = key_from_row(row)
        policy = decide_patch(
            row,
            windows.get(key),
            abnormal.get(key, set()),
            memory_quality.get(row["recording_id"]),
            args,
        )
        decision = {
            "patch_id": f"{row['recording_id']}:{row['window_size']}:{row['segment_idx']}:{row['source']}:{row['segment_id']}",
            "recording_id": row["recording_id"],
            "window_size": int(row["window_size"]),
            "segment_idx": int(row["segment_idx"]),
            "source": row["source"],
            "patch_type": row["patch_type"],
            "start": float(row["start"]),
            "end": float(row["end"]),
            "duration": duration(row),
            "speaker": row["speaker"],
            "matched_source": row.get("matched_source", ""),
            "matched_speaker": row.get("matched_speaker", ""),
            "support_ratio": float(row.get("support_ratio") or 0.0),
            "gt_support_ratio_eval_only": float(row.get("gt_support_ratio") or 0.0),
            "decision": policy["decision"],
            "reason": policy["reason"],
            "constraints": policy["constraints"],
            "next_action": policy["next_action"],
            "confidence": policy["confidence"],
            "abnormal_flags": sorted(abnormal.get(key, set())),
            "decision_index": idx,
        }
        decisions.append(decision)

    with args.output_jsonl.open("w", encoding="utf-8") as f:
        for decision in decisions:
            f.write(json.dumps(decision, ensure_ascii=False) + "\n")

    csv_fieldnames = [
        "patch_id",
        "recording_id",
        "window_size",
        "segment_idx",
        "source",
        "patch_type",
        "start",
        "end",
        "duration",
        "speaker",
        "matched_source",
        "matched_speaker",
        "support_ratio",
        "gt_support_ratio_eval_only",
        "decision",
        "reason",
        "constraints",
        "next_action",
        "confidence",
        "abnormal_flags",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fieldnames)
        writer.writeheader()
        for decision in decisions:
            row = {key: decision[key] for key in csv_fieldnames}
            row["constraints"] = "|".join(decision["constraints"])
            row["abnormal_flags"] = "|".join(decision["abnormal_flags"])
            writer.writerow(row)

    decision_counts = Counter(decision["decision"] for decision in decisions)
    reason_counts = Counter(decision["reason"] for decision in decisions)
    patch_decision_counts = Counter((decision["patch_type"], decision["decision"]) for decision in decisions)
    accepted_true_speech = sum(
        1
        for decision in decisions
        if decision["decision"] == "accept"
        and decision["patch_type"] == "recover_slow_segment"
        and decision["gt_support_ratio_eval_only"] >= args.true_speech_threshold
    )
    accepted_recover = sum(
        1
        for decision in decisions
        if decision["decision"] == "accept" and decision["patch_type"] == "recover_slow_segment"
    )
    accepted_true_fa = sum(
        1
        for decision in decisions
        if decision["decision"] == "accept"
        and decision["patch_type"] == "suppress_fast_candidate"
        and decision["gt_support_ratio_eval_only"] <= args.true_fa_threshold
    )
    accepted_suppress = sum(
        1
        for decision in decisions
        if decision["decision"] == "accept" and decision["patch_type"] == "suppress_fast_candidate"
    )
    summary = {
        "patches": str(args.patches),
        "windows": str(args.windows) if args.windows else None,
        "abnormal_windows": str(args.abnormal_windows) if args.abnormal_windows else None,
        "memory": str(args.memory) if args.memory else None,
        "decisions": len(decisions),
        "decision_counts": dict(decision_counts),
        "reason_counts": dict(reason_counts),
        "patch_decision_counts": {f"{key[0]}::{key[1]}": value for key, value in patch_decision_counts.items()},
        "accepted_recover_slow_segments": accepted_recover,
        "accepted_recover_true_speech_rate": accepted_true_speech / accepted_recover if accepted_recover else 0.0,
        "accepted_suppress_fast_segments": accepted_suppress,
        "accepted_suppress_true_fa_rate": accepted_true_fa / accepted_suppress if accepted_suppress else 0.0,
        "output_jsonl": str(args.output_jsonl),
        "output_csv": str(output_csv),
    }
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Policy Agent decisions")
    print("decisions=%d jsonl=%s csv=%s" % (len(decisions), args.output_jsonl, output_csv))
    print("decision_counts", dict(decision_counts))
    print("top_reasons", reason_counts.most_common(10))
    print(
        "accepted recover true speech=%.1f%%, accepted suppress true FA=%.1f%%"
        % (
            summary["accepted_recover_true_speech_rate"] * 100,
            summary["accepted_suppress_true_fa_rate"] * 100,
        )
    )
    print("summary_json=%s" % summary_output)


if __name__ == "__main__":
    main()
