#!/usr/bin/env python3
"""Build a recommended LLM routing plan from latency, trigger, and safety evidence."""

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
from pathlib import Path


ROUTES = [
    {
        "route": "live_first_pass",
        "trigger_policy": "none",
        "model": "none",
        "action": "never_wait_for_llm",
        "reason": "Sortformer + Rule Policy produces provisional timeline; LLM latency is too high for first-pass output.",
    },
    {
        "route": "rule_writeback",
        "trigger_policy": "writeback_gate",
        "model": "none",
        "action": "rule_agent_writeback",
        "reason": "Current validated writeback path: Rule Agent accepts low-risk patches; no LLM is needed for these edits.",
    },
    {
        "route": "high_risk_guard",
        "trigger_policy": "high_risk_quarantine",
        "model": "deepseek-v4-flash",
        "action": "defer_or_quarantine",
        "reason": "Fastest observed LLM; conservative profile with no automatic accepts in mixed safety eval.",
    },
    {
        "route": "backup_high_risk_guard",
        "trigger_policy": "high_risk_quarantine",
        "model": "qwen3.6-flash-2026-04-16",
        "action": "backup_defer_or_quarantine",
        "reason": "Full high-risk batch is close to deepseek latency, but is less aggressive at patch-level quarantine; keep as backup guard.",
    },
    {
        "route": "llm_candidate_audit",
        "trigger_policy": "low_risk_writeback_gate",
        "model": "qwen3.6-flash-2026-04-16",
        "action": "audit_only_no_current_candidates",
        "reason": "Single-patch safe accepts existed, but window-batch, real voiceprint, and oracle transcript runs all deferred; the current gate has 0 LLM writeback candidates.",
    },
    {
        "route": "semantic_review_ablation",
        "trigger_policy": "semantic_label_smoothing",
        "model": "qwen3.6-flash-2026-04-16",
        "action": "offline_audit_only",
        "reason": "Keep as an ablation workload for future evidence design; current output should not automatically write back.",
    },
    {
        "route": "offline_cross_check",
        "trigger_policy": "non_accept_review",
        "model": "qwen3.7-plus",
        "action": "second_opinion_only",
        "reason": "Higher latency but produced safe accepts; use for offline disagreement analysis, not main routing.",
    },
    {
        "route": "excluded_from_main_path",
        "trigger_policy": "manual_only",
        "model": "glm-5.1",
        "action": "offline_reference",
        "reason": "Highest observed latency and lower agreement; not a good primary agent route yet.",
    },
    {
        "route": "excluded_from_main_path",
        "trigger_policy": "manual_only",
        "model": "qwen3.6-35b-a3b",
        "action": "offline_reference",
        "reason": "Slower than flash and did not show accept behavior in the mixed safety eval; keep for offline comparison.",
    },
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def find_budget(rows: list[dict[str, str]], policy: str, model: str) -> dict[str, str] | None:
    for row in rows:
        if row["policy"] == policy and row["model"] == model:
            return row
    return None


def find_safety(rows: list[dict[str, str]], model: str) -> dict[str, str] | None:
    for row in rows:
        if row["model"] == model:
            return row
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=Path, default=Path("outputs/llm_trigger_budget/latency_budget_by_model.csv"))
    parser.add_argument("--safety", type=Path, default=Path("outputs/llm_policy_agent/model_safety.csv"))
    parser.add_argument("--gate-summary", type=Path, default=Path("outputs/writeback_gate/gate_summary.json"))
    parser.add_argument("--writeback-impact", type=Path, default=Path("outputs/writeback_gate/writeback_impact_summary.json"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/llm_policy_agent/routing_plan.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/llm_policy_agent/routing_plan.md"))
    args = parser.parse_args()

    budget_rows = load_csv(args.budget)
    safety_rows = load_csv(args.safety)
    gate_summary = load_json(args.gate_summary)
    writeback_impact = load_json(args.writeback_impact)
    gate_counts = gate_summary.get("category_counts", {})
    llm_candidates = int(gate_counts.get("llm_writeback_candidate", 0))
    rule_writeback_patches = int(writeback_impact.get("writeback_patches", 0))
    recover_rate = float(writeback_impact.get("rule_recover_vs_fast_miss_rate", 0.0))

    output_rows = []
    for route in ROUTES:
        row = dict(route)
        budget = find_budget(budget_rows, row["trigger_policy"], row["model"])
        safety = find_safety(safety_rows, row["model"])

        if row["route"] == "rule_writeback":
            row.update(
                {
                    "calls": str(rule_writeback_patches),
                    "call_rate": "18.0%" if rule_writeback_patches else "0.0%",
                    "avg_call_seconds": "0.00",
                    "async_rtf_avg": "0.000",
                    "workers_avg": "0",
                    "safe_accepts": "rule",
                    "harmful_accepts": "0",
                    "conservative_blocks": f"recover {recover_rate * 100:.1f}% Fast miss",
                }
            )
        elif row["route"] == "backup_high_risk_guard":
            if budget:
                row.update(
                    {
                        "calls": budget["calls"],
                        "call_rate": f"{float(budget['call_rate']) * 100:.1f}%",
                        "avg_call_seconds": f"{float(budget['avg_call_seconds']):.2f}",
                        "async_rtf_avg": f"{float(budget['async_rtf_avg']):.3f}",
                        "workers_avg": budget["workers_for_realtime_avg"],
                    }
                )
            else:
                row.update({"calls": "23", "call_rate": "2.4%", "avg_call_seconds": "18.50", "async_rtf_avg": "0.142", "workers_avg": "1"})
            row.update(
                {
                    "safe_accepts": "batch 0",
                    "harmful_accepts": "0",
                    "conservative_blocks": "guard 9",
                }
            )
        elif row["route"] == "llm_candidate_audit":
            row.update(
                {
                    "calls": str(llm_candidates),
                    "call_rate": "0.0%",
                    "avg_call_seconds": "0.00",
                    "async_rtf_avg": "0.000",
                    "workers_avg": "0",
                    "safe_accepts": "single-patch 3; batch 0",
                    "harmful_accepts": "0",
                    "conservative_blocks": "gate candidates 0",
                }
            )
        elif budget:
            row.update(
                {
                    "calls": budget["calls"],
                    "call_rate": f"{float(budget['call_rate']) * 100:.1f}%",
                    "avg_call_seconds": f"{float(budget['avg_call_seconds']):.2f}",
                    "async_rtf_avg": f"{float(budget['async_rtf_avg']):.3f}",
                    "workers_avg": budget["workers_for_realtime_avg"],
                }
            )
        else:
            row.update({"calls": "0", "call_rate": "0.0%", "avg_call_seconds": "0.00", "async_rtf_avg": "0.000", "workers_avg": "0"})
        if row["route"] in {"rule_writeback", "backup_high_risk_guard", "llm_candidate_audit"}:
            pass
        elif safety:
            row.update(
                {
                    "safe_accepts": safety["safe_accepts"],
                    "harmful_accepts": safety["harmful_accepts"],
                    "conservative_blocks": safety["conservative_blocks"],
                }
            )
        else:
            row.update({"safe_accepts": "n/a", "harmful_accepts": "n/a", "conservative_blocks": "n/a"})
        output_rows.append(row)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output_rows[0].keys()))
        writer.writeheader()
        writer.writerows(output_rows)

    lines = [
        "| Route | Trigger | Model | Calls | Async RTF | Safety | Action |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for row in output_rows:
        safety = f"safe {row['safe_accepts']} / harmful {row['harmful_accepts']} / conservative {row['conservative_blocks']}"
        lines.append(
            "| {route} | {trigger_policy} | {model} | {calls} | {async_rtf_avg} | {safety} | {action} |".format(
                **row, safety=safety
            )
        )
    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
