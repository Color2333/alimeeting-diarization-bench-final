#!/usr/bin/env python3
"""Evaluate LLM Policy Agent decisions against eval-only patch support.

This does not expose ground-truth fields to the LLM. It joins completed LLM
runs back to the rule-agent decision table after inference and reports whether
LLM accepts are safe/actionable or overly conservative.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Any


TRUE_SPEECH_THRESHOLD = 0.5
TRUE_FA_THRESHOLD = 0.2


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def has_high_error(row: dict[str, Any]) -> bool:
    flags = str(row.get("abnormal_flags", "")).split("|")
    return any("high_der" in flag or "high_fa" in flag for flag in flags)


def is_actionable_accept(row: dict[str, Any]) -> bool:
    gt = float(row["gt_support_ratio_eval_only"])
    patch_type = row["patch_type"]
    if patch_type == "suppress_fast_candidate":
        return gt <= TRUE_FA_THRESHOLD
    if patch_type in {
        "recover_slow_segment",
        "boundary_fix_or_relabel",
        "keep_fast_supported",
        "align_slow_segment",
    }:
        return gt >= TRUE_SPEECH_THRESHOLD
    return False


def classify_row(row: dict[str, Any]) -> str:
    decision = row["llm_decision"]
    actionable = is_actionable_accept(row)
    if decision == "accept" and actionable:
        return "safe_accept"
    if decision == "accept" and not actionable:
        return "harmful_accept"
    if decision in {"defer", "reject", "quarantine"} and actionable and row["rule_decision"] == "accept":
        return "conservative_block"
    if decision in {"defer", "reject", "quarantine"} and not actionable:
        return "safe_block"
    if decision == "error":
        return "error"
    return "neutral_review"


def summarize_model(model: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    decision_counts = Counter(row["llm_decision"] for row in rows)
    class_counts = Counter(classify_row(row) for row in rows)
    accept_rows = [row for row in rows if row["llm_decision"] == "accept"]
    high_error_quarantines = sum(1 for row in rows if row["llm_decision"] == "quarantine" and has_high_error(row))
    rule_accept_to_nonaccept = sum(
        1 for row in rows if row["rule_decision"] == "accept" and row["llm_decision"] != "accept"
    )
    avg_call = sum(float(row.get("call_seconds") or 0.0) for row in rows) / len(rows) if rows else 0.0
    return {
        "model": model,
        "samples": len(rows),
        "decision_counts": " / ".join(f"{k} {decision_counts[k]}" for k in ["accept", "defer", "reject", "quarantine", "error"] if decision_counts.get(k)),
        "safe_accepts": class_counts["safe_accept"],
        "harmful_accepts": class_counts["harmful_accept"],
        "conservative_blocks": class_counts["conservative_block"],
        "safe_blocks": class_counts["safe_block"],
        "accept_precision": class_counts["safe_accept"] / len(accept_rows) if accept_rows else 0.0,
        "rule_accept_to_nonaccept": rule_accept_to_nonaccept,
        "high_error_quarantines": high_error_quarantines,
        "avg_call_seconds": avg_call,
    }


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "| Model | Samples | Decisions | Safe accepts | Harmful accepts | Conservative blocks | Accept precision |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {model} | {samples} | {decision_counts} | {safe_accepts} | {harmful_accepts} | {conservative_blocks} | {accept_precision:.1%} |".format(
                **row
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-decisions", type=Path, default=Path("outputs/policy_agent/sortformer_diarizen_48_decisions.csv"))
    parser.add_argument("--llm-dir", type=Path, default=Path("outputs/llm_policy_agent"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/llm_policy_agent/model_safety.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/llm_policy_agent/model_safety.md"))
    args = parser.parse_args()

    policy_by_id = {row["patch_id"]: row for row in load_csv(args.policy_decisions)}
    model_rows: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(args.llm_dir.glob("*mixed*.csv")):
        if path.name in {"model_comparison.csv", "model_safety.csv"}:
            continue
        for row in load_csv(path):
            policy = policy_by_id.get(row["patch_id"])
            if not policy:
                continue
            joined = {**policy, **row}
            model_rows.setdefault(joined["model"], []).append(joined)

    if not model_rows:
        raise SystemExit("No LLM mixed CSV rows found")

    summaries = [summarize_model(model, rows) for model, rows in sorted(model_rows.items())]
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0].keys()))
        writer.writeheader()
        writer.writerows(summaries)
    write_markdown(args.output_md, summaries)
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
