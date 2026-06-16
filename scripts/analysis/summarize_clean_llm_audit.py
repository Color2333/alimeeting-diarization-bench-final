#!/usr/bin/env python3
"""Summarize LLM audit agreement on clean rule-auto voiceprint patches."""

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


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Clean LLM Audit Summary",
        "",
        "| Windows | Patches | Window clean | LLM accepts | Non-accepts | Rule-auto agreement | Avg call | Max call | Total tokens |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        (
            "| {windows} | {patches} | {window_clean} | {llm_accepts} | {llm_non_accepts} | {rule_auto_agreement_rate:.1%} | "
            "{avg_call_seconds:.2f}s | {max_call_seconds:.2f}s | {total_tokens} |"
        ).format(**summary),
        "",
        "## Reading",
        "",
        "- This is an audit-only LLM run on deterministic rule-auto, no-abnormal, high-voiceprint patches.",
        "- Agreement means the LLM also returned `accept`; the deterministic Rule Agent remains the writeback executor.",
        "- Non-accepts are conservative audit disagreements; they do not undo deterministic rule writeback evidence by themselves.",
        "- Passing this audit supports using LLM explanations on clean patches, not granting LLM direct writeback authority.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm-jsonl", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit.jsonl"))
    parser.add_argument("--llm-summary", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_summary.json"))
    parser.add_argument("--audit-csv", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_candidate_120_audit.csv"))
    parser.add_argument("--patch-id-file", type=Path, default=Path("outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_patch_ids.txt"))
    parser.add_argument("--output-json", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_agreement.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_agreement.md"))
    args = parser.parse_args()

    patch_ids = [
        line.strip()
        for line in args.patch_id_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    audit_rows = {row["patch_id"]: row for row in load_csv(args.audit_csv)}
    llm_rows = load_jsonl(args.llm_jsonl)
    run_summary = load_json(args.llm_summary)
    decisions: dict[str, str] = {}
    window_decisions = Counter()
    for row in llm_rows:
        window_decisions[row.get("window_decision", "")] += 1
        for patch in row.get("patch_decisions", []):
            decisions[patch["patch_id"]] = patch.get("decision", "")

    llm_accepts = sum(1 for patch_id in patch_ids if decisions.get(patch_id) == "accept")
    non_accept_patch_ids = [
        patch_id for patch_id in patch_ids if decisions.get(patch_id) != "accept"
    ]
    non_accept_decisions = Counter(decisions.get(patch_id, "missing") for patch_id in non_accept_patch_ids)
    rule_auto = sum(1 for patch_id in patch_ids if audit_rows.get(patch_id, {}).get("gate_category") == "rule_auto_writeback")
    high_rule_auto = sum(1 for patch_id in patch_ids if audit_rows.get(patch_id, {}).get("candidate_class") == "voiceprint_high_rule_auto")
    call_seconds = [float(row.get("call_seconds", 0.0)) for row in llm_rows if row.get("call_seconds") is not None]

    summary = {
        "llm_jsonl": str(args.llm_jsonl),
        "patch_id_file": str(args.patch_id_file),
        "windows": len(llm_rows),
        "patches": len(patch_ids),
        "window_clean": window_decisions.get("clean", 0),
        "window_decisions": dict(window_decisions),
        "rule_auto_patches": rule_auto,
        "high_rule_auto_patches": high_rule_auto,
        "llm_accepts": llm_accepts,
        "llm_non_accepts": len(patch_ids) - llm_accepts,
        "non_accept_decisions": dict(non_accept_decisions),
        "non_accept_patch_ids": non_accept_patch_ids,
        "rule_auto_agreement_rate": llm_accepts / len(patch_ids) if patch_ids else 0.0,
        "avg_call_seconds": sum(call_seconds) / len(call_seconds) if call_seconds else 0.0,
        "max_call_seconds": max(call_seconds) if call_seconds else 0.0,
        "wall_seconds": float(run_summary.get("wall_seconds") or 0.0),
        "total_tokens": int(run_summary.get("total_tokens") or 0),
        "runtime_contract": "llm_audit_only_clean_high_voiceprint_rule_auto_patches",
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
