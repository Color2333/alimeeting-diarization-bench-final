#!/usr/bin/env python3
"""Build a no-live-call timing plan for pending live LLM/Omni execution."""

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
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_execution_timing_plan.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_execution_timing_plan.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_execution_timing_plan.csv")


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


def find_step(rows: list[dict[str, Any]], step_id: str) -> dict[str, Any]:
    return next((row for row in rows if row.get("step_id") == step_id), {})


def build_plan(root: Path) -> dict[str, Any]:
    agent_plan = read_json(root / "outputs/research_progress_snapshot/live_agent_execution_plan.json")
    runbook = read_json(root / "outputs/research_progress_snapshot/live_execution_runbook.json")
    split_policy = read_json(root / "outputs/research_progress_snapshot/split_policy_optimization.json")
    latency_mitigation = read_json(root / "outputs/research_progress_snapshot/latency_risk_mitigation_plan.json")
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    scoring = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    omni48 = read_json(root / "outputs/research_progress_snapshot/omni48_live_call_manifest.json")

    agent_steps = agent_plan.get("steps", [])
    deepseek = find_step(agent_steps, "split20_deepseek_resume_after_top3")
    qwen = find_step(agent_steps, "split20_qwen_backup_full_surface")
    omni = find_step(agent_steps, "omni48_label_only_live")
    refresh = find_step(agent_steps, "postrun_refresh_and_validation")

    split_summary = split_policy.get("summary", {})
    mitigation_summary = latency_mitigation.get("summary", {})
    omni_summary = omni48.get("summary", {})

    deepseek_calls = as_int(deepseek.get("planned_calls"), as_int(split_summary.get("primary_resume_calls")))
    deepseek_workers = as_int(deepseek.get("parallel_workers"), 8)
    deepseek_waves = as_int(deepseek.get("estimated_waves"), ceil_waves(deepseek_calls, deepseek_workers))
    deepseek_p95 = as_float(split_summary.get("primary_simulated_p95_call_seconds"))
    deepseek_wall = as_float(deepseek.get("estimated_wall_seconds"), deepseek_waves * deepseek_p95)

    qwen_calls = as_int(qwen.get("planned_calls"), as_int(split_summary.get("primary_calls")))
    qwen_workers = as_int(qwen.get("parallel_workers"), 8)
    qwen_waves = as_int(qwen.get("estimated_waves"), ceil_waves(qwen_calls, qwen_workers))
    qwen_wall = as_float(qwen.get("estimated_wall_seconds"))
    qwen_wave_seconds = round(qwen_wall / qwen_waves, 3) if qwen_waves else 0.0

    omni_calls = as_int(omni.get("planned_calls"), as_int(omni_summary.get("call_count")))
    omni_clip_model_seconds = as_float(omni.get("clip_model_seconds_proxy"), as_float(omni_summary.get("clip_model_seconds_proxy")))

    rows = [
        {
            "timing_id": "credential_preflight",
            "priority": "P0",
            "phase": "preflight",
            "planned_calls": 0,
            "parallel_workers": 0,
            "estimated_waves": 0,
            "estimated_wall_seconds": 0.0,
            "estimate_source": "env_presence_gate_only",
            "claim_status": "gate_only_no_latency_claim",
            "blocking_state": "blocked_missing_credentials" if readiness.get("summary", {}).get("ready_count", 0) == 0 else "ready",
            "next_action": "set API key env in shell and rerun live readiness; do not write secret values to artifacts",
        },
        {
            "timing_id": "deepseek_max20_resume_live_call",
            "priority": "P0",
            "phase": "primary_live_call",
            "planned_calls": deepseek_calls,
            "parallel_workers": deepseek_workers,
            "estimated_waves": deepseek_waves,
            "estimated_wall_seconds": round(deepseek_wall, 3),
            "estimate_source": "split20_simulated_p95_call_seconds_x_parallel_waves",
            "claim_status": "not_claimable_until_resume_output_and_scoring",
            "blocking_state": deepseek.get("status", "blocked_by_provider_quota_or_capacity"),
            "next_action": "run max20 resume first when credentials/quota are ready",
        },
        {
            "timing_id": "deepseek_postrun_audit_and_scoring",
            "priority": "P0",
            "phase": "postrun_scoring",
            "planned_calls": 0,
            "parallel_workers": 0,
            "estimated_waves": 0,
            "estimated_wall_seconds": "",
            "estimate_source": "not_estimated_waits_for_live_jsonl",
            "claim_status": "not_claimable_until_output_audit_and_safety_comparison_pass",
            "blocking_state": scoring.get("status", "blocked_waiting_live_outputs"),
            "next_action": "run output audit, safety summary, split comparison, then refresh validation",
        },
        {
            "timing_id": "omni48_label_only_live",
            "priority": "P1",
            "phase": "label_only_live_call",
            "planned_calls": omni_calls,
            "parallel_workers": 0,
            "estimated_waves": 0,
            "estimated_wall_seconds": "",
            "estimate_source": f"clip_model_seconds_proxy_{omni_clip_model_seconds:.1f}_needs_live_latency",
            "claim_status": "label_only_not_timeline_writeback_not_guard_latency_claim",
            "blocking_state": omni.get("status", "blocked_missing_credentials"),
            "next_action": "run only after P0 or when explicitly spending Omni quota",
        },
        {
            "timing_id": "qwen_full_backup_optional",
            "priority": "P1",
            "phase": "fallback_live_call",
            "planned_calls": qwen_calls,
            "parallel_workers": qwen_workers,
            "estimated_waves": qwen_waves,
            "estimated_wall_seconds": round(qwen_wall, 3),
            "estimate_source": "top4_5_backup_wall_seconds_x_parallel_waves",
            "claim_status": "fallback_only_not_primary_latency_claim",
            "blocking_state": qwen.get("status", "blocked_missing_credentials"),
            "next_action": "keep as backup; current evidence is slower than original max",
        },
        {
            "timing_id": "refresh_report_ppt_validation",
            "priority": "P0",
            "phase": "refresh_and_validate",
            "planned_calls": 0,
            "parallel_workers": 0,
            "estimated_waves": 0,
            "estimated_wall_seconds": "",
            "estimate_source": "local_refresh_runtime_not_live_latency",
            "claim_status": "validation_only",
            "blocking_state": refresh.get("status", "waiting_for_live_outputs"),
            "next_action": "rerun refresh after live outputs and scoring artifacts exist",
        },
    ]

    p0_known_seconds = sum(
        as_float(row.get("estimated_wall_seconds"))
        for row in rows
        if row["priority"] == "P0" and row.get("estimated_wall_seconds") not in {"", None}
    )
    p1_known_seconds = sum(
        as_float(row.get("estimated_wall_seconds"))
        for row in rows
        if row["priority"] == "P1" and row.get("estimated_wall_seconds") not in {"", None}
    )
    unknown_rows = [row["timing_id"] for row in rows if row.get("estimated_wall_seconds") in {"", None}]
    blocked_rows = [row["timing_id"] for row in rows if str(row.get("blocking_state", "")).startswith("blocked")]

    return {
        "runtime_contract": "live_execution_timing_plan_no_live_calls",
        "status": "blocked_waiting_for_credentials_or_live_outputs",
        "source_contracts": {
            "live_agent_execution_plan": agent_plan.get("runtime_contract", ""),
            "live_execution_runbook": runbook.get("runtime_contract", ""),
            "split_policy_optimization": split_policy.get("runtime_contract", ""),
            "latency_risk_mitigation_plan": latency_mitigation.get("runtime_contract", ""),
            "live_run_readiness": readiness.get("runtime_contract", ""),
            "live_output_audit": output_audit.get("runtime_contract", ""),
            "live_scoring_readiness": scoring.get("runtime_contract", ""),
            "omni48_live_call_manifest": omni48.get("runtime_contract", ""),
        },
        "summary": {
            "timing_rows": len(rows),
            "p0_rows": sum(1 for row in rows if row["priority"] == "P0"),
            "p1_rows": sum(1 for row in rows if row["priority"] == "P1"),
            "known_wall_rows": len(rows) - len(unknown_rows),
            "unknown_wall_rows": len(unknown_rows),
            "blocked_rows": len(blocked_rows),
            "deepseek_resume_calls": deepseek_calls,
            "deepseek_parallel_workers": deepseek_workers,
            "deepseek_parallel_waves": deepseek_waves,
            "deepseek_p95_call_seconds": deepseek_p95,
            "deepseek_estimated_wall_seconds": round(deepseek_wall, 3),
            "qwen_backup_calls": qwen_calls,
            "qwen_parallel_workers": qwen_workers,
            "qwen_parallel_waves": qwen_waves,
            "qwen_wave_seconds_proxy": qwen_wave_seconds,
            "qwen_estimated_wall_seconds": round(qwen_wall, 3),
            "omni48_label_only_calls": omni_calls,
            "omni48_clip_model_seconds_proxy": round(omni_clip_model_seconds, 3),
            "p0_known_wall_seconds": round(p0_known_seconds, 3),
            "p1_known_wall_seconds": round(p1_known_seconds, 3),
            "primary_policy": mitigation_summary.get("primary_policy", split_summary.get("primary_policy", "max20")),
            "stretch_policy": mitigation_summary.get("stretch_policy", split_summary.get("stretch_policy", "max15")),
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "unknown_wall_timing_ids": unknown_rows,
        "blocked_timing_ids": blocked_rows,
        "rows": rows,
    }


def write_csv(plan: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "timing_id",
        "priority",
        "phase",
        "planned_calls",
        "parallel_workers",
        "estimated_waves",
        "estimated_wall_seconds",
        "estimate_source",
        "claim_status",
        "blocking_state",
        "next_action",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in plan["rows"]:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_markdown(plan: dict[str, Any], path: Path) -> None:
    summary = plan["summary"]
    lines = [
        "# Live Execution Timing Plan",
        "",
        f"- Runtime contract: `{plan['runtime_contract']}`",
        f"- Status: `{plan['status']}`",
        f"- Timing rows: `{summary['timing_rows']}`",
        f"- P0 / P1 rows: `{summary['p0_rows']}` / `{summary['p1_rows']}`",
        f"- DeepSeek resume calls: `{summary['deepseek_resume_calls']}`",
        f"- DeepSeek workers / waves: `{summary['deepseek_parallel_workers']}` / `{summary['deepseek_parallel_waves']}`",
        f"- DeepSeek estimated wall: `{summary['deepseek_estimated_wall_seconds']}`",
        f"- Qwen estimated wall: `{summary['qwen_estimated_wall_seconds']}`",
        f"- Omni48 label-only calls: `{summary['omni48_label_only_calls']}`",
        f"- Unknown wall rows: `{summary['unknown_wall_rows']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Timing | Priority | Phase | Calls | Workers | Waves | Wall estimate | Claim status | Blocking state |",
        "|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in plan["rows"]:
        wall = row["estimated_wall_seconds"] if row["estimated_wall_seconds"] != "" else "n/a"
        lines.append(
            f"| `{row['timing_id']}` | `{row['priority']}` | `{row['phase']}` | {row['planned_calls']} | "
            f"{row['parallel_workers']} | {row['estimated_waves']} | {wall} | `{row['claim_status']}` | `{row['blocking_state']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This artifact separates live-call wall estimates from reportable latency claims.",
            "- DeepSeek max20 resume is the P0 timed path: 139 calls, 8 workers, 18 waves, 384.444s estimated wall from simulated P95.",
            "- Qwen backup is slower and fallback-only; Omni48 has clip-model seconds but still needs live first-text and total latency measurement.",
            "- Postrun scoring and refresh are validation steps, not live latency claims.",
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

    plan = build_plan(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(plan, args.output_md)
    write_csv(plan, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
