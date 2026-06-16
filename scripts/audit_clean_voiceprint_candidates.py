#!/usr/bin/env python3
"""Audit clean low-risk patches for possible voiceprint-backed writeback."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "patch_id",
        "recording_id",
        "window_size",
        "segment_idx",
        "source",
        "patch_type",
        "decision",
        "gate_category",
        "duration",
        "support_ratio",
        "voiceprint_bucket",
        "memory_confidence",
        "similarity_margin",
        "evidence_status",
        "candidate_class",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Clean Voiceprint Candidate Audit",
        "",
        "| Clean patches | With voiceprint | High bucket | Medium bucket | LLM candidates | Rule auto | Rule reference | Avg margin | P95 margin |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        (
            "| {clean_patches} | {with_voiceprint} | {high_bucket} | {medium_bucket} | {llm_candidates} | "
            "{rule_auto_writeback} | {rule_reference_only} | {avg_margin:.3f} | {p95_margin:.3f} |"
        ).format(**summary),
        "",
        "## Reading",
        "",
        "- Clean means no abnormal flags, non-first window, duration and support above thresholds.",
        "- The current clean surface is already accepted by deterministic rules or reference-only alignment; it is not an LLM-defer backlog.",
        "- High voiceprint margin can be used as an audit signal for future low-risk relabel tests, but does not create direct writeback authority.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-decisions", type=Path, default=Path("outputs/writeback_gate_120/gate_decisions.csv"))
    parser.add_argument("--voiceprint-evidence", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_candidate_120_voiceprint.csv"))
    parser.add_argument("--min-duration", type=float, default=0.6)
    parser.add_argument("--min-support", type=float, default=0.8)
    parser.add_argument("--min-segment-idx", type=int, default=1)
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_candidate_120_audit.csv"))
    parser.add_argument("--patch-id-file", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_candidate_120_patch_ids.txt"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_candidate_120_summary.json"))
    parser.add_argument("--summary-md", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_candidate_120_summary.md"))
    args = parser.parse_args()

    evidence = {row["patch_id"]: row for row in load_csv(args.voiceprint_evidence)} if args.voiceprint_evidence.exists() else {}
    output_rows = []
    for row in load_csv(args.gate_decisions):
        if row.get("abnormal_flags"):
            continue
        if int(row["segment_idx"]) < args.min_segment_idx:
            continue
        if float(row["duration"]) < args.min_duration:
            continue
        if float(row["support_ratio"]) < args.min_support:
            continue
        vp = evidence.get(row["patch_id"], {})
        bucket = vp.get("confidence_bucket", "missing") if vp else row.get("voiceprint_bucket", "missing")
        status = vp.get("evidence_status", "") if vp else row.get("voiceprint_status", "")
        candidate_class = (
            "voiceprint_high_rule_auto"
            if bucket == "high" and row["gate_category"] == "rule_auto_writeback"
            else "voiceprint_high_reference"
            if bucket == "high" and row["gate_category"] == "rule_reference_only"
            else row["gate_category"]
        )
        output_rows.append(
            {
                "patch_id": row["patch_id"],
                "recording_id": row["recording_id"],
                "window_size": row["window_size"],
                "segment_idx": row["segment_idx"],
                "source": row["patch_id"].split(":")[3],
                "patch_type": row["patch_type"],
                "decision": row["decision"],
                "gate_category": row["gate_category"],
                "duration": row["duration"],
                "support_ratio": row["support_ratio"],
                "voiceprint_bucket": bucket,
                "memory_confidence": vp.get("memory_confidence", ""),
                "similarity_margin": vp.get("similarity_margin", ""),
                "evidence_status": status,
                "candidate_class": candidate_class,
            }
        )

    margins = [float(row["similarity_margin"]) for row in output_rows if row["similarity_margin"]]
    buckets = Counter(row["voiceprint_bucket"] for row in output_rows)
    categories = Counter(row["gate_category"] for row in output_rows)
    classes = Counter(row["candidate_class"] for row in output_rows)
    with_voiceprint = sum(1 for row in output_rows if row["evidence_status"] == "ok")
    summary = {
        "gate_decisions": str(args.gate_decisions),
        "voiceprint_evidence": str(args.voiceprint_evidence),
        "clean_patches": len(output_rows),
        "with_voiceprint": with_voiceprint,
        "high_bucket": buckets.get("high", 0),
        "medium_bucket": buckets.get("medium", 0),
        "low_bucket": buckets.get("low", 0),
        "missing_bucket": buckets.get("missing", 0),
        "llm_candidates": categories.get("llm_writeback_candidate", 0),
        "rule_auto_writeback": categories.get("rule_auto_writeback", 0),
        "rule_reference_only": categories.get("rule_reference_only", 0),
        "category_counts": dict(categories),
        "candidate_class_counts": dict(classes),
        "avg_margin": mean(margins),
        "p50_margin": percentile(margins, 0.50),
        "p95_margin": percentile(margins, 0.95),
        "runtime_contract": "clean_no_abnormal_high_support_voiceprint_candidate_audit",
    }

    write_csv(output_rows, args.output_csv)
    args.patch_id_file.parent.mkdir(parents=True, exist_ok=True)
    args.patch_id_file.write_text("\n".join(row["patch_id"] for row in output_rows) + "\n", encoding="utf-8")
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, args.summary_md)
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.patch_id_file}")
    print(f"Wrote {args.summary_json}")
    print(f"Wrote {args.summary_md}")


if __name__ == "__main__":
    main()
