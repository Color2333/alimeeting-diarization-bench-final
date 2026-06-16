#!/usr/bin/env python3
"""Build an offline timeline audit table from LLM review-signal cases."""

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


def load_llm_patch_context(path: Path) -> dict[str, dict[str, Any]]:
    context = {}
    for row in load_jsonl(path):
        window_id = row.get("window_id", "")
        for patch in row.get("patch_decisions", []):
            context[patch["patch_id"]] = {
                "window_id": window_id,
                "window_reason": row.get("window_reason", ""),
                "llm_call_seconds": float(row.get("call_seconds") or 0.0),
                "llm_decision": patch.get("decision", ""),
                "llm_reason": patch.get("reason", ""),
                "llm_constraints": ";".join(patch.get("constraints", [])),
                "llm_next_action": patch.get("next_action", ""),
            }
    return context


def should_block_memory_update(case: dict[str, str], llm: dict[str, Any]) -> bool:
    duration = float(case.get("duration") or 0.0)
    support = float(case.get("support_ratio") or 0.0)
    margin = float(case.get("similarity_margin") or 0.0)
    constraints = str(llm.get("llm_constraints", ""))
    reason = str(llm.get("llm_reason", ""))
    if duration < 1.0:
        return True
    if support < 0.85:
        return True
    if margin < 0.50:
        return True
    if "memory" in constraints or "memory" in reason:
        return True
    return False


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "patch_id",
        "window_id",
        "case_type",
        "gate_category",
        "rule_timeline_action",
        "llm_review_action",
        "blocks_timeline_writeback",
        "blocks_memory_update",
        "rule_arrival_avg_sec",
        "llm_review_arrival_sec",
        "duration",
        "support_ratio",
        "similarity_margin",
        "memory_confidence",
        "full_decision",
        "full_reason",
        "full_constraints",
        "expanded_decision",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(summary: dict[str, Any], rows: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "# Timeline Review Audit",
        "",
        "| Review cases | Blocks timeline writeback | Blocks memory update | Avg rule arrival | Avg LLM review arrival |",
        "|---:|---:|---:|---:|---:|",
        (
            "| {review_cases} | {blocks_timeline_writeback} | {blocks_memory_update} | "
            "{rule_arrival_avg_sec:.2f}s | {llm_review_arrival_avg_sec:.2f}s |"
        ).format(**summary),
        "",
        "## Cases",
        "",
        "| Patch ID | Case | Gate | Rule action | LLM action | Block timeline | Block memory | LLM arrival |",
        "|---|---|---|---|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| `{patch_id}` | {case_type} | {gate_category} | {rule_timeline_action} | "
            "{llm_review_action} | {blocks_timeline_writeback} | {blocks_memory_update} | "
            "{llm_review_arrival_sec}s |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- LLM review signals do not block bounded Rule timeline writeback.",
            "- They do block speaker-memory update or request a review note when short duration, low support/margin, or LLM memory-risk constraints appear.",
            "- The arrival estimate is rule-writeback average delay plus the observed LLM call duration for that window.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_disagreement_cases.csv"))
    parser.add_argument("--gate-decisions", type=Path, default=Path("outputs/writeback_gate_120/gate_decisions.csv"))
    parser.add_argument("--system-timeline", type=Path, default=Path("outputs/system_timeline/summary.json"))
    parser.add_argument("--llm-jsonl", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_full.jsonl"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/timeline_review_audit/llm_review_signal_timeline_audit.csv"))
    parser.add_argument("--output-json", type=Path, default=Path("outputs/timeline_review_audit/llm_review_signal_timeline_audit_summary.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/timeline_review_audit/llm_review_signal_timeline_audit.md"))
    args = parser.parse_args()

    cases = load_csv(args.cases)
    gate = {row["patch_id"]: row for row in load_csv(args.gate_decisions)}
    timeline = load_json(args.system_timeline)
    llm_context = load_llm_patch_context(args.llm_jsonl)
    rule_avg = float(timeline.get("rule_writeback_avg_delay_sec") or 0.0)
    rule_p95 = float(timeline.get("rule_writeback_p95_delay_sec") or rule_avg)

    rows = []
    for case in cases:
        patch_id = case["patch_id"]
        gate_row = gate.get(patch_id, {})
        llm = llm_context.get(patch_id, {})
        memory_block = should_block_memory_update(case, llm)
        llm_call = float(llm.get("llm_call_seconds") or 0.0)
        llm_decision = case.get("full_decision", "") or llm.get("llm_decision", "")
        if case.get("case_type") == "repeatability_drift":
            llm_action = "review_repeatability_drift"
        elif llm_decision == "defer":
            llm_action = "review_llm_defer"
        else:
            llm_action = "review_signal_only"
        rows.append(
            {
                "patch_id": patch_id,
                "window_id": ":".join(patch_id.split(":")[:3]),
                "case_type": case.get("case_type", ""),
                "gate_category": gate_row.get("gate_category", ""),
                "rule_timeline_action": "keep_rule_bounded_writeback",
                "llm_review_action": llm_action,
                "blocks_timeline_writeback": "0",
                "blocks_memory_update": "1" if memory_block else "0",
                "rule_arrival_avg_sec": f"{rule_avg:.2f}",
                "llm_review_arrival_sec": f"{rule_avg + llm_call:.2f}",
                "duration": case.get("duration", ""),
                "support_ratio": case.get("support_ratio", ""),
                "similarity_margin": case.get("similarity_margin", ""),
                "memory_confidence": case.get("memory_confidence", ""),
                "full_decision": case.get("full_decision", ""),
                "full_reason": case.get("full_reason", ""),
                "full_constraints": case.get("full_constraints", ""),
                "expanded_decision": case.get("expanded_decision", ""),
            }
        )

    blocks_timeline = sum(int(row["blocks_timeline_writeback"]) for row in rows)
    blocks_memory = sum(int(row["blocks_memory_update"]) for row in rows)
    arrivals = [float(row["llm_review_arrival_sec"]) for row in rows]
    summary = {
        "cases": str(args.cases),
        "gate_decisions": str(args.gate_decisions),
        "system_timeline": str(args.system_timeline),
        "review_cases": len(rows),
        "blocks_timeline_writeback": blocks_timeline,
        "blocks_memory_update": blocks_memory,
        "rule_arrival_avg_sec": rule_avg,
        "rule_arrival_p95_sec": rule_p95,
        "llm_review_arrival_avg_sec": sum(arrivals) / len(arrivals) if arrivals else 0.0,
        "llm_review_arrival_max_sec": max(arrivals) if arrivals else 0.0,
        "case_type_counts": dict(Counter(row["case_type"] for row in rows)),
        "llm_review_action_counts": dict(Counter(row["llm_review_action"] for row in rows)),
        "runtime_contract": "llm_review_signal_timeline_audit_no_writeback_override",
    }

    write_csv(rows, args.output_csv)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, rows, args.output_md)
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
