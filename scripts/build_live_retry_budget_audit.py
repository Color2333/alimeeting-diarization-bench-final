#!/usr/bin/env python3
"""Build a no-live-call retry attempt and timing budget audit."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_retry_budget_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_retry_budget_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_retry_budget_audit.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def ceil_waves(calls: int, workers: int) -> int:
    if calls <= 0:
        return 0
    return int(math.ceil(calls / max(workers, 1)))


def row_for_command(command: dict[str, Any], timing_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    command_id = str(command.get("command_id", ""))
    timing_id_by_command = {
        "deepseek_resume_primary": "deepseek_max20_resume_live_call",
        "qwen_full_backup_optional": "qwen_full_backup_optional",
        "omni48_label_only_live": "omni48_label_only_live",
    }
    timing = timing_rows.get(timing_id_by_command.get(command_id, ""), {})
    planned_calls = as_int(command.get("planned_live_calls"))
    max_attempts = max(1, as_int(command.get("max_call_attempts"), 1))
    backoff_seconds = as_float(command.get("retry_backoff_seconds"))
    workers = as_int(timing.get("parallel_workers"))
    waves = as_int(timing.get("estimated_waves"), ceil_waves(planned_calls, workers))
    per_attempt_wall = as_float(timing.get("estimated_wall_seconds"))
    per_attempt_wave_seconds = round(per_attempt_wall / waves, 3) if waves and per_attempt_wall else 0.0
    retry_ceiling_wall = ""
    retry_wall_overhead = ""
    if waves and per_attempt_wave_seconds:
        retry_ceiling_wall = round(waves * (max_attempts * per_attempt_wave_seconds + (max_attempts - 1) * backoff_seconds), 3)
        retry_wall_overhead = round(as_float(retry_ceiling_wall) - per_attempt_wall, 3)

    return {
        "command_id": command_id,
        "priority": command.get("priority", ""),
        "planned_live_calls": planned_calls,
        "max_call_attempts": max_attempts,
        "retry_backoff_seconds": backoff_seconds,
        "max_attempted_requests": planned_calls * max_attempts,
        "additional_retry_attempt_budget": planned_calls * (max_attempts - 1),
        "backoff_ceiling_seconds": round(planned_calls * (max_attempts - 1) * backoff_seconds, 3),
        "parallel_workers": workers,
        "waves": waves,
        "per_attempt_wall_seconds": round(per_attempt_wall, 3) if per_attempt_wall else "",
        "retry_ceiling_wall_seconds": retry_ceiling_wall,
        "retry_wall_overhead_seconds": retry_wall_overhead,
        "claim_status": "retry_budget_planning_only_no_live_metric_claim",
    }


def build_audit(root: Path) -> dict[str, Any]:
    command_audit = read_json(root / "outputs/research_progress_snapshot/live_command_surface_audit.json")
    timing = read_json(root / "outputs/research_progress_snapshot/live_execution_timing_plan.json")
    resume = read_json(root / "outputs/research_progress_snapshot/live_resume_state_audit.json")
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")

    timing_rows = {row.get("timing_id"): row for row in timing.get("rows", [])}
    rows = [row_for_command(command, timing_rows) for command in command_audit.get("rows", [])]
    p0_rows = [row for row in rows if row["priority"] == "P0"]
    retry_rows = [row for row in rows if row["max_call_attempts"] > 1]
    deepseek = next((row for row in rows if row["command_id"] == "deepseek_resume_primary"), {})
    qwen = next((row for row in rows if row["command_id"] == "qwen_full_backup_optional"), {})
    omni = next((row for row in rows if row["command_id"] == "omni48_label_only_live"), {})

    return {
        "runtime_contract": "live_retry_budget_audit_no_live_calls",
        "status": "retry_budget_ready_waiting_credentials_or_quota",
        "source_contracts": {
            "live_command_surface_audit": command_audit.get("runtime_contract", ""),
            "live_execution_timing_plan": timing.get("runtime_contract", ""),
            "live_resume_state_audit": resume.get("runtime_contract", ""),
            "live_run_readiness": readiness.get("runtime_contract", ""),
        },
        "summary": {
            "surface_count": len(rows),
            "bounded_retry_surfaces": len(retry_rows),
            "planned_live_calls": sum(row["planned_live_calls"] for row in rows),
            "max_attempted_requests": sum(row["max_attempted_requests"] for row in rows),
            "additional_retry_attempt_budget": sum(row["additional_retry_attempt_budget"] for row in rows),
            "backoff_ceiling_seconds": round(sum(row["backoff_ceiling_seconds"] for row in rows), 3),
            "p0_planned_live_calls": sum(row["planned_live_calls"] for row in p0_rows),
            "p0_max_attempted_requests": sum(row["max_attempted_requests"] for row in p0_rows),
            "p0_backoff_ceiling_seconds": round(sum(row["backoff_ceiling_seconds"] for row in p0_rows), 3),
            "deepseek_retry_ceiling_wall_seconds": deepseek.get("retry_ceiling_wall_seconds", ""),
            "deepseek_retry_wall_overhead_seconds": deepseek.get("retry_wall_overhead_seconds", ""),
            "qwen_retry_ceiling_wall_seconds": qwen.get("retry_ceiling_wall_seconds", ""),
            "omni_retry_attempt_budget": omni.get("max_attempted_requests", ""),
            "credential_ready": readiness.get("environment", {}).get("dashscope_like_api_key_present") is True,
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(audit: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "command_id",
        "priority",
        "planned_live_calls",
        "max_call_attempts",
        "retry_backoff_seconds",
        "max_attempted_requests",
        "additional_retry_attempt_budget",
        "backoff_ceiling_seconds",
        "parallel_workers",
        "waves",
        "per_attempt_wall_seconds",
        "retry_ceiling_wall_seconds",
        "retry_wall_overhead_seconds",
        "claim_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in audit["rows"]:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    lines = [
        "# Live Retry Budget Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Surfaces: `{summary['surface_count']}`",
        f"- Bounded-retry surfaces: `{summary['bounded_retry_surfaces']}`",
        f"- Planned live calls: `{summary['planned_live_calls']}`",
        f"- Max attempted requests: `{summary['max_attempted_requests']}`",
        f"- Additional retry attempt budget: `{summary['additional_retry_attempt_budget']}`",
        f"- Backoff ceiling seconds: `{summary['backoff_ceiling_seconds']}`",
        f"- P0 max attempted requests: `{summary['p0_max_attempted_requests']}`",
        f"- DeepSeek retry ceiling wall: `{summary['deepseek_retry_ceiling_wall_seconds']}`",
        f"- DeepSeek retry wall overhead: `{summary['deepseek_retry_wall_overhead_seconds']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Command | Priority | Calls | Attempts | Max requests | Backoff ceiling | Workers | Waves | Per-attempt wall | Retry ceiling wall |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in audit["rows"]:
        lines.append(
            f"| `{row['command_id']}` | `{row['priority']}` | {row['planned_live_calls']} | "
            f"{row['max_call_attempts']} | {row['max_attempted_requests']} | {row['backoff_ceiling_seconds']} | "
            f"{row['parallel_workers']} | {row['waves']} | {row['per_attempt_wall_seconds'] or 'n/a'} | "
            f"{row['retry_ceiling_wall_seconds'] or 'n/a'} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This audit turns bounded retry into an explicit attempt and wall-time ceiling before any live run starts.",
            "- The 382 planned live calls can become at most 764 attempted requests under the current 2-attempt command policy.",
            "- P0 DeepSeek max20 remains the first run, but retry ceiling wall is a planning ceiling, not a reportable latency metric.",
            "- Omni48 still has no live first-text/total latency; this audit only counts its attempt budget.",
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
