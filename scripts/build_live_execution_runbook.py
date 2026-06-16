#!/usr/bin/env python3
"""Build a no-live-call runbook for executing pending LLM/Omni work."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_execution_runbook.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_execution_runbook.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_execution_runbook.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def by_id(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key)): row for row in rows}


def build_runbook(root: Path) -> dict[str, Any]:
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    agent_plan = read_json(root / "outputs/research_progress_snapshot/live_agent_execution_plan.json")
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    scoring = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    split_policy = read_json(root / "outputs/research_progress_snapshot/split_policy_optimization.json")
    slo = read_json(root / "outputs/research_progress_snapshot/stage_latency_slo_audit.json")

    plan_steps = by_id(agent_plan.get("steps", []), "step_id")
    scoring_steps = by_id(scoring.get("scoring_steps", []), "scoring_id")
    readiness_runs = by_id(readiness.get("runs", []), "run_id")

    credential_ready = bool(readiness.get("environment", {}).get("dashscope_like_api_key_present"))
    deepseek_plan = plan_steps.get("split20_deepseek_resume_after_top3", {})
    qwen_plan = plan_steps.get("split20_qwen_backup_full_surface", {})
    omni_plan = plan_steps.get("omni48_label_only_live", {})
    postrun_plan = plan_steps.get("postrun_refresh_and_validation", {})

    steps = [
        {
            "runbook_step": 1,
            "step_id": "credential_preflight",
            "priority": "P0",
            "phase": "preflight",
            "status": "ready" if credential_ready else "blocked_missing_credentials",
            "blocking_gate": "dashscope_or_bailian_api_key_env_present",
            "planned_live_calls": 0,
            "command": "export DASHSCOPE_API_KEY=...  # or BAILIAN_API_KEY / ALIYUN_BAILIAN_API_KEY; keep secrets out of artifacts",
            "expected_artifacts": "outputs/research_progress_snapshot/live_run_readiness.json",
            "success_gate": "live_run_readiness reports credential env presence true; no secret values written",
            "writeback_right": "none",
        },
        {
            "runbook_step": 2,
            "step_id": "deepseek_resume_primary",
            "priority": "P0",
            "phase": "live_call",
            "status": deepseek_plan.get("status", "not_built"),
            "blocking_gate": ";".join(deepseek_plan.get("blockers", [])) or "none",
            "planned_live_calls": int(deepseek_plan.get("planned_calls") or 139),
            "command": deepseek_plan.get("run_command", ""),
            "expected_artifacts": "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl",
            "success_gate": "139 successful calls / 101 parent windows; no provider quota failures",
            "writeback_right": deepseek_plan.get("writeback_right", "block_or_quarantine_only"),
        },
        {
            "runbook_step": 3,
            "step_id": "post_live_output_audit",
            "priority": "P0",
            "phase": "postrun_audit",
            "status": output_audit.get("status", "not_built"),
            "blocking_gate": "live output JSONL must exist before claim-ready",
            "planned_live_calls": 0,
            "command": "python scripts/build_live_output_audit.py",
            "expected_artifacts": "outputs/research_progress_snapshot/live_output_audit.json",
            "success_gate": "deepseek_resume_after_top3 claim_gate is ready_for_llm_safety_latency_scoring",
            "writeback_right": "none",
        },
        {
            "runbook_step": 4,
            "step_id": "deepseek_resume_safety_and_comparison",
            "priority": "P0",
            "phase": "postrun_scoring",
            "status": "blocked_waiting_live_output"
            if scoring_steps.get("deepseek_resume_safety", {}).get("status", "").startswith("blocked")
            else "ready_to_score",
            "blocking_gate": scoring_steps.get("deepseek_resume_safety", {}).get("coverage_gate", ""),
            "planned_live_calls": 0,
            "command": (
                scoring_steps.get("deepseek_resume_safety", {}).get("scoring_command", "")
                + " && "
                + scoring_steps.get("deepseek_full_split20_comparison", {}).get("scoring_command", "")
            ),
            "expected_artifacts": ";".join(
                scoring_steps.get("deepseek_resume_safety", {}).get("output_artifacts", [])
                + scoring_steps.get("deepseek_full_split20_comparison", {}).get("output_artifacts", [])
            ),
            "success_gate": "harmful_accepts == 0 and parent_windows == 104 and split_calls == 147",
            "writeback_right": "none",
        },
        {
            "runbook_step": 5,
            "step_id": "omni48_label_only_live",
            "priority": "P1",
            "phase": "live_call",
            "status": omni_plan.get("status", "not_built"),
            "blocking_gate": ";".join(omni_plan.get("blockers", [])) or "none",
            "planned_live_calls": int(omni_plan.get("planned_calls") or 96),
            "command": omni_plan.get("run_command", ""),
            "expected_artifacts": "outputs/omni_guard/omni_expansion_48_live.jsonl",
            "success_gate": "96 successful label-only calls; no timeline writeback",
            "writeback_right": omni_plan.get("writeback_right", "label_only_no_timeline_writeback"),
        },
        {
            "runbook_step": 6,
            "step_id": "qwen_full_backup_optional",
            "priority": "P1",
            "phase": "fallback_live_call",
            "status": qwen_plan.get("status", "not_built"),
            "blocking_gate": ";".join(qwen_plan.get("blockers", [])) or "none",
            "planned_live_calls": int(qwen_plan.get("planned_calls") or 147),
            "command": qwen_plan.get("run_command", ""),
            "expected_artifacts": "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl",
            "success_gate": "fallback safety harmful_accepts == 0; do not promote as primary latency unless faster",
            "writeback_right": qwen_plan.get("writeback_right", "block_or_quarantine_only"),
        },
        {
            "runbook_step": 7,
            "step_id": "refresh_report_ppt_validation",
            "priority": "P0",
            "phase": "refresh_and_validate",
            "status": postrun_plan.get("status", "waiting_for_live_outputs"),
            "blocking_gate": ";".join(postrun_plan.get("blockers", [])) or "requires_completed_live_outputs",
            "planned_live_calls": 0,
            "command": postrun_plan.get("run_command", "python scripts/refresh_latest_research_artifacts.py"),
            "expected_artifacts": "outputs/research_progress_snapshot/latest_artifact_validation.md; ../研究进展汇报.pptx; docs/reports/2026-06-03-realtime-dual-agent-roadmap.md",
            "success_gate": "refresh pass and validation failed_checks == []",
            "writeback_right": "none",
        },
    ]

    blocked_steps = [row for row in steps if str(row["status"]).startswith("blocked") or "blocked" in str(row["blocking_gate"])]
    command_steps = [row for row in steps if row["command"]]
    p0_steps = [row for row in steps if row["priority"] == "P0"]
    p1_steps = [row for row in steps if row["priority"] == "P1"]
    return {
        "runtime_contract": "live_execution_runbook_no_live_calls_no_secret_values",
        "secret_policy": "env_presence_only_no_secret_values_written",
        "status": "blocked_waiting_for_credentials_or_live_outputs" if blocked_steps else "ready_for_ordered_execution",
        "source_contracts": {
            "live_run_readiness": readiness.get("runtime_contract", ""),
            "live_agent_execution_plan": agent_plan.get("runtime_contract", ""),
            "live_output_audit": output_audit.get("runtime_contract", ""),
            "live_scoring_readiness": scoring.get("runtime_contract", ""),
            "split_policy_optimization": split_policy.get("runtime_contract", ""),
            "stage_latency_slo_audit": slo.get("runtime_contract", ""),
        },
        "summary": {
            "runbook_step_count": len(steps),
            "p0_steps": len(p0_steps),
            "p1_steps": len(p1_steps),
            "blocked_steps": len(blocked_steps),
            "command_steps": len(command_steps),
            "planned_live_calls_total": sum(int(row["planned_live_calls"]) for row in steps),
            "p0_planned_live_calls": sum(int(row["planned_live_calls"]) for row in p0_steps),
            "p1_planned_live_calls": sum(int(row["planned_live_calls"]) for row in p1_steps),
            "deepseek_primary_policy": split_policy.get("summary", {}).get("primary_policy", "max20"),
            "claim_now_slo_pass": slo.get("summary", {}).get("claim_now_slo_pass", 0),
            "claim_now_slo_rows": slo.get("summary", {}).get("claim_now_slo_rows", 0),
            "ready_runs": readiness.get("summary", {}).get("ready_count", 0),
            "missing_output_surfaces": output_audit.get("summary", {}).get("missing_output_surfaces", 0),
            "ready_to_score_steps": scoring.get("summary", {}).get("ready_to_score_steps", 0),
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
        },
        "steps": steps,
    }


def write_csv(runbook: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "runbook_step",
        "step_id",
        "priority",
        "phase",
        "status",
        "blocking_gate",
        "planned_live_calls",
        "writeback_right",
        "success_gate",
        "expected_artifacts",
        "command",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in runbook["steps"]:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_markdown(runbook: dict[str, Any], path: Path) -> None:
    summary = runbook["summary"]
    lines = [
        "# Live Execution Runbook",
        "",
        f"- Runtime contract: `{runbook['runtime_contract']}`",
        f"- Secret policy: `{runbook['secret_policy']}`",
        f"- Status: `{runbook['status']}`",
        f"- Steps: `{summary['runbook_step_count']}`",
        f"- P0 / P1 steps: `{summary['p0_steps']}` / `{summary['p1_steps']}`",
        f"- Blocked steps: `{summary['blocked_steps']}`",
        f"- Planned live calls total: `{summary['planned_live_calls_total']}`",
        f"- P0 planned live calls: `{summary['p0_planned_live_calls']}`",
        f"- DeepSeek primary policy: `{summary['deepseek_primary_policy']}`",
        f"- Claim-now SLO pass: `{summary['claim_now_slo_pass']}/{summary['claim_now_slo_rows']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No secret values written: `{summary['no_secret_values_written']}`",
        "",
        "| # | Step | Priority | Phase | Status | Calls | Writeback | Success gate |",
        "|---:|---|---|---|---|---:|---|---|",
    ]
    for row in runbook["steps"]:
        success = str(row["success_gate"]).replace("|", "/")
        lines.append(
            f"| {row['runbook_step']} | `{row['step_id']}` | `{row['priority']}` | `{row['phase']}` | "
            f"`{row['status']}` | {row['planned_live_calls']} | `{row['writeback_right']}` | {success} |"
        )
    lines.extend(["", "## Commands", ""])
    for row in runbook["steps"]:
        lines.extend(
            [
                f"### {row['runbook_step']}. {row['step_id']}",
                "",
                f"- Blocking gate: `{row['blocking_gate']}`",
                f"- Expected artifacts: `{row['expected_artifacts']}`",
                "",
                "```bash",
                str(row["command"]),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Reading",
            "",
            "- This runbook is a live-execution handoff artifact; it performs no model/API calls.",
            "- Credentials are represented only as environment-presence gates; no secret values are written.",
            "- P0 execution remains DeepSeek max20 resume first, followed by output audit, safety scoring, comparison, and refresh validation.",
            "- Omni48 and Qwen full backup remain P1 unless the user explicitly chooses to spend provider quota there.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    runbook = build_runbook(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(runbook, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(runbook, args.output_md)
    write_csv(runbook, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
