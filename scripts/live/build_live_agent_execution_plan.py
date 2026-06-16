#!/usr/bin/env python3
"""Build a no-live-call Agent execution plan for pending LLM/Omni runs."""

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
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_agent_execution_plan.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_agent_execution_plan.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_agent_execution_plan.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def csv_escape(value: object) -> str:
    text = str(value)
    if any(ch in text for ch in [",", "\n", '"']):
        return '"' + text.replace('"', '""') + '"'
    return text


def split_resume_command(output_jsonl: str) -> str:
    return (
        "python scripts/llm/llm_window_batch_policy_eval.py --mode call "
        "--decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl "
        "--trigger-policy proxy_flagged_window "
        "--window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv "
        "--patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt "
        "--window-id-file outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt "
        "--max-patches-per-call 20 --model deepseek-v4-flash --parallel-workers 8 --skip-existing-output "
        "--max-call-attempts 2 --retry-backoff-seconds 2.0 "
        f"--output-jsonl {output_jsonl}"
    )


def ceil_waves(calls: int, workers: int) -> int:
    return int(math.ceil(calls / max(workers, 1)))


def build_plan(root: Path) -> dict[str, Any]:
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    split20 = read_json(root / "outputs/research_progress_snapshot/split20_full_live_manifest.json")
    split_export = read_json(root / "outputs/research_progress_snapshot/split20_resume_export_audit.json")
    omni_calls = read_json(root / "outputs/research_progress_snapshot/omni48_live_call_manifest.json")
    qwen = read_json(root / "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json")
    readiness_by_run = {row.get("run_id"): row for row in readiness.get("runs", [])}
    split_summary = split20.get("summary", {})
    export_summary = split_export.get("summary", {})
    omni_summary = omni_calls.get("summary", {})
    qwen_run = (qwen.get("runs") or [{}])[0]

    deepseek_resume_calls = int(export_summary.get("export_prompts") or split_summary.get("deepseek_resume_required_calls_min") or 0)
    deepseek_resume_parents = int(export_summary.get("export_parent_windows") or split_summary.get("deepseek_resume_parent_windows") or 0)
    deepseek_workers = 8
    deepseek_call_p95 = float(split_summary.get("simulated_p95_call_seconds") or 0.0)
    deepseek_est_wall = ceil_waves(deepseek_resume_calls, deepseek_workers) * deepseek_call_p95
    qwen_calls = int(split_summary.get("prompt_calls") or 0)
    qwen_parents = int(split_summary.get("parent_windows") or 0)
    qwen_workers = 8
    qwen_top45_wall = float(qwen_run.get("wall_seconds") or split_summary.get("qwen_backup_wall_seconds") or 0.0)
    qwen_est_wall = ceil_waves(qwen_calls, qwen_workers) * qwen_top45_wall if qwen_top45_wall else 0.0
    omni_call_count = int(omni_summary.get("call_count") or 0)
    omni_windows = int(omni_summary.get("window_count") or 0)

    source_artifacts = [
        "outputs/research_progress_snapshot/live_run_readiness.json",
        "outputs/research_progress_snapshot/split20_full_live_manifest.json",
        "outputs/research_progress_snapshot/split20_resume_export_audit.json",
        "outputs/research_progress_snapshot/omni48_live_call_manifest.json",
    ]
    missing_sources = [artifact for artifact in source_artifacts if not (root / artifact).exists()]
    credential_ready = bool(readiness.get("environment", {}).get("dashscope_like_api_key_present"))
    preflight_blockers = [] if credential_ready else ["missing_dashscope_or_bailian_api_key_env"]
    deepseek_blockers = readiness_by_run.get("split20_deepseek_full", {}).get("blockers", [])
    qwen_blockers = readiness_by_run.get("split20_qwen_backup", {}).get("blockers", [])
    omni_blockers = readiness_by_run.get("omni48_live", {}).get("blockers", [])

    steps = [
        {
            "step_id": "credential_preflight",
            "priority": "P0",
            "run_id": "credential_preflight",
            "status": "ready_for_live_steps" if credential_ready else "blocked_missing_credentials",
            "planned_calls": 0,
            "planned_windows": 0,
            "parallel_workers": 0,
            "target_models": [],
            "estimated_wall_seconds": 0.0,
            "latency_metric_status": "gate_only",
            "blockers": preflight_blockers,
            "run_command": "export DASHSCOPE_API_KEY=...  # or BAILIAN_API_KEY / ALIYUN_BAILIAN_API_KEY; do not write secrets to artifacts",
            "postrun_artifacts": ["outputs/research_progress_snapshot/live_run_readiness.json"],
            "writeback_right": "none",
        },
        {
            "step_id": "split20_deepseek_resume_after_top3",
            "priority": "P0",
            "run_id": "split20_deepseek_full",
            "status": readiness_by_run.get("split20_deepseek_full", {}).get("status", "not_built"),
            "planned_calls": deepseek_resume_calls,
            "planned_windows": deepseek_resume_parents,
            "parallel_workers": deepseek_workers,
            "target_models": ["deepseek-v4-flash"],
            "estimated_wall_seconds": round(deepseek_est_wall, 3),
            "estimated_waves": ceil_waves(deepseek_resume_calls, deepseek_workers),
            "latency_metric_status": "resume_budget_from_split20_simulated_p95",
            "blockers": deepseek_blockers,
            "run_command": split_resume_command(
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl"
            ),
            "postrun_artifacts": [
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl",
                "outputs/research_progress_snapshot/split20_full_live_manifest.json",
                "outputs/research_progress_snapshot/latest_artifact_validation.md",
            ],
            "writeback_right": "block_or_quarantine_only",
        },
        {
            "step_id": "split20_qwen_backup_full_surface",
            "priority": "P1",
            "run_id": "split20_qwen_backup",
            "status": readiness_by_run.get("split20_qwen_backup", {}).get("status", "not_built"),
            "planned_calls": qwen_calls,
            "planned_windows": qwen_parents,
            "parallel_workers": qwen_workers,
            "target_models": ["qwen3.6-flash-2026-04-16"],
            "estimated_wall_seconds": round(qwen_est_wall, 3),
            "estimated_waves": ceil_waves(qwen_calls, qwen_workers),
            "latency_metric_status": "backup_path_budget_not_latency_supporting",
            "blockers": qwen_blockers,
            "run_command": readiness_by_run.get("split20_qwen_backup", {}).get("run_command", ""),
            "postrun_artifacts": [
                "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl",
                "outputs/research_progress_snapshot/latest_artifact_validation.md",
            ],
            "writeback_right": "block_or_quarantine_only",
        },
        {
            "step_id": "omni48_label_only_live",
            "priority": "P1",
            "run_id": "omni48_live",
            "status": readiness_by_run.get("omni48_live", {}).get("status", "not_built"),
            "planned_calls": omni_call_count,
            "planned_windows": omni_windows,
            "parallel_workers": 0,
            "target_models": omni_summary.get("target_models", []),
            "estimated_wall_seconds": None,
            "clip_model_seconds_proxy": float(omni_summary.get("clip_model_seconds_proxy") or 0.0),
            "latency_metric_status": "needs_live_first_text_and_total_latency_measurement",
            "blockers": omni_blockers,
            "run_command": readiness_by_run.get("omni48_live", {}).get("run_command", ""),
            "postrun_artifacts": [
                "outputs/omni_guard/omni_expansion_48_live.jsonl",
                "outputs/research_progress_snapshot/latest_artifact_validation.md",
            ],
            "writeback_right": "label_only_no_timeline_writeback",
        },
        {
            "step_id": "postrun_refresh_and_validation",
            "priority": "P0",
            "run_id": "postrun_refresh_and_validation",
            "status": "waiting_for_live_outputs",
            "planned_calls": 0,
            "planned_windows": 0,
            "parallel_workers": 0,
            "target_models": [],
            "estimated_wall_seconds": None,
            "latency_metric_status": "validation_only",
            "blockers": ["requires_completed_live_outputs"],
            "run_command": "python scripts/misc/refresh_latest_research_artifacts.py",
            "postrun_artifacts": [
                "outputs/research_progress_snapshot/refresh_latest_artifacts.md",
                "outputs/research_progress_snapshot/latest_artifact_validation.md",
                "../研究进展汇报.pptx",
            ],
            "writeback_right": "none",
        },
    ]

    live_steps = [step for step in steps if int(step["planned_calls"]) > 0]
    blocked_steps = [step for step in steps if str(step["status"]).startswith("blocked") or step.get("blockers")]
    p0_live_steps = [step for step in live_steps if step["priority"] == "P0"]
    return {
        "runtime_contract": "live_agent_execution_plan_no_live_calls",
        "secret_policy": "env_presence_only_no_secret_values_written",
        "source_artifacts": source_artifacts,
        "missing_sources": missing_sources,
        "status": "pass" if not missing_sources else "fail",
        "summary": {
            "step_count": len(steps),
            "live_step_count": len(live_steps),
            "blocked_step_count": len(blocked_steps),
            "p0_live_step_count": len(p0_live_steps),
            "planned_live_calls": sum(int(step["planned_calls"]) for step in live_steps),
            "p0_planned_live_calls": sum(int(step["planned_calls"]) for step in p0_live_steps),
            "omni_label_only_calls": omni_call_count,
            "deepseek_resume_calls": deepseek_resume_calls,
            "qwen_backup_calls": qwen_calls,
            "deepseek_resume_estimated_wall_seconds": round(deepseek_est_wall, 3),
            "qwen_backup_estimated_wall_seconds": round(qwen_est_wall, 3),
            "live_calls_performed": 0,
            "no_secret_values_written": True,
        },
        "steps": steps,
    }


def write_csv(plan: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "step_id",
        "priority",
        "run_id",
        "status",
        "planned_calls",
        "planned_windows",
        "parallel_workers",
        "target_models",
        "estimated_wall_seconds",
        "latency_metric_status",
        "blockers",
        "writeback_right",
        "run_command",
    ]
    lines = [",".join(fieldnames)]
    for step in plan["steps"]:
        row = []
        for name in fieldnames:
            value = step.get(name, "")
            if isinstance(value, list):
                value = ";".join(str(part) for part in value)
            row.append(csv_escape(value))
        lines.append(",".join(row))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(plan: dict[str, Any], path: Path) -> None:
    summary = plan["summary"]
    lines = [
        "# Live Agent Execution Plan",
        "",
        f"- Runtime contract: `{plan['runtime_contract']}`",
        f"- Status: `{plan['status']}`",
        f"- Steps: `{summary['step_count']}`",
        f"- Live steps: `{summary['live_step_count']}`",
        f"- Blocked steps: `{summary['blocked_step_count']}`",
        f"- Planned live calls: `{summary['planned_live_calls']}`",
        f"- P0 planned live calls: `{summary['p0_planned_live_calls']}`",
        f"- DeepSeek resume calls: `{summary['deepseek_resume_calls']}`",
        f"- Omni label-only calls: `{summary['omni_label_only_calls']}`",
        f"- Live calls performed: `{summary['live_calls_performed']}`",
        f"- No secret values written: `{summary['no_secret_values_written']}`",
        "",
        "## Steps",
        "",
        "| Step | Priority | Status | Calls | Windows | Est. wall | Latency metric | Writeback |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for step in plan["steps"]:
        est = step.get("estimated_wall_seconds")
        est_text = "n/a" if est is None else f"{float(est):.3f}s"
        lines.append(
            f"| `{step['step_id']}` | `{step['priority']}` | `{step['status']}` | "
            f"{step['planned_calls']} | {step['planned_windows']} | {est_text} | "
            f"`{step['latency_metric_status']}` | `{step['writeback_right']}` |"
        )
    lines.extend(["", "## Commands", ""])
    for step in plan["steps"]:
        lines.extend(
            [
                f"### {step['step_id']}",
                "",
                f"- Blockers: `{'; '.join(step.get('blockers') or []) or 'none'}`",
                f"- Postrun artifacts: `{'; '.join(step.get('postrun_artifacts') or [])}`",
                "",
                "```bash",
                str(step.get("run_command", "")),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Reading",
            "",
            "- This plan is an Agent handoff manifest; it performs no live model/API calls.",
            "- DeepSeek resume is the P0 path for finishing the split20 latency claim after the completed top3 smoke.",
            "- Qwen backup is kept as an execution fallback, but current evidence says it is not latency-supporting.",
            "- Omni48 remains label-only and has no timeline writeback right; first text and total latency still require a live run.",
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
