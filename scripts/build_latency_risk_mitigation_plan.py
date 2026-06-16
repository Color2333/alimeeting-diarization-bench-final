#!/usr/bin/env python3
"""Build a no-live-call mitigation plan for latency risk rows."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/latency_risk_mitigation_plan.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/latency_risk_mitigation_plan.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/latency_risk_mitigation_plan.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_plan(root: Path) -> dict[str, Any]:
    latency_risk = read_json(root / "outputs/research_progress_snapshot/latency_risk_margin_audit.json")
    split_policy = read_json(root / "outputs/research_progress_snapshot/split_policy_optimization.json")
    split15_export = read_json(root / "outputs/research_progress_snapshot/split15_stretch_reexport_audit.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    runbook = read_json(root / "outputs/research_progress_snapshot/live_execution_runbook.json")
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    selector_split = read_json(root / "outputs/research_progress_snapshot/selector_true_heldout_split_validation.json")

    risk_summary = latency_risk.get("summary", {})
    split_summary = split_policy.get("summary", {})
    split15_summary = split15_export.get("summary", {})
    promotion_summary = promotion.get("summary", {})
    readiness_summary = readiness.get("summary", {})
    runbook_summary = runbook.get("summary", {})
    output_summary = output_audit.get("summary", {})
    selector_summary = selector_split.get("summary", {})

    primary_p95 = as_float(split_summary.get("primary_simulated_p95_call_seconds"))
    stretch_p95 = as_float(split_summary.get("stretch_simulated_p95_call_seconds"))
    primary_calls = as_int(split_summary.get("primary_calls"))
    stretch_calls = as_int(split_summary.get("stretch_calls"))

    rows = [
        {
            "action_id": "preserve_current_slo_with_guard_risk_tag",
            "priority": "P0",
            "action_type": "preserve_current_claim",
            "status": "active_current_claim",
            "decision": "Keep current 4/4 claim-now SLO rows, but label runtime-safe LLM guard as tight-margin.",
            "success_gate": "claim_now_slo_pass == claim_now_slo_rows == 4 and guard risk remains explicit",
            "blocked_by": "",
            "source_artifacts": [
                "outputs/research_progress_snapshot/stage_latency_slo_audit.json",
                "outputs/research_progress_snapshot/latency_risk_margin_audit.json",
            ],
            "claim_boundary": "preserve_existing_slo_no_new_metric_claim",
        },
        {
            "action_id": "deepseek_max20_resume_primary",
            "priority": "P0",
            "action_type": "primary_latency_mitigation",
            "status": "blocked_waiting_credentials_quota_or_live_output",
            "decision": (
                f"Run DeepSeek {split_summary.get('primary_policy', 'max20')} resume first: "
                f"{split_summary.get('primary_resume_calls', 139)} calls / 101 parents after top3."
            ),
            "success_gate": "resume JSONL complete, output audit passes, safety/comparison scoring passes",
            "blocked_by": "missing credentials or provider quota/capacity and missing resume live output",
            "source_artifacts": [
                "outputs/research_progress_snapshot/split20_full_live_manifest.json",
                "outputs/research_progress_snapshot/split20_resume_export_audit.json",
                "outputs/research_progress_snapshot/split_policy_optimization.json",
                "outputs/research_progress_snapshot/live_execution_runbook.json",
            ],
            "claim_boundary": "blocked_until_full_surface_live_output_and_scoring",
        },
        {
            "action_id": "max15_stretch_reexport",
            "priority": "P1",
            "action_type": "stretch_latency_candidate",
            "status": "prepared_export_audited_waiting_live_output",
            "decision": (
                f"Keep {split_summary.get('stretch_policy', 'max15')} ready as a stretch comparison: "
                f"{split15_summary.get('export_prompts', stretch_calls)} exported calls, simulated P95 {stretch_p95:.3f}s."
            ),
            "success_gate": "fresh max15 prompt export, live output, and scoring exist before any latency claim",
            "blocked_by": "fresh prompt export is audited, but live output and scoring are still missing",
            "source_artifacts": [
                "outputs/research_progress_snapshot/split_policy_optimization.json",
                "outputs/research_progress_snapshot/split15_stretch_reexport_audit.json",
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation_summary.json",
            ],
            "claim_boundary": "stretch_plan_no_new_metric_claim",
        },
        {
            "action_id": "qwen_backup_not_primary_latency",
            "priority": "P1",
            "action_type": "fallback_boundary",
            "status": "fallback_only",
            "decision": "Keep Qwen backup as execution/safety fallback, not as primary latency mitigation.",
            "success_gate": "may support fallback safety only after full output and scoring",
            "blocked_by": "top4/top5 backup wall is slower than original max and full output is missing",
            "source_artifacts": [
                "outputs/research_progress_snapshot/split_policy_optimization.json",
                "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json",
            ],
            "claim_boundary": "fallback_only_not_primary_latency_claim",
        },
        {
            "action_id": "omni48_label_only_not_guard_latency",
            "priority": "P1",
            "action_type": "scope_boundary",
            "status": "blocked_waiting_omni48_live_outputs",
            "decision": "Keep Omni48 as label-only risk tagging; do not use it as timeline writeback or guard latency mitigation.",
            "success_gate": "96 label-only live calls complete and Omni scoring passes",
            "blocked_by": "missing Omni credentials or outputs",
            "source_artifacts": [
                "outputs/research_progress_snapshot/omni48_live_call_manifest.json",
                "outputs/research_progress_snapshot/live_output_audit.json",
            ],
            "claim_boundary": "label_only_no_timeline_writeback",
        },
        {
            "action_id": "selector_true_heldout_not_latency_mitigation",
            "priority": "P1",
            "action_type": "scope_boundary",
            "status": "blocked_waiting_valid_sealed_split",
            "decision": "Keep selector true-heldout as generalization evidence, not as a guard latency mitigation path.",
            "success_gate": "sealed split with at least 8 new recordings and no development overlap",
            "blocked_by": f"missing {selector_summary.get('missing_new_recordings_to_minimum', 8)} new recordings",
            "source_artifacts": [
                "outputs/research_progress_snapshot/selector_true_heldout_split_validation.json",
                "outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.json",
            ],
            "claim_boundary": "data_generalization_not_latency_claim",
        },
    ]

    for row in rows:
        row["live_calls_performed_by_builder"] = 0

    blocked_rows = [row["action_id"] for row in rows if row["status"].startswith("blocked")]
    fallback_rows = [row["action_id"] for row in rows if row["status"] == "fallback_only"]
    stretch_rows = [row["action_id"] for row in rows if row["action_type"] == "stretch_latency_candidate"]
    p0_rows = [row["action_id"] for row in rows if row["priority"] == "P0"]
    active_rows = [row["action_id"] for row in rows if row["status"].startswith("active")]

    return {
        "runtime_contract": "latency_risk_mitigation_plan_no_live_calls",
        "status": "blocked_waiting_for_primary_live_resume" if blocked_rows else "ready",
        "source_contracts": {
            "latency_risk_margin": latency_risk.get("runtime_contract", ""),
            "split_policy_optimization": split_policy.get("runtime_contract", ""),
            "split15_stretch_reexport_audit": split15_export.get("runtime_contract", ""),
            "promotion_gate": promotion.get("runtime_contract", ""),
            "live_readiness": readiness.get("runtime_contract", ""),
            "live_execution_runbook": runbook.get("runtime_contract", ""),
        },
        "summary": {
            "action_count": len(rows),
            "p0_action_count": len(p0_rows),
            "active_current_claim_count": len(active_rows),
            "mitigation_ready_count": 0,
            "blocked_action_count": len(blocked_rows),
            "fallback_only_count": len(fallback_rows),
            "stretch_candidate_count": len(stretch_rows),
            "guard_risk_level": risk_summary.get("guard_risk_level", ""),
            "guard_p95_margin_seconds": risk_summary.get("guard_p95_margin_seconds", ""),
            "guard_p95_margin_ratio": risk_summary.get("guard_p95_margin_ratio", ""),
            "primary_policy": split_summary.get("primary_policy", ""),
            "primary_resume_calls": split_summary.get("primary_resume_calls", 0),
            "primary_simulated_p95_call_seconds": split_summary.get("primary_simulated_p95_call_seconds", 0.0),
            "primary_token_multiplier": split_summary.get("primary_token_multiplier", 0.0),
            "stretch_policy": split_summary.get("stretch_policy", ""),
            "stretch_calls": stretch_calls,
            "stretch_simulated_p95_call_seconds": split_summary.get("stretch_simulated_p95_call_seconds", 0.0),
            "stretch_token_multiplier": split_summary.get("stretch_token_multiplier", 0.0),
            "stretch_requires_reexport": split_summary.get("stretch_requires_reexport", False),
            "stretch_call_delta": stretch_calls - primary_calls,
            "stretch_p95_call_gain_seconds": round(primary_p95 - stretch_p95, 3),
            "stretch_export_status": split15_export.get("status", ""),
            "stretch_export_prompts": split15_summary.get("export_prompts", 0),
            "stretch_export_parent_windows": split15_summary.get("export_parent_windows", 0),
            "stretch_export_split_parent_windows": split15_summary.get("split_parent_windows", 0),
            "stretch_export_prompt_jsonl": split15_export.get("export_prompt_jsonl", ""),
            "stretch_export_live_calls_performed": split15_summary.get("live_calls_performed", 0),
            "post_live_ready_to_promote": promotion_summary.get("ready_to_promote_count", 0),
            "live_ready_runs": readiness_summary.get("ready_count", 0),
            "runbook_p0_planned_live_calls": runbook_summary.get("p0_planned_live_calls", 0),
            "missing_output_surfaces": output_summary.get("missing_output_surfaces", 0),
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "blocked_action_ids": blocked_rows,
        "fallback_only_action_ids": fallback_rows,
        "stretch_candidate_action_ids": stretch_rows,
        "actions": rows,
    }


def write_csv(plan: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "action_id",
        "priority",
        "action_type",
        "status",
        "decision",
        "success_gate",
        "blocked_by",
        "claim_boundary",
        "live_calls_performed_by_builder",
        "source_artifacts",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in plan["actions"]:
            out = dict(row)
            out["source_artifacts"] = "; ".join(out["source_artifacts"])
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def write_markdown(plan: dict[str, Any], path: Path) -> None:
    summary = plan["summary"]
    lines = [
        "# Latency Risk Mitigation Plan",
        "",
        f"- Runtime contract: `{plan['runtime_contract']}`",
        f"- Status: `{plan['status']}`",
        f"- Actions: `{summary['action_count']}`",
        f"- P0 actions: `{summary['p0_action_count']}`",
        f"- Blocked actions: `{summary['blocked_action_count']}`",
        f"- Fallback-only actions: `{summary['fallback_only_count']}`",
        f"- Stretch candidates: `{summary['stretch_candidate_count']}`",
        f"- Guard risk level: `{summary['guard_risk_level']}`",
        f"- Guard P95 margin: `{summary['guard_p95_margin_seconds']}`",
        f"- Primary mitigation: `{summary['primary_policy']}_resume`",
        f"- Primary resume calls: `{summary['primary_resume_calls']}`",
        f"- Stretch candidate: `{summary['stretch_policy']}_reexport`",
        f"- Stretch export status: `{summary['stretch_export_status']}`",
        f"- Stretch export prompts: `{summary['stretch_export_prompts']}`",
        f"- Stretch P95 gain vs primary: `{summary['stretch_p95_call_gain_seconds']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "## Actions",
        "",
        "| Action | Priority | Type | Status | Boundary | Decision |",
        "|---|---|---|---|---|---|",
    ]
    for row in plan["actions"]:
        lines.append(
            f"| `{row['action_id']}` | `{row['priority']}` | `{row['action_type']}` | "
            f"`{row['status']}` | `{row['claim_boundary']}` | {row['decision']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This plan converts the guard tight-margin audit into ordered next actions.",
            "- `max20_resume` stays the primary mitigation because it has exported prompts, top3 smoke evidence, and a resume surface.",
            "- `max15_reexport` is a stretch candidate only after provider quota/capacity is stable.",
            "- Qwen, Omni48, and selector true-heldout remain useful surfaces, but they do not support a primary guard-latency mitigation claim today.",
            "- The builder only reads local artifacts; it performs no live/API/model calls and writes no secrets.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    plan = build_plan(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(plan, args.output_md)
    write_csv(plan, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
