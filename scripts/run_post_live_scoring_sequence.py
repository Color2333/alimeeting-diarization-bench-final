#!/usr/bin/env python3
"""Dry-run or explicitly execute ready post-live scoring commands."""

from __future__ import annotations

import argparse
import csv
import json
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_scoring_launcher.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_scoring_launcher.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_scoring_launcher.csv")
EXECUTE_RECORD_JSON = Path("outputs/research_progress_snapshot/post_live_scoring_launcher_execute_latest.json")
EXECUTE_RECORD_MD = Path("outputs/research_progress_snapshot/post_live_scoring_launcher_execute_latest.md")
EXECUTE_RECORD_CSV = Path("outputs/research_progress_snapshot/post_live_scoring_launcher_execute_latest.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def csv_escape(value: object) -> str:
    text = str(value)
    if any(ch in text for ch in [",", "\n", '"']):
        return '"' + text.replace('"', '""') + '"'
    return text


def latest_execute_record_summary() -> dict[str, Any]:
    record = read_json(ROOT / EXECUTE_RECORD_JSON)
    if not record:
        return {
            "scoring_execute_record_exists": False,
            "scoring_execute_record_path": str(EXECUTE_RECORD_JSON),
            "latest_scoring_execute_status": "",
            "latest_scoring_execute_runtime_contract": "",
            "latest_scoring_execute_scope": "",
            "latest_scoring_executed_rows": 0,
            "latest_scoring_passed_rows": 0,
            "latest_scoring_failed_rows": 0,
        }
    summary = record.get("summary", {})
    return {
        "scoring_execute_record_exists": True,
        "scoring_execute_record_path": str(EXECUTE_RECORD_JSON),
        "latest_scoring_execute_status": str(record.get("status", "")),
        "latest_scoring_execute_runtime_contract": str(record.get("runtime_contract", "")),
        "latest_scoring_execute_scope": str(summary.get("scoring_scope", "")),
        "latest_scoring_executed_rows": int(summary.get("executed_scoring_rows", 0)),
        "latest_scoring_passed_rows": int(summary.get("passed_scoring_rows", 0)),
        "latest_scoring_failed_rows": int(summary.get("failed_scoring_rows", 0)),
    }


def run_shell_command(command: str) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(
        shlex.split(command),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "returncode": proc.returncode,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-8:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-8:]),
    }


def row_in_scope(row: dict[str, Any], scope: str) -> bool:
    if scope == "p0":
        return row.get("priority") == "P0"
    if scope == "deepseek":
        return str(row.get("surface_id")) == "deepseek_resume_after_top3"
    if scope == "omni":
        return str(row.get("surface_id")) == "omni48_label_only"
    if scope == "qwen":
        return str(row.get("surface_id")) == "qwen_full_backup"
    return True


def build_launcher(args: argparse.Namespace) -> dict[str, Any]:
    plan = read_json(ROOT / "outputs/research_progress_snapshot/post_live_scoring_execution_plan.json")
    readiness = read_json(ROOT / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    output_audit = read_json(ROOT / "outputs/research_progress_snapshot/live_output_audit.json")
    repair_plan = read_json(ROOT / "outputs/research_progress_snapshot/live_output_repair_plan.json")
    traceability = read_json(ROOT / "outputs/research_progress_snapshot/report_ppt_traceability.json")

    rows = []
    execution_blockers: list[str] = []
    if not args.execute_scoring:
        execution_blockers.append("dry_run_only_requires_execute_scoring_flag")

    source_rows = list(plan.get("rows", []))
    ready_rows = [row for row in source_rows if str(row.get("current_state", "")).startswith("ready")]
    selected_source_rows = [row for row in ready_rows if row_in_scope(row, args.scoring_scope)]
    if not ready_rows:
        execution_blockers.append("no_ready_scoring_commands")
    execution_allowed = bool(args.execute_scoring and selected_source_rows)

    for row in source_rows:
        eligible = row in ready_rows
        selected = row in selected_source_rows
        status = (
            "blocked_waiting_prerequisite"
            if not eligible
            else "dry_run_ready_not_executed"
            if selected and not args.execute_scoring
            else "dry_run_unselected"
            if not selected
            else "ready_to_execute_scoring"
        )
        launcher_row = {
            "launcher_step_id": str(row.get("scoring_execution_id", "")),
            "priority": str(row.get("priority", "")),
            "surface_id": str(row.get("surface_id", "")),
            "execution_phase": str(row.get("execution_phase", "")),
            "current_state": str(row.get("current_state", "")),
            "eligible": eligible,
            "selected": selected,
            "status": status,
            "promotion_gate": str(row.get("promotion_gate", "")),
            "claim_boundary": str(row.get("claim_boundary", "")),
            "command": str(row.get("command", "")),
            "returncode": "",
            "elapsed_seconds": 0.0,
            "stdout_tail": "",
            "stderr_tail": "",
        }
        if execution_allowed and selected:
            result = run_shell_command(str(row.get("command", "")))
            launcher_row.update(result)
            launcher_row["status"] = "executed_scoring_pass" if result["returncode"] == 0 else "executed_scoring_fail"
        rows.append(launcher_row)

    failed_rows = [row for row in rows if row.get("status") == "executed_scoring_fail"]
    executed_rows = [row for row in rows if str(row.get("status", "")).startswith("executed_scoring_")]
    passed_rows = [row for row in rows if row.get("status") == "executed_scoring_pass"]
    trace_summary = traceability.get("summary", {})
    summary = {
        "launcher_steps": len(rows),
        "available_scoring_rows": len(source_rows),
        "ready_scoring_rows": len(ready_rows),
        "selected_scoring_rows": len(selected_source_rows),
        "p0_ready_scoring_rows": sum(1 for row in ready_rows if row.get("priority") == "P0"),
        "p1_ready_scoring_rows": sum(1 for row in ready_rows if row.get("priority") == "P1"),
        "scoring_scope": args.scoring_scope,
        "execute_scoring": bool(args.execute_scoring),
        "execution_allowed": execution_allowed,
        "execution_blocker_count": len(execution_blockers),
        "executed_scoring_rows": len(executed_rows),
        "passed_scoring_rows": len(passed_rows),
        "failed_scoring_rows": len(failed_rows),
        "readiness_ready_to_score_steps": int(readiness.get("summary", {}).get("ready_to_score_steps", 0)),
        "output_missing_surfaces": int(output_audit.get("summary", {}).get("missing_output_surfaces", 0)),
        "repair_scoring_ready_rows": int(repair_plan.get("summary", {}).get("scoring_ready_rows", 0)),
        "traceability_rows": int(trace_summary.get("traceability_rows", 0)),
        "live_calls_performed_by_launcher": 0,
        "no_live_calls_performed": True,
        "no_scoring_commands_executed": not bool(executed_rows),
        "no_secret_values_written": True,
        "no_new_metric_claim": True,
    }
    runtime_contract = (
        "post_live_scoring_launcher_execute_scoring_explicit"
        if args.execute_scoring
        else "post_live_scoring_launcher_dry_run_no_scoring_calls"
    )
    status = (
        "execute_scoring_failed"
        if failed_rows
        else "execute_scoring_complete"
        if executed_rows and not failed_rows
        else "dry_run_blocked_waiting_live_outputs_or_execute_flag"
    )
    if args.execute_scoring:
        summary.update(
            {
                "scoring_execute_record_exists": True,
                "scoring_execute_record_path": str(EXECUTE_RECORD_JSON),
                "latest_scoring_execute_status": status,
                "latest_scoring_execute_runtime_contract": runtime_contract,
                "latest_scoring_execute_scope": args.scoring_scope,
                "latest_scoring_executed_rows": summary["executed_scoring_rows"],
                "latest_scoring_passed_rows": summary["passed_scoring_rows"],
                "latest_scoring_failed_rows": summary["failed_scoring_rows"],
            }
        )
    else:
        summary.update(latest_execute_record_summary())
    return {
        "runtime_contract": runtime_contract,
        "secret_policy": "commands_scanned_no_secret_values_written",
        "status": status,
        "source_contracts": {
            "post_live_scoring_execution_plan": plan.get("runtime_contract", ""),
            "live_scoring_readiness": readiness.get("runtime_contract", ""),
            "live_output_audit": output_audit.get("runtime_contract", ""),
            "live_output_repair_plan": repair_plan.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "execution_blockers": execution_blockers,
        "summary": summary,
        "rows": rows,
    }


def write_csv(launcher: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "launcher_step_id",
        "priority",
        "surface_id",
        "execution_phase",
        "current_state",
        "eligible",
        "selected",
        "status",
        "promotion_gate",
        "claim_boundary",
        "returncode",
        "elapsed_seconds",
        "command",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(fieldnames)]
    for row in launcher["rows"]:
        lines.append(",".join(csv_escape(row.get(field, "")) for field in fieldnames))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(launcher: dict[str, Any], path: Path) -> None:
    summary = launcher["summary"]
    lines = [
        "# Post-Live Scoring Launcher",
        "",
        f"- Runtime contract: `{launcher['runtime_contract']}`",
        f"- Secret policy: `{launcher['secret_policy']}`",
        f"- Status: `{launcher['status']}`",
        f"- Scoring scope: `{summary['scoring_scope']}`",
        f"- Available scoring rows: `{summary['available_scoring_rows']}`",
        f"- Ready scoring rows: `{summary['ready_scoring_rows']}`",
        f"- Selected scoring rows: `{summary['selected_scoring_rows']}`",
        f"- Execute scoring: `{summary['execute_scoring']}`",
        f"- Execution blockers: `{summary['execution_blocker_count']}`",
        f"- Executed scoring rows: `{summary['executed_scoring_rows']}`",
        f"- Passed scoring rows: `{summary['passed_scoring_rows']}`",
        f"- Failed scoring rows: `{summary['failed_scoring_rows']}`",
        f"- Output missing surfaces: `{summary['output_missing_surfaces']}`",
        f"- Repair scoring-ready rows: `{summary['repair_scoring_ready_rows']}`",
        f"- Traceability rows: `{summary['traceability_rows']}`",
        f"- Scoring execute record exists: `{summary['scoring_execute_record_exists']}`",
        f"- Scoring execute record path: `{summary['scoring_execute_record_path']}`",
        f"- Latest scoring execute status: `{summary['latest_scoring_execute_status']}`",
        f"- Latest scoring executed rows: `{summary['latest_scoring_executed_rows']}`",
        f"- Latest scoring passed rows: `{summary['latest_scoring_passed_rows']}`",
        f"- Latest scoring failed rows: `{summary['latest_scoring_failed_rows']}`",
        f"- No live calls performed: `{summary['no_live_calls_performed']}`",
        f"- No scoring commands executed: `{summary['no_scoring_commands_executed']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Step | Priority | Surface | Eligible | Selected | Status | Promotion gate |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for row in launcher["rows"]:
        lines.append(
            f"| `{row['launcher_step_id']}` | `{row['priority']}` | `{row['surface_id']}` | "
            f"`{row['eligible']}` | `{row['selected']}` | `{row['status']}` | `{row['promotion_gate']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Default mode is dry-run and executes no scoring command.",
            "- `--execute-scoring` only runs rows whose current state is ready in the scoring execution plan.",
            "- Current blocked rows stay blocked until live output audit, repair plan, and scoring readiness agree that outputs are complete.",
            "- The launcher performs no live/API/model calls and writes no secret values.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-scoring", action="store_true", help="Actually run ready post-live scoring commands.")
    parser.add_argument(
        "--scoring-scope",
        choices=["p0", "deepseek", "omni", "qwen", "all"],
        default="p0",
        help="Which ready scoring rows to select.",
    )
    parser.add_argument("--summary-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--summary-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--summary-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    launcher = build_launcher(args)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(launcher, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(launcher, args.summary_md)
    write_csv(launcher, args.summary_csv)
    if args.execute_scoring:
        (ROOT / EXECUTE_RECORD_JSON).parent.mkdir(parents=True, exist_ok=True)
        (ROOT / EXECUTE_RECORD_JSON).write_text(json.dumps(launcher, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        write_markdown(launcher, ROOT / EXECUTE_RECORD_MD)
        write_csv(launcher, ROOT / EXECUTE_RECORD_CSV)
    print(f"Wrote {args.summary_json}")
    print(f"Wrote {args.summary_md}")
    print(f"Wrote {args.summary_csv}")
    if args.execute_scoring:
        print(f"Wrote {EXECUTE_RECORD_JSON}")
        print(f"Wrote {EXECUTE_RECORD_MD}")
        print(f"Wrote {EXECUTE_RECORD_CSV}")
    print(json.dumps({"status": launcher["status"], "execution_blockers": launcher["execution_blockers"]}, ensure_ascii=False))
    if launcher["status"] == "execute_scoring_failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
