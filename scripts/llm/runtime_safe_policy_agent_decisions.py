#!/usr/bin/env python3
"""Runtime-safe deterministic Policy Agent for diarization patches.

This gate mirrors the shape of the earlier development Policy Agent but does
not read GT support, DER, Miss, FA, Conf, or oracle speaker labels. Its only
abnormal-window evidence is the deployable prediction proxy built from
Fast/Slow outputs.
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


WindowKey = tuple[str, int, int]


def as_float(value: object, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def key_from_row(row: dict[str, object]) -> WindowKey:
    return (str(row["recording_id"]), int(as_float(row["window_size"])), int(as_float(row["segment_idx"])))


def duration(row: dict[str, object]) -> float:
    return max(0.0, as_float(row.get("end")) - as_float(row.get("start")))


def load_proxy_flags(path: Path | None) -> dict[WindowKey, set[str]]:
    flags: dict[WindowKey, set[str]] = defaultdict(set)
    for row in load_csv(path):
        model = row.get("model_name", "")
        prefix = "fast" if model.startswith("nemo") else "slow" if model.startswith("diarizen") else "model"
        key = key_from_row(row)
        for reason in row.get("reason", "").split(","):
            if reason:
                flags[key].add(f"{prefix}_{reason}")
    return flags


def load_window_rows(path: Path | None) -> dict[WindowKey, dict[str, str]]:
    return {key_from_row(row): row for row in load_csv(path)}


def constraints_for(row: dict[str, str], window: dict[str, str] | None, flags: set[str]) -> list[str]:
    constraints = []
    if duration(row) < 0.6:
        constraints.append("do_not_update_memory_on_short_segment")
    if as_float(row.get("support_ratio")) < 0.35:
        constraints.append("low_cross_model_support")
    if flags:
        constraints.append("window_has_deployable_proxy_flags")
    if any(flag.startswith("slow_") for flag in flags):
        constraints.append("slow_proxy_window_requires_review")
    if window and as_float(window.get("fast_slow_disagreement_sec")) >= 8.0:
        constraints.append("cross_model_disagreement_high")
    return constraints


def decide_patch(row: dict[str, str], window: dict[str, str] | None, flags: set[str], args: argparse.Namespace) -> dict[str, object]:
    patch_type = row["patch_type"]
    support = as_float(row.get("support_ratio"))
    seg_dur = duration(row)
    constraints = constraints_for(row, window, flags)
    slow_proxy_risky = any(
        flag.startswith("slow_")
        and (
            "pred_speech_too_long" in flag
            or "speech_much_longer" in flag
            or "disagreement_high" in flag
            or "segment_count_gap" in flag
        )
        for flag in flags
    )
    fast_proxy_risky = any(flag.startswith("fast_") for flag in flags)

    decision = "defer"
    reason = "runtime_safe_review"
    next_action = "hold_for_more_context"
    confidence = 0.45

    if patch_type == "recover_slow_segment":
        if slow_proxy_risky and support < args.recover_accept_support:
            decision = "quarantine"
            reason = "recover_from_slow_proxy_risk_window"
            next_action = "do_not_write_back_until_proxy_review"
            confidence = 0.25
        elif seg_dur < args.min_recover_sec:
            decision = "defer"
            reason = "recover_segment_too_short"
            next_action = "merge_with_neighbor_or_wait"
            confidence = 0.5
        elif support >= args.recover_accept_support:
            decision = "accept"
            reason = "recover_supported_by_cross_model_evidence"
            next_action = "write_slow_segment_to_timeline"
            confidence = 0.72
        else:
            decision = "defer"
            reason = "recover_needs_semantic_or_memory_check"
            next_action = "ask_semantic_agent_or_wait_for_more_context"
            confidence = 0.52
    elif patch_type == "boundary_fix_or_relabel":
        if slow_proxy_risky:
            decision = "defer"
            reason = "boundary_patch_from_slow_proxy_risk_window"
            next_action = "keep_fast_boundary_temporarily"
            confidence = 0.35
        elif support >= args.boundary_accept_support:
            decision = "accept"
            reason = "slow_supports_fast_boundary_or_label_update"
            next_action = "apply_bounded_boundary_or_label_update"
            confidence = 0.7
        else:
            decision = "defer"
            reason = "boundary_patch_low_support"
            next_action = "keep_fast_boundary_temporarily"
            confidence = 0.45
    elif patch_type == "keep_fast_supported":
        decision = "accept"
        reason = "fast_segment_cross_model_supported"
        next_action = "keep_fast_segment"
        confidence = 0.8 if support >= 0.65 else 0.62
    elif patch_type == "suppress_fast_candidate":
        if fast_proxy_risky and support <= args.suppress_accept_support and seg_dur <= args.max_suppress_sec:
            decision = "accept"
            reason = "suppress_short_fast_candidate_with_proxy_risk"
            next_action = "remove_fast_segment"
            confidence = 0.62
        else:
            decision = "defer"
            reason = "do_not_suppress_without_strong_deployable_evidence"
            next_action = "keep_fast_segment_until_semantic_or_memory_check"
            confidence = 0.48
    elif patch_type == "align_slow_segment":
        decision = "accept"
        reason = "slow_segment_aligned_for_reference"
        next_action = "use_for_boundary_or_identity_consistency"
        confidence = 0.66

    return {
        "decision": decision,
        "reason": reason,
        "constraints": constraints,
        "next_action": next_action,
        "confidence": round(confidence, 3),
    }


def write_outputs(decisions: list[dict[str, object]], args: argparse.Namespace) -> None:
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    output_csv = args.output_csv or args.output_jsonl.with_suffix(".csv")
    summary_output = args.summary_output or args.output_jsonl.with_name(args.output_jsonl.stem + "_summary.json")

    with args.output_jsonl.open("w", encoding="utf-8") as handle:
        for row in decisions:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    fieldnames = [
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
        "decision",
        "reason",
        "constraints",
        "next_action",
        "confidence",
        "abnormal_flags",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for decision in decisions:
            row = {field: decision.get(field, "") for field in fieldnames}
            row["constraints"] = "|".join(decision.get("constraints", []))
            row["abnormal_flags"] = "|".join(decision.get("abnormal_flags", []))
            writer.writerow(row)

    decision_counts = Counter(str(row["decision"]) for row in decisions)
    reason_counts = Counter(str(row["reason"]) for row in decisions)
    summary = {
        "patches": str(args.patches),
        "window_features": str(args.windows) if args.windows else None,
        "deployable_proxy_flags": str(args.deployable_abnormal_windows) if args.deployable_abnormal_windows else None,
        "decisions": len(decisions),
        "decision_counts": dict(decision_counts),
        "reason_counts": dict(reason_counts),
        "output_jsonl": str(args.output_jsonl),
        "output_csv": str(output_csv),
        "runtime_contract": "no_gt_der_miss_fa_or_oracle_fields_used",
    }
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output_jsonl}")
    print(f"Wrote {output_csv}")
    print(f"Wrote {summary_output}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patches", type=Path, default=Path("outputs/segment_patches/sortformer_diarizen_120_patches.csv"))
    parser.add_argument("--windows", type=Path, default=Path("outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv"))
    parser.add_argument("--deployable-abnormal-windows", type=Path, default=Path("outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl"))
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--summary-output", type=Path, default=None)
    parser.add_argument("--min-recover-sec", type=float, default=0.6)
    parser.add_argument("--max-suppress-sec", type=float, default=1.2)
    parser.add_argument("--recover-accept-support", type=float, default=0.65)
    parser.add_argument("--boundary-accept-support", type=float, default=0.65)
    parser.add_argument("--suppress-accept-support", type=float, default=0.15)
    args = parser.parse_args()

    patches = load_csv(args.patches)
    windows = load_window_rows(args.windows)
    flags_by_window = load_proxy_flags(args.deployable_abnormal_windows)
    if not patches:
        raise SystemExit("No patch rows found")

    decisions: list[dict[str, object]] = []
    for idx, row in enumerate(patches):
        key = key_from_row(row)
        flags = sorted(flags_by_window.get(key, set()))
        policy = decide_patch(row, windows.get(key), set(flags), args)
        decisions.append(
            {
                "patch_id": f"{row['recording_id']}:{int(as_float(row['window_size']))}:{int(as_float(row['segment_idx']))}:{row['source']}:{row['segment_id']}",
                "recording_id": row["recording_id"],
                "window_size": int(as_float(row["window_size"])),
                "segment_idx": int(as_float(row["segment_idx"])),
                "source": row["source"],
                "patch_type": row["patch_type"],
                "start": as_float(row["start"]),
                "end": as_float(row["end"]),
                "duration": duration(row),
                "speaker": row["speaker"],
                "matched_source": row.get("matched_source", ""),
                "matched_speaker": row.get("matched_speaker", ""),
                "support_ratio": as_float(row.get("support_ratio")),
                "decision": policy["decision"],
                "reason": policy["reason"],
                "constraints": policy["constraints"],
                "next_action": policy["next_action"],
                "confidence": policy["confidence"],
                "abnormal_flags": flags,
                "decision_index": idx,
            }
        )

    write_outputs(decisions, args)


if __name__ == "__main__":
    main()
