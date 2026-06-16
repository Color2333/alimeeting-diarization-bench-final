#!/usr/bin/env python3
"""Build a no-live-call go/no-go gate for executing live LLM/Omni commands."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_execution_eligibility_gate.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_execution_eligibility_gate.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_execution_eligibility_gate.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def gate_row(
    *,
    gate_id: str,
    stage: str,
    status: str,
    observed_state: str,
    pass_condition: str,
    blocker: str,
    next_action: str,
    source_artifacts: list[str],
    claim_boundary: str,
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "stage": stage,
        "status": status,
        "observed_state": observed_state,
        "pass_condition": pass_condition,
        "blocker": blocker,
        "next_action": next_action,
        "source_artifacts": source_artifacts,
        "source_artifacts_exist": all((ROOT / source).exists() for source in source_artifacts if source.startswith("outputs/")),
        "claim_boundary": claim_boundary,
        "live_calls_performed_by_builder": 0,
    }


def build_gate(root: Path) -> dict[str, Any]:
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    input_integrity = read_json(root / "outputs/research_progress_snapshot/live_input_integrity_audit.json")
    command_surface = read_json(root / "outputs/research_progress_snapshot/live_command_surface_audit.json")
    runtime_env = read_json(root / "outputs/research_progress_snapshot/live_runtime_environment_audit.json")
    handoff = read_json(root / "outputs/research_progress_snapshot/live_execution_handoff_packet.json")
    launcher = read_json(root / "outputs/research_progress_snapshot/live_execution_launcher.json")
    provider_route = read_json(root / "outputs/research_progress_snapshot/live_provider_routing_decision.json")
    promotion_preflight = read_json(root / "outputs/research_progress_snapshot/post_live_promotion_preflight_audit.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")

    readiness_summary = readiness.get("summary", {})
    input_summary = input_integrity.get("summary", {})
    command_summary = command_surface.get("summary", {})
    env_summary = runtime_env.get("summary", {})
    handoff_summary = handoff.get("summary", {})
    launcher_summary = launcher.get("summary", {})
    route_summary = provider_route.get("summary", {})
    preflight_summary = promotion_preflight.get("summary", {})
    trace_summary = traceability.get("summary", {})

    input_pass = as_int(input_summary.get("input_ready_surfaces")) == as_int(input_summary.get("surface_count")) == 3
    command_pass = as_int(command_summary.get("command_ready_count")) == as_int(command_summary.get("command_count")) == 3
    runtime_pass = (
        as_int(env_summary.get("passed_checks")) == as_int(env_summary.get("check_count")) == 14
        and bool(env_summary.get("credential_ready")) is True
        and as_int(env_summary.get("known_provider_quota_blockers")) == 0
    )
    readiness_pass = as_int(readiness_summary.get("ready_count")) == as_int(readiness_summary.get("run_count")) == 3
    launcher_pass = bool(launcher_summary.get("execution_allowed")) is True
    provider_route_pass = (
        provider_route.get("status") != "blocked_no_default_primary_provider"
        and route_summary.get("recommended_default_execute_scope") not in {"none", "", None}
        and as_int(route_summary.get("default_selected_routes"), -1) > 0
    )
    handoff_pass = handoff.get("status") == "ready_for_live_execution"
    preflight_pass = bool(preflight_summary.get("ready_for_promotion_review")) is True
    traceability_pass = (
        traceability.get("status") == "pass"
        and as_int(trace_summary.get("traceability_rows")) == as_int(trace_summary.get("fully_covered_rows"))
    )

    rows = [
        gate_row(
            gate_id="live_input_surface_gate",
            stage="input_integrity",
            status="pass" if input_pass else "blocked",
            observed_state=(
                f"input-ready surfaces {input_summary.get('input_ready_surfaces', 0)}/"
                f"{input_summary.get('surface_count', 0)}; missing inputs {input_summary.get('missing_input_surfaces', 0)}"
            ),
            pass_condition="all three live input surfaces are locally complete",
            blocker="" if input_pass else "missing_live_inputs",
            next_action="keep input manifests unchanged unless live plan changes",
            source_artifacts=["outputs/research_progress_snapshot/live_input_integrity_audit.md"],
            claim_boundary="input_integrity_no_live_metric_claim",
        ),
        gate_row(
            gate_id="live_command_surface_gate",
            stage="command_surface",
            status="pass" if command_pass else "blocked",
            observed_state=(
                f"command-ready {command_summary.get('command_ready_count', 0)}/"
                f"{command_summary.get('command_count', 0)}; planned live calls {command_summary.get('planned_live_calls', 0)}"
            ),
            pass_condition="all live command surfaces parse, use skip-existing, bounded retry, and no secret literals",
            blocker="" if command_pass else "command_surface_needs_fix",
            next_action="use live launcher instead of manually copying raw commands",
            source_artifacts=["outputs/research_progress_snapshot/live_command_surface_audit.md"],
            claim_boundary="command_surface_no_live_metric_claim",
        ),
        gate_row(
            gate_id="live_runtime_credential_gate",
            stage="runtime_environment",
            status="pass" if runtime_pass else "blocked",
            observed_state=(
                f"checks {env_summary.get('passed_checks', 0)}/{env_summary.get('check_count', 0)}; "
                f"credential ready {env_summary.get('credential_ready', False)}; "
                f"quota blockers {env_summary.get('known_provider_quota_blockers', 0)}"
            ),
            pass_condition="runtime checks pass, credential is present in runner env, and quota blocker count is zero",
            blocker="credentials_or_quota_not_ready" if not runtime_pass else "",
            next_action="set provider credentials only in runner shell and clear/verify quota before execute-live",
            source_artifacts=["outputs/research_progress_snapshot/live_runtime_environment_audit.md"],
            claim_boundary="runtime_env_no_secret_values_no_live_metric_claim",
        ),
        gate_row(
            gate_id="live_readiness_gate",
            stage="live_readiness",
            status="pass" if readiness_pass else "blocked",
            observed_state=(
                f"ready runs {readiness_summary.get('ready_count', 0)}/"
                f"{readiness_summary.get('run_count', 0)}; blocked runs {readiness_summary.get('blocked_count', 0)}"
            ),
            pass_condition="all planned live runs are ready",
            blocker="planned_runs_blocked" if not readiness_pass else "",
            next_action="rerun readiness after credential/quota state changes",
            source_artifacts=["outputs/research_progress_snapshot/live_run_readiness.md"],
            claim_boundary="readiness_no_live_metric_claim",
        ),
        gate_row(
            gate_id="live_launcher_execute_gate",
            stage="live_launcher",
            status="pass" if launcher_pass else "blocked",
            observed_state=(
                f"execute_live {launcher_summary.get('execute_live', False)}; "
                f"execution_allowed {launcher_summary.get('execution_allowed', False)}; "
                f"selected calls {launcher_summary.get('selected_live_calls', 0)}; "
                f"provider default {launcher_summary.get('provider_route_default_scope', '')}"
            ),
            pass_condition="launcher is invoked with explicit execute flag and selected scope has ready commands",
            blocker="execute_live_flag_credentials_or_provider_route_missing" if not launcher_pass else "",
            next_action="do not use default P0; choose explicit qwen/omni only after credentials and route review",
            source_artifacts=["outputs/research_progress_snapshot/live_execution_launcher.md"],
            claim_boundary="launcher_execute_requires_explicit_flag",
        ),
        gate_row(
            gate_id="provider_route_gate",
            stage="provider_routing",
            status="pass" if provider_route_pass else "blocked",
            observed_state=(
                f"default scope {route_summary.get('recommended_default_execute_scope', '')}; "
                f"deepseek no-go {route_summary.get('deepseek_no_go', False)}; "
                f"default selected routes {route_summary.get('default_selected_routes', 0)}"
            ),
            pass_condition="provider route selects a non-empty default execution scope",
            blocker="default_provider_route_none" if not provider_route_pass else "",
            next_action="keep default live execution blocked; use explicit qwen/omni fallback only after credentials are ready",
            source_artifacts=["outputs/research_progress_snapshot/live_provider_routing_decision.md"],
            claim_boundary="provider_route_blocks_default_execute",
        ),
        gate_row(
            gate_id="operator_handoff_gate",
            stage="handoff_packet",
            status="pass" if handoff_pass else "blocked",
            observed_state=(
                f"handoff status {handoff.get('status', '')}; "
                f"blocked rows {handoff_summary.get('handoff_blocked_rows', 0)}; "
                f"P0 calls {handoff_summary.get('p0_planned_live_calls', 0)}"
            ),
            pass_condition="handoff packet is ready for live execution",
            blocker="handoff_waiting_credentials_or_quota" if not handoff_pass else "",
            next_action="follow handoff packet from credential preflight through P0 DeepSeek resume",
            source_artifacts=["outputs/research_progress_snapshot/live_execution_handoff_packet.md"],
            claim_boundary="handoff_no_live_metric_claim",
        ),
        gate_row(
            gate_id="post_live_promotion_preflight_gate",
            stage="post_live_promotion_preflight",
            status="pass" if preflight_pass else "blocked",
            observed_state=(
                f"promotion review ready {preflight_summary.get('ready_for_promotion_review', False)}; "
                f"blocked preflight rows {preflight_summary.get('blocked_rows', 0)}; "
                f"traceability {trace_summary.get('fully_covered_rows', 0)}/{trace_summary.get('traceability_rows', 0)}"
            ),
            pass_condition="post-live promotion preflight is ready and report/PPT traceability remains fully covered",
            blocker="post_live_evidence_missing" if not preflight_pass else "",
            next_action="keep promotion blocked until live outputs, scoring outputs, and time metrics exist",
            source_artifacts=[
                "outputs/research_progress_snapshot/post_live_promotion_preflight_audit.md",
                "outputs/research_progress_snapshot/report_ppt_traceability.md",
            ],
            claim_boundary="post_live_claim_promotion_not_live_execution_prerequisite",
        ),
    ]

    pass_rows = [row for row in rows if row["status"] == "pass"]
    blocked_rows = [row for row in rows if row["status"] == "blocked"]
    missing_source_rows = [row for row in rows if not row["source_artifacts_exist"]]
    ready_to_execute_live = not missing_source_rows and all(
        row["status"] == "pass"
        for row in rows
        if row["gate_id"]
        in {
            "live_input_surface_gate",
            "live_command_surface_gate",
            "live_runtime_credential_gate",
            "live_readiness_gate",
            "live_launcher_execute_gate",
            "provider_route_gate",
            "operator_handoff_gate",
        }
    )

    return {
        "runtime_contract": "live_execution_eligibility_gate_no_live_calls_no_secret_values",
        "status": "ready_to_execute_live" if ready_to_execute_live else "blocked_waiting_credentials_quota_or_execute_flag",
        "source_contracts": {
            "live_run_readiness": readiness.get("runtime_contract", ""),
            "live_input_integrity_audit": input_integrity.get("runtime_contract", ""),
            "live_command_surface_audit": command_surface.get("runtime_contract", ""),
            "live_runtime_environment_audit": runtime_env.get("runtime_contract", ""),
            "live_execution_handoff_packet": handoff.get("runtime_contract", ""),
            "live_execution_launcher": launcher.get("runtime_contract", ""),
            "live_provider_routing_decision": provider_route.get("runtime_contract", ""),
            "post_live_promotion_preflight_audit": promotion_preflight.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "summary": {
            "eligibility_rows": len(rows),
            "pass_rows": len(pass_rows),
            "blocked_rows": len(blocked_rows),
            "missing_source_rows": len(missing_source_rows),
            "ready_to_execute_live": ready_to_execute_live,
            "input_ready_surfaces": as_int(input_summary.get("input_ready_surfaces")),
            "command_ready_count": as_int(command_summary.get("command_ready_count")),
            "credential_ready": bool(env_summary.get("credential_ready")),
            "known_provider_quota_blockers": as_int(env_summary.get("known_provider_quota_blockers")),
            "ready_runs": as_int(readiness_summary.get("ready_count")),
            "selected_live_calls": as_int(launcher_summary.get("selected_live_calls")),
            "p0_selected_live_calls": as_int(launcher_summary.get("p0_selected_live_calls")),
            "provider_route_default_scope": str(route_summary.get("recommended_default_execute_scope", "")),
            "provider_route_blocks_default": bool(launcher_summary.get("provider_route_blocks_default")),
            "provider_route_deepseek_no_go": bool(route_summary.get("deepseek_no_go")),
            "provider_route_default_selected_routes": as_int(route_summary.get("default_selected_routes")),
            "execute_live": bool(launcher_summary.get("execute_live")),
            "execution_allowed": bool(launcher_summary.get("execution_allowed")),
            "handoff_blocked_rows": as_int(handoff_summary.get("handoff_blocked_rows")),
            "promotion_preflight_ready": bool(preflight_summary.get("ready_for_promotion_review")),
            "traceability_rows": as_int(trace_summary.get("traceability_rows")),
            "traceability_fully_covered_rows": as_int(trace_summary.get("fully_covered_rows")),
            "live_calls_performed_by_builder": 0,
            "no_live_calls_performed": True,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "recommended_first_execute_command": "none_default_blocked_by_provider_route",
        "explicit_fallback_commands": [
            "python scripts/live/run_live_execution_sequence.py --execute-live --live-scope qwen",
            "python scripts/live/run_live_execution_sequence.py --execute-live --live-scope omni",
        ],
        "rows": rows,
    }


def write_csv(gate: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "gate_id",
        "stage",
        "status",
        "observed_state",
        "pass_condition",
        "blocker",
        "next_action",
        "source_artifacts_exist",
        "claim_boundary",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in gate["rows"]:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_markdown(gate: dict[str, Any], path: Path) -> None:
    summary = gate["summary"]
    lines = [
        "# Live Execution Eligibility Gate",
        "",
        f"- Runtime contract: `{gate['runtime_contract']}`",
        f"- Status: `{gate['status']}`",
        f"- Eligibility rows: `{summary['eligibility_rows']}`",
        f"- Pass rows: `{summary['pass_rows']}`",
        f"- Blocked rows: `{summary['blocked_rows']}`",
        f"- Missing source rows: `{summary['missing_source_rows']}`",
        f"- Ready to execute live: `{summary['ready_to_execute_live']}`",
        f"- Input-ready surfaces: `{summary['input_ready_surfaces']}`",
        f"- Command-ready count: `{summary['command_ready_count']}`",
        f"- Credential ready: `{summary['credential_ready']}`",
        f"- Known provider quota blockers: `{summary['known_provider_quota_blockers']}`",
        f"- Ready runs: `{summary['ready_runs']}`",
        f"- Selected live calls: `{summary['selected_live_calls']}`",
        f"- P0 selected live calls: `{summary['p0_selected_live_calls']}`",
        f"- Provider route default scope: `{summary['provider_route_default_scope']}`",
        f"- Provider route blocks default: `{summary['provider_route_blocks_default']}`",
        f"- Provider route DeepSeek no-go: `{summary['provider_route_deepseek_no_go']}`",
        f"- Execute live: `{summary['execute_live']}`",
        f"- Execution allowed: `{summary['execution_allowed']}`",
        f"- Handoff blocked rows: `{summary['handoff_blocked_rows']}`",
        f"- Promotion preflight ready: `{summary['promotion_preflight_ready']}`",
        f"- Traceability rows: `{summary['traceability_rows']}`",
        f"- Traceability fully covered rows: `{summary['traceability_fully_covered_rows']}`",
        f"- No live calls performed: `{summary['no_live_calls_performed']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        f"- Recommended first execute command: `{gate['recommended_first_execute_command']}`",
        "",
        "| Gate | Stage | Status | Blocker | Observed state |",
        "|---|---|---|---|---|",
    ]
    for row in gate["rows"]:
        lines.append(
            f"| `{row['gate_id']}` | `{row['stage']}` | `{row['status']}` | "
            f"`{row['blocker']}` | {row['observed_state']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Input and command surfaces are ready, but live execution is still blocked by credential/quota readiness and the explicit execute flag.",
            "- The recommended command is recorded for operator handoff; this builder does not execute it.",
            "- Post-live promotion readiness is tracked separately and remains blocked until live/scoring/time evidence exists.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    gate = build_gate(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(gate, args.output_md)
    write_csv(gate, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")
    print(json.dumps({"status": gate["status"], "summary": gate["summary"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
