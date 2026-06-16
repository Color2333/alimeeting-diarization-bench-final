#!/usr/bin/env python3
"""Compare patch decisions between two clean LLM audit runs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_patch_decisions(path: Path) -> dict[str, str]:
    decisions = {}
    for row in load_jsonl(path):
        for patch in row.get("patch_decisions", []):
            decisions[patch["patch_id"]] = patch.get("decision", "")
    return decisions


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Clean LLM Audit Run Comparison",
        "",
        "| Overlap patches | Same decision | Changed decision | Agreement | Run A non-accepts | Run B non-accepts |",
        "|---:|---:|---:|---:|---:|---:|",
        (
            "| {overlap_patches} | {same_decision} | {changed_decision} | {decision_agreement_rate:.1%} | "
            "{run_a_non_accepts} | {run_b_non_accepts} |"
        ).format(**summary),
        "",
        "## Changed Decisions",
        "",
    ]
    changed = summary.get("changed_patch_decisions", [])
    if changed:
        lines.append("| Patch ID | Run A | Run B |")
        lines.append("|---|---|---|")
        for row in changed:
            lines.append(f"| `{row['patch_id']}` | {row['run_a_decision']} | {row['run_b_decision']} |")
    else:
        lines.append("- No patch-level decision changes on the overlap set.")
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This comparison measures audit reproducibility on overlapping patch IDs.",
            "- Decision drift supports keeping the deterministic Rule Agent as executor while using the LLM for review/explanation.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-a", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_expanded.jsonl"))
    parser.add_argument("--run-b", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_full.jsonl"))
    parser.add_argument("--output-json", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_repeatability.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_repeatability.md"))
    args = parser.parse_args()

    run_a = load_patch_decisions(args.run_a)
    run_b = load_patch_decisions(args.run_b)
    overlap = sorted(set(run_a).intersection(run_b))
    changed = [
        {
            "patch_id": patch_id,
            "run_a_decision": run_a[patch_id],
            "run_b_decision": run_b[patch_id],
        }
        for patch_id in overlap
        if run_a[patch_id] != run_b[patch_id]
    ]
    same = len(overlap) - len(changed)
    summary = {
        "run_a": str(args.run_a),
        "run_b": str(args.run_b),
        "overlap_patches": len(overlap),
        "same_decision": same,
        "changed_decision": len(changed),
        "decision_agreement_rate": same / len(overlap) if overlap else 0.0,
        "run_a_decision_counts": dict(Counter(run_a[patch_id] for patch_id in overlap)),
        "run_b_decision_counts": dict(Counter(run_b[patch_id] for patch_id in overlap)),
        "run_a_non_accepts": sum(1 for patch_id in overlap if run_a[patch_id] != "accept"),
        "run_b_non_accepts": sum(1 for patch_id in overlap if run_b[patch_id] != "accept"),
        "changed_patch_decisions": changed,
        "runtime_contract": "clean_llm_audit_repeatability_check",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
