#!/usr/bin/env python3
"""Build a deterministic repair plan for live output surfaces without running calls."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_output_repair_plan.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_output_repair_plan.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_output_repair_plan.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def surface_command_id(surface_id: str) -> str:
    return {
        "deepseek_resume_after_top3": "deepseek_resume_primary",
        "omni48_label_only": "omni48_label_only_live",
        "qwen_full_backup": "qwen_full_backup_optional",
    }.get(surface_id, "")


def repair_action(surface: dict[str, Any], command: dict[str, Any], scoring_steps: list[dict[str, Any]]) -> tuple[str, str, str]:
    status = str(surface.get("status", ""))
    has_bad_structure = any(
        int(surface.get(field) or 0) > 0
        for field in ["parse_errors", "duplicate_call_ids", "extra_call_ids", "extra_parent_windows"]
    ) or bool(surface.get("summary_mismatches"))
    if status == "missing_output":
        return (
            "clean_run_waiting_credentials_or_quota",
            "run_live_command",
            str(command.get("command", "")),
        )
    if status == "partial_or_invalid_output" and has_bad_structure:
        return (
            "quarantine_then_skip_existing_rerun",
            "archive_bad_output_then_rerun",
            str(command.get("command", "")),
        )
    if status == "partial_or_invalid_output":
        return (
            "skip_existing_rerun_missing_or_failed_calls",
            "rerun_live_command_with_skip_existing",
            str(command.get("command", "")),
        )
    if str(surface.get("claim_gate", "")).startswith("ready"):
        scoring_commands = [str(row.get("scoring_command", "")) for row in scoring_steps if row.get("scoring_command")]
        return (
            "ready_for_scoring",
            "run_scoring_commands",
            " && ".join(scoring_commands),
        )
    return ("blocked_unknown_output_state", "inspect_surface", "")


def build_plan(root: Path) -> dict[str, Any]:
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    command_audit = read_json(root / "outputs/research_progress_snapshot/live_command_surface_audit.json")
    scoring = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    commands = {row.get("command_id"): row for row in command_audit.get("rows", [])}
    scoring_by_surface: dict[str, list[dict[str, Any]]] = {}
    for row in scoring.get("scoring_steps", []):
        scoring_by_surface.setdefault(str(row.get("surface_id", "")), []).append(row)

    rows = []
    for surface in output_audit.get("surfaces", []):
        surface_id = str(surface.get("surface_id", ""))
        command_id = surface_command_id(surface_id)
        command = commands.get(command_id, {})
        action, next_step, next_command = repair_action(surface, command, scoring_by_surface.get(surface_id, []))
        missing_calls = int(surface.get("missing_calls") or 0)
        failed_calls = int(surface.get("failed_calls") or 0)
        rows.append(
            {
                "surface_id": surface_id,
                "priority": str(command.get("priority", "")),
                "command_id": command_id,
                "output_status": str(surface.get("status", "")),
                "claim_gate": str(surface.get("claim_gate", "")),
                "repair_action": action,
                "next_step": next_step,
                "expected_calls": int(surface.get("expected_calls") or 0),
                "observed_calls": int(surface.get("observed_calls") or 0),
                "successful_calls": int(surface.get("successful_calls") or 0),
                "failed_calls": failed_calls,
                "missing_calls": missing_calls,
                "parse_errors": int(surface.get("parse_errors") or 0),
                "duplicate_call_ids": int(surface.get("duplicate_call_ids") or 0),
                "extra_call_ids": int(surface.get("extra_call_ids") or 0),
                "summary_mismatches": ";".join(surface.get("summary_mismatches", [])),
                "skip_existing_supported": bool(command.get("skip_existing_output")),
                "bounded_retry_supported": bool(command.get("max_call_attempts")),
                "max_call_attempts": str(command.get("max_call_attempts", "")),
                "retry_backoff_seconds": str(command.get("retry_backoff_seconds", "")),
                "writeback_right": str(command.get("writeback_right", "")),
                "output_jsonl": str(surface.get("output_jsonl", "")),
                "next_command": next_command,
                "live_calls_performed_by_builder": 0,
            }
        )

    clean_run_rows = [row for row in rows if row["repair_action"] == "clean_run_waiting_credentials_or_quota"]
    skip_existing_rows = [row for row in rows if row["repair_action"] == "skip_existing_rerun_missing_or_failed_calls"]
    quarantine_rows = [row for row in rows if row["repair_action"] == "quarantine_then_skip_existing_rerun"]
    scoring_ready_rows = [row for row in rows if row["repair_action"] == "ready_for_scoring"]
    return {
        "runtime_contract": "live_output_repair_plan_no_live_calls_no_scoring",
        "status": "waiting_live_outputs" if clean_run_rows else "repair_or_score_ready",
        "source_contracts": {
            "live_output_audit": output_audit.get("runtime_contract", ""),
            "live_command_surface_audit": command_audit.get("runtime_contract", ""),
            "live_scoring_readiness": scoring.get("runtime_contract", ""),
        },
        "summary": {
            "repair_rows": len(rows),
            "clean_run_rows": len(clean_run_rows),
            "skip_existing_rerun_rows": len(skip_existing_rows),
            "quarantine_required_rows": len(quarantine_rows),
            "scoring_ready_rows": len(scoring_ready_rows),
            "expected_calls": sum(int(row["expected_calls"]) for row in rows),
            "observed_calls": sum(int(row["observed_calls"]) for row in rows),
            "successful_calls": sum(int(row["successful_calls"]) for row in rows),
            "failed_calls": sum(int(row["failed_calls"]) for row in rows),
            "missing_calls": sum(int(row["missing_calls"]) for row in rows),
            "skip_existing_supported_rows": sum(1 for row in rows if row["skip_existing_supported"]),
            "bounded_retry_supported_rows": sum(1 for row in rows if row["bounded_retry_supported"]),
            "live_calls_performed_by_builder": 0,
            "no_scoring_commands_executed": True,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(plan: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "surface_id",
        "priority",
        "command_id",
        "output_status",
        "repair_action",
        "next_step",
        "expected_calls",
        "observed_calls",
        "successful_calls",
        "failed_calls",
        "missing_calls",
        "parse_errors",
        "duplicate_call_ids",
        "skip_existing_supported",
        "bounded_retry_supported",
        "writeback_right",
        "output_jsonl",
        "next_command",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in plan["rows"]:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_markdown(plan: dict[str, Any], path: Path) -> None:
    summary = plan["summary"]
    lines = [
        "# Live Output Repair Plan",
        "",
        f"- Runtime contract: `{plan['runtime_contract']}`",
        f"- Status: `{plan['status']}`",
        f"- Repair rows: `{summary['repair_rows']}`",
        f"- Clean-run rows: `{summary['clean_run_rows']}`",
        f"- Skip-existing rerun rows: `{summary['skip_existing_rerun_rows']}`",
        f"- Quarantine-required rows: `{summary['quarantine_required_rows']}`",
        f"- Scoring-ready rows: `{summary['scoring_ready_rows']}`",
        f"- Expected calls: `{summary['expected_calls']}`",
        f"- Missing calls: `{summary['missing_calls']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- Scoring commands executed: `{not summary['no_scoring_commands_executed']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Surface | Priority | Output status | Repair action | Expected | Observed | Missing | Next step |",
        "|---|---:|---|---|---:|---:|---:|---|",
    ]
    for row in plan["rows"]:
        lines.append(
            f"| `{row['surface_id']}` | `{row['priority']}` | `{row['output_status']}` | "
            f"`{row['repair_action']}` | {row['expected_calls']} | {row['observed_calls']} | "
            f"{row['missing_calls']} | `{row['next_step']}` |"
        )
    lines.extend(["", "## Reading", ""])
    lines.extend(
        [
            "- Missing outputs map to clean live runs using the audited command surface.",
            "- Partial outputs with parse, duplicate, extra-call, or summary mismatch signals map to quarantine-before-rerun.",
            "- Partial but structurally valid outputs map to skip-existing rerun for missing or failed calls.",
            "- Complete outputs map to scoring commands; this plan itself executes no live or scoring command.",
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
    args.output_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(plan, args.output_md)
    write_csv(plan, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
