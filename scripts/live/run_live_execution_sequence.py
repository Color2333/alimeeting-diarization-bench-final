#!/usr/bin/env python3
"""Dry-run or explicitly execute the pending live LLM/Omni command sequence."""

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
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_execution_launcher.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_execution_launcher.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_execution_launcher.csv")
EXECUTE_RECORD_JSON = Path("outputs/research_progress_snapshot/live_execution_launcher_execute_latest.json")
EXECUTE_RECORD_MD = Path("outputs/research_progress_snapshot/live_execution_launcher_execute_latest.md")
EXECUTE_RECORD_CSV = Path("outputs/research_progress_snapshot/live_execution_launcher_execute_latest.csv")
CREDENTIAL_ENV_VARS = ["DASHSCOPE_API_KEY", "BAILIAN_API_KEY", "ALIYUN_BAILIAN_API_KEY"]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def csv_escape(value: object) -> str:
    text = str(value)
    if any(ch in text for ch in [",", "\n", '"']):
        return '"' + text.replace('"', '""') + '"'
    return text


def env_credential_present() -> bool:
    return any(bool(os.environ.get(name)) for name in CREDENTIAL_ENV_VARS)


def latest_execute_record_summary() -> dict[str, Any]:
    record = read_json(ROOT / EXECUTE_RECORD_JSON)
    if not record:
        return {
            "execute_record_exists": False,
            "execute_record_path": str(EXECUTE_RECORD_JSON),
            "latest_execute_status": "",
            "latest_execute_runtime_contract": "",
            "latest_execute_live_scope": "",
            "latest_execute_started_live_command_calls": 0,
            "latest_execute_passed_live_command_calls": 0,
            "latest_execute_failed_live_command_calls": 0,
            "latest_execute_live_calls_performed_by_launcher": 0,
            "latest_execute_failed_live_command_rows": 0,
            "latest_execute_postrun_refresh_executed": False,
        }
    summary = record.get("summary", {})
    return {
        "execute_record_exists": True,
        "execute_record_path": str(EXECUTE_RECORD_JSON),
        "latest_execute_status": str(record.get("status", "")),
        "latest_execute_runtime_contract": str(record.get("runtime_contract", "")),
        "latest_execute_live_scope": str(summary.get("live_scope", "")),
        "latest_execute_started_live_command_calls": int(summary.get("started_live_command_calls", 0)),
        "latest_execute_passed_live_command_calls": int(summary.get("passed_live_command_calls", 0)),
        "latest_execute_failed_live_command_calls": int(summary.get("failed_live_command_calls", 0)),
        "latest_execute_live_calls_performed_by_launcher": int(summary.get("live_calls_performed_by_launcher", 0)),
        "latest_execute_failed_live_command_rows": int(summary.get("failed_live_command_rows", 0)),
        "latest_execute_postrun_refresh_executed": bool(summary.get("postrun_refresh_executed", False)),
    }


def selected_command_rows(rows: list[dict[str, Any]], live_scope: str) -> list[dict[str, Any]]:
    if live_scope == "p0":
        return [row for row in rows if row.get("priority") == "P0"]
    if live_scope == "deepseek":
        return [row for row in rows if row.get("command_id") == "deepseek_resume_primary"]
    if live_scope == "omni":
        return [row for row in rows if row.get("command_id") == "omni48_label_only_live"]
    if live_scope == "qwen":
        return [row for row in rows if row.get("command_id") == "qwen_full_backup_optional"]
    return list(rows)


def route_allowed_scopes(provider_route: dict[str, Any]) -> set[str]:
    allowed: set[str] = set()
    for row in provider_route.get("rows", []):
        command = str(row.get("execute_command", ""))
        if command and row.get("selected_for_default_execute") is False:
            scope = str(row.get("planned_scope", ""))
            if scope:
                allowed.add(scope)
    if provider_route.get("summary", {}).get("recommended_default_execute_scope") not in {"", "none", None}:
        allowed.add(str(provider_route["summary"]["recommended_default_execute_scope"]))
    return allowed


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


def launcher_row(
    *,
    step_id: str,
    priority: str,
    phase: str,
    command: str,
    planned_live_calls: int,
    execute_live: bool,
    selected: bool,
    status: str,
    source_command_id: str = "",
    writeback_right: str = "",
) -> dict[str, Any]:
    row = {
        "launcher_step_id": step_id,
        "source_command_id": source_command_id,
        "priority": priority,
        "phase": phase,
        "selected": selected,
        "status": status,
        "planned_live_calls": planned_live_calls,
        "writeback_right": writeback_right,
        "command": command,
        "returncode": "",
        "elapsed_seconds": 0.0,
        "stdout_tail": "",
        "stderr_tail": "",
    }
    if execute_live and selected and planned_live_calls > 0:
        result = run_shell_command(command)
        row.update(result)
        row["status"] = "executed_live_pass" if result["returncode"] == 0 else "executed_live_fail"
    elif execute_live and selected and planned_live_calls == 0:
        result = run_shell_command(command)
        row.update(result)
        row["status"] = "executed_postrun_pass" if result["returncode"] == 0 else "executed_postrun_fail"
    return row


def build_launcher(args: argparse.Namespace) -> dict[str, Any]:
    command_audit = read_json(ROOT / "outputs/research_progress_snapshot/live_command_surface_audit.json")
    readiness = read_json(ROOT / "outputs/research_progress_snapshot/live_run_readiness.json")
    bundle = read_json(ROOT / "outputs/research_progress_snapshot/live_execution_bundle.json")
    traceability = read_json(ROOT / "outputs/research_progress_snapshot/report_ppt_traceability.json")
    provider_route = read_json(ROOT / "outputs/research_progress_snapshot/live_provider_routing_decision.json")

    command_rows = [
        row
        for row in command_audit.get("rows", [])
        if row.get("command_ready") is True and int(row.get("planned_live_calls") or 0) > 0
    ]
    route_summary = provider_route.get("summary", {})
    recommended_default_scope = str(route_summary.get("recommended_default_execute_scope", "p0"))
    allowed_scopes = route_allowed_scopes(provider_route)
    route_blocks_default = (
        provider_route.get("runtime_contract") == "live_provider_routing_decision_no_live_calls_no_secret_values"
        and recommended_default_scope == "none"
        and args.live_scope in {"p0", "deepseek", "all"}
    )
    selected_live_rows = [] if route_blocks_default else selected_command_rows(command_rows, args.live_scope)
    credential_ready = env_credential_present()
    artifact_credential_ready = bool(readiness.get("environment", {}).get("dashscope_like_api_key_present"))
    execution_allowed = bool(args.execute_live and credential_ready)
    execution_blockers: list[str] = []
    if not args.execute_live:
        execution_blockers.append("dry_run_only_requires_execute_live_flag")
    if args.execute_live and not credential_ready:
        execution_blockers.append("missing_dashscope_or_bailian_api_key_env")
    if not command_rows:
        execution_blockers.append("no_ready_live_commands")
    if route_blocks_default:
        execution_blockers.append("provider_route_blocks_default_primary_execute")
    if args.live_scope not in {"p0", "deepseek", "all"} and args.live_scope not in allowed_scopes:
        execution_blockers.append("provider_route_does_not_allow_selected_scope")

    rows = [
        launcher_row(
            step_id="credential_preflight_refresh",
            priority="P0",
            phase="preflight",
            command="python scripts/live/build_live_run_readiness.py",
            planned_live_calls=0,
            execute_live=args.execute_live and args.refresh_preflight,
            selected=args.refresh_preflight,
            status="dry_run_preflight_not_executed" if not args.execute_live else "ready_to_execute_preflight",
            writeback_right="none",
        )
    ]
    for row in command_rows:
        selected = row in selected_live_rows
        rows.append(
            launcher_row(
                step_id=f"live_{row['command_id']}",
                source_command_id=str(row["command_id"]),
                priority=str(row["priority"]),
                phase=str(row["phase"]),
                command=str(row["command"]),
                planned_live_calls=int(row["planned_live_calls"]),
                execute_live=execution_allowed,
                selected=selected,
                status=(
                    "dry_run_selected_not_executed"
                    if selected and not args.execute_live
                    else "blocked_by_provider_route"
                    if row in selected_command_rows(command_rows, args.live_scope) and route_blocks_default
                    else "blocked_missing_credentials"
                    if selected and args.execute_live and not credential_ready
                    else "dry_run_unselected"
                ),
                writeback_right=str(row.get("writeback_right", "")),
            )
        )
    live_command_rows = [row for row in rows if int(row.get("planned_live_calls") or 0) > 0]
    failed_live_rows = [row for row in live_command_rows if row.get("status") == "executed_live_fail"]
    if failed_live_rows:
        execution_blockers.append("postrun_refresh_blocked_by_failed_live_commands")
    postrun_selected = not args.skip_postrun_refresh
    postrun_execute_live = bool(execution_allowed and postrun_selected and not failed_live_rows)
    if not args.execute_live:
        postrun_status = "dry_run_postrun_not_executed"
    elif not credential_ready:
        postrun_status = "blocked_missing_credentials"
    elif args.skip_postrun_refresh:
        postrun_status = "skipped_by_operator"
    elif failed_live_rows:
        postrun_status = "blocked_by_failed_live_commands"
    else:
        postrun_status = "waiting_for_live_commands"
    rows.append(
        launcher_row(
            step_id="postrun_refresh_validation",
            priority="P0",
            phase="refresh_and_validate",
            command="python scripts/misc/refresh_latest_research_artifacts.py",
            planned_live_calls=0,
            execute_live=postrun_execute_live,
            selected=postrun_selected,
            status=postrun_status,
            writeback_right="none",
        )
    )

    failed_rows = [row for row in rows if str(row.get("status", "")).endswith("_fail")]
    executed_live_rows = [row for row in live_command_rows if str(row.get("status", "")).startswith("executed_live_")]
    passed_live_rows = [row for row in live_command_rows if row.get("status") == "executed_live_pass"]
    postrun_refresh_executed = any(
        str(row.get("status", "")).startswith("executed_postrun_")
        for row in rows
        if row.get("launcher_step_id") == "postrun_refresh_validation"
    )
    available_live_calls = sum(int(row.get("planned_live_calls") or 0) for row in command_rows)
    selected_live_calls = sum(int(row.get("planned_live_calls") or 0) for row in selected_live_rows)
    p0_selected_live_calls = sum(
        int(row.get("planned_live_calls") or 0)
        for row in selected_live_rows
        if row.get("priority") == "P0"
    )
    p1_selected_live_calls = selected_live_calls - p0_selected_live_calls
    trace_summary = traceability.get("summary", {})
    summary = {
        "launcher_steps": len(rows),
        "available_live_command_rows": len(command_rows),
        "selected_live_command_rows": len(selected_live_rows),
        "available_live_calls": available_live_calls,
        "selected_live_calls": selected_live_calls,
        "p0_selected_live_calls": p0_selected_live_calls,
        "p1_selected_live_calls": p1_selected_live_calls,
        "live_scope": args.live_scope,
        "provider_route_status": provider_route.get("status", ""),
        "provider_route_default_scope": recommended_default_scope,
        "provider_route_allowed_scopes": sorted(allowed_scopes),
        "provider_route_blocks_default": route_blocks_default,
        "execute_live": bool(args.execute_live),
        "credential_ready": credential_ready,
        "artifact_credential_ready": artifact_credential_ready,
        "known_provider_quota_blockers": int(bundle.get("summary", {}).get("known_provider_quota_blockers", 0)),
        "execution_allowed": execution_allowed,
        "execution_blocker_count": len(execution_blockers),
        "failed_execution_rows": len(failed_rows),
        "executed_live_command_rows": len(executed_live_rows),
        "failed_live_command_rows": len(failed_live_rows),
        "started_live_command_calls": sum(int(row.get("planned_live_calls") or 0) for row in executed_live_rows),
        "passed_live_command_calls": sum(int(row.get("planned_live_calls") or 0) for row in passed_live_rows),
        "failed_live_command_calls": sum(int(row.get("planned_live_calls") or 0) for row in failed_live_rows),
        "postrun_refresh_executed": postrun_refresh_executed,
        "postrun_refresh_blocked_by_live_failures": bool(failed_live_rows),
        "traceability_rows": int(trace_summary.get("traceability_rows", 0)),
        "live_calls_performed_by_launcher": sum(int(row.get("planned_live_calls") or 0) for row in passed_live_rows),
        "dry_run_no_live_calls": not args.execute_live,
        "no_secret_values_written": True,
        "no_new_metric_claim": True,
    }
    runtime_contract = (
        "live_execution_launcher_execute_live_explicit"
        if args.execute_live
        else "live_execution_launcher_dry_run_no_live_calls"
    )
    status = (
        "execute_live_failed"
        if failed_rows
        else "execute_live_complete"
        if execution_allowed and args.execute_live
        else "dry_run_blocked_waiting_credentials_or_execute_flag"
    )
    if args.execute_live:
        summary.update(
            {
                "execute_record_exists": True,
                "execute_record_path": str(EXECUTE_RECORD_JSON),
                "latest_execute_status": status,
                "latest_execute_runtime_contract": runtime_contract,
                "latest_execute_live_scope": args.live_scope,
                "latest_execute_started_live_command_calls": summary["started_live_command_calls"],
                "latest_execute_passed_live_command_calls": summary["passed_live_command_calls"],
                "latest_execute_failed_live_command_calls": summary["failed_live_command_calls"],
                "latest_execute_live_calls_performed_by_launcher": summary["live_calls_performed_by_launcher"],
                "latest_execute_failed_live_command_rows": summary["failed_live_command_rows"],
                "latest_execute_postrun_refresh_executed": summary["postrun_refresh_executed"],
            }
        )
    else:
        summary.update(latest_execute_record_summary())
    return {
        "runtime_contract": runtime_contract,
        "secret_policy": "env_presence_only_no_secret_values_written",
        "status": status,
        "source_contracts": {
            "live_command_surface_audit": command_audit.get("runtime_contract", ""),
            "live_run_readiness": readiness.get("runtime_contract", ""),
            "live_execution_bundle": bundle.get("runtime_contract", ""),
            "live_provider_routing_decision": provider_route.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "execution_blockers": execution_blockers,
        "summary": summary,
        "rows": rows,
    }


def write_csv(launcher: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "launcher_step_id",
        "source_command_id",
        "priority",
        "phase",
        "selected",
        "status",
        "planned_live_calls",
        "writeback_right",
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
        "# Live Execution Launcher",
        "",
        f"- Runtime contract: `{launcher['runtime_contract']}`",
        f"- Secret policy: `{launcher['secret_policy']}`",
        f"- Status: `{launcher['status']}`",
        f"- Live scope: `{summary['live_scope']}`",
        f"- Available live commands: `{summary['available_live_command_rows']}`",
        f"- Selected live commands: `{summary['selected_live_command_rows']}`",
        f"- Available live calls: `{summary['available_live_calls']}`",
        f"- Launcher selected calls: `{summary['selected_live_calls']}`",
        f"- P0 selected calls: `{summary['p0_selected_live_calls']}`",
        f"- P1 selected calls: `{summary['p1_selected_live_calls']}`",
        f"- Provider route status: `{summary['provider_route_status']}`",
        f"- Provider route default scope: `{summary['provider_route_default_scope']}`",
        f"- Provider route blocks default: `{summary['provider_route_blocks_default']}`",
        f"- Credential ready: `{summary['credential_ready']}`",
        f"- Execute live: `{summary['execute_live']}`",
        f"- Execution blockers: `{summary['execution_blocker_count']}`",
        f"- Executed live command rows: `{summary['executed_live_command_rows']}`",
        f"- Failed live command rows: `{summary['failed_live_command_rows']}`",
        f"- Started live command calls: `{summary['started_live_command_calls']}`",
        f"- Passed live command calls: `{summary['passed_live_command_calls']}`",
        f"- Failed live command calls: `{summary['failed_live_command_calls']}`",
        f"- Postrun refresh executed: `{summary['postrun_refresh_executed']}`",
        f"- Postrun refresh blocked by live failures: `{summary['postrun_refresh_blocked_by_live_failures']}`",
        f"- Live calls performed by launcher: `{summary['live_calls_performed_by_launcher']}`",
        f"- Execute record exists: `{summary['execute_record_exists']}`",
        f"- Execute record path: `{summary['execute_record_path']}`",
        f"- Latest execute status: `{summary['latest_execute_status']}`",
        f"- Latest execute started calls: `{summary['latest_execute_started_live_command_calls']}`",
        f"- Latest execute passed calls: `{summary['latest_execute_passed_live_command_calls']}`",
        f"- Latest execute failed calls: `{summary['latest_execute_failed_live_command_calls']}`",
        f"- Latest execute postrun refresh executed: `{summary['latest_execute_postrun_refresh_executed']}`",
        f"- No secret values written: `{summary['no_secret_values_written']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Step | Priority | Phase | Selected | Status | Calls | Command |",
        "|---|---|---|---:|---|---:|---|",
    ]
    for row in launcher["rows"]:
        command = str(row["command"]).replace("|", "/")
        lines.append(
            f"| `{row['launcher_step_id']}` | `{row['priority']}` | `{row['phase']}` | "
            f"`{row['selected']}` | `{row['status']}` | {row['planned_live_calls']} | `{command}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Default mode is dry-run and performs no live/API/model calls.",
            "- Live execution requires `--execute-live` plus a DashScope/Bailian credential in the runner environment.",
            "- Provider routing can block the old default P0/DeepSeek selection; explicit Qwen/Omni fallback scopes remain separate from primary latency claims.",
            "- The launcher reuses the command surface audit rows, so command readiness, skip-existing output, retry limits, input paths, and secret-literal checks stay aligned with the runbook.",
            "- Use an explicit scope only after the provider route decision and claim boundary are understood.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-live", action="store_true", help="Actually run selected live commands.")
    parser.add_argument(
        "--live-scope",
        choices=["p0", "deepseek", "omni", "qwen", "all"],
        default="p0",
        help="Which live command rows to select.",
    )
    parser.add_argument("--refresh-preflight", action="store_true", help="Execute preflight refresh in execute-live mode.")
    parser.add_argument("--skip-postrun-refresh", action="store_true", help="Skip final refresh in execute-live mode.")
    parser.add_argument("--summary-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--summary-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--summary-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    launcher = build_launcher(args)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(launcher, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(launcher, args.summary_md)
    write_csv(launcher, args.summary_csv)
    if args.execute_live:
        (ROOT / EXECUTE_RECORD_JSON).parent.mkdir(parents=True, exist_ok=True)
        (ROOT / EXECUTE_RECORD_JSON).write_text(json.dumps(launcher, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        write_markdown(launcher, ROOT / EXECUTE_RECORD_MD)
        write_csv(launcher, ROOT / EXECUTE_RECORD_CSV)
    print(f"Wrote {args.summary_json}")
    print(f"Wrote {args.summary_md}")
    print(f"Wrote {args.summary_csv}")
    if args.execute_live:
        print(f"Wrote {EXECUTE_RECORD_JSON}")
        print(f"Wrote {EXECUTE_RECORD_MD}")
        print(f"Wrote {EXECUTE_RECORD_CSV}")
    print(json.dumps({"status": launcher["status"], "execution_blockers": launcher["execution_blockers"]}, ensure_ascii=False))
    if launcher["status"] == "execute_live_failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
