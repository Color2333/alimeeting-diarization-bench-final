#!/usr/bin/env python3
"""Evaluate safety of window-batched LLM Policy Agent outputs."""

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


TRUE_SPEECH_THRESHOLD = 0.5
TRUE_FA_THRESHOLD = 0.2


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def has_high_error_flags(flags: str) -> bool:
    return any("high_der" in flag or "high_fa" in flag for flag in flags.split("|") if flag)


def is_actionable_accept(policy_row: dict[str, str]) -> bool:
    gt_support = float(policy_row["gt_support_ratio_eval_only"])
    patch_type = policy_row["patch_type"]
    if patch_type == "suppress_fast_candidate":
        return gt_support <= TRUE_FA_THRESHOLD
    return gt_support >= TRUE_SPEECH_THRESHOLD


def classify_patch(policy_row: dict[str, str], llm_decision: str) -> str:
    actionable = is_actionable_accept(policy_row)
    if llm_decision == "accept" and actionable:
        return "safe_accept"
    if llm_decision == "accept" and not actionable:
        return "harmful_accept"
    if llm_decision in {"defer", "reject", "quarantine"} and actionable:
        return "conservative_block"
    if llm_decision in {"defer", "reject", "quarantine"} and not actionable:
        return "safe_block"
    return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-jsonl", type=Path, default=Path("outputs/llm_window_batch/deepseek_high_risk_48.jsonl"))
    parser.add_argument("--policy-decisions", type=Path, default=Path("outputs/policy_agent/sortformer_diarizen_48_decisions.csv"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/llm_window_batch/window_batch_safety.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/llm_window_batch/window_batch_safety.md"))
    args = parser.parse_args()

    policy_by_id = {row["patch_id"]: row for row in load_csv(args.policy_decisions)}
    batch_rows = load_jsonl(args.batch_jsonl)
    patch_classes = Counter()
    patch_decisions = Counter()
    window_decisions = Counter()
    high_error_quarantined = 0
    high_error_reviewed = 0
    detail_rows = []

    for window in batch_rows:
        window_decisions[window["window_decision"]] += 1
        patch_ids = [item["patch_id"] for item in window.get("patch_decisions", [])]
        flags = "|".join(policy_by_id[patch_id]["abnormal_flags"] for patch_id in patch_ids if patch_id in policy_by_id)
        is_high_error = has_high_error_flags(flags)
        if is_high_error and window["window_decision"] == "quarantine":
            high_error_quarantined += 1
        elif is_high_error:
            high_error_reviewed += 1

        for item in window.get("patch_decisions", []):
            policy = policy_by_id[item["patch_id"]]
            klass = classify_patch(policy, item["decision"])
            patch_classes[klass] += 1
            patch_decisions[item["decision"]] += 1
            detail_rows.append(
                {
                    "window_id": window["window_id"],
                    "patch_id": item["patch_id"],
                    "patch_type": policy["patch_type"],
                    "rule_decision": policy["decision"],
                    "llm_decision": item["decision"],
                    "gt_support_ratio_eval_only": policy["gt_support_ratio_eval_only"],
                    "safety_class": klass,
                    "window_decision": window["window_decision"],
                }
            )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = list(detail_rows[0].keys()) if detail_rows else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(detail_rows)

    summary = {
        "windows": len(batch_rows),
        "patches": len(detail_rows),
        "window_decisions": " / ".join(f"{key} {window_decisions[key]}" for key in sorted(window_decisions)),
        "patch_decisions": " / ".join(f"{key} {patch_decisions[key]}" for key in sorted(patch_decisions)),
        "safe_accepts": patch_classes["safe_accept"],
        "harmful_accepts": patch_classes["harmful_accept"],
        "conservative_blocks": patch_classes["conservative_block"],
        "safe_blocks": patch_classes["safe_block"],
        "high_error_quarantined_windows": high_error_quarantined,
        "high_error_reviewed_windows": high_error_reviewed,
    }
    md = [
        "| Windows | Patches | Window decisions | Patch decisions | Safe accepts | Harmful accepts | Conservative blocks | Safe blocks | High-error quarantined |",
        "|---:|---:|---|---|---:|---:|---:|---:|---:|",
        "| {windows} | {patches} | {window_decisions} | {patch_decisions} | {safe_accepts} | {harmful_accepts} | {conservative_blocks} | {safe_blocks} | {high_error_quarantined_windows} |".format(
            **summary
        ),
    ]
    args.output_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    summary_path = args.output_md.with_name(args.output_md.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
