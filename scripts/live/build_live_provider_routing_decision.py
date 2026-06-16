#!/usr/bin/env python3
"""Build a no-live-call provider routing decision for the next live execution step."""

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
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_provider_routing_decision.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_provider_routing_decision.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_provider_routing_decision.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def find_by(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any]:
    for row in rows:
        if row.get(key) == value:
            return row
    return {}


def routing_row(
    *,
    route_id: str,
    provider: str,
    planned_scope: str,
    status: str,
    selected_for_default_execute: bool,
    planned_live_calls: int,
    evidence: str,
    recommended_action: str,
    execute_command: str,
    claim_boundary: str,
    source_artifacts: list[str],
) -> dict[str, Any]:
    return {
        "route_id": route_id,
        "provider": provider,
        "planned_scope": planned_scope,
        "status": status,
        "selected_for_default_execute": selected_for_default_execute,
        "planned_live_calls": planned_live_calls,
        "evidence": evidence,
        "recommended_action": recommended_action,
        "execute_command": execute_command,
        "claim_boundary": claim_boundary,
        "source_artifacts": source_artifacts,
        "source_artifacts_exist": all((ROOT / source).exists() for source in source_artifacts),
        "live_calls_performed_by_builder": 0,
    }


def build_decision(root: Path) -> dict[str, Any]:
    phase_scorecard = read_json(root / "outputs/research_progress_snapshot/phase_result_scorecard.json")
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    command_surface = read_json(root / "outputs/research_progress_snapshot/live_command_surface_audit.json")
    launcher = read_json(root / "outputs/research_progress_snapshot/live_execution_launcher.json")
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    qwen_smoke = read_json(root / "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json")

    phase_summary = phase_scorecard.get("summary", {})
    readiness_summary = readiness.get("summary", {})
    command_summary = command_surface.get("summary", {})
    launcher_summary = launcher.get("summary", {})
    output_summary = output_audit.get("summary", {})
    command_rows = command_surface.get("rows", [])
    readiness_runs = readiness.get("runs", [])
    phase_rows = phase_scorecard.get("rows", [])

    deepseek_command = find_by(command_rows, "command_id", "deepseek_resume_primary")
    qwen_command = find_by(command_rows, "command_id", "qwen_full_backup_optional")
    omni_command = find_by(command_rows, "command_id", "omni48_label_only_live")
    deepseek_ready = find_by(readiness_runs, "run_id", "split20_deepseek_full")
    qwen_ready = find_by(readiness_runs, "run_id", "split20_qwen_backup")
    omni_ready = find_by(readiness_runs, "run_id", "omni48_live")
    deepseek_scorecard = find_by(phase_rows, "result_id", "deepseek_no_go")

    deepseek_no_go = (
        as_int(phase_summary.get("deepseek_no_go_rows")) == 1
        and phase_summary.get("no_deepseek_api_calls") is True
        and deepseek_scorecard.get("claim_boundary") == "do_not_use_deepseek_api"
    )
    qwen_wall = 0.0
    if qwen_smoke.get("runs") and isinstance(qwen_smoke["runs"][0], dict):
        qwen_wall = float(qwen_smoke["runs"][0].get("wall_seconds", 0.0))
    qwen_harmful = as_int(qwen_smoke.get("harmful_accepts"), -1)
    credential_ready = bool(readiness.get("environment", {}).get("dashscope_like_api_key_present"))

    rows = [
        routing_row(
            route_id="deepseek_resume_primary",
            provider="deepseek-v4-flash",
            planned_scope="deepseek",
            status="no_go_current" if deepseek_no_go else "blocked_by_quota_or_capacity",
            selected_for_default_execute=False,
            planned_live_calls=as_int(deepseek_command.get("planned_live_calls")),
            evidence=(
                f"phase scorecard no-go {deepseek_no_go}; "
                f"readiness {deepseek_ready.get('status', 'missing')}; "
                f"missing outputs {output_summary.get('missing_output_surfaces', 0)}"
            ),
            recommended_action="do not execute DeepSeek by default; reopen only after quota/capacity is explicitly cleared",
            execute_command="",
            claim_boundary="do_not_use_deepseek_api_by_default",
            source_artifacts=[
                "outputs/research_progress_snapshot/phase_result_scorecard.md",
                "outputs/research_progress_snapshot/live_run_readiness.md",
                "outputs/research_progress_snapshot/live_output_audit.md",
            ],
        ),
        routing_row(
            route_id="qwen_full_backup_optional",
            provider="qwen3.6-flash-2026-04-16",
            planned_scope="qwen",
            status="fallback_candidate_blocked_credentials" if not credential_ready else "fallback_candidate_explicit_only",
            selected_for_default_execute=False,
            planned_live_calls=as_int(qwen_command.get("planned_live_calls")),
            evidence=(
                f"fallback smoke calls {qwen_smoke.get('split_calls', 0)}; "
                f"wall {qwen_wall:.3f}s; harmful accepts {qwen_harmful}; "
                f"readiness {qwen_ready.get('status', 'missing')}"
            ),
            recommended_action="use only as explicit fallback/safety route; do not promote as primary latency path",
            execute_command="python scripts/live/run_live_execution_sequence.py --execute-live --live-scope qwen",
            claim_boundary="fallback_only_not_primary_latency_claim",
            source_artifacts=[
                "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json",
                "outputs/research_progress_snapshot/live_command_surface_audit.md",
                "outputs/research_progress_snapshot/live_run_readiness.md",
            ],
        ),
        routing_row(
            route_id="omni48_label_only",
            provider="qwen3.5-omni-flash/qwen3.5-omni-plus",
            planned_scope="omni",
            status="label_only_candidate_blocked_credentials" if not credential_ready else "label_only_candidate_explicit_only",
            selected_for_default_execute=False,
            planned_live_calls=as_int(omni_command.get("planned_live_calls")),
            evidence=f"readiness {omni_ready.get('status', 'missing')}; label-only route; no timeline writeback",
            recommended_action="use only for label/review evidence after credentials are ready",
            execute_command="python scripts/live/run_live_execution_sequence.py --execute-live --live-scope omni",
            claim_boundary="label_only_no_timeline_writeback",
            source_artifacts=[
                "outputs/research_progress_snapshot/omni48_live_call_manifest.md",
                "outputs/research_progress_snapshot/live_command_surface_audit.md",
                "outputs/research_progress_snapshot/live_run_readiness.md",
            ],
        ),
        routing_row(
            route_id="default_live_execute",
            provider="none",
            planned_scope="none",
            status="blocked_no_default_primary_provider",
            selected_for_default_execute=False,
            planned_live_calls=0,
            evidence=(
                f"credential ready {credential_ready}; "
                f"ready runs {readiness_summary.get('ready_count', 0)}/{readiness_summary.get('run_count', 0)}; "
                f"launcher default selected calls {launcher_summary.get('selected_live_calls', 0)}"
            ),
            recommended_action="do not run the default P0 live execute command until provider route is explicitly reopened",
            execute_command="",
            claim_boundary="default_execute_blocked_by_provider_route",
            source_artifacts=[
                "outputs/research_progress_snapshot/live_execution_launcher.md",
                "outputs/research_progress_snapshot/live_execution_eligibility_gate.md",
            ],
        ),
    ]

    selected = [row for row in rows if row["selected_for_default_execute"]]
    missing_sources = [row for row in rows if not row["source_artifacts_exist"]]
    return {
        "runtime_contract": "live_provider_routing_decision_no_live_calls_no_secret_values",
        "status": "blocked_no_default_primary_provider",
        "source_contracts": {
            "phase_result_scorecard": phase_scorecard.get("runtime_contract", ""),
            "live_run_readiness": readiness.get("runtime_contract", ""),
            "live_command_surface_audit": command_surface.get("runtime_contract", ""),
            "live_execution_launcher": launcher.get("runtime_contract", ""),
            "live_output_audit": output_audit.get("runtime_contract", ""),
        },
        "summary": {
            "route_rows": len(rows),
            "default_selected_routes": len(selected),
            "recommended_default_execute_scope": "none",
            "deepseek_no_go": deepseek_no_go,
            "deepseek_planned_calls_not_selected": as_int(deepseek_command.get("planned_live_calls")),
            "qwen_fallback_calls": as_int(qwen_command.get("planned_live_calls")),
            "qwen_smoke_calls": as_int(qwen_smoke.get("split_calls")),
            "qwen_smoke_harmful_accepts": qwen_harmful,
            "omni_label_calls": as_int(omni_command.get("planned_live_calls")),
            "credential_ready": credential_ready,
            "ready_runs": as_int(readiness_summary.get("ready_count")),
            "command_ready_count": as_int(command_summary.get("command_ready_count")),
            "missing_output_surfaces": as_int(output_summary.get("missing_output_surfaces")),
            "missing_source_rows": len(missing_sources),
            "live_calls_performed_by_builder": 0,
            "no_live_calls_performed": True,
            "no_secret_values_written": True,
            "no_scoring_commands_executed": True,
            "no_new_metric_claim": True,
        },
        "recommended_operator_action": "no default live execute; explicit qwen/omni fallback only after credentials are ready",
        "rows": rows,
    }


def write_csv(decision: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "route_id",
        "provider",
        "planned_scope",
        "status",
        "selected_for_default_execute",
        "planned_live_calls",
        "evidence",
        "recommended_action",
        "execute_command",
        "claim_boundary",
        "source_artifacts_exist",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in decision["rows"]:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_markdown(decision: dict[str, Any], path: Path) -> None:
    summary = decision["summary"]
    lines = [
        "# Live Provider Routing Decision",
        "",
        f"- Runtime contract: `{decision['runtime_contract']}`",
        f"- Status: `{decision['status']}`",
        f"- Route rows: `{summary['route_rows']}`",
        f"- Recommended default execute scope: `{summary['recommended_default_execute_scope']}`",
        f"- DeepSeek no-go: `{summary['deepseek_no_go']}`",
        f"- DeepSeek planned calls not selected: `{summary['deepseek_planned_calls_not_selected']}`",
        f"- Qwen fallback calls: `{summary['qwen_fallback_calls']}`",
        f"- Omni label calls: `{summary['omni_label_calls']}`",
        f"- Credential ready: `{summary['credential_ready']}`",
        f"- Ready runs: `{summary['ready_runs']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- No live calls performed: `{summary['no_live_calls_performed']}`",
        f"- No scoring commands executed: `{summary['no_scoring_commands_executed']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Route | Provider | Scope | Status | Default | Calls | Boundary |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in decision["rows"]:
        lines.append(
            f"| `{row['route_id']}` | `{row['provider']}` | `{row['planned_scope']}` | "
            f"`{row['status']}` | `{row['selected_for_default_execute']}` | "
            f"{row['planned_live_calls']} | `{row['claim_boundary']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This artifact overrides stale default execution wording with the current provider route decision.",
            "- DeepSeek is not selected for default live execution while the phase scorecard records the API no-go boundary.",
            "- Qwen and Omni remain explicit fallback/label-only routes after credentials are ready; neither can promote primary latency claims by itself.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    decision = build_decision(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(decision, args.output_md)
    write_csv(decision, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")
    print(json.dumps({"status": decision["status"], "summary": decision["summary"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
