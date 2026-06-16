#!/usr/bin/env python3
"""Build a no-live-call execution plan for post-live scoring commands."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_scoring_execution_plan.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_scoring_execution_plan.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_scoring_execution_plan.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def by_id(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key)): row for row in rows}


def plan_row(
    step_order: int,
    scoring_execution_id: str,
    priority: str,
    surface_id: str,
    execution_phase: str,
    current_state: str,
    prerequisite_gate: str,
    command: str,
    output_artifacts: list[str],
    success_gate: str,
    promotion_gate: str,
    claim_boundary: str,
) -> dict[str, Any]:
    return {
        "step_order": step_order,
        "scoring_execution_id": scoring_execution_id,
        "priority": priority,
        "surface_id": surface_id,
        "execution_phase": execution_phase,
        "current_state": current_state,
        "prerequisite_gate": prerequisite_gate,
        "command": command,
        "output_artifacts": output_artifacts,
        "success_gate": success_gate,
        "promotion_gate": promotion_gate,
        "claim_boundary": claim_boundary,
    }


def build_plan(root: Path) -> dict[str, Any]:
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    scoring = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    metric = read_json(root / "outputs/research_progress_snapshot/live_metric_extraction_contract.json")
    schema = read_json(root / "outputs/research_progress_snapshot/live_output_schema_contract.json")
    scorecard = read_json(root / "outputs/research_progress_snapshot/post_live_acceptance_scorecard.json")
    latency_matrix = read_json(root / "outputs/research_progress_snapshot/post_live_latency_claim_matrix.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")

    scoring_steps = by_id(scoring.get("scoring_steps", []), "scoring_id")
    scoring_summary = scoring.get("summary", {})
    output_summary = output_audit.get("summary", {})
    metric_summary = metric.get("summary", {})
    schema_summary = schema.get("summary", {})
    scorecard_summary = scorecard.get("summary", {})
    latency_summary = latency_matrix.get("summary", {})
    promotion_summary = promotion.get("summary", {})
    traceability_summary = traceability.get("summary", {})

    deepseek_safety = scoring_steps.get("deepseek_resume_safety", {})
    deepseek_comparison = scoring_steps.get("deepseek_full_split20_comparison", {})
    qwen_safety = scoring_steps.get("qwen_full_backup_safety", {})
    qwen_comparison = scoring_steps.get("qwen_full_backup_comparison", {})
    omni_summary = scoring_steps.get("omni48_label_summary", {})

    rows = [
        plan_row(
            1,
            "deepseek_resume_safety_score",
            "P0",
            "deepseek_resume_after_top3",
            "safety_scoring",
            deepseek_safety.get("status", "blocked_waiting_live_output"),
            "deepseek resume JSONL exists with 139 successful rows and clean output audit",
            deepseek_safety.get("scoring_command", ""),
            deepseek_safety.get("output_artifacts", []),
            deepseek_safety.get("success_gate", ""),
            "deepseek_split20_resume_safety",
            "required_before_zero_harm_safety_claim",
        ),
        plan_row(
            2,
            "deepseek_full_split20_comparison_score",
            "P0",
            "deepseek_resume_after_top3",
            "latency_comparison",
            deepseek_comparison.get("status", "blocked_waiting_live_output"),
            "deepseek resume safety summary exists and harmful_accepts == 0",
            deepseek_comparison.get("scoring_command", ""),
            deepseek_comparison.get("output_artifacts", []),
            deepseek_comparison.get("success_gate", ""),
            "deepseek_split20_resume_latency",
            "required_before_full_surface_latency_claim",
        ),
        plan_row(
            3,
            "omni48_label_summary_score",
            "P1",
            "omni48_label_only",
            "label_metric_scoring",
            omni_summary.get("status", "blocked_waiting_live_output"),
            "Omni48 live CSV/JSONL exists with 96 complete label-only calls",
            omni_summary.get("scoring_command", ""),
            omni_summary.get("output_artifacts", []),
            omni_summary.get("success_gate", ""),
            "omni48_label_metrics",
            "label_only_no_timeline_writeback",
        ),
        plan_row(
            4,
            "qwen_full_backup_safety_score",
            "P1",
            "qwen_full_backup",
            "fallback_safety_scoring",
            qwen_safety.get("status", "blocked_waiting_live_output"),
            "Qwen full backup JSONL exists with 147 successful rows and clean output audit",
            qwen_safety.get("scoring_command", ""),
            qwen_safety.get("output_artifacts", []),
            qwen_safety.get("success_gate", ""),
            "qwen_full_backup_claim",
            "fallback_only_not_primary_claim",
        ),
        plan_row(
            5,
            "qwen_full_backup_comparison_score",
            "P1",
            "qwen_full_backup",
            "fallback_latency_comparison",
            qwen_comparison.get("status", "blocked_waiting_live_output"),
            "Qwen backup safety summary exists and fallback comparison is explicitly requested",
            qwen_comparison.get("scoring_command", ""),
            qwen_comparison.get("output_artifacts", []),
            qwen_comparison.get("success_gate", ""),
            "qwen_full_backup_claim",
            "fallback_only_not_primary_latency_claim",
        ),
        plan_row(
            6,
            "promotion_refresh_validation",
            "P0",
            "report_ppt",
            "promotion_and_refresh",
            "blocked_waiting_scoring_outputs",
            "required P0 scoring outputs exist and promotion gates remain traceable",
            "python scripts/refresh_latest_research_artifacts.py",
            [
                "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json",
                "outputs/research_progress_snapshot/latest_artifact_validation.json",
                "../研究进展汇报.pptx",
                "docs/reports/2026-06-03-realtime-dual-agent-roadmap.md",
            ],
            "refresh pass; validator failed_checks empty; traceability fully covered",
            "report_ppt_traceability_after_promotion",
            "required_before_report_ppt_claim_promotion",
        ),
    ]

    return {
        "runtime_contract": "post_live_scoring_execution_plan_no_live_calls",
        "status": "blocked_waiting_live_outputs",
        "source_contracts": {
            "live_output_audit": output_audit.get("runtime_contract", ""),
            "live_scoring_readiness": scoring.get("runtime_contract", ""),
            "live_metric_extraction_contract": metric.get("runtime_contract", ""),
            "live_output_schema_contract": schema.get("runtime_contract", ""),
            "post_live_acceptance_scorecard": scorecard.get("runtime_contract", ""),
            "post_live_latency_claim_matrix": latency_matrix.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "summary": {
            "scoring_execution_steps": len(rows),
            "p0_execution_steps": sum(1 for row in rows if row["priority"] == "P0"),
            "p1_execution_steps": sum(1 for row in rows if row["priority"] == "P1"),
            "blocked_execution_steps": sum(1 for row in rows if "blocked" in row["current_state"]),
            "ready_execution_steps": sum(1 for row in rows if str(row["current_state"]).startswith("ready")),
            "scoring_commands": sum(1 for row in rows if row["command"].startswith("python ")),
            "p0_scoring_steps": as_int(scoring_summary.get("p0_scoring_steps")),
            "readiness_ready_to_score_steps": as_int(scoring_summary.get("ready_to_score_steps")),
            "missing_output_surfaces": as_int(output_summary.get("missing_output_surfaces")),
            "expected_live_calls": as_int(output_summary.get("expected_live_calls")),
            "metric_contract_count": as_int(metric_summary.get("metric_contract_count")),
            "schema_contract_count": as_int(schema_summary.get("schema_contract_count")),
            "scorecard_rows": as_int(scorecard_summary.get("scorecard_rows")),
            "latency_claim_rows": as_int(latency_summary.get("latency_claim_rows")),
            "ready_to_promote_count": as_int(promotion_summary.get("ready_to_promote_count")),
            "traceability_rows": as_int(traceability_summary.get("traceability_rows")),
            "live_calls_performed_by_builder": 0,
            "no_scoring_commands_executed": True,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(plan: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "step_order",
        "scoring_execution_id",
        "priority",
        "surface_id",
        "execution_phase",
        "current_state",
        "prerequisite_gate",
        "command",
        "output_artifacts",
        "success_gate",
        "promotion_gate",
        "claim_boundary",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in plan["rows"]:
            out = dict(row)
            out["output_artifacts"] = "; ".join(out["output_artifacts"])
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def write_markdown(plan: dict[str, Any], path: Path) -> None:
    summary = plan["summary"]
    lines = [
        "# Post-Live Scoring Execution Plan",
        "",
        f"- Runtime contract: `{plan['runtime_contract']}`",
        f"- Status: `{plan['status']}`",
        f"- Scoring execution steps: `{summary['scoring_execution_steps']}`",
        f"- P0 / P1 execution steps: `{summary['p0_execution_steps']}` / `{summary['p1_execution_steps']}`",
        f"- Blocked execution steps: `{summary['blocked_execution_steps']}`",
        f"- Ready execution steps: `{summary['ready_execution_steps']}`",
        f"- Scoring commands: `{summary['scoring_commands']}`",
        f"- P0 scoring steps: `{summary['p0_scoring_steps']}`",
        f"- Readiness ready to score: `{summary['readiness_ready_to_score_steps']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- Expected live calls: `{summary['expected_live_calls']}`",
        f"- Metric contracts: `{summary['metric_contract_count']}`",
        f"- Schema contracts: `{summary['schema_contract_count']}`",
        f"- Scorecard rows: `{summary['scorecard_rows']}`",
        f"- Latency claim rows: `{summary['latency_claim_rows']}`",
        f"- Ready to promote: `{summary['ready_to_promote_count']}`",
        f"- Traceability rows: `{summary['traceability_rows']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No scoring commands executed: `{summary['no_scoring_commands_executed']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| # | Step | Priority | Surface | Phase | State | Promotion gate | Claim boundary |",
        "|---:|---|---|---|---|---|---|---|",
    ]
    for row in plan["rows"]:
        lines.append(
            f"| {row['step_order']} | `{row['scoring_execution_id']}` | `{row['priority']}` | "
            f"`{row['surface_id']}` | `{row['execution_phase']}` | `{row['current_state']}` | "
            f"`{row['promotion_gate']}` | `{row['claim_boundary']}` |"
        )
    lines.extend(["", "## Commands", ""])
    for row in plan["rows"]:
        lines.extend(
            [
                f"### {row['step_order']}. {row['scoring_execution_id']}",
                "",
                f"- Prerequisite gate: `{row['prerequisite_gate']}`",
                f"- Success gate: `{row['success_gate']}`",
                "",
                "```bash",
                row["command"],
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Reading",
            "",
            "- This plan orders post-live scoring commands after live output audit has clean complete outputs.",
            "- DeepSeek P0 safety must pass before the full split20 comparison can support latency promotion.",
            "- Omni48 remains label-only and Qwen remains fallback-only unless a later promotion gate changes those claim boundaries.",
            "- The builder performs no live/API/model/scoring calls and writes no secret values.",
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
