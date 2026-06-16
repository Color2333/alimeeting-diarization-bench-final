#!/usr/bin/env python3
"""Build a no-live-call failure recovery playbook for live handoff surfaces."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_failure_recovery_playbook.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_failure_recovery_playbook.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_failure_recovery_playbook.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def scenario(
    scenario_id: str,
    priority: str,
    status: str,
    source_artifact: str,
    current_observation: str,
    recovery_action: str,
    success_gate: str,
    claim_status: str,
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "priority": priority,
        "status": status,
        "source_artifact": source_artifact,
        "current_observation": current_observation,
        "recovery_action": recovery_action,
        "success_gate": success_gate,
        "claim_status": claim_status,
    }


def build_playbook(root: Path) -> dict[str, Any]:
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    command = read_json(root / "outputs/research_progress_snapshot/live_command_surface_audit.json")
    retry = read_json(root / "outputs/research_progress_snapshot/live_retry_budget_audit.json")
    token = read_json(root / "outputs/research_progress_snapshot/live_token_quota_budget_audit.json")
    output = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    resume = read_json(root / "outputs/research_progress_snapshot/live_resume_state_audit.json")
    runtime = read_json(root / "outputs/research_progress_snapshot/live_runtime_environment_audit.json")
    scoring = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")

    command_summary = command.get("summary", {})
    retry_summary = retry.get("summary", {})
    token_summary = token.get("summary", {})
    output_summary = output.get("summary", {})
    runtime_summary = runtime.get("summary", {})
    scoring_summary = scoring.get("summary", {})
    promotion_summary = promotion.get("summary", {})
    env = readiness.get("environment", {})

    rows = [
        scenario(
            "missing_credentials",
            "P0",
            "current_blocker" if not env.get("dashscope_like_api_key_present") else "not_triggered",
            "outputs/research_progress_snapshot/live_runtime_environment_audit.md",
            f"credential_ready={bool(runtime_summary.get('credential_ready'))}",
            "Set a DashScope/Bailian API key in the live runner environment only, then rerun readiness and runtime environment audits; never write secret values into artifacts.",
            "live_runtime_environment_audit status remains ready and credential_ready becomes true without secret literals.",
            "blocked_no_secret_value_no_metric_claim",
        ),
        scenario(
            "known_provider_quota_blocker",
            "P0",
            "current_blocker" if as_int(runtime_summary.get("known_provider_quota_blockers")) else "not_triggered",
            "outputs/research_progress_snapshot/live_run_readiness.md",
            "DeepSeek top4/top5 previously failed with AllocationQuota.FreeTierOnly.",
            "Wait for quota/paid tier capacity or choose an explicitly tracked fallback; keep P0 DeepSeek resume blocked until provider capacity is available.",
            "P0 live command finishes without AllocationQuota.FreeTierOnly and output audit sees complete DeepSeek resume rows.",
            "blocked_by_provider_quota_no_metric_claim",
        ),
        scenario(
            "missing_output_clean_run",
            "P0",
            "current_blocker" if as_int(output_summary.get("missing_output_surfaces")) else "not_triggered",
            "outputs/research_progress_snapshot/live_output_audit.md",
            f"missing_output_surfaces={as_int(output_summary.get('missing_output_surfaces'))}; expected_live_calls={as_int(output_summary.get('expected_live_calls'))}",
            "Run the current skip-existing, bounded-retry live commands after credentials and quota are ready; preserve the configured output paths.",
            "live_output_audit reports no missing surfaces and no parse/duplicate/extra call errors.",
            "blocked_missing_output_no_metric_claim",
        ),
        scenario(
            "partial_or_invalid_output",
            "P0",
            "future_recovery_path",
            "outputs/research_progress_snapshot/live_output_audit.md",
            f"partial_or_invalid_surfaces={as_int(output_summary.get('partial_or_invalid_surfaces'))}",
            "Quarantine/archive malformed output JSONL, inspect parse errors, duplicate ids, missing ids, and extra ids, then rerun with --skip-existing-output.",
            "output audit status advances to complete output needing metric/safety scoring instead of partial_or_invalid_output.",
            "future_recovery_no_metric_claim",
        ),
        scenario(
            "retry_exhausted_errors",
            "P0",
            "future_recovery_path",
            "outputs/research_progress_snapshot/live_retry_budget_audit.md",
            f"max_attempted_requests={as_int(retry_summary.get('max_attempted_requests'))}; max_call_attempts=2",
            "Keep failed rows as evidence, fix the provider-side or transient error, then rerun only missing/failed calls through the skip-existing surface.",
            "failed rows shrink to zero or are explicitly isolated before scoring; call_attempts remain recorded for failed rows.",
            "future_recovery_no_metric_claim",
        ),
        scenario(
            "scoring_blocked_missing_output",
            "P0",
            "current_blocker" if as_int(scoring_summary.get("ready_to_score_steps")) == 0 else "not_triggered",
            "outputs/research_progress_snapshot/live_scoring_readiness.md",
            f"ready_to_score_steps={as_int(scoring_summary.get('ready_to_score_steps'))}/{as_int(scoring_summary.get('scoring_step_count'))}",
            "Run output audit first; only then run the safety/comparison/Omni scoring commands listed by scoring readiness.",
            "ready_to_score_steps reaches the expected scored surfaces and scoring artifacts exist.",
            "blocked_waiting_live_outputs_no_metric_claim",
        ),
        scenario(
            "promotion_blocked",
            "P0",
            "current_blocker" if as_int(promotion_summary.get("ready_to_promote_count")) == 0 else "not_triggered",
            "outputs/research_progress_snapshot/post_live_claim_promotion_gate.md",
            f"ready_to_promote={as_int(promotion_summary.get('ready_to_promote_count'))}/{as_int(promotion_summary.get('gate_count'))}",
            "Promote claims only after output audit, scoring, SLO, and report/PPT traceability all pass; keep smoke/planning rows out of metric claims.",
            "promotion gate marks the relevant live rows ready_to_promote and traceability remains fully covered.",
            "promote_only_after_output_audit_scoring_slo_and_traceability_pass",
        ),
        scenario(
            "token_or_attempt_budget_ceiling",
            "P1",
            "planning_guardrail",
            "outputs/research_progress_snapshot/live_token_quota_budget_audit.md",
            f"max_attempted_requests={as_int(retry_summary.get('max_attempted_requests'))}; llm_retry_token_proxy_ceiling={as_int(token_summary.get('llm_retry_token_proxy_ceiling'))}",
            "Treat 764 attempted requests and the 1.66M prompt-token proxy ceiling as planning ceilings; keep P1 Qwen/Omni expansion behind P0 stability.",
            "live run choice stays within the audited attempt/token/clip proxy budget or records a new budget audit before execution.",
            "quota_planning_only_no_metric_claim",
        ),
    ]
    return {
        "runtime_contract": "live_failure_recovery_playbook_no_live_calls",
        "status": "ready_waiting_credentials_or_live_outputs",
        "source_contracts": {
            "live_run_readiness": readiness.get("runtime_contract", ""),
            "live_command_surface_audit": command.get("runtime_contract", ""),
            "live_retry_budget_audit": retry.get("runtime_contract", ""),
            "live_token_quota_budget_audit": token.get("runtime_contract", ""),
            "live_output_audit": output.get("runtime_contract", ""),
            "live_resume_state_audit": resume.get("runtime_contract", ""),
            "live_runtime_environment_audit": runtime.get("runtime_contract", ""),
            "live_scoring_readiness": scoring.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
        },
        "summary": {
            "scenario_count": len(rows),
            "p0_scenario_count": sum(1 for row in rows if row["priority"] == "P0"),
            "current_blocker_scenarios": sum(1 for row in rows if row["status"] == "current_blocker"),
            "future_recovery_scenarios": sum(1 for row in rows if row["status"] == "future_recovery_path"),
            "planning_guardrail_scenarios": sum(1 for row in rows if row["status"] == "planning_guardrail"),
            "ready_recovery_actions": sum(1 for row in rows if row["recovery_action"]),
            "planned_live_calls": as_int(command_summary.get("planned_live_calls") or retry_summary.get("planned_live_calls")),
            "max_attempted_requests": as_int(retry_summary.get("max_attempted_requests")),
            "llm_retry_token_proxy_ceiling": as_int(token_summary.get("llm_retry_token_proxy_ceiling")),
            "missing_output_surfaces": as_int(output_summary.get("missing_output_surfaces")),
            "partial_or_invalid_surfaces": as_int(output_summary.get("partial_or_invalid_surfaces")),
            "ready_to_score_steps": as_int(scoring_summary.get("ready_to_score_steps")),
            "ready_to_promote_count": as_int(promotion_summary.get("ready_to_promote_count")),
            "known_provider_quota_blockers": as_int(runtime_summary.get("known_provider_quota_blockers")),
            "credential_ready": bool(runtime_summary.get("credential_ready")),
            "skip_existing_supported_surfaces": as_int(resume.get("summary", {}).get("skip_existing_supported_surfaces")),
            "bounded_retry_supported_surfaces": as_int(resume.get("summary", {}).get("bounded_retry_supported_surfaces")),
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(playbook: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "scenario_id",
        "priority",
        "status",
        "source_artifact",
        "current_observation",
        "recovery_action",
        "success_gate",
        "claim_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in playbook["rows"]:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_markdown(playbook: dict[str, Any], path: Path) -> None:
    summary = playbook["summary"]
    lines = [
        "# Live Failure Recovery Playbook",
        "",
        f"- Runtime contract: `{playbook['runtime_contract']}`",
        f"- Status: `{playbook['status']}`",
        f"- Scenarios: `{summary['scenario_count']}`",
        f"- P0 scenarios: `{summary['p0_scenario_count']}`",
        f"- Current blocker scenarios: `{summary['current_blocker_scenarios']}`",
        f"- Ready recovery actions: `{summary['ready_recovery_actions']}`",
        f"- Planned live calls: `{summary['planned_live_calls']}`",
        f"- Max attempted requests: `{summary['max_attempted_requests']}`",
        f"- LLM retry token proxy ceiling: `{summary['llm_retry_token_proxy_ceiling']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- Ready to score: `{summary['ready_to_score_steps']}`",
        f"- Ready to promote: `{summary['ready_to_promote_count']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No secret values written: `{summary['no_secret_values_written']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Scenario | Priority | Status | Observation | Recovery action | Success gate |",
        "|---|---|---|---|---|---|",
    ]
    for row in playbook["rows"]:
        lines.append(
            f"| `{row['scenario_id']}` | `{row['priority']}` | `{row['status']}` | "
            f"{row['current_observation']} | {row['recovery_action']} | {row['success_gate']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Use this playbook before any post-live claim promotion when credentials, quota, output completeness, scoring, or traceability is uncertain.",
            "- Current blockers are operational gates, not new metric claims.",
            "- Future recovery paths keep partial output and retry exhaustion auditable without blind append or silent overwrite.",
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

    playbook = build_playbook(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(playbook, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(playbook, args.output_md)
    write_csv(playbook, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
