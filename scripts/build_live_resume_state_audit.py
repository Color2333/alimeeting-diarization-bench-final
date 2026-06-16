#!/usr/bin/env python3
"""Audit live-output resume state without making live calls."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_resume_state_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_resume_state_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_resume_state_audit.csv")


SURFACE_TO_COMMAND = {
    "deepseek_resume_after_top3": "deepseek_resume_primary",
    "qwen_full_backup": "qwen_full_backup_optional",
    "omni48_label_only": "omni48_label_only_live",
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def csv_escape(value: object) -> str:
    text = str(value)
    if any(ch in text for ch in [",", "\n", '"']):
        return '"' + text.replace('"', '""') + '"'
    return text


def by_id(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key)): row for row in rows}


def output_state(surface: dict[str, Any]) -> str:
    if not surface.get("output_exists"):
        return "missing_output_clean_run"
    if surface.get("claim_gate") in {"ready_for_llm_safety_latency_scoring", "ready_for_omni_metric_scoring"}:
        return "complete_output_score_only"
    return "partial_or_invalid_output_quarantine_before_rerun"


def recommended_action(state: str, command_ready: bool) -> str:
    if state == "missing_output_clean_run":
        return "run_current_command_when_credentials_and_quota_are_ready" if command_ready else "fix_command_surface_before_live_run"
    if state == "complete_output_score_only":
        return "do_not_rerun_live_command_run_output_audit_and_scoring"
    return "rerun_with_skip_existing_output_after_quarantining_invalid_rows_if_needed"


def claim_gate(state: str) -> str:
    if state == "complete_output_score_only":
        return "ready_for_scoring_not_metric_claim"
    if state == "missing_output_clean_run":
        return "blocked_missing_output"
    return "blocked_partial_output_requires_recovery"


def build_audit(root: Path) -> dict[str, Any]:
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    command_audit = read_json(root / "outputs/research_progress_snapshot/live_command_surface_audit.json")
    runbook = read_json(root / "outputs/research_progress_snapshot/live_execution_runbook.json")
    scoring = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")

    command_rows = by_id(command_audit.get("rows", []), "command_id")
    surfaces = output_audit.get("surfaces", [])
    rows: list[dict[str, Any]] = []
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", ""))
        command_id = SURFACE_TO_COMMAND.get(surface_id, "")
        command = command_rows.get(command_id, {})
        state = output_state(surface)
        planned_calls = int(command.get("planned_live_calls") or surface.get("expected_calls") or 0)
        observed_calls = int(surface.get("observed_calls") or 0)
        successful_calls = int(surface.get("successful_calls") or 0)
        missing_calls = max(planned_calls - successful_calls, 0)
        command_ready = bool(command.get("command_ready"))
        current_command_safe_to_run = state == "missing_output_clean_run" and command_ready
        run_command = str(command.get("command", ""))
        append_resume_supported = False
        skip_existing_supported = "--skip-existing-output" in run_command
        bounded_retry_supported = str(command.get("max_call_attempts", "")) == "2"
        quarantine_required = state == "partial_or_invalid_output_quarantine_before_rerun"
        rows.append(
            {
                "surface_id": surface_id,
                "command_id": command_id,
                "priority": command.get("priority", ""),
                "output_jsonl": surface.get("output_jsonl", ""),
                "output_state": state,
                "planned_calls": planned_calls,
                "observed_calls": observed_calls,
                "successful_calls": successful_calls,
                "missing_calls": missing_calls,
                "observed_parent_windows": int(surface.get("observed_parent_windows") or 0),
                "expected_parent_windows": int(surface.get("expected_parent_windows") or 0),
                "runner_write_mode": "merge_successful_existing_then_overwrite_output_jsonl_and_csv",
                "append_resume_supported": append_resume_supported,
                "skip_existing_supported": skip_existing_supported,
                "bounded_retry_supported": bounded_retry_supported,
                "max_call_attempts": command.get("max_call_attempts", ""),
                "retry_backoff_seconds": command.get("retry_backoff_seconds", ""),
                "current_command_safe_to_run": current_command_safe_to_run,
                "quarantine_required": quarantine_required,
                "recommended_action": recommended_action(state, command_ready),
                "claim_gate": claim_gate(state),
                "writeback_right": command.get("writeback_right", ""),
                "run_command": run_command,
            }
        )

    clean_run_rows = [row for row in rows if row["output_state"] == "missing_output_clean_run"]
    completed_rows = [row for row in rows if row["output_state"] == "complete_output_score_only"]
    partial_rows = [row for row in rows if row["output_state"] == "partial_or_invalid_output_quarantine_before_rerun"]
    safe_rows = [row for row in rows if row["current_command_safe_to_run"]]
    p0_safe_rows = [row for row in safe_rows if row["priority"] == "P0"]
    return {
        "runtime_contract": "live_resume_state_audit_no_live_calls",
        "status": "clean_run_ready_waiting_credentials_or_quota" if len(safe_rows) == len(rows) else "resume_recovery_needed_or_scoring_ready",
        "source_contracts": {
            "live_output_audit": output_audit.get("runtime_contract", ""),
            "live_command_surface_audit": command_audit.get("runtime_contract", ""),
            "live_execution_runbook": runbook.get("runtime_contract", ""),
            "live_scoring_readiness": scoring.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
        },
        "summary": {
            "surface_count": len(rows),
            "clean_run_surfaces": len(clean_run_rows),
            "partial_or_invalid_surfaces": len(partial_rows),
            "completed_output_surfaces": len(completed_rows),
            "current_commands_safe_to_run": len(safe_rows),
            "p0_current_commands_safe_to_run": len(p0_safe_rows),
            "append_resume_supported_surfaces": sum(1 for row in rows if row["append_resume_supported"]),
            "skip_existing_supported_surfaces": sum(1 for row in rows if row["skip_existing_supported"]),
            "bounded_retry_supported_surfaces": sum(1 for row in rows if row["bounded_retry_supported"]),
            "quarantine_required_surfaces": len(partial_rows),
            "planned_live_calls": sum(int(row["planned_calls"]) for row in rows),
            "p0_planned_live_calls": sum(int(row["planned_calls"]) for row in rows if row["priority"] == "P0"),
            "observed_live_output_rows": sum(int(row["observed_calls"]) for row in rows),
            "successful_live_output_rows": sum(int(row["successful_calls"]) for row in rows),
            "missing_live_calls": sum(int(row["missing_calls"]) for row in rows),
            "ready_to_score_steps": int(scoring.get("summary", {}).get("ready_to_score_steps", 0)),
            "ready_to_promote_gates": int(promotion.get("summary", {}).get("ready_to_promote_count", 0)),
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(audit: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "surface_id",
        "command_id",
        "priority",
        "output_state",
        "planned_calls",
        "observed_calls",
        "successful_calls",
        "missing_calls",
        "runner_write_mode",
        "append_resume_supported",
        "skip_existing_supported",
        "bounded_retry_supported",
        "max_call_attempts",
        "retry_backoff_seconds",
        "current_command_safe_to_run",
        "quarantine_required",
        "recommended_action",
        "claim_gate",
        "output_jsonl",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(fieldnames)]
    for row in audit["rows"]:
        lines.append(",".join(csv_escape(row.get(key, "")) for key in fieldnames))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    lines = [
        "# Live Resume State Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Clean-run surfaces: `{summary['clean_run_surfaces']}` / `{summary['surface_count']}`",
        f"- Current commands safe to run: `{summary['current_commands_safe_to_run']}`",
        f"- P0 current commands safe to run: `{summary['p0_current_commands_safe_to_run']}`",
        f"- Partial/invalid surfaces: `{summary['partial_or_invalid_surfaces']}`",
        f"- Completed output surfaces: `{summary['completed_output_surfaces']}`",
        f"- Append resume supported surfaces: `{summary['append_resume_supported_surfaces']}`",
        f"- Skip-existing supported surfaces: `{summary['skip_existing_supported_surfaces']}`",
        f"- Bounded-retry supported surfaces: `{summary['bounded_retry_supported_surfaces']}`",
        f"- Quarantine required surfaces: `{summary['quarantine_required_surfaces']}`",
        f"- Planned live calls: `{summary['planned_live_calls']}`",
        f"- Missing live calls: `{summary['missing_live_calls']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Surface | Command | State | Calls | Safe now | Action | Claim gate |",
        "|---|---|---|---:|---|---|---|",
    ]
    for row in audit["rows"]:
        lines.append(
            f"| `{row['surface_id']}` | `{row['command_id']}` | `{row['output_state']}` | "
            f"{row['planned_calls']} | `{row['current_command_safe_to_run']}` | "
            f"`{row['recommended_action']}` | `{row['claim_gate']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This audit is a no-live-call recovery decision table for pending live outputs.",
            "- The current LLM and Omni runners reuse successful existing rows with `--skip-existing-output`, then overwrite a complete merged JSONL/CSV.",
            "- They use bounded retry (`--max-call-attempts 2 --retry-backoff-seconds 2.0`) for transient call failures.",
            "- They still do not append blindly; failed or invalid rows are rerun, while successful rows can be preserved.",
            "- When an output is missing, the current command is safe as a clean run after credentials and quota are available.",
            "- When a partial output appears, prefer `--skip-existing-output`; quarantine/archive invalid rows first if parsing or duplicate-id checks fail.",
            "- Command-safe and resume-state-ready are not metric claims; output audit, scoring, SLO, promotion, and traceability gates must still pass.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    audit = build_audit(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(audit, args.output_md)
    write_csv(audit, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
