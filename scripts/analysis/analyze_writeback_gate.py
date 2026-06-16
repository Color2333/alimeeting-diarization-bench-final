#!/usr/bin/env python3
"""Analyze low-risk writeback gates for diarization patch decisions.

The goal is to separate:
- patches that the rule agent can safely write back without LLM;
- patches that are plausible LLM writeback candidates;
- patches that should stay defer/review/quarantine.
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
from collections import Counter
from pathlib import Path
from typing import Any


SEMANTIC_REASONS = {
    "memory_low_confidence_relabel_deferred",
    "recover_segment_too_short",
    "do_not_suppress_without_strong_evidence",
}

WRITEBACK_PATCH_TYPES = {
    "boundary_fix_or_relabel",
    "recover_slow_segment",
    "keep_fast_supported",
}


def load_decisions(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        rows = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_voiceprint(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {row["patch_id"]: row for row in csv.DictReader(f)}


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def flags(row: dict[str, Any]) -> list[str]:
    value = row.get("abnormal_flags", [])
    if isinstance(value, list):
        return value
    if not value:
        return []
    return [item for item in str(value).split(";") if item]


def classify(row: dict[str, Any], vp: dict[str, str], args: argparse.Namespace) -> tuple[str, list[str]]:
    blockers: list[str] = []
    duration = as_float(row.get("duration"))
    support = as_float(row.get("support_ratio"))
    segment_idx = int(as_float(row.get("segment_idx"), -1))
    patch_type = row.get("patch_type", "")
    decision = row.get("decision", "")
    reason = row.get("reason", "")
    abnormal_flags = flags(row)
    has_abnormal = bool(abnormal_flags)
    slow_abnormal = any(flag.startswith("slow_high_der") or flag.startswith("slow_high_fa") for flag in abnormal_flags)
    bucket = vp.get("confidence_bucket", "missing") if vp else "missing"
    evidence_status = vp.get("evidence_status", "") if vp else ""

    if decision == "quarantine" or any("high_der" in flag or "high_fa" in flag for flag in abnormal_flags):
        return "guard_or_quarantine", ["high_error_or_quarantine"]

    if decision == "accept":
        if patch_type == "align_slow_segment":
            return "rule_reference_only", ["slow_reference_segment"]
        if patch_type == "recover_slow_segment":
            if slow_abnormal:
                blockers.append("slow_abnormal_flags")
            if duration < args.min_duration:
                blockers.append("short_duration")
            if blockers:
                return "rule_accept_needs_review", blockers
            return "rule_recover_writeback", []
        if has_abnormal:
            blockers.append("abnormal_flags")
        if duration < args.min_duration:
            blockers.append("short_duration")
        if support < args.min_support:
            blockers.append("low_cross_model_support")
        if patch_type not in WRITEBACK_PATCH_TYPES:
            blockers.append("unsupported_patch_type")
        if blockers == ["short_duration"] and patch_type == "boundary_fix_or_relabel":
            return "rule_label_only_writeback", ["do_not_update_memory_on_short_segment"]
        if blockers:
            return "rule_accept_needs_review", blockers
        return "rule_auto_writeback", []

    if reason in SEMANTIC_REASONS:
        if has_abnormal:
            blockers.append("abnormal_flags")
        if segment_idx < args.min_segment_idx:
            blockers.append("enrollment_or_first_window")
        if duration < args.min_duration:
            blockers.append("short_duration")
        if support < args.min_support:
            blockers.append("low_cross_model_support")
        if patch_type not in {"boundary_fix_or_relabel", "recover_slow_segment"}:
            blockers.append("unsupported_patch_type")
        if not vp:
            blockers.append("missing_voiceprint")
        elif bucket != "high":
            blockers.append(f"voiceprint_{bucket}")
        if evidence_status and evidence_status != "ok":
            blockers.append(f"voiceprint_status_{evidence_status}")
        if blockers:
            return "llm_defer_review", blockers
        return "llm_writeback_candidate", []

    if decision != "accept":
        return "non_accept_review", ["non_semantic_non_accept"]
    return "other", []


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, default=Path("outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl"))
    parser.add_argument("--voiceprint-evidence", type=Path, default=Path("outputs/voiceprint_patch_evidence/real_semantic_all_patch_evidence.csv"))
    parser.add_argument("--min-duration", type=float, default=0.6)
    parser.add_argument("--min-support", type=float, default=0.8)
    parser.add_argument("--min-segment-idx", type=int, default=1)
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/writeback_gate/gate_decisions.csv"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/writeback_gate/gate_summary.json"))
    parser.add_argument("--summary-md", type=Path, default=Path("outputs/writeback_gate/gate_summary.md"))
    args = parser.parse_args()

    voiceprint = load_voiceprint(args.voiceprint_evidence)
    rows = []
    category_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    semantic_blocker_counts: Counter[str] = Counter()
    semantic_total = 0

    for row in load_decisions(args.decisions):
        vp = voiceprint.get(row["patch_id"], {})
        category, blockers = classify(row, vp, args)
        category_counts[category] += 1
        blocker_counts.update(blockers)
        if row.get("reason") in SEMANTIC_REASONS:
            semantic_total += 1
            semantic_blocker_counts.update(blockers)
        rows.append(
            {
                "patch_id": row["patch_id"],
                "recording_id": row["recording_id"],
                "window_size": row["window_size"],
                "segment_idx": row["segment_idx"],
                "patch_type": row["patch_type"],
                "decision": row["decision"],
                "reason": row["reason"],
                "duration": row["duration"],
                "support_ratio": row.get("support_ratio", ""),
                "abnormal_flags": ";".join(flags(row)),
                "voiceprint_bucket": vp.get("confidence_bucket", "missing") if vp else "missing",
                "voiceprint_status": vp.get("evidence_status", "") if vp else "",
                "gate_category": category,
                "gate_blockers": ";".join(blockers),
            }
        )

    write_csv(
        args.output_csv,
        rows,
        [
            "patch_id",
            "recording_id",
            "window_size",
            "segment_idx",
            "patch_type",
            "decision",
            "reason",
            "duration",
            "support_ratio",
            "abnormal_flags",
            "voiceprint_bucket",
            "voiceprint_status",
            "gate_category",
            "gate_blockers",
        ],
    )

    summary = {
        "decisions": str(args.decisions),
        "voiceprint_evidence": str(args.voiceprint_evidence),
        "total_patches": len(rows),
        "semantic_patches": semantic_total,
        "category_counts": dict(category_counts),
        "blocker_counts": dict(blocker_counts),
        "semantic_blocker_counts": dict(semantic_blocker_counts),
        "gate": {
            "min_duration": args.min_duration,
            "min_support": args.min_support,
            "min_segment_idx": args.min_segment_idx,
            "voiceprint_required": "high",
        },
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "| Category | Patches |",
        "|---|---:|",
        *[f"| {key} | {value} |" for key, value in sorted(category_counts.items())],
        "",
        "| Semantic blocker | Count |",
        "|---|---:|",
        *[f"| {key} | {value} |" for key, value in sorted(semantic_blocker_counts.items())],
    ]
    args.summary_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.summary_json}")
    print(f"Wrote {args.summary_md}")


if __name__ == "__main__":
    main()
