#!/usr/bin/env python3
"""Analyze LLM audit defers and repeatability drift on clean rule-auto patches."""

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
from typing import Any


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_patch_decisions(path: Path) -> dict[str, dict[str, Any]]:
    decisions = {}
    for row in load_jsonl(path):
        for patch in row.get("patch_decisions", []):
            decisions[patch["patch_id"]] = {
                "window_id": row.get("window_id", ""),
                "window_reason": row.get("window_reason", ""),
                "call_seconds": row.get("call_seconds", ""),
                **patch,
            }
    return decisions


def read_patch_ids(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def duration_bucket(value: float) -> str:
    if value < 0.9:
        return "lt_0.9s"
    if value < 1.5:
        return "0.9_1.5s"
    if value < 3.0:
        return "1.5_3.0s"
    return "gte_3.0s"


def support_bucket(value: float) -> str:
    if value < 0.85:
        return "lt_0.85"
    if value < 0.95:
        return "0.85_0.95"
    return "gte_0.95"


def margin_bucket(value: float) -> str:
    if value < 0.5:
        return "lt_0.50"
    if value < 0.6:
        return "0.50_0.60"
    return "gte_0.60"


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "patch_id",
        "case_type",
        "recording_id",
        "segment_idx",
        "duration",
        "support_ratio",
        "similarity_margin",
        "memory_confidence",
        "full_decision",
        "full_reason",
        "full_constraints",
        "expanded_decision",
        "runtime_policy",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(summary: dict[str, Any], cases: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "# Clean LLM Disagreement Analysis",
        "",
        "| Surface patches | Full accepts | Full defers | Repeat drift | Review-signal cases | Avg review duration |",
        "|---:|---:|---:|---:|---:|---:|",
        (
            "| {surface_patches} | {full_accepts} | {full_defers} | {repeatability_drifts} | "
            "{review_signal_cases} | {avg_review_duration:.2f}s |"
        ).format(**summary),
        "",
        "## Duration Buckets",
        "",
        "| Bucket | Patches | Full defers | Defer rate |",
        "|---|---:|---:|---:|",
    ]
    for row in summary["duration_buckets"]:
        lines.append(
            f"| {row['bucket']} | {row['patches']} | {row['full_defers']} | {row['defer_rate']:.1%} |"
        )
    lines.extend(
        [
            "",
            "## Review-Signal Cases",
            "",
            "| Patch ID | Case | Duration | Support | Margin | Full decision | Expanded decision | Runtime policy |",
            "|---|---|---:|---:|---:|---|---|---|",
        ]
    )
    for row in cases:
        lines.append(
            "| `{patch_id}` | {case_type} | {duration} | {support_ratio} | {similarity_margin} | "
            "{full_decision} | {expanded_decision} | {runtime_policy} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Full-surface LLM defers and repeatability drifts are treated as review/explanation signals.",
            "- They do not grant the LLM authority to override deterministic bounded Rule writeback.",
            "- Short duration and lower support/margin are useful triage features, but the full surface still has high Rule/LLM agreement.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-jsonl", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_full.jsonl"))
    parser.add_argument("--expanded-jsonl", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_expanded.jsonl"))
    parser.add_argument("--repeatability-json", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_repeatability.json"))
    parser.add_argument("--audit-csv", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_candidate_120_audit.csv"))
    parser.add_argument("--patch-id-file", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_full_patch_ids.txt"))
    parser.add_argument("--output-json", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_disagreement_analysis.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_disagreement_analysis.md"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_disagreement_cases.csv"))
    args = parser.parse_args()

    full_decisions = load_patch_decisions(args.full_jsonl)
    expanded_decisions = load_patch_decisions(args.expanded_jsonl) if args.expanded_jsonl.exists() else {}
    repeatability = load_json(args.repeatability_json)
    audit_rows = {row["patch_id"]: row for row in load_csv(args.audit_csv)}
    patch_ids = read_patch_ids(args.patch_id_file)

    drift_ids = {row["patch_id"] for row in repeatability.get("changed_patch_decisions", [])}
    full_defer_ids = {
        patch_id
        for patch_id in patch_ids
        if full_decisions.get(patch_id, {}).get("decision") != "accept"
    }
    review_ids = sorted(full_defer_ids.union(drift_ids))

    surface_rows = [audit_rows[patch_id] for patch_id in patch_ids if patch_id in audit_rows]
    duration_counts = Counter(duration_bucket(float(row["duration"])) for row in surface_rows)
    duration_defers = Counter(
        duration_bucket(float(audit_rows[patch_id]["duration"]))
        for patch_id in full_defer_ids
        if patch_id in audit_rows
    )
    duration_bucket_rows = []
    for bucket in ["lt_0.9s", "0.9_1.5s", "1.5_3.0s", "gte_3.0s"]:
        patches = duration_counts.get(bucket, 0)
        defers = duration_defers.get(bucket, 0)
        duration_bucket_rows.append(
            {
                "bucket": bucket,
                "patches": patches,
                "full_defers": defers,
                "defer_rate": defers / patches if patches else 0.0,
            }
        )

    cases = []
    for patch_id in review_ids:
        audit = audit_rows.get(patch_id, {})
        full = full_decisions.get(patch_id, {})
        expanded = expanded_decisions.get(patch_id, {})
        is_full_defer = patch_id in full_defer_ids
        is_drift = patch_id in drift_ids
        if is_full_defer and is_drift:
            case_type = "full_defer_and_repeatability_drift"
        elif is_full_defer:
            case_type = "full_defer"
        else:
            case_type = "repeatability_drift"
        cases.append(
            {
                "patch_id": patch_id,
                "case_type": case_type,
                "recording_id": audit.get("recording_id", ""),
                "segment_idx": audit.get("segment_idx", ""),
                "duration": f"{float(audit.get('duration') or 0.0):.2f}",
                "support_ratio": f"{float(audit.get('support_ratio') or 0.0):.3f}",
                "similarity_margin": f"{float(audit.get('similarity_margin') or 0.0):.3f}",
                "memory_confidence": f"{float(audit.get('memory_confidence') or 0.0):.3f}",
                "full_decision": full.get("decision", ""),
                "full_reason": full.get("reason", ""),
                "full_constraints": ";".join(full.get("constraints", [])),
                "expanded_decision": expanded.get("decision", ""),
                "runtime_policy": "review_signal_only_no_rule_override",
            }
        )

    full_accepts = sum(1 for patch_id in patch_ids if full_decisions.get(patch_id, {}).get("decision") == "accept")
    review_durations = [float(row["duration"]) for row in cases]
    support_counts = Counter(support_bucket(float(row["support_ratio"])) for row in surface_rows)
    margin_counts = Counter(margin_bucket(float(row["similarity_margin"])) for row in surface_rows)
    summary = {
        "full_jsonl": str(args.full_jsonl),
        "expanded_jsonl": str(args.expanded_jsonl),
        "surface_patches": len(patch_ids),
        "surface_windows": len({":".join(patch_id.split(":")[:3]) for patch_id in patch_ids}),
        "full_accepts": full_accepts,
        "full_defers": len(full_defer_ids),
        "repeatability_drifts": len(drift_ids),
        "review_signal_cases": len(review_ids),
        "review_signal_patch_ids": review_ids,
        "avg_review_duration": mean(review_durations),
        "duration_buckets": duration_bucket_rows,
        "support_bucket_counts": dict(support_counts),
        "margin_bucket_counts": dict(margin_counts),
        "runtime_contract": "llm_disagreement_review_signal_only",
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(cases, args.output_csv)
    write_markdown(summary, cases, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
