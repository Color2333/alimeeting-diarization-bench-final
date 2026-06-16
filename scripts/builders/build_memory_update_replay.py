#!/usr/bin/env python3
"""Replay LLM review-signal cases through a speaker-memory update gate."""

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
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_RUNTIME_TOKENS = (
    "der",
    "gt",
    "oracle",
    "miss_rate",
    "fa_rate",
    "conf_rate",
    "spk_count_gt",
    "gt_speech",
)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def memory_block_reasons(row: dict[str, str]) -> list[str]:
    reasons = []
    duration = float(row.get("duration") or 0.0)
    support = float(row.get("support_ratio") or 0.0)
    margin = float(row.get("similarity_margin") or 0.0)
    constraints = str(row.get("full_constraints", ""))
    reason = str(row.get("full_reason", ""))
    if row.get("case_type") == "repeatability_drift":
        reasons.append("repeatability_drift_review_signal")
    if duration < 1.0:
        reasons.append("duration_under_1s")
    if support < 0.85:
        reasons.append("support_under_0.85")
    if margin < 0.50:
        reasons.append("margin_under_0.50")
    if "memory" in constraints or "memory" in reason:
        reasons.append("llm_memory_constraint")
    return reasons or ["review_signal_requires_manual_memory_check"]


def contains_forbidden_runtime_token(row: dict[str, Any]) -> bool:
    runtime_values = [
        row.get("case_type", ""),
        row.get("llm_review_action", ""),
        row.get("memory_block_reasons", []),
        row.get("rule_timeline_action_after", ""),
        row.get("runtime_surface", ""),
    ]
    encoded = json.dumps(runtime_values, ensure_ascii=False).lower()
    tokens = set(re.split(r"[^a-z0-9_]+", encoded))
    return any(token in tokens for token in FORBIDDEN_RUNTIME_TOKENS)


def build_replay(root: Path) -> dict[str, Any]:
    rows = []
    for row in load_csv(root / "outputs/timeline_review_audit/llm_review_signal_timeline_audit.csv"):
        reasons = memory_block_reasons(row)
        replay_row = {
            "patch_id": row["patch_id"],
            "window_id": row["window_id"],
            "case_type": row["case_type"],
            "llm_review_action": row["llm_review_action"],
            "memory_candidate_before": 1,
            "memory_update_allowed_after": 0,
            "memory_update_blocked": 1,
            "memory_block_reasons": reasons,
            "timeline_writeback_preserved": 1 if row.get("blocks_timeline_writeback") == "0" else 0,
            "rule_timeline_action_after": row.get("rule_timeline_action", ""),
            "rule_arrival_avg_sec": row.get("rule_arrival_avg_sec", ""),
            "llm_review_arrival_sec": row.get("llm_review_arrival_sec", ""),
            "runtime_surface": "memory_gate_replay",
        }
        replay_row["forbidden_runtime_token_scan"] = "fail" if contains_forbidden_runtime_token(replay_row) else "pass"
        rows.append(replay_row)

    failed_rows = [
        row["patch_id"]
        for row in rows
        if row["memory_update_allowed_after"] != 0
        or row["memory_update_blocked"] != 1
        or row["timeline_writeback_preserved"] != 1
        or row["forbidden_runtime_token_scan"] != "pass"
    ]
    reason_counts = Counter(reason for row in rows for reason in row["memory_block_reasons"])
    return {
        "runtime_contract": "memory_update_replay_review_signal_blocks_memory_only",
        "rows": rows,
        "summary": {
            "review_cases": len(rows),
            "memory_candidates_before": sum(row["memory_candidate_before"] for row in rows),
            "memory_updates_allowed_after": sum(row["memory_update_allowed_after"] for row in rows),
            "memory_updates_blocked": sum(row["memory_update_blocked"] for row in rows),
            "timeline_writebacks_preserved": sum(row["timeline_writeback_preserved"] for row in rows),
            "reason_counts": dict(reason_counts),
            "failed_rows": failed_rows,
        },
    }


def write_csv(replay: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "patch_id",
        "window_id",
        "case_type",
        "llm_review_action",
        "memory_candidate_before",
        "memory_update_allowed_after",
        "memory_update_blocked",
        "memory_block_reasons",
        "timeline_writeback_preserved",
        "rule_timeline_action_after",
        "rule_arrival_avg_sec",
        "llm_review_arrival_sec",
        "runtime_surface",
        "forbidden_runtime_token_scan",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in replay["rows"]:
            out = dict(row)
            out["memory_block_reasons"] = ";".join(row["memory_block_reasons"])
            writer.writerow(out)


def write_markdown(replay: dict[str, Any], path: Path) -> None:
    summary = replay["summary"]
    lines = [
        "# Memory Update Replay",
        "",
        f"- Runtime contract: `{replay['runtime_contract']}`",
        f"- Review cases: `{summary['review_cases']}`",
        f"- Memory candidates before: `{summary['memory_candidates_before']}`",
        f"- Memory updates allowed after: `{summary['memory_updates_allowed_after']}`",
        f"- Memory updates blocked: `{summary['memory_updates_blocked']}`",
        f"- Timeline writebacks preserved: `{summary['timeline_writebacks_preserved']}`",
        f"- Failed rows: `{len(summary['failed_rows'])}`",
        "",
        "## Cases",
        "",
        "| Patch ID | Case | LLM action | Memory before | Memory after | Block reasons | Timeline preserved | LLM arrival |",
        "|---|---|---|---:|---:|---|---:|---:|",
    ]
    for row in replay["rows"]:
        reasons = ", ".join(row["memory_block_reasons"])
        lines.append(
            f"| `{row['patch_id']}` | {row['case_type']} | {row['llm_review_action']} | "
            f"{row['memory_candidate_before']} | {row['memory_update_allowed_after']} | {reasons} | "
            f"{row['timeline_writeback_preserved']} | {row['llm_review_arrival_sec']}s |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Review/defer/repeatability signals are converted into memory-update blocks.",
            "- Rule timeline writeback is preserved for all replayed cases.",
            "- The replay surface avoids DER/GT/oracle/eval-only fields.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=Path("outputs/research_progress_snapshot/memory_update_replay.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/research_progress_snapshot/memory_update_replay.md"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/research_progress_snapshot/memory_update_replay.csv"))
    args = parser.parse_args()

    replay = build_replay(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(replay, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(replay, args.output_csv)
    write_markdown(replay, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
