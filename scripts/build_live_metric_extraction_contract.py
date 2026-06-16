#!/usr/bin/env python3
"""Build a no-live-call metric extraction contract for pending live outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_metric_extraction_contract.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_metric_extraction_contract.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_metric_extraction_contract.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def scoring_step_by_id(scoring: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("scoring_id")): row for row in scoring.get("scoring_steps", [])}


def row(
    metric_id: str,
    surface_id: str,
    priority: str,
    metric_family: str,
    scoring_dependency: str,
    statistic_fields: list[str],
    promotion_gate: str,
    current_status: str,
    claim_status: str,
    scoring_steps: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    scoring = scoring_steps.get(scoring_dependency, {})
    return {
        "metric_id": metric_id,
        "surface_id": surface_id,
        "priority": priority,
        "metric_family": metric_family,
        "scoring_dependency": scoring_dependency,
        "expected_input_calls": as_int(scoring.get("expected_input_calls")),
        "coverage_gate": scoring.get("coverage_gate", "blocked_missing_output"),
        "current_status": current_status,
        "statistic_fields": "; ".join(statistic_fields),
        "input_artifacts": "; ".join(scoring.get("input_artifacts", [])),
        "output_artifacts": "; ".join(scoring.get("output_artifacts", [])),
        "promotion_gate": promotion_gate,
        "claim_status": claim_status,
    }


def build_contract(root: Path) -> dict[str, Any]:
    scoring = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    output = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    postrun = read_json(root / "outputs/research_progress_snapshot/live_postrun_metrics_closure.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    timing = read_json(root / "outputs/research_progress_snapshot/live_execution_timing_plan.json")
    failure = read_json(root / "outputs/research_progress_snapshot/live_failure_recovery_playbook.json")
    steps = scoring_step_by_id(scoring)

    rows = [
        row(
            "deepseek_resume_safety_zero_harm",
            "deepseek_resume_after_top3",
            "P0",
            "llm_safety",
            "deepseek_resume_safety",
            ["harmful_accepts", "conservative_blocks", "missing_patch_eval", "parent_window_decision_override"],
            "deepseek_split20_resume_safety",
            "blocked_waiting_live_output",
            "not_claimable_until_resume_safety_summary_exists",
            steps,
        ),
        row(
            "deepseek_resume_call_latency",
            "deepseek_resume_after_top3",
            "P0",
            "llm_latency",
            "deepseek_full_split20_comparison",
            ["parent_windows", "split_calls", "original_max_call_seconds", "split_max_call_seconds", "split_parent_avg_max_call_seconds", "wall_seconds"],
            "deepseek_split20_resume_latency",
            "blocked_waiting_live_output",
            "not_claimable_until_full_split20_comparison_exists",
            steps,
        ),
        row(
            "deepseek_resume_token_multiplier",
            "deepseek_resume_after_top3",
            "P0",
            "llm_quota_efficiency",
            "deepseek_full_split20_comparison",
            ["split_total_tokens", "original_total_tokens", "token_multiplier"],
            "deepseek_split20_resume_latency",
            "blocked_waiting_live_output",
            "planning_support_until_full_split20_comparison_exists",
            steps,
        ),
        row(
            "qwen_backup_safety_zero_harm",
            "qwen_full_backup",
            "P1",
            "llm_backup_safety",
            "qwen_full_backup_safety",
            ["harmful_accepts", "conservative_blocks", "missing_patch_eval", "parent_window_decision_override"],
            "qwen_full_backup_claim",
            "blocked_waiting_live_output",
            "fallback_only_not_primary_claim",
            steps,
        ),
        row(
            "qwen_backup_call_latency",
            "qwen_full_backup",
            "P1",
            "llm_backup_latency",
            "qwen_full_backup_comparison",
            ["parent_windows", "split_calls", "split_max_call_seconds", "wall_seconds", "token_multiplier"],
            "qwen_full_backup_claim",
            "blocked_waiting_live_output",
            "fallback_only_not_primary_latency_claim",
            steps,
        ),
        row(
            "omni48_label_quality",
            "omni48_label_only",
            "P1",
            "omni_label_quality",
            "omni48_label_summary",
            ["high_positive_rate", "clean_false_positive_rate", "quarantines", "defers", "risk_counts"],
            "omni48_label_metrics",
            "blocked_waiting_live_output",
            "label_only_no_timeline_writeback",
            steps,
        ),
        row(
            "omni48_call_latency",
            "omni48_label_only",
            "P1",
            "omni_call_latency",
            "omni48_label_summary",
            ["avg_call_seconds", "p95_call_seconds", "max_call_seconds"],
            "omni48_label_metrics",
            "blocked_waiting_live_output",
            "pending_96_call_live_latency",
            steps,
        ),
        row(
            "post_live_promotion_sync",
            "all_live_surfaces",
            "P0",
            "promotion_traceability",
            "post_live_claim_promotion_gate",
            ["ready_to_promote_count", "traceability_rows", "fully_covered_rows", "missing_source_rows"],
            "report_ppt_sync_after_promotion",
            "blocked_waiting_live_output",
            "promote_only_after_output_audit_scoring_slo_and_traceability_pass",
            steps,
        ),
    ]
    output_summary = output.get("summary", {})
    scoring_summary = scoring.get("summary", {})
    promotion_summary = promotion.get("summary", {})
    timing_summary = timing.get("summary", {})

    return {
        "runtime_contract": "live_metric_extraction_contract_no_live_calls",
        "status": "blocked_waiting_live_outputs",
        "source_contracts": {
            "live_scoring_readiness": scoring.get("runtime_contract", ""),
            "live_output_audit": output.get("runtime_contract", ""),
            "live_postrun_metrics_closure": postrun.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
            "live_execution_timing_plan": timing.get("runtime_contract", ""),
            "live_failure_recovery_playbook": failure.get("runtime_contract", ""),
        },
        "summary": {
            "metric_contract_count": len(rows),
            "p0_metric_contracts": sum(1 for item in rows if item["priority"] == "P0"),
            "time_metric_contracts": sum(1 for item in rows if "latency" in item["metric_family"]),
            "safety_metric_contracts": sum(1 for item in rows if "safety" in item["metric_family"]),
            "omni_metric_contracts": sum(1 for item in rows if item["surface_id"] == "omni48_label_only"),
            "promotion_metric_contracts": sum(1 for item in rows if item["metric_family"] == "promotion_traceability"),
            "blocked_metric_contracts": sum(1 for item in rows if item["current_status"].startswith("blocked")),
            "required_scoring_steps": as_int(scoring_summary.get("scoring_step_count")),
            "ready_to_score_steps": as_int(scoring_summary.get("ready_to_score_steps")),
            "expected_live_calls": as_int(output_summary.get("expected_live_calls")),
            "expected_input_calls": as_int(scoring_summary.get("expected_input_calls")),
            "deepseek_resume_expected_calls": as_int(scoring_summary.get("deepseek_resume_expected_calls")),
            "qwen_full_expected_calls": as_int(scoring_summary.get("qwen_full_expected_calls")),
            "omni48_expected_calls": as_int(scoring_summary.get("omni48_expected_calls")),
            "missing_output_surfaces": as_int(output_summary.get("missing_output_surfaces")),
            "ready_to_promote_count": as_int(promotion_summary.get("ready_to_promote_count")),
            "deepseek_estimated_wall_seconds": timing_summary.get("deepseek_estimated_wall_seconds", ""),
            "live_calls_performed_by_builder": 0,
            "no_scoring_commands_executed": True,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(contract: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "metric_id",
        "surface_id",
        "priority",
        "metric_family",
        "scoring_dependency",
        "expected_input_calls",
        "coverage_gate",
        "current_status",
        "statistic_fields",
        "input_artifacts",
        "output_artifacts",
        "promotion_gate",
        "claim_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in contract["rows"]:
            writer.writerow({key: item.get(key, "") for key in fieldnames})


def write_markdown(contract: dict[str, Any], path: Path) -> None:
    summary = contract["summary"]
    lines = [
        "# Live Metric Extraction Contract",
        "",
        f"- Runtime contract: `{contract['runtime_contract']}`",
        f"- Status: `{contract['status']}`",
        f"- Metric contracts: `{summary['metric_contract_count']}`",
        f"- P0 metric contracts: `{summary['p0_metric_contracts']}`",
        f"- Time metric contracts: `{summary['time_metric_contracts']}`",
        f"- Safety metric contracts: `{summary['safety_metric_contracts']}`",
        f"- Omni metric contracts: `{summary['omni_metric_contracts']}`",
        f"- Ready to score: `{summary['ready_to_score_steps']}`",
        f"- Expected live calls: `{summary['expected_live_calls']}`",
        f"- Expected input calls: `{summary['expected_input_calls']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- Ready to promote: `{summary['ready_to_promote_count']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No scoring commands executed: `{summary['no_scoring_commands_executed']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Metric | Surface | Priority | Family | Dependency | Fields | Promotion gate | Claim status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in contract["rows"]:
        lines.append(
            f"| `{item['metric_id']}` | `{item['surface_id']}` | `{item['priority']}` | "
            f"`{item['metric_family']}` | `{item['scoring_dependency']}` | {item['statistic_fields']} | "
            f"`{item['promotion_gate']}` | `{item['claim_status']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This contract defines which post-live metrics may be extracted after output audit and scoring readiness unblock.",
            "- DeepSeek P0 metrics require both resume safety and full split20 comparison outputs before promotion.",
            "- Qwen remains fallback-only unless a later promotion gate explicitly changes that boundary.",
            "- Omni48 metrics are label-only and cannot write timeline changes back.",
            "- The builder only reads local artifacts; it runs no scoring, live/API/model calls, and writes no secrets.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    contract = build_contract(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(contract, args.output_md)
    write_csv(contract, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
