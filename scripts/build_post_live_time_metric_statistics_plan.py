#!/usr/bin/env python3
"""Build a no-live-call statistics plan for post-live time metrics."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_time_metric_statistics_plan.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_time_metric_statistics_plan.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_time_metric_statistics_plan.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def stage_by_id(rows: list[dict[str, Any]], stage_id: str) -> dict[str, Any]:
    return next((row for row in rows if row.get("stage_id") == stage_id), {})


def stat_row(
    time_metric_id: str,
    priority: str,
    surface_id: str,
    current_state: str,
    statistic_family: str,
    source_artifacts: list[str],
    statistic_formula: str,
    promotion_gate: str,
    report_ppt_effect: str,
    claim_boundary: str,
    expected_rows: int = 0,
) -> dict[str, Any]:
    return {
        "time_metric_id": time_metric_id,
        "priority": priority,
        "surface_id": surface_id,
        "current_state": current_state,
        "statistic_family": statistic_family,
        "source_artifacts": source_artifacts,
        "statistic_formula": statistic_formula,
        "promotion_gate": promotion_gate,
        "report_ppt_effect": report_ppt_effect,
        "claim_boundary": claim_boundary,
        "expected_rows": expected_rows,
    }


def build_plan(root: Path) -> dict[str, Any]:
    ledger = read_json(root / "outputs/research_progress_snapshot/runtime_latency_budget_ledger.json")
    slo = read_json(root / "outputs/research_progress_snapshot/stage_latency_slo_audit.json")
    risk = read_json(root / "outputs/research_progress_snapshot/latency_risk_margin_audit.json")
    metric = read_json(root / "outputs/research_progress_snapshot/live_metric_extraction_contract.json")
    schema = read_json(root / "outputs/research_progress_snapshot/live_output_schema_contract.json")
    latency_matrix = read_json(root / "outputs/research_progress_snapshot/post_live_latency_claim_matrix.json")
    bundle = read_json(root / "outputs/research_progress_snapshot/live_execution_bundle.json")
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")

    ledger_rows = ledger.get("rows", [])
    fast = stage_by_id(ledger_rows, "fast_first_output")
    rule = stage_by_id(ledger_rows, "rule_writeback")
    guard = stage_by_id(ledger_rows, "runtime_safe_llm_guard")
    review = stage_by_id(ledger_rows, "llm_review_signal")
    metric_summary = metric.get("summary", {})
    schema_summary = schema.get("summary", {})
    matrix_summary = latency_matrix.get("summary", {})
    bundle_summary = bundle.get("summary", {})
    output_summary = output_audit.get("summary", {})
    promotion_summary = promotion.get("summary", {})
    trace_summary = traceability.get("summary", {})

    rows = [
        stat_row(
            "fast_first_output_latency_current",
            "P0",
            "runtime_120_windows",
            "claim_now_preserve",
            "stage_arrival_latency",
            ["outputs/research_progress_snapshot/runtime_latency_budget_ledger.md"],
            f"avg_seconds={fast.get('avg_seconds')}; p95_seconds={fast.get('p95_seconds')}; SLO avg<=1s and p95<=1s",
            "current_claim_now_slo",
            "keep current first visible update timing claim",
            "claim_now_latency_preserve",
        ),
        stat_row(
            "rule_writeback_latency_current",
            "P0",
            "runtime_120_windows",
            "claim_now_preserve",
            "stage_arrival_latency",
            ["outputs/research_progress_snapshot/runtime_latency_budget_ledger.md"],
            f"avg_seconds={rule.get('avg_seconds')}; p95_seconds={rule.get('p95_seconds')}; SLO avg<=30s and p95<=35s",
            "current_claim_now_slo",
            "keep bounded rule-writeback timing claim",
            "claim_now_latency_preserve",
        ),
        stat_row(
            "runtime_safe_guard_latency_current",
            "P0",
            "104_proxy_flagged_windows",
            "claim_now_preserve_with_tight_margin_watch",
            "stage_arrival_latency",
            [
                "outputs/research_progress_snapshot/runtime_latency_budget_ledger.md",
                "outputs/research_progress_snapshot/latency_risk_margin_audit.md",
            ],
            f"avg_seconds={guard.get('avg_seconds')}; p95_seconds={guard.get('p95_seconds')}; margin_seconds={risk.get('summary', {}).get('guard_p95_margin_seconds')}",
            "current_claim_now_slo_and_risk_watch",
            "keep current guard timing claim but retain tight-margin warning",
            "claim_now_latency_preserve_no_broader_claim",
        ),
        stat_row(
            "llm_review_signal_latency_current",
            "P0",
            "4_review_cases",
            "claim_now_memory_protection_preserve",
            "stage_arrival_latency",
            ["outputs/research_progress_snapshot/runtime_latency_budget_ledger.md"],
            f"avg_seconds={review.get('avg_seconds')}; p95_seconds={review.get('p95_seconds')}; memory-protection only",
            "current_claim_now_review_only",
            "keep review timing as memory-protection evidence only",
            "review_only_no_timeline_override",
        ),
        stat_row(
            "deepseek_resume_call_latency_stats",
            "P0",
            "deepseek_resume_after_top3",
            "blocked_waiting_live_outputs",
            "llm_call_latency",
            [
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl",
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_summary.json",
            ],
            "from successful JSONL rows: count, avg(call_seconds), p50, p95, max, wall_seconds, retry_count",
            "deepseek_split20_resume_latency",
            "feed full-surface split20 latency only after safety and comparison summaries pass",
            "not_claimable_until_resume_output_audit_scoring_and_traceability",
            as_int(metric_summary.get("deepseek_resume_expected_calls")),
        ),
        stat_row(
            "deepseek_parent_completion_latency_stats",
            "P0",
            "deepseek_resume_after_top3",
            "blocked_waiting_comparison_summary",
            "parent_window_completion_latency",
            ["outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.json"],
            "from split comparison: original_max_call_seconds vs split_max_call_seconds; parent avg/max; token_multiplier",
            "deepseek_split20_resume_latency",
            "promote split20 latency only if 104 parents / 147 calls are covered and harmful_accepts == 0",
            "required_before_full_surface_latency_claim",
            147,
        ),
        stat_row(
            "qwen_backup_latency_stats",
            "P1",
            "qwen_full_backup",
            "fallback_only_waiting_credentials",
            "fallback_llm_call_latency",
            ["outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl"],
            "fallback-only: count, avg(call_seconds), p95, max, wall_seconds, token_multiplier",
            "qwen_full_backup_claim",
            "keep as fallback timing context, not primary latency claim",
            "fallback_only_not_primary_latency_claim",
            as_int(metric_summary.get("qwen_full_expected_calls")),
        ),
        stat_row(
            "omni48_label_latency_stats",
            "P1",
            "omni48_label_only",
            "blocked_waiting_live_outputs",
            "omni_label_call_latency",
            ["outputs/omni_guard/omni_expansion_48_live.jsonl"],
            "label-only: avg(first_text_seconds if present), avg/p95/max(call_seconds), per-model split",
            "omni48_label_metrics",
            "report only as label latency and quality; never timeline writeback",
            "label_only_latency_not_guard_or_timeline_claim",
            as_int(metric_summary.get("omni48_expected_calls")),
        ),
        stat_row(
            "report_ppt_time_claim_refresh",
            "P0",
            "report_ppt",
            "waiting_post_live_promotion",
            "time_claim_traceability",
            [
                "outputs/research_progress_snapshot/post_live_latency_claim_matrix.md",
                "outputs/research_progress_snapshot/report_ppt_traceability.md",
            ],
            "after refresh: latest_artifact_validation pass; traceability fully covered; no missing source rows",
            "report_ppt_traceability_after_promotion",
            "force report/PPT wording to match claim-now, promoted, fallback-only, and blocked time surfaces",
            "report_ppt_sync_required_before_time_metric_claim_promotion",
        ),
    ]

    return {
        "runtime_contract": "post_live_time_metric_statistics_plan_no_live_calls",
        "status": "blocked_waiting_live_outputs",
        "source_contracts": {
            "runtime_latency_budget_ledger": ledger.get("runtime_contract", ""),
            "stage_latency_slo_audit": slo.get("runtime_contract", ""),
            "latency_risk_margin_audit": risk.get("runtime_contract", ""),
            "live_metric_extraction_contract": metric.get("runtime_contract", ""),
            "live_output_schema_contract": schema.get("runtime_contract", ""),
            "post_live_latency_claim_matrix": latency_matrix.get("runtime_contract", ""),
            "live_execution_bundle": bundle.get("runtime_contract", ""),
            "live_output_audit": output_audit.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "summary": {
            "time_stat_rows": len(rows),
            "p0_time_stat_rows": sum(1 for item in rows if item["priority"] == "P0"),
            "p1_time_stat_rows": sum(1 for item in rows if item["priority"] == "P1"),
            "claim_now_preserve_rows": sum(1 for item in rows if item["current_state"].startswith("claim_now")),
            "blocked_or_waiting_rows": sum(1 for item in rows if "blocked" in item["current_state"] or "waiting" in item["current_state"]),
            "fallback_only_rows": sum(1 for item in rows if "fallback_only" in item["current_state"] or "fallback_only" in item["claim_boundary"]),
            "label_only_rows": sum(1 for item in rows if "label_only" in item["claim_boundary"]),
            "stage_arrival_rows": sum(1 for item in rows if item["statistic_family"] == "stage_arrival_latency"),
            "post_live_stat_rows": sum(1 for item in rows if item["expected_rows"] > 0),
            "formula_count": len(rows),
            "claim_now_slo_pass": as_int(slo.get("summary", {}).get("claim_now_slo_pass")),
            "claim_now_slo_rows": as_int(slo.get("summary", {}).get("claim_now_slo_rows")),
            "guard_p95_margin_seconds": risk.get("summary", {}).get("guard_p95_margin_seconds", ""),
            "metric_contract_count": as_int(metric_summary.get("metric_contract_count")),
            "schema_contract_count": as_int(schema_summary.get("schema_contract_count")),
            "latency_claim_rows": as_int(matrix_summary.get("latency_claim_rows")),
            "planned_live_calls": as_int(bundle_summary.get("planned_live_calls")),
            "p0_planned_live_calls": as_int(bundle_summary.get("p0_planned_live_calls")),
            "expected_live_calls": as_int(output_summary.get("expected_live_calls")),
            "missing_output_surfaces": as_int(output_summary.get("missing_output_surfaces")),
            "ready_to_promote_count": as_int(promotion_summary.get("ready_to_promote_count")),
            "traceability_rows": as_int(trace_summary.get("traceability_rows")),
            "live_calls_performed_by_builder": 0,
            "no_scoring_commands_executed": True,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(plan: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "time_metric_id",
        "priority",
        "surface_id",
        "current_state",
        "statistic_family",
        "expected_rows",
        "source_artifacts",
        "statistic_formula",
        "promotion_gate",
        "report_ppt_effect",
        "claim_boundary",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in plan["rows"]:
            out = dict(row)
            out["source_artifacts"] = "; ".join(out["source_artifacts"])
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def write_markdown(plan: dict[str, Any], path: Path) -> None:
    summary = plan["summary"]
    lines = [
        "# Post-Live Time Metric Statistics Plan",
        "",
        f"- Runtime contract: `{plan['runtime_contract']}`",
        f"- Status: `{plan['status']}`",
        f"- Time statistic rows: `{summary['time_stat_rows']}`",
        f"- P0 / P1 rows: `{summary['p0_time_stat_rows']}` / `{summary['p1_time_stat_rows']}`",
        f"- Claim-now preserve rows: `{summary['claim_now_preserve_rows']}`",
        f"- Blocked/waiting rows: `{summary['blocked_or_waiting_rows']}`",
        f"- Fallback-only rows: `{summary['fallback_only_rows']}`",
        f"- Label-only rows: `{summary['label_only_rows']}`",
        f"- Stage-arrival rows: `{summary['stage_arrival_rows']}`",
        f"- Post-live statistic rows: `{summary['post_live_stat_rows']}`",
        f"- Formula count: `{summary['formula_count']}`",
        f"- Claim-now SLO pass: `{summary['claim_now_slo_pass']}/{summary['claim_now_slo_rows']}`",
        f"- Guard P95 margin seconds: `{summary['guard_p95_margin_seconds']}`",
        f"- Metric contracts: `{summary['metric_contract_count']}`",
        f"- Schema contracts: `{summary['schema_contract_count']}`",
        f"- Latency claim rows: `{summary['latency_claim_rows']}`",
        f"- Planned live calls: `{summary['planned_live_calls']}`",
        f"- P0 planned live calls: `{summary['p0_planned_live_calls']}`",
        f"- Expected live calls: `{summary['expected_live_calls']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- Ready to promote: `{summary['ready_to_promote_count']}`",
        f"- Traceability rows: `{summary['traceability_rows']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No scoring commands executed: `{summary['no_scoring_commands_executed']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Metric | Priority | Surface | State | Family | Expected rows | Boundary |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in plan["rows"]:
        lines.append(
            f"| `{row['time_metric_id']}` | `{row['priority']}` | `{row['surface_id']}` | "
            f"`{row['current_state']}` | `{row['statistic_family']}` | {row['expected_rows']} | "
            f"`{row['claim_boundary']}` |"
        )
    lines.extend(["", "## Formulas", ""])
    for row in plan["rows"]:
        lines.extend(
            [
                f"### {row['time_metric_id']}",
                "",
                f"- Source artifacts: `{'; '.join(row['source_artifacts'])}`",
                f"- Formula: `{row['statistic_formula']}`",
                f"- Promotion gate: `{row['promotion_gate']}`",
                f"- Report/PPT effect: `{row['report_ppt_effect']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Reading",
            "",
            "- This plan fixes the statistics formulas for current and post-live timing metrics.",
            "- Claim-now rows preserve existing stage-arrival timing; post-live rows stay blocked until live outputs, scoring, promotion, and traceability pass.",
            "- Qwen remains fallback-only and Omni48 remains label-only, so neither can promote a primary timeline latency claim from this plan.",
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
