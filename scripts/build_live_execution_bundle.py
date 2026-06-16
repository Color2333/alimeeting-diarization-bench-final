#!/usr/bin/env python3
"""Build a no-live-call execution bundle for pending live LLM/Omni work."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_execution_bundle.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_execution_bundle.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_execution_bundle.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def by_id(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key)): row for row in rows}


def bundle_row(
    step_order: int,
    bundle_step_id: str,
    priority: str,
    phase: str,
    current_state: str,
    depends_on: list[str],
    dag_node: str,
    command: str,
    expected_artifacts: list[str],
    success_gate: str,
    claim_boundary: str,
    planned_live_calls: int = 0,
) -> dict[str, Any]:
    return {
        "step_order": step_order,
        "bundle_step_id": bundle_step_id,
        "priority": priority,
        "phase": phase,
        "current_state": current_state,
        "depends_on": depends_on,
        "dag_node": dag_node,
        "command": command,
        "expected_artifacts": expected_artifacts,
        "success_gate": success_gate,
        "claim_boundary": claim_boundary,
        "planned_live_calls": planned_live_calls,
    }


def build_bundle(root: Path) -> dict[str, Any]:
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    agent_plan = read_json(root / "outputs/research_progress_snapshot/live_agent_execution_plan.json")
    runbook = read_json(root / "outputs/research_progress_snapshot/live_execution_runbook.json")
    command_audit = read_json(root / "outputs/research_progress_snapshot/live_command_surface_audit.json")
    handoff = read_json(root / "outputs/research_progress_snapshot/live_execution_handoff_packet.json")
    evidence_dag = read_json(root / "outputs/research_progress_snapshot/post_live_evidence_dependency_dag.json")
    timing = read_json(root / "outputs/research_progress_snapshot/live_execution_timing_plan.json")
    retry_budget = read_json(root / "outputs/research_progress_snapshot/live_retry_budget_audit.json")
    token_budget = read_json(root / "outputs/research_progress_snapshot/live_token_quota_budget_audit.json")
    scoring_plan = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_execution_plan.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")

    runbook_steps = by_id(runbook.get("steps", []), "step_id")
    scoring_steps = by_id(scoring_plan.get("rows", []), "scoring_execution_id")
    readiness_summary = readiness.get("summary", {})
    agent_summary = agent_plan.get("summary", {})
    command_summary = command_audit.get("summary", {})
    handoff_summary = handoff.get("summary", {})
    dag_summary = evidence_dag.get("summary", {})
    timing_summary = timing.get("summary", {})
    retry_summary = retry_budget.get("summary", {})
    token_summary = token_budget.get("summary", {})
    trace_summary = traceability.get("summary", {})

    credential_step = runbook_steps.get("credential_preflight", {})
    deepseek_step = runbook_steps.get("deepseek_resume_primary", {})
    output_audit_step = runbook_steps.get("post_live_output_audit", {})
    omni_step = runbook_steps.get("omni48_label_only_live", {})
    qwen_step = runbook_steps.get("qwen_full_backup_optional", {})
    refresh_step = runbook_steps.get("refresh_report_ppt_validation", {})

    safety_command = scoring_steps.get("deepseek_resume_safety_score", {}).get("command", "")
    comparison_command = scoring_steps.get("deepseek_full_split20_comparison_score", {}).get("command", "")
    scoring_command = "\n".join(command for command in [safety_command, comparison_command] if command)

    rows = [
        bundle_row(
            1,
            "credential_preflight",
            "P0",
            "preflight",
            credential_step.get("status", "blocked_missing_credentials"),
            [],
            "live_outputs_complete",
            "python scripts/build_live_run_readiness.py",
            ["outputs/research_progress_snapshot/live_run_readiness.json"],
            "credential env presence true; no secret values written",
            "no_secret_values_no_live_calls",
        ),
        bundle_row(
            2,
            "p0_deepseek_resume_live",
            "P0",
            "live_call",
            deepseek_step.get("status", "blocked_by_provider_quota_or_capacity"),
            ["credential_preflight"],
            "live_outputs_complete",
            deepseek_step.get("command", ""),
            [deepseek_step.get("expected_artifacts", "")],
            "139 successful calls / 101 parent windows; no provider quota failures",
            "block_or_quarantine_only_until_safety_scored",
            as_int(deepseek_step.get("planned_live_calls")),
        ),
        bundle_row(
            3,
            "p0_output_audit",
            "P0",
            "postrun_audit",
            output_audit_step.get("status", "pending_live_outputs"),
            ["p0_deepseek_resume_live"],
            "output_schema_clean",
            output_audit_step.get("command", "python scripts/build_live_output_audit.py"),
            ["outputs/research_progress_snapshot/live_output_audit.json"],
            "missing_output_surfaces == 0 for P0 surface before scoring",
            "output_audit_no_metric_claim",
        ),
        bundle_row(
            4,
            "p0_safety_then_latency_scoring",
            "P0",
            "postrun_scoring",
            "blocked_waiting_live_output",
            ["p0_output_audit"],
            "deepseek_resume_safety_score",
            scoring_command,
            [
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety_summary.json",
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.json",
            ],
            "harmful_accepts == 0 before full split20 latency comparison can promote",
            "required_before_zero_harm_and_full_surface_latency_claim",
        ),
        bundle_row(
            5,
            "p0_metrics_promotion_refresh",
            "P0",
            "promotion_refresh",
            "blocked_waiting_scoring_outputs",
            ["p0_safety_then_latency_scoring"],
            "promotion_gate_pass",
            "python scripts/refresh_latest_research_artifacts.py",
            [
                "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json",
                "outputs/research_progress_snapshot/latest_artifact_validation.json",
                "../研究进展汇报.pptx",
            ],
            "refresh pass; validator failed_checks empty; traceability fully covered",
            "report_ppt_sync_required_before_claim_promotion",
        ),
        bundle_row(
            6,
            "p1_omni48_label_live",
            "P1",
            "live_call",
            omni_step.get("status", "blocked_missing_credentials"),
            ["credential_preflight"],
            "omni48_label_metrics",
            omni_step.get("command", ""),
            [omni_step.get("expected_artifacts", "")],
            "96 successful label-only calls; no timeline writeback",
            "label_only_no_timeline_writeback",
            as_int(omni_step.get("planned_live_calls")),
        ),
        bundle_row(
            7,
            "p1_qwen_backup_live",
            "P1",
            "fallback_live_call",
            qwen_step.get("status", "blocked_missing_credentials"),
            ["credential_preflight"],
            "qwen_backup_metrics",
            qwen_step.get("command", ""),
            [qwen_step.get("expected_artifacts", "")],
            "fallback safety harmful_accepts == 0; do not promote as primary latency unless policy changes",
            "fallback_only_not_primary_claim",
            as_int(qwen_step.get("planned_live_calls")),
        ),
        bundle_row(
            8,
            "final_report_ppt_validation",
            "P0",
            "refresh_and_validate",
            refresh_step.get("status", "waiting_for_live_outputs"),
            ["p0_metrics_promotion_refresh"],
            "report_ppt_refresh_validation",
            refresh_step.get("command", "python scripts/refresh_latest_research_artifacts.py"),
            [
                "outputs/research_progress_snapshot/refresh_latest_artifacts.json",
                "outputs/research_progress_snapshot/latest_artifact_validation.json",
                "outputs/research_progress_snapshot/report_ppt_traceability.json",
            ],
            "refresh pass; latest validation failed_checks == []",
            "final_validation_no_new_metric_claim",
        ),
    ]

    blocked_or_waiting = [
        row
        for row in rows
        if any(token in str(row["current_state"]) for token in ["blocked", "waiting", "pending"])
    ]
    live_rows = [row for row in rows if row["planned_live_calls"] > 0]
    p0_rows = [row for row in rows if row["priority"] == "P0"]
    p1_rows = [row for row in rows if row["priority"] == "P1"]

    return {
        "runtime_contract": "live_execution_bundle_no_live_calls_no_secret_values",
        "status": "blocked_waiting_credentials_quota_or_live_outputs",
        "secret_policy": "env_presence_only_no_secret_values_written",
        "source_contracts": {
            "live_run_readiness": readiness.get("runtime_contract", ""),
            "live_agent_execution_plan": agent_plan.get("runtime_contract", ""),
            "live_execution_runbook": runbook.get("runtime_contract", ""),
            "live_command_surface_audit": command_audit.get("runtime_contract", ""),
            "live_execution_handoff_packet": handoff.get("runtime_contract", ""),
            "post_live_evidence_dependency_dag": evidence_dag.get("runtime_contract", ""),
            "live_execution_timing_plan": timing.get("runtime_contract", ""),
            "live_retry_budget_audit": retry_budget.get("runtime_contract", ""),
            "live_token_quota_budget_audit": token_budget.get("runtime_contract", ""),
            "post_live_scoring_execution_plan": scoring_plan.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "summary": {
            "bundle_steps": len(rows),
            "p0_bundle_steps": len(p0_rows),
            "p1_bundle_steps": len(p1_rows),
            "blocked_or_waiting_steps": len(blocked_or_waiting),
            "live_call_steps": len(live_rows),
            "command_ready_count": as_int(command_summary.get("command_ready_count")),
            "command_count": as_int(command_summary.get("command_count")),
            "planned_live_calls": sum(row["planned_live_calls"] for row in live_rows),
            "p0_planned_live_calls": sum(row["planned_live_calls"] for row in p0_rows),
            "p1_planned_live_calls": sum(row["planned_live_calls"] for row in p1_rows),
            "ready_runs": as_int(readiness_summary.get("ready_count")),
            "credential_ready": bool(readiness.get("environment", {}).get("dashscope_like_api_key_present")),
            "known_provider_quota_blockers": as_int(handoff_summary.get("known_provider_quota_blockers")),
            "missing_output_surfaces": as_int(dag_summary.get("missing_output_surfaces")),
            "dag_nodes": as_int(dag_summary.get("dag_nodes")),
            "deepseek_estimated_wall_seconds": timing_summary.get("deepseek_estimated_wall_seconds", ""),
            "max_attempted_requests": as_int(retry_summary.get("max_attempted_requests")),
            "llm_retry_token_proxy_ceiling": as_int(token_summary.get("llm_retry_token_proxy_ceiling")),
            "traceability_rows": as_int(trace_summary.get("traceability_rows")),
            "live_calls_performed_by_builder": 0,
            "no_scoring_commands_executed": True,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(bundle: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "step_order",
        "bundle_step_id",
        "priority",
        "phase",
        "current_state",
        "depends_on",
        "dag_node",
        "planned_live_calls",
        "expected_artifacts",
        "success_gate",
        "claim_boundary",
        "command",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in bundle["rows"]:
            out = dict(row)
            out["depends_on"] = "; ".join(out["depends_on"])
            out["expected_artifacts"] = "; ".join(out["expected_artifacts"])
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def write_markdown(bundle: dict[str, Any], path: Path) -> None:
    summary = bundle["summary"]
    lines = [
        "# Live Execution Bundle",
        "",
        f"- Runtime contract: `{bundle['runtime_contract']}`",
        f"- Secret policy: `{bundle['secret_policy']}`",
        f"- Status: `{bundle['status']}`",
        f"- Bundle steps: `{summary['bundle_steps']}`",
        f"- P0 / P1 steps: `{summary['p0_bundle_steps']}` / `{summary['p1_bundle_steps']}`",
        f"- Blocked/waiting steps: `{summary['blocked_or_waiting_steps']}`",
        f"- Live-call steps: `{summary['live_call_steps']}`",
        f"- Command-ready: `{summary['command_ready_count']}/{summary['command_count']}`",
        f"- Planned live calls: `{summary['planned_live_calls']}`",
        f"- P0 planned live calls: `{summary['p0_planned_live_calls']}`",
        f"- Credential ready: `{summary['credential_ready']}`",
        f"- Known provider quota blockers: `{summary['known_provider_quota_blockers']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- DAG nodes: `{summary['dag_nodes']}`",
        f"- DeepSeek estimated wall seconds: `{summary['deepseek_estimated_wall_seconds']}`",
        f"- Max attempted requests: `{summary['max_attempted_requests']}`",
        f"- LLM retry token proxy ceiling: `{summary['llm_retry_token_proxy_ceiling']}`",
        f"- Traceability rows: `{summary['traceability_rows']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No scoring commands executed: `{summary['no_scoring_commands_executed']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| # | Step | Priority | Phase | State | Calls | DAG node | Boundary |",
        "|---:|---|---|---|---|---:|---|---|",
    ]
    for row in bundle["rows"]:
        lines.append(
            f"| {row['step_order']} | `{row['bundle_step_id']}` | `{row['priority']}` | "
            f"`{row['phase']}` | `{row['current_state']}` | {row['planned_live_calls']} | "
            f"`{row['dag_node']}` | `{row['claim_boundary']}` |"
        )
    lines.extend(["", "## Commands", ""])
    for row in bundle["rows"]:
        lines.extend(
            [
                f"### {row['step_order']}. {row['bundle_step_id']}",
                "",
                f"- Depends on: `{'; '.join(row['depends_on']) or 'root'}`",
                f"- Expected artifacts: `{'; '.join(row['expected_artifacts'])}`",
                f"- Success gate: `{row['success_gate']}`",
                "",
                "```bash",
                row["command"],
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Reading",
            "",
            "- This bundle is the ordered handoff between readiness/runbook artifacts and the post-live evidence DAG.",
            "- It keeps P0 DeepSeek resume, output audit, safety, latency comparison, promotion, and report/PPT validation in one executable sequence.",
            "- Omni48 remains label-only and Qwen remains fallback-only; neither can promote timeline writeback or primary latency claims from this bundle alone.",
            "- The builder performs no live/API/model/scoring calls, writes no secret values, and makes no new metric claim.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    bundle = build_bundle(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(bundle, args.output_md)
    write_csv(bundle, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
