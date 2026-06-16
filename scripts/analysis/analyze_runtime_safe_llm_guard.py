#!/usr/bin/env python3
"""Evaluate runtime-safe LLM guard outputs with eval-only patch support.

The LLM prompt and runtime-safe gate do not contain GT support. This analysis
joins GT support after the call to measure harmful accepts and conservative
blocks.
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


TRUE_SPEECH_THRESHOLD = 0.5
TRUE_FA_THRESHOLD = 0.2


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def patch_id(row: dict[str, str]) -> str:
    return (
        f"{row['recording_id']}:{int(float(row['window_size']))}:"
        f"{int(float(row['segment_idx']))}:{row['source']}:{row['segment_id']}"
    )


def is_actionable_accept(patch: dict[str, str]) -> bool:
    support = float(patch.get("gt_support_ratio") or 0.0)
    if patch.get("patch_type") == "suppress_fast_candidate":
        return support <= TRUE_FA_THRESHOLD
    return support >= TRUE_SPEECH_THRESHOLD


def classify_patch(patch: dict[str, str], llm_decision: str) -> str:
    actionable = is_actionable_accept(patch)
    if llm_decision == "accept" and actionable:
        return "safe_accept"
    if llm_decision == "accept" and not actionable:
        return "harmful_accept"
    if llm_decision in {"defer", "reject", "quarantine"} and actionable:
        return "conservative_block"
    if llm_decision in {"defer", "reject", "quarantine"} and not actionable:
        return "safe_block"
    return "unknown"


def effective_decision(
    window_decision: str,
    llm_decision: str,
    override_window_quarantine: bool,
    patch_type: str = "",
    allow_keep_fast_passthrough: bool = False,
) -> str:
    if (
        allow_keep_fast_passthrough
        and window_decision == "quarantine"
        and llm_decision == "accept"
        and patch_type == "keep_fast_supported"
    ):
        return llm_decision
    if override_window_quarantine and window_decision == "quarantine" and llm_decision == "accept":
        return "quarantine"
    return llm_decision


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * 0.95)))
    return ordered[idx]


def parent_window_decision(window: dict[str, Any]) -> str:
    return str(window.get("parent_window_id") or window.get("window_id", ""))


def aggregate_parent_window_decisions(batch_rows: list[dict[str, Any]]) -> dict[str, str]:
    grouped: dict[str, set[str]] = {}
    for window in batch_rows:
        parent_id = parent_window_decision(window)
        if not parent_id:
            continue
        grouped.setdefault(parent_id, set()).add(str(window.get("window_decision", "unknown")))
    aggregate = {}
    for parent_id, decisions in grouped.items():
        if "quarantine" in decisions:
            aggregate[parent_id] = "quarantine"
        elif "review" in decisions:
            aggregate[parent_id] = "review"
        elif "clean" in decisions:
            aggregate[parent_id] = "clean"
        else:
            aggregate[parent_id] = "unknown"
    return aggregate


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(summary: dict[str, object], path: Path) -> None:
    lines = [
        "# Runtime-Safe LLM Guard Safety",
        "",
        "| Windows | Patches | Window decisions | Patch decisions | Harmful accepts | Conservative blocks | Safe blocks | Overrides | Avg call | P95 call | Avg correction | P95 correction |",
        "|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        (
            "| {windows} | {patches} | {window_decisions} | {patch_decisions} | "
            "{harmful_accepts} | {conservative_blocks} | {safe_blocks} | "
            "{window_quarantine_accept_overrides} | "
            "{avg_call_seconds:.2f}s | {p95_call_seconds:.2f}s | "
            "{avg_correction_delay_seconds:.2f}s | {p95_correction_delay_seconds:.2f}s |"
        ).format(**summary),
        "",
        "## Reading",
        "",
        "- The prompt surface passed runtime evidence audit before these calls.",
        "- GT support is joined only here, after the LLM response, to classify safety.",
        "- A conservative block means the patch had true speech/FA support but the guard deferred/rejected/quarantined it.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-jsonl", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_8w.jsonl"))
    parser.add_argument("--patches", type=Path, default=Path("outputs/segment_patches/sortformer_diarizen_120_patches.csv"))
    parser.add_argument("--system-timeline", type=Path, default=Path("outputs/system_timeline/summary.json"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_8w_safety.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_8w_safety.md"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_8w_safety_summary.json"))
    parser.add_argument(
        "--no-window-quarantine-override",
        action="store_true",
        help="Do not treat window-level quarantine as an execution-layer override for patch accepts.",
    )
    parser.add_argument(
        "--allow-keep-fast-passthrough-in-quarantine",
        action="store_true",
        help="Allow keep_fast_supported accepts inside quarantine windows because they preserve visible fast output rather than writing a new slow patch.",
    )
    args = parser.parse_args()

    patch_eval = {patch_id(row): row for row in load_csv(args.patches)}
    batch_rows = load_jsonl(args.batch_jsonl)
    parent_decisions = aggregate_parent_window_decisions(batch_rows)
    timeline = load_json(args.system_timeline)
    slow_avg = float(timeline.get("rule_writeback_avg_delay_sec", 0.0))
    slow_p95 = float(timeline.get("rule_writeback_p95_delay_sec", slow_avg))

    detail_rows: list[dict[str, object]] = []
    patch_classes: Counter[str] = Counter()
    patch_decisions: Counter[str] = Counter()
    window_decisions: Counter[str] = Counter()
    call_seconds = []
    missing_patch_eval = 0
    window_quarantine_accept_overrides = 0

    for window in batch_rows:
        raw_window_decision = str(window.get("window_decision", "unknown"))
        window_decision = parent_decisions.get(parent_window_decision(window), raw_window_decision)
        window_decisions[window_decision] += 1
        call_seconds.append(float(window.get("call_seconds") or 0.0))
        for item in window.get("patch_decisions", []):
            patch = patch_eval.get(item["patch_id"])
            if patch is None:
                missing_patch_eval += 1
                continue
            raw_decision = str(item.get("decision", ""))
            decision = effective_decision(
                window_decision,
                raw_decision,
                override_window_quarantine=not args.no_window_quarantine_override,
                patch_type=patch["patch_type"],
                allow_keep_fast_passthrough=args.allow_keep_fast_passthrough_in_quarantine,
            )
            if decision != raw_decision:
                window_quarantine_accept_overrides += 1
            klass = classify_patch(patch, decision)
            patch_classes[klass] += 1
            patch_decisions[decision] += 1
            detail_rows.append(
                {
                    "window_id": window["window_id"],
                    "patch_id": item["patch_id"],
                    "patch_type": patch["patch_type"],
                    "raw_llm_decision": raw_decision,
                    "effective_decision": decision,
                    "llm_decision": decision,
                    "gt_support_ratio_eval_only": patch.get("gt_support_ratio", ""),
                    "safety_class": klass,
                    "window_decision": window_decision,
                    "raw_window_decision": raw_window_decision,
                    "parent_window_id": parent_window_decision(window),
                }
            )

    summary = {
        "windows": len(batch_rows),
        "patches": len(detail_rows),
        "window_decisions": " / ".join(f"{key} {window_decisions[key]}" for key in sorted(window_decisions)),
        "patch_decisions": " / ".join(f"{key} {patch_decisions[key]}" for key in sorted(patch_decisions)),
        "safe_accepts": patch_classes["safe_accept"],
        "harmful_accepts": patch_classes["harmful_accept"],
        "conservative_blocks": patch_classes["conservative_block"],
        "safe_blocks": patch_classes["safe_block"],
        "missing_patch_eval": missing_patch_eval,
        "window_quarantine_accept_overrides": window_quarantine_accept_overrides,
        "parent_window_decision_override": any(
            str(row.get("parent_window_id") or row.get("window_id", "")) != str(row.get("window_id", ""))
            for row in batch_rows
        ),
        "avg_call_seconds": sum(call_seconds) / len(call_seconds) if call_seconds else 0.0,
        "p95_call_seconds": p95(call_seconds),
        "avg_correction_delay_seconds": slow_avg + (sum(call_seconds) / len(call_seconds) if call_seconds else 0.0),
        "p95_correction_delay_seconds": slow_p95 + p95(call_seconds),
        "batch_jsonl": str(args.batch_jsonl),
        "patches_eval": str(args.patches),
        "runtime_contract": (
            "prompt_passed_runtime_evidence_audit; window_quarantine_accept_override"
            + ("; keep_fast_supported_passthrough_exception" if args.allow_keep_fast_passthrough_in_quarantine else "")
        ),
    }

    if detail_rows:
        write_csv(detail_rows, args.output_csv)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, args.output_md)
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.summary_json}")
    print(f"Wrote {args.output_md}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
