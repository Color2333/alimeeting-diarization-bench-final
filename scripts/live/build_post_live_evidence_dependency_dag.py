#!/usr/bin/env python3
"""Build a no-live-call evidence dependency DAG for post-live promotion."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_evidence_dependency_dag.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_evidence_dependency_dag.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_evidence_dependency_dag.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def dag_row(
    node_order: int,
    node_id: str,
    priority: str,
    stage: str,
    current_state: str,
    depends_on: list[str],
    evidence_artifacts: list[str],
    success_gate: str,
    claim_boundary: str,
) -> dict[str, Any]:
    return {
        "node_order": node_order,
        "node_id": node_id,
        "priority": priority,
        "stage": stage,
        "current_state": current_state,
        "depends_on": depends_on,
        "evidence_artifacts": evidence_artifacts,
        "success_gate": success_gate,
        "claim_boundary": claim_boundary,
    }


def build_dag(root: Path) -> dict[str, Any]:
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    scoring_readiness = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    scoring_plan = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_execution_plan.json")
    scoring_output_audit = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_output_audit.json")
    metric_contract = read_json(root / "outputs/research_progress_snapshot/live_metric_extraction_contract.json")
    schema_contract = read_json(root / "outputs/research_progress_snapshot/live_output_schema_contract.json")
    scorecard = read_json(root / "outputs/research_progress_snapshot/post_live_acceptance_scorecard.json")
    latency_matrix = read_json(root / "outputs/research_progress_snapshot/post_live_latency_claim_matrix.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")

    output_summary = output_audit.get("summary", {})
    scoring_summary = scoring_readiness.get("summary", {})
    scoring_plan_summary = scoring_plan.get("summary", {})
    scoring_output_summary = scoring_output_audit.get("summary", {})
    metric_summary = metric_contract.get("summary", {})
    schema_summary = schema_contract.get("summary", {})
    scorecard_summary = scorecard.get("summary", {})
    latency_summary = latency_matrix.get("summary", {})
    promotion_summary = promotion.get("summary", {})
    traceability_summary = traceability.get("summary", {})

    rows = [
        dag_row(
            1,
            "live_outputs_complete",
            "P0",
            "live_output_coverage",
            "blocked_missing_output",
            [],
            ["outputs/research_progress_snapshot/live_output_audit.md"],
            "expected_live_calls == 382 and missing_output_surfaces == 0",
            "no_metric_claim_until_live_outputs_complete",
        ),
        dag_row(
            2,
            "output_schema_clean",
            "P0",
            "schema_validation",
            "blocked_waiting_live_outputs",
            ["live_outputs_complete"],
            [
                "outputs/research_progress_snapshot/live_output_schema_contract.md",
                "outputs/research_progress_snapshot/live_output_audit.md",
            ],
            "all live/scoring/promotion schema contracts parse with required fields present",
            "schema_gate_no_live_metric_claim",
        ),
        dag_row(
            3,
            "deepseek_resume_safety_score",
            "P0",
            "safety_scoring",
            "blocked_missing_output",
            ["output_schema_clean"],
            [
                "outputs/research_progress_snapshot/live_scoring_readiness.md",
                "outputs/research_progress_snapshot/post_live_scoring_execution_plan.md",
            ],
            "DeepSeek resume safety summary exists and harmful_accepts == 0",
            "required_before_zero_harm_safety_claim",
        ),
        dag_row(
            4,
            "deepseek_split20_latency_score",
            "P0",
            "latency_comparison",
            "blocked_waiting_safety_score",
            ["deepseek_resume_safety_score"],
            [
                "outputs/research_progress_snapshot/post_live_scoring_execution_plan.md",
                "outputs/research_progress_snapshot/post_live_latency_claim_matrix.md",
            ],
            "full split20 comparison covers 104 parents / 147 planned calls",
            "required_before_full_surface_latency_claim",
        ),
        dag_row(
            5,
            "omni48_label_metrics",
            "P1",
            "label_metric_scoring",
            "blocked_missing_output",
            ["output_schema_clean"],
            [
                "outputs/research_progress_snapshot/live_metric_extraction_contract.md",
                "outputs/research_progress_snapshot/post_live_scoring_execution_plan.md",
            ],
            "96 Omni48 label-only rows produce quality and latency summaries",
            "label_only_no_timeline_writeback",
        ),
        dag_row(
            6,
            "qwen_backup_metrics",
            "P1",
            "fallback_metric_scoring",
            "fallback_only_waiting_credentials",
            ["output_schema_clean"],
            [
                "outputs/research_progress_snapshot/live_metric_extraction_contract.md",
                "outputs/research_progress_snapshot/post_live_scoring_execution_plan.md",
            ],
            "Qwen fallback safety/comparison summaries exist and remain marked fallback-only",
            "fallback_only_not_primary_claim",
        ),
        dag_row(
            7,
            "metric_extraction_complete",
            "P0",
            "metric_extraction",
            "blocked_waiting_scoring_outputs",
            [
                "deepseek_resume_safety_score",
                "deepseek_split20_latency_score",
                "omni48_label_metrics",
                "qwen_backup_metrics",
            ],
            [
                "outputs/research_progress_snapshot/live_metric_extraction_contract.md",
                "outputs/research_progress_snapshot/post_live_acceptance_scorecard.md",
                "outputs/research_progress_snapshot/post_live_scoring_output_audit.md",
            ],
            "all 8 metric contracts are populated with post-live values or explicit fallback labels and scoring output audit is promotion-ready",
            "metric_extraction_schema_no_live_metric_claim",
        ),
        dag_row(
            8,
            "latency_claim_matrix_update",
            "P0",
            "latency_claim_boundary",
            "blocked_waiting_metric_extraction",
            ["metric_extraction_complete"],
            [
                "outputs/research_progress_snapshot/post_live_latency_claim_matrix.md",
                "outputs/research_progress_snapshot/post_live_acceptance_scorecard.md",
            ],
            "latency matrix separates claim-now, promoted, blocked, label-only, and fallback-only rows",
            "latency_claim_matrix_no_new_metric_claim_until_promotion",
        ),
        dag_row(
            9,
            "promotion_gate_pass",
            "P0",
            "claim_promotion",
            "blocked_waiting_traceability_and_promotion_inputs",
            ["latency_claim_matrix_update"],
            [
                "outputs/research_progress_snapshot/post_live_claim_promotion_gate.md",
                "outputs/research_progress_snapshot/report_ppt_traceability.md",
            ],
            "ready_to_promote_count only increases after output audit, scoring, SLO, and traceability pass",
            "promote_only_after_output_audit_scoring_slo_and_traceability_pass",
        ),
        dag_row(
            10,
            "report_ppt_refresh_validation",
            "P0",
            "report_ppt_validation",
            "blocked_waiting_promotion_refresh",
            ["promotion_gate_pass"],
            [
                "outputs/research_progress_snapshot/latest_artifact_validation.md",
                "outputs/research_progress_snapshot/report_ppt_traceability.md",
                "docs/reports/2026-06-03-realtime-dual-agent-roadmap.md",
                "../研究进展汇报.pptx",
            ],
            "refresh pass; validator failed_checks empty; report/PPT traceability fully covered",
            "report_ppt_sync_required_before_claim_promotion",
        ),
    ]

    return {
        "runtime_contract": "post_live_evidence_dependency_dag_no_live_calls",
        "status": "blocked_waiting_live_outputs",
        "source_contracts": {
            "live_output_audit": output_audit.get("runtime_contract", ""),
            "live_scoring_readiness": scoring_readiness.get("runtime_contract", ""),
            "post_live_scoring_execution_plan": scoring_plan.get("runtime_contract", ""),
            "post_live_scoring_output_audit": scoring_output_audit.get("runtime_contract", ""),
            "live_metric_extraction_contract": metric_contract.get("runtime_contract", ""),
            "live_output_schema_contract": schema_contract.get("runtime_contract", ""),
            "post_live_acceptance_scorecard": scorecard.get("runtime_contract", ""),
            "post_live_latency_claim_matrix": latency_matrix.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "summary": {
            "dag_nodes": len(rows),
            "p0_dag_nodes": sum(1 for row in rows if row["priority"] == "P0"),
            "p1_dag_nodes": sum(1 for row in rows if row["priority"] == "P1"),
            "blocked_nodes": sum(
                1 for row in rows if "blocked" in row["current_state"] or "waiting" in row["current_state"]
            ),
            "fallback_only_nodes": sum(1 for row in rows if "fallback_only" in row["current_state"]),
            "label_only_nodes": sum(1 for row in rows if "label_only" in row["claim_boundary"]),
            "ready_nodes": sum(1 for row in rows if str(row["current_state"]).startswith("ready")),
            "expected_live_calls": as_int(output_summary.get("expected_live_calls")),
            "missing_output_surfaces": as_int(output_summary.get("missing_output_surfaces")),
            "ready_to_score_steps": as_int(scoring_summary.get("ready_to_score_steps")),
            "scoring_execution_steps": as_int(scoring_plan_summary.get("scoring_execution_steps")),
            "scoring_output_promotion_ready_rows": as_int(scoring_output_summary.get("promotion_ready_rows")),
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


def write_csv(dag: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "node_order",
        "node_id",
        "priority",
        "stage",
        "current_state",
        "depends_on",
        "evidence_artifacts",
        "success_gate",
        "claim_boundary",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in dag["rows"]:
            out = dict(row)
            out["depends_on"] = "; ".join(out["depends_on"])
            out["evidence_artifacts"] = "; ".join(out["evidence_artifacts"])
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def write_markdown(dag: dict[str, Any], path: Path) -> None:
    summary = dag["summary"]
    lines = [
        "# Post-Live Evidence Dependency DAG",
        "",
        f"- Runtime contract: `{dag['runtime_contract']}`",
        f"- Status: `{dag['status']}`",
        f"- DAG nodes: `{summary['dag_nodes']}`",
        f"- P0 / P1 nodes: `{summary['p0_dag_nodes']}` / `{summary['p1_dag_nodes']}`",
        f"- Blocked nodes: `{summary['blocked_nodes']}`",
        f"- Fallback-only nodes: `{summary['fallback_only_nodes']}`",
        f"- Label-only nodes: `{summary['label_only_nodes']}`",
        f"- Ready nodes: `{summary['ready_nodes']}`",
        f"- Expected live calls: `{summary['expected_live_calls']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- Ready to score: `{summary['ready_to_score_steps']}`",
        f"- Scoring execution steps: `{summary['scoring_execution_steps']}`",
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
        "| # | Node | Priority | Stage | State | Depends on | Boundary |",
        "|---:|---|---|---|---|---|---|",
    ]
    for row in dag["rows"]:
        deps = ", ".join(f"`{dep}`" for dep in row["depends_on"]) or "`root`"
        lines.append(
            f"| {row['node_order']} | `{row['node_id']}` | `{row['priority']}` | "
            f"`{row['stage']}` | `{row['current_state']}` | {deps} | `{row['claim_boundary']}` |"
        )
    lines.extend(["", "## Gates", ""])
    for row in dag["rows"]:
        lines.extend(
            [
                f"### {row['node_order']}. {row['node_id']}",
                "",
                f"- Evidence artifacts: `{'; '.join(row['evidence_artifacts'])}`",
                f"- Success gate: `{row['success_gate']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Reading",
            "",
            "- This DAG fixes the dependency order from live output coverage through schema, scoring, metric extraction, latency claim boundary, promotion, and report/PPT validation.",
            "- DeepSeek safety remains upstream of full split20 latency promotion; Omni48 remains label-only and Qwen remains fallback-only.",
            "- The builder performs no live/API/model/scoring calls, writes no secret values, and makes no new metric claim.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    dag = build_dag(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(dag, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(dag, args.output_md)
    write_csv(dag, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
