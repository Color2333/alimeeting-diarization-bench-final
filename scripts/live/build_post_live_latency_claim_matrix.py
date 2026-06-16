#!/usr/bin/env python3
"""Build a no-live-call matrix for post-live latency claim promotion."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_latency_claim_matrix.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_latency_claim_matrix.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_latency_claim_matrix.csv")


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


def metric_by_id(rows: list[dict[str, Any]], metric_id: str) -> dict[str, Any]:
    return next((row for row in rows if row.get("metric_id") == metric_id), {})


def matrix_row(
    latency_claim_id: str,
    priority: str,
    latency_surface: str,
    current_state: str,
    current_metric_or_budget: str,
    promotion_gate: str,
    required_evidence: str,
    report_ppt_effect: str,
    claim_boundary: str,
) -> dict[str, Any]:
    return {
        "latency_claim_id": latency_claim_id,
        "priority": priority,
        "latency_surface": latency_surface,
        "current_state": current_state,
        "current_metric_or_budget": current_metric_or_budget,
        "promotion_gate": promotion_gate,
        "required_evidence": required_evidence,
        "report_ppt_effect": report_ppt_effect,
        "claim_boundary": claim_boundary,
    }


def build_matrix(root: Path) -> dict[str, Any]:
    ledger = read_json(root / "outputs/research_progress_snapshot/runtime_latency_budget_ledger.json")
    slo = read_json(root / "outputs/research_progress_snapshot/stage_latency_slo_audit.json")
    risk = read_json(root / "outputs/research_progress_snapshot/latency_risk_margin_audit.json")
    timing = read_json(root / "outputs/research_progress_snapshot/live_execution_timing_plan.json")
    metric = read_json(root / "outputs/research_progress_snapshot/live_metric_extraction_contract.json")
    scorecard = read_json(root / "outputs/research_progress_snapshot/post_live_acceptance_scorecard.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    handoff = read_json(root / "outputs/research_progress_snapshot/live_execution_handoff_packet.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")

    ledger_rows = ledger.get("rows", [])
    metric_rows = metric.get("rows", [])
    slo_summary = slo.get("summary", {})
    risk_summary = risk.get("summary", {})
    timing_summary = timing.get("summary", {})
    scorecard_summary = scorecard.get("summary", {})
    promotion_summary = promotion.get("summary", {})
    handoff_summary = handoff.get("summary", {})
    trace_summary = traceability.get("summary", {})

    fast = stage_by_id(ledger_rows, "fast_first_output")
    rule = stage_by_id(ledger_rows, "rule_writeback")
    guard = stage_by_id(ledger_rows, "runtime_safe_llm_guard")
    review = stage_by_id(ledger_rows, "llm_review_signal")
    deepseek_metric = metric_by_id(metric_rows, "deepseek_resume_call_latency")
    qwen_metric = metric_by_id(metric_rows, "qwen_backup_call_latency")
    omni_metric = metric_by_id(metric_rows, "omni48_call_latency")

    rows = [
        matrix_row(
            "fast_first_output_current",
            "P0",
            "runtime_120_windows",
            "claim_now_preserve",
            f"avg {fast.get('avg_seconds')}s / p95 {fast.get('p95_seconds')}s",
            "current_claim_now_slo",
            "stage_latency_slo_audit claim-now row remains pass",
            "keep current first-output latency claim in report/PPT",
            "claim_now_latency_preserve",
        ),
        matrix_row(
            "rule_writeback_current",
            "P0",
            "runtime_120_windows",
            "claim_now_preserve",
            f"avg {rule.get('avg_seconds')}s / p95 {rule.get('p95_seconds')}s",
            "current_claim_now_slo",
            "stage_latency_slo_audit claim-now row remains pass",
            "keep current bounded writeback latency claim in report/PPT",
            "claim_now_latency_preserve",
        ),
        matrix_row(
            "runtime_safe_guard_current",
            "P0",
            "104_proxy_flagged_windows",
            "claim_now_preserve_with_tight_margin_watch",
            f"avg {guard.get('avg_seconds')}s / p95 {guard.get('p95_seconds')}s / margin {risk_summary.get('guard_p95_margin_seconds')}s",
            "current_claim_now_slo_and_risk_watch",
            "4/4 SLO remains pass and guard risk remains explicit tight_margin",
            "keep current guard latency claim but flag tight margin before broader promotion",
            "claim_now_latency_preserve_no_broader_claim",
        ),
        matrix_row(
            "llm_review_signal_current",
            "P0",
            "4_review_cases",
            "claim_now_memory_protection_preserve",
            f"avg {review.get('avg_seconds')}s / p95 {review.get('p95_seconds')}s",
            "current_claim_now_review_only",
            "review signal remains memory-protection only and no timeline override",
            "keep review timing as memory-protection evidence only",
            "review_only_no_timeline_override",
        ),
        matrix_row(
            "deepseek_split20_full_surface",
            "P0",
            "104_parent_windows_147_split_calls",
            "blocked_waiting_live_outputs",
            f"planned resume {timing_summary.get('deepseek_resume_calls')} calls / estimated wall {timing_summary.get('deepseek_estimated_wall_seconds')}s",
            "deepseek_split20_resume_latency",
            f"{deepseek_metric.get('statistic_fields', '')}; output audit; safety summary harmful_accepts == 0; full comparison summary",
            "promote split20 from smoke/planning to full-surface latency only after post-live gates pass",
            "not_claimable_until_resume_output_audit_scoring_and_traceability",
        ),
        matrix_row(
            "omni48_label_latency",
            "P1",
            "48_windows_96_calls",
            "blocked_waiting_live_outputs",
            "clip-model seconds proxy 768.0; first-text/total latency pending",
            "omni48_label_metrics",
            f"{omni_metric.get('statistic_fields', '')}; 96 schema_ok rows; label-only metrics",
            "report Omni48 call latency as label-only metrics, never timeline writeback",
            "label_only_latency_not_guard_or_timeline_claim",
        ),
        matrix_row(
            "qwen_full_backup_latency",
            "P1",
            "104_parent_windows_147_split_calls",
            "fallback_only_waiting_credentials",
            f"fallback budget {timing_summary.get('qwen_estimated_wall_seconds')}s",
            "qwen_full_backup_claim",
            f"{qwen_metric.get('statistic_fields', '')}; fallback safety/comparison summary",
            "keep Qwen out of primary latency claim unless promotion policy explicitly changes",
            "fallback_only_not_primary_latency_claim",
        ),
        matrix_row(
            "report_ppt_latency_sync",
            "P0",
            "report_ppt",
            "waiting_post_live_promotion",
            f"traceability {trace_summary.get('fully_covered_rows')}/{trace_summary.get('traceability_rows')}",
            "report_ppt_traceability_after_promotion",
            "refresh_latest_research_artifacts pass and latest validation failed_checks empty after any latency promotion",
            "force report/PPT wording to match promoted, fallback-only, and blocked latency surfaces",
            "report_ppt_sync_required_before_latency_claim_promotion",
        ),
    ]

    return {
        "runtime_contract": "post_live_latency_claim_matrix_no_live_calls",
        "status": "blocked_waiting_live_outputs",
        "source_contracts": {
            "runtime_latency_budget_ledger": ledger.get("runtime_contract", ""),
            "stage_latency_slo_audit": slo.get("runtime_contract", ""),
            "latency_risk_margin_audit": risk.get("runtime_contract", ""),
            "live_execution_timing_plan": timing.get("runtime_contract", ""),
            "live_metric_extraction_contract": metric.get("runtime_contract", ""),
            "post_live_acceptance_scorecard": scorecard.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
            "live_execution_handoff_packet": handoff.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "summary": {
            "latency_claim_rows": len(rows),
            "p0_latency_claim_rows": sum(1 for row in rows if row["priority"] == "P0"),
            "p1_latency_claim_rows": sum(1 for row in rows if row["priority"] == "P1"),
            "claim_now_preserve_rows": sum(1 for row in rows if row["current_state"].startswith("claim_now")),
            "blocked_or_waiting_rows": sum(1 for row in rows if "blocked" in row["current_state"] or "waiting" in row["current_state"]),
            "fallback_only_rows": sum(1 for row in rows if "fallback_only" in row["current_state"]),
            "label_only_rows": sum(1 for row in rows if "label_only" in row["claim_boundary"]),
            "tight_margin_rows": as_int(risk_summary.get("tight_margin_rows")),
            "claim_now_slo_pass": as_int(slo_summary.get("claim_now_slo_pass")),
            "claim_now_slo_rows": as_int(slo_summary.get("claim_now_slo_rows")),
            "guard_p95_margin_seconds": risk_summary.get("guard_p95_margin_seconds", ""),
            "expected_live_calls": as_int(scorecard_summary.get("expected_live_calls")),
            "missing_output_surfaces": as_int(scorecard_summary.get("missing_output_surfaces")),
            "deepseek_estimated_wall_seconds": timing_summary.get("deepseek_estimated_wall_seconds", ""),
            "qwen_estimated_wall_seconds": timing_summary.get("qwen_estimated_wall_seconds", ""),
            "omni48_label_only_calls": as_int(timing_summary.get("omni48_label_only_calls")),
            "ready_to_promote_count": as_int(promotion_summary.get("ready_to_promote_count")),
            "traceability_rows": as_int(trace_summary.get("traceability_rows")),
            "handoff_packet_rows": as_int(handoff_summary.get("packet_rows")),
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(matrix: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "latency_claim_id",
        "priority",
        "latency_surface",
        "current_state",
        "current_metric_or_budget",
        "promotion_gate",
        "required_evidence",
        "report_ppt_effect",
        "claim_boundary",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in matrix["rows"]:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_markdown(matrix: dict[str, Any], path: Path) -> None:
    summary = matrix["summary"]
    lines = [
        "# Post-Live Latency Claim Matrix",
        "",
        f"- Runtime contract: `{matrix['runtime_contract']}`",
        f"- Status: `{matrix['status']}`",
        f"- Latency claim rows: `{summary['latency_claim_rows']}`",
        f"- P0 / P1 rows: `{summary['p0_latency_claim_rows']}` / `{summary['p1_latency_claim_rows']}`",
        f"- Claim-now preserve rows: `{summary['claim_now_preserve_rows']}`",
        f"- Blocked/waiting rows: `{summary['blocked_or_waiting_rows']}`",
        f"- Fallback-only rows: `{summary['fallback_only_rows']}`",
        f"- Label-only rows: `{summary['label_only_rows']}`",
        f"- Tight-margin rows: `{summary['tight_margin_rows']}`",
        f"- Claim-now SLO pass: `{summary['claim_now_slo_pass']}/{summary['claim_now_slo_rows']}`",
        f"- Guard P95 margin seconds: `{summary['guard_p95_margin_seconds']}`",
        f"- Expected live calls: `{summary['expected_live_calls']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- DeepSeek estimated wall seconds: `{summary['deepseek_estimated_wall_seconds']}`",
        f"- Qwen estimated wall seconds: `{summary['qwen_estimated_wall_seconds']}`",
        f"- Omni48 label-only calls: `{summary['omni48_label_only_calls']}`",
        f"- Ready to promote: `{summary['ready_to_promote_count']}`",
        f"- Traceability rows: `{summary['traceability_rows']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Claim | Priority | Surface | State | Metric/budget | Promotion gate | Boundary |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in matrix["rows"]:
        lines.append(
            f"| `{row['latency_claim_id']}` | `{row['priority']}` | `{row['latency_surface']}` | "
            f"`{row['current_state']}` | {row['current_metric_or_budget']} | "
            f"`{row['promotion_gate']}` | `{row['claim_boundary']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This matrix separates current reportable latency claims from post-live claim candidates.",
            "- DeepSeek split20 can become full-surface latency evidence only after live output audit, safety scoring, comparison, and traceability pass.",
            "- Omni48 latency remains label-only; Qwen remains fallback-only unless a later promotion gate changes the boundary.",
            "- The builder reads local artifacts only; it performs no live/API/model/scoring calls and writes no secrets.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    matrix = build_matrix(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(matrix, args.output_md)
    write_csv(matrix, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
