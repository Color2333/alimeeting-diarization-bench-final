#!/usr/bin/env python3
"""Audit pending live-call command surfaces without making live calls."""

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
import shlex
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_command_surface_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_command_surface_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_command_surface_audit.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def csv_escape(value: object) -> str:
    text = str(value)
    if any(ch in text for ch in [",", "\n", '"']):
        return '"' + text.replace('"', '""') + '"'
    return text


def args_after(tokens: list[str], flag: str) -> list[str]:
    values: list[str] = []
    for idx, token in enumerate(tokens[:-1]):
        if token == flag:
            values.append(tokens[idx + 1])
    return values


def arg_after(tokens: list[str], flag: str) -> str:
    values = args_after(tokens, flag)
    return values[-1] if values else ""


def has_secret_literal(command: str) -> bool:
    lowered = command.lower()
    secret_markers = ["api_key=", "dashscope_api_key=", "bailian_api_key=", "aliyun_bailian_api_key="]
    return any(marker in lowered for marker in secret_markers)


def command_kind(tokens: list[str]) -> str:
    joined = " ".join(tokens)
    if "scripts/llm/llm_window_batch_policy_eval.py" in joined:
        return "llm_window_batch_policy_eval"
    if "scripts/llm/omni_guard_window_batch.py" in joined:
        return "omni_guard_window_batch"
    return "unknown"


def command_inputs(kind: str, tokens: list[str]) -> list[str]:
    if kind == "llm_window_batch_policy_eval":
        flags = ["--decisions", "--window-evidence", "--patch-id-file", "--window-id-file"]
    elif kind == "omni_guard_window_batch":
        flags = ["--input-windows-csv"]
    else:
        flags = []
    inputs: list[str] = []
    for flag in flags:
        value = arg_after(tokens, flag)
        if value:
            inputs.append(value)
    return inputs


def required_flags(kind: str) -> list[str]:
    if kind == "llm_window_batch_policy_eval":
        return ["--mode", "--decisions", "--trigger-policy", "--window-evidence", "--patch-id-file", "--model", "--output-jsonl"]
    if kind == "omni_guard_window_batch":
        return ["--input-windows-csv", "--model", "--output-jsonl"]
    return []


def command_row(root: Path, runbook_step: dict[str, Any], output_paths_seen: dict[str, str]) -> dict[str, Any]:
    command = str(runbook_step.get("command", ""))
    try:
        tokens = shlex.split(command)
        parse_error = ""
    except ValueError as exc:
        tokens = []
        parse_error = str(exc)
    kind = command_kind(tokens)
    required = required_flags(kind)
    missing_flags = [flag for flag in required if flag not in tokens]
    input_paths = command_inputs(kind, tokens)
    missing_inputs = [path for path in input_paths if not (root / path).exists()]
    output_jsonl = arg_after(tokens, "--output-jsonl")
    output_parent_exists = bool(output_jsonl) and (root / output_jsonl).parent.exists()
    output_duplicate_with = output_paths_seen.get(output_jsonl, "") if output_jsonl else ""
    if output_jsonl and output_jsonl not in output_paths_seen:
        output_paths_seen[output_jsonl] = str(runbook_step.get("step_id", ""))
    planned_calls = int(runbook_step.get("planned_live_calls") or 0)
    models = args_after(tokens, "--model")
    max_patches = arg_after(tokens, "--max-patches-per-call")
    parallel_workers = arg_after(tokens, "--parallel-workers")
    max_call_attempts = arg_after(tokens, "--max-call-attempts")
    retry_backoff_seconds = arg_after(tokens, "--retry-backoff-seconds")
    command_ready = (
        not parse_error
        and kind != "unknown"
        and not missing_flags
        and not missing_inputs
        and output_parent_exists
        and not output_duplicate_with
        and not has_secret_literal(command)
        and planned_calls > 0
    )
    return {
        "command_id": str(runbook_step.get("step_id", "")),
        "priority": str(runbook_step.get("priority", "")),
        "phase": str(runbook_step.get("phase", "")),
        "kind": kind,
        "status": "command_surface_ready" if command_ready else "command_surface_needs_fix",
        "command_ready": command_ready,
        "planned_live_calls": planned_calls,
        "writeback_right": str(runbook_step.get("writeback_right", "")),
        "model_count": len(models),
        "models": models,
        "parallel_workers": parallel_workers,
        "max_patches_per_call": max_patches,
        "skip_existing_output": "--skip-existing-output" in tokens,
        "max_call_attempts": max_call_attempts,
        "retry_backoff_seconds": retry_backoff_seconds,
        "input_files": input_paths,
        "input_file_count": len(input_paths),
        "missing_input_files": missing_inputs,
        "output_jsonl": output_jsonl,
        "output_parent_exists": output_parent_exists,
        "output_duplicate_with": output_duplicate_with,
        "missing_required_flags": missing_flags,
        "parse_error": parse_error,
        "secret_literal_present": has_secret_literal(command),
        "command": command,
    }


def build_audit(root: Path) -> dict[str, Any]:
    runbook = read_json(root / "outputs/research_progress_snapshot/live_execution_runbook.json")
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    input_integrity = read_json(root / "outputs/research_progress_snapshot/live_input_integrity_audit.json")
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    runbook_steps = [
        row
        for row in runbook.get("steps", [])
        if str(row.get("phase")) in {"live_call", "fallback_live_call"} and int(row.get("planned_live_calls") or 0) > 0
    ]
    output_paths_seen: dict[str, str] = {}
    rows = [command_row(root, step, output_paths_seen) for step in runbook_steps]
    command_ready = [row for row in rows if row["command_ready"]]
    p0_ready = [row for row in rows if row["priority"] == "P0" and row["command_ready"]]
    p0_calls = sum(int(row["planned_live_calls"]) for row in rows if row["priority"] == "P0")
    blockers = []
    if len(command_ready) != len(rows):
        blockers.append("command_surface_needs_fix")
    if readiness.get("summary", {}).get("ready_count", 0) == 0:
        blockers.append("credentials_or_provider_quota_not_ready")
    summary = {
        "command_count": len(rows),
        "command_ready_count": len(command_ready),
        "p0_command_ready_count": len(p0_ready),
        "missing_input_commands": sum(1 for row in rows if row["missing_input_files"]),
        "duplicate_output_paths": sum(1 for row in rows if row["output_duplicate_with"]),
        "secret_literal_commands": sum(1 for row in rows if row["secret_literal_present"]),
        "missing_required_flag_commands": sum(1 for row in rows if row["missing_required_flags"]),
        "skip_existing_output_commands": sum(1 for row in rows if row["skip_existing_output"]),
        "bounded_retry_commands": sum(1 for row in rows if str(row["max_call_attempts"]) == "2"),
        "planned_live_calls": sum(int(row["planned_live_calls"]) for row in rows),
        "p0_planned_live_calls": p0_calls,
        "deepseek_resume_calls": next((int(row["planned_live_calls"]) for row in rows if row["command_id"] == "deepseek_resume_primary"), 0),
        "qwen_backup_calls": next((int(row["planned_live_calls"]) for row in rows if row["command_id"] == "qwen_full_backup_optional"), 0),
        "omni48_calls": next((int(row["planned_live_calls"]) for row in rows if row["command_id"] == "omni48_label_only_live"), 0),
        "readiness_ready_runs": int(readiness.get("summary", {}).get("ready_count", 0)),
        "input_ready_surfaces": int(input_integrity.get("summary", {}).get("input_ready_surfaces", 0)),
        "missing_output_surfaces": int(output_audit.get("summary", {}).get("missing_output_surfaces", 0)),
        "live_calls_performed_by_builder": 0,
        "no_secret_values_written": True,
        "no_new_metric_claim": True,
    }
    return {
        "runtime_contract": "live_command_surface_audit_no_live_calls",
        "secret_policy": "commands_scanned_no_secret_values_written",
        "status": "commands_ready_waiting_credentials_or_quota" if not [b for b in blockers if b == "command_surface_needs_fix"] else "needs_command_surface_fix",
        "source_contracts": {
            "live_execution_runbook": runbook.get("runtime_contract", ""),
            "live_run_readiness": readiness.get("runtime_contract", ""),
            "live_input_integrity_audit": input_integrity.get("runtime_contract", ""),
            "live_output_audit": output_audit.get("runtime_contract", ""),
        },
        "blockers": blockers,
        "summary": summary,
        "rows": rows,
    }


def write_csv(audit: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "command_id",
        "priority",
        "phase",
        "kind",
        "status",
        "command_ready",
        "planned_live_calls",
        "writeback_right",
        "model_count",
        "models",
        "parallel_workers",
        "max_patches_per_call",
        "skip_existing_output",
        "max_call_attempts",
        "retry_backoff_seconds",
        "input_file_count",
        "missing_input_files",
        "output_jsonl",
        "output_parent_exists",
        "output_duplicate_with",
        "missing_required_flags",
        "secret_literal_present",
        "command",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(fieldnames)]
    for row in audit["rows"]:
        out = dict(row)
        out["models"] = ";".join(out["models"])
        out["missing_input_files"] = ";".join(out["missing_input_files"])
        out["missing_required_flags"] = ";".join(out["missing_required_flags"])
        lines.append(",".join(csv_escape(out.get(key, "")) for key in fieldnames))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    lines = [
        "# Live Command Surface Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Secret policy: `{audit['secret_policy']}`",
        f"- Status: `{audit['status']}`",
        f"- Command-ready: `{summary['command_ready_count']}` / `{summary['command_count']}`",
        f"- P0 command-ready: `{summary['p0_command_ready_count']}`",
        f"- Planned live calls: `{summary['planned_live_calls']}`",
        f"- P0 planned live calls: `{summary['p0_planned_live_calls']}`",
        f"- Missing-input commands: `{summary['missing_input_commands']}`",
        f"- Duplicate output paths: `{summary['duplicate_output_paths']}`",
        f"- Skip-existing commands: `{summary['skip_existing_output_commands']}`",
        f"- Bounded-retry commands: `{summary['bounded_retry_commands']}`",
        f"- Secret literal commands: `{summary['secret_literal_commands']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Command | Priority | Kind | Calls | Ready | Inputs missing | Output | Writeback |",
        "|---|---|---|---:|---|---|---|---|",
    ]
    for row in audit["rows"]:
        missing = "<br>".join(row["missing_input_files"]) if row["missing_input_files"] else "none"
        lines.append(
            f"| `{row['command_id']}` | `{row['priority']}` | `{row['kind']}` | {row['planned_live_calls']} | "
            f"`{row['command_ready']}` | {missing} | `{row['output_jsonl']}` | `{row['writeback_right']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This audit parses pending live-call commands and checks local command/input/output surfaces only.",
            "- It performs no live/API/model calls and writes no secret values.",
            "- A ready command surface is not a live metric claim; credentials, quota, live outputs, output audit, scoring, and validation must still pass before promotion.",
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
