#!/usr/bin/env python3
"""Build a no-live-call handoff packet for the pending live execution."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_execution_handoff_packet.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_execution_handoff_packet.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_execution_handoff_packet.csv")


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


def packet_row(
    packet_id: str,
    priority: str,
    execution_stage: str,
    current_state: str,
    required_action: str,
    success_gate: str,
    evidence_artifacts: list[str],
    claim_boundary: str,
) -> dict[str, Any]:
    return {
        "packet_id": packet_id,
        "priority": priority,
        "execution_stage": execution_stage,
        "current_state": current_state,
        "required_action": required_action,
        "success_gate": success_gate,
        "evidence_artifacts": evidence_artifacts,
        "claim_boundary": claim_boundary,
    }


def build_packet(root: Path) -> dict[str, Any]:
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    runtime_env = read_json(root / "outputs/research_progress_snapshot/live_runtime_environment_audit.json")
    input_integrity = read_json(root / "outputs/research_progress_snapshot/live_input_integrity_audit.json")
    runbook = read_json(root / "outputs/research_progress_snapshot/live_execution_runbook.json")
    command_surface = read_json(root / "outputs/research_progress_snapshot/live_command_surface_audit.json")
    timing = read_json(root / "outputs/research_progress_snapshot/live_execution_timing_plan.json")
    retry = read_json(root / "outputs/research_progress_snapshot/live_retry_budget_audit.json")
    token_quota = read_json(root / "outputs/research_progress_snapshot/live_token_quota_budget_audit.json")
    failure_recovery = read_json(root / "outputs/research_progress_snapshot/live_failure_recovery_playbook.json")
    scoring = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    scorecard = read_json(root / "outputs/research_progress_snapshot/post_live_acceptance_scorecard.json")

    readiness_summary = readiness.get("summary", {})
    env_summary = runtime_env.get("summary", {})
    input_summary = input_integrity.get("summary", {})
    runbook_summary = runbook.get("summary", {})
    command_summary = command_surface.get("summary", {})
    timing_summary = timing.get("summary", {})
    retry_summary = retry.get("summary", {})
    token_summary = token_quota.get("summary", {})
    recovery_summary = failure_recovery.get("summary", {})
    scoring_summary = scoring.get("summary", {})
    promotion_summary = promotion.get("summary", {})
    scorecard_summary = scorecard.get("summary", {})
    command_rows = by_id(command_surface.get("rows", []), "command_id")

    deepseek_command = command_rows.get("deepseek_resume_primary", {}).get("command", "")
    omni_command = command_rows.get("omni48_label_only_live", {}).get("command", "")
    qwen_command = command_rows.get("qwen_full_backup_optional", {}).get("command", "")

    rows = [
        packet_row(
            "credential_quota_preflight",
            "P0",
            "preflight",
            "blocked_missing_credentials_or_provider_quota",
            "Set DashScope/Bailian credentials only in the runner shell, then rerun readiness/runtime environment audits.",
            "credential_ready true, known provider quota blocker cleared, and no secret literal appears in artifacts",
            [
                "outputs/research_progress_snapshot/live_run_readiness.json",
                "outputs/research_progress_snapshot/live_runtime_environment_audit.json",
            ],
            "no_secret_values_no_live_metric_claim",
        ),
        packet_row(
            "deepseek_resume_primary_command",
            "P0",
            "primary_live_call",
            "command_ready_waiting_credentials_or_quota",
            deepseek_command,
            "139 successful resume rows, 101 parent windows, no parse/duplicate/extra/missing call errors",
            [
                "outputs/research_progress_snapshot/live_command_surface_audit.json",
                "outputs/research_progress_snapshot/live_input_integrity_audit.json",
                "outputs/research_progress_snapshot/split20_resume_export_audit.json",
            ],
            "block_or_quarantine_only_until_postrun_scoring_passes",
        ),
        packet_row(
            "deepseek_postrun_scoring_gate",
            "P0",
            "postrun_scoring",
            "blocked_waiting_live_outputs",
            "Run output audit, DeepSeek safety scoring, full split20 comparison, then promotion gate.",
            "harmful_accepts == 0, 104 parent windows, 147 split calls, token multiplier and latency summary present",
            [
                "outputs/research_progress_snapshot/live_output_audit.json",
                "outputs/research_progress_snapshot/live_scoring_readiness.json",
                "outputs/research_progress_snapshot/live_metric_extraction_contract.json",
            ],
            "post_live_metrics_only_after_output_audit_and_scoring",
        ),
        packet_row(
            "claim_preservation_boundary",
            "P0",
            "claim_guard",
            "preserve_current_claims_only",
            "Keep current 4/4 SLO claims; do not promote split20/Omni/Qwen until scorecard and promotion gates pass.",
            "ready_to_promote remains 0 until live outputs, scoring, SLO, and traceability are complete",
            [
                "outputs/research_progress_snapshot/stage_latency_slo_audit.json",
                "outputs/research_progress_snapshot/post_live_acceptance_scorecard.json",
                "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json",
            ],
            "no_new_metric_claim",
        ),
        packet_row(
            "omni48_label_only_boundary",
            "P1",
            "label_only_live_call",
            "command_ready_waiting_credentials",
            omni_command,
            "96 successful Omni rows, schema_ok true, label metrics present, no timeline writeback",
            [
                "outputs/research_progress_snapshot/omni48_live_call_manifest.json",
                "outputs/research_progress_snapshot/live_command_surface_audit.json",
            ],
            "label_only_no_timeline_writeback",
        ),
        packet_row(
            "qwen_full_backup_boundary",
            "P1",
            "fallback_live_call",
            "fallback_only_waiting_credentials",
            qwen_command,
            "fallback safety/comparison can be reported only as backup unless the promotion gate changes boundary",
            [
                "outputs/research_progress_snapshot/live_command_surface_audit.json",
                "outputs/research_progress_snapshot/live_metric_extraction_contract.json",
            ],
            "fallback_only_not_primary_latency_claim",
        ),
        packet_row(
            "final_refresh_validation_sync",
            "P0",
            "refresh_and_validate",
            "waiting_live_outputs",
            "Run python scripts/refresh_latest_research_artifacts.py after live output and scoring artifacts are present.",
            "refresh pass, latest validator failed_checks empty, report/PPT traceability fully covered",
            [
                "outputs/research_progress_snapshot/refresh_latest_artifacts.json",
                "outputs/research_progress_snapshot/latest_artifact_validation.json",
                "outputs/research_progress_snapshot/report_ppt_traceability.json",
            ],
            "report_ppt_sync_required_before_claim_promotion",
        ),
    ]

    return {
        "runtime_contract": "live_execution_handoff_packet_no_live_calls",
        "secret_policy": "env_presence_only_no_secret_values_written",
        "status": "blocked_waiting_credentials_or_quota",
        "source_contracts": {
            "live_run_readiness": readiness.get("runtime_contract", ""),
            "live_runtime_environment_audit": runtime_env.get("runtime_contract", ""),
            "live_input_integrity_audit": input_integrity.get("runtime_contract", ""),
            "live_execution_runbook": runbook.get("runtime_contract", ""),
            "live_command_surface_audit": command_surface.get("runtime_contract", ""),
            "live_execution_timing_plan": timing.get("runtime_contract", ""),
            "live_retry_budget_audit": retry.get("runtime_contract", ""),
            "live_token_quota_budget_audit": token_quota.get("runtime_contract", ""),
            "live_failure_recovery_playbook": failure_recovery.get("runtime_contract", ""),
            "live_scoring_readiness": scoring.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
            "post_live_acceptance_scorecard": scorecard.get("runtime_contract", ""),
        },
        "summary": {
            "packet_rows": len(rows),
            "p0_packet_rows": sum(1 for row in rows if row["priority"] == "P0"),
            "p1_packet_rows": sum(1 for row in rows if row["priority"] == "P1"),
            "handoff_blocked_rows": sum(1 for row in rows if "blocked" in row["current_state"] or "waiting" in row["current_state"]),
            "credential_ready": bool(env_summary.get("credential_ready")),
            "known_provider_quota_blockers": as_int(env_summary.get("known_provider_quota_blockers")),
            "ready_runs": as_int(readiness_summary.get("ready_count")),
            "blocked_runs": as_int(readiness_summary.get("blocked_count")),
            "input_ready_surfaces": as_int(input_summary.get("input_ready_surfaces")),
            "command_ready_count": as_int(command_summary.get("command_ready_count")),
            "command_count": as_int(command_summary.get("command_count")),
            "planned_live_calls": as_int(command_summary.get("planned_live_calls")),
            "p0_planned_live_calls": as_int(command_summary.get("p0_planned_live_calls")),
            "runbook_steps": as_int(runbook_summary.get("runbook_step_count")),
            "deepseek_estimated_wall_seconds": timing_summary.get("deepseek_estimated_wall_seconds", ""),
            "max_attempted_requests": as_int(retry_summary.get("max_attempted_requests")),
            "llm_retry_token_proxy_ceiling": as_int(token_summary.get("llm_retry_token_proxy_ceiling")),
            "ready_recovery_actions": as_int(recovery_summary.get("ready_recovery_actions")),
            "missing_output_surfaces": as_int(scorecard_summary.get("missing_output_surfaces")),
            "ready_to_score_steps": as_int(scoring_summary.get("ready_to_score_steps")),
            "ready_to_promote_count": as_int(promotion_summary.get("ready_to_promote_count")),
            "scorecard_rows": as_int(scorecard_summary.get("scorecard_rows")),
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(packet: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "packet_id",
        "priority",
        "execution_stage",
        "current_state",
        "required_action",
        "success_gate",
        "evidence_artifacts",
        "claim_boundary",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in packet["rows"]:
            out = dict(row)
            out["evidence_artifacts"] = "; ".join(out["evidence_artifacts"])
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def write_markdown(packet: dict[str, Any], path: Path) -> None:
    summary = packet["summary"]
    lines = [
        "# Live Execution Handoff Packet",
        "",
        f"- Runtime contract: `{packet['runtime_contract']}`",
        f"- Secret policy: `{packet['secret_policy']}`",
        f"- Status: `{packet['status']}`",
        f"- Packet rows: `{summary['packet_rows']}`",
        f"- P0 / P1 rows: `{summary['p0_packet_rows']}` / `{summary['p1_packet_rows']}`",
        f"- Handoff blocked/waiting rows: `{summary['handoff_blocked_rows']}`",
        f"- Credential ready: `{summary['credential_ready']}`",
        f"- Known provider quota blockers: `{summary['known_provider_quota_blockers']}`",
        f"- Command-ready: `{summary['command_ready_count']}` / `{summary['command_count']}`",
        f"- Input-ready surfaces: `{summary['input_ready_surfaces']}`",
        f"- Planned live calls: `{summary['planned_live_calls']}`",
        f"- P0 planned live calls: `{summary['p0_planned_live_calls']}`",
        f"- DeepSeek estimated wall seconds: `{summary['deepseek_estimated_wall_seconds']}`",
        f"- Max attempted requests: `{summary['max_attempted_requests']}`",
        f"- LLM retry token proxy ceiling: `{summary['llm_retry_token_proxy_ceiling']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- Ready to score: `{summary['ready_to_score_steps']}`",
        f"- Ready to promote: `{summary['ready_to_promote_count']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Packet | Priority | Stage | State | Success gate | Claim boundary |",
        "|---|---|---|---|---|---|",
    ]
    for row in packet["rows"]:
        lines.append(
            f"| `{row['packet_id']}` | `{row['priority']}` | `{row['execution_stage']}` | "
            f"`{row['current_state']}` | {row['success_gate']} | `{row['claim_boundary']}` |"
        )
    lines.extend(["", "## Actions", ""])
    for row in packet["rows"]:
        action = str(row["required_action"]).replace("\n", " ")
        lines.extend(
            [
                f"### {row['packet_id']}",
                "",
                f"- Current state: `{row['current_state']}`",
                f"- Evidence: `{'`; `'.join(row['evidence_artifacts'])}`",
                "",
                "```bash" if action.startswith("python ") else "```text",
                action,
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Reading",
            "",
            "- This handoff packet is for the next live execution attempt; it performs no live/model/API/scoring calls.",
            "- P0 remains DeepSeek max20 resume first, then output audit, safety scoring, split20 comparison, promotion gate, and full refresh.",
            "- Omni48 remains label-only and Qwen remains fallback-only unless a later promotion gate explicitly changes those boundaries.",
            "- Credential state is represented only as booleans; secret values must stay in the runner environment and out of artifacts.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    packet = build_packet(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(packet, args.output_md)
    write_csv(packet, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
