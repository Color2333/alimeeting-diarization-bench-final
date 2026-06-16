#!/usr/bin/env python3
"""Audit post-live time metric extraction receipts without live or scoring calls."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_time_metric_receipt_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_time_metric_receipt_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_time_metric_receipt_audit.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def receipt_row(
    *,
    receipt_id: str,
    status: str,
    observed_state: str,
    success_gate: str,
    blocker: str,
    next_action: str,
    source_artifacts: list[str],
    claim_boundary: str,
) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "status": status,
        "observed_state": observed_state,
        "success_gate": success_gate,
        "blocker": blocker,
        "next_action": next_action,
        "source_artifacts": source_artifacts,
        "source_artifacts_exist": all((ROOT / source).exists() for source in source_artifacts if source.startswith("outputs/")),
        "claim_boundary": claim_boundary,
        "live_calls_performed_by_builder": 0,
    }


def build_audit(root: Path) -> dict[str, Any]:
    stats_plan = read_json(root / "outputs/research_progress_snapshot/post_live_time_metric_statistics_plan.json")
    extractor = read_json(root / "outputs/research_progress_snapshot/post_live_time_metric_extractor.json")
    scoring_receipt = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_receipt_audit.json")
    scoring_output = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_output_audit.json")
    latency_matrix = read_json(root / "outputs/research_progress_snapshot/post_live_latency_claim_matrix.json")
    promotion_preflight = read_json(root / "outputs/research_progress_snapshot/post_live_promotion_preflight_audit.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")

    stats_summary = stats_plan.get("summary", {})
    extractor_summary = extractor.get("summary", {})
    scoring_receipt_summary = scoring_receipt.get("summary", {})
    scoring_output_summary = scoring_output.get("summary", {})
    latency_summary = latency_matrix.get("summary", {})
    preflight_summary = promotion_preflight.get("summary", {})
    trace_summary = traceability.get("summary", {})

    plan_aligned = (
        stats_plan.get("runtime_contract") == "post_live_time_metric_statistics_plan_no_live_calls"
        and as_int(stats_summary.get("time_stat_rows")) == 9
        and as_int(stats_summary.get("post_live_stat_rows")) == 4
        and as_int(stats_summary.get("expected_live_calls")) == 382
        and as_int(stats_summary.get("traceability_rows")) == as_int(trace_summary.get("traceability_rows"))
    )
    extractor_ready = (
        extractor.get("runtime_contract") == "post_live_time_metric_extractor_no_live_calls"
        and as_int(extractor_summary.get("extractor_rows")) == 3
        and as_int(extractor_summary.get("ready_time_metric_rows")) == 3
        and as_int(extractor_summary.get("missing_output_rows")) == 0
    )
    metrics_computed = (
        extractor_ready
        and as_int(extractor_summary.get("computed_time_metric_rows")) == 3
        and as_int(extractor_summary.get("successful_rows_total")) == as_int(extractor_summary.get("expected_rows_total"))
        and as_int(extractor_summary.get("observed_rows_total")) >= as_int(extractor_summary.get("expected_rows_total"))
    )
    parse_clean = (
        extractor_ready
        and metrics_computed
        and as_int(extractor_summary.get("parse_error_rows")) == 0
        and as_int(extractor_summary.get("retry_rows_total")) >= 0
    )
    scoring_ready = (
        scoring_receipt.get("status") == "ready_for_promotion_review"
        and scoring_receipt_summary.get("ready_for_promotion_review") is True
        and as_int(scoring_output_summary.get("promotion_ready_rows")) > 0
    )
    promotion_ready = (
        metrics_computed
        and scoring_ready
        and promotion_preflight.get("status") == "ready_for_promotion_review"
        and preflight_summary.get("ready_for_promotion_review") is True
    )

    rows = [
        receipt_row(
            receipt_id="time_statistics_plan_alignment",
            status="pass" if plan_aligned else "blocked",
            observed_state=(
                f"time stat rows {stats_summary.get('time_stat_rows', 0)}; "
                f"post-live stat rows {stats_summary.get('post_live_stat_rows', 0)}; "
                f"expected live calls {stats_summary.get('expected_live_calls', 0)}"
            ),
            success_gate="statistics plan exists with expected post-live formulas and current traceability row count",
            blocker="" if plan_aligned else "time_statistics_plan_not_aligned",
            next_action="keep plan synced with metric contract, schema, latency matrix, and traceability",
            source_artifacts=["outputs/research_progress_snapshot/post_live_time_metric_statistics_plan.md"],
            claim_boundary="time_formula_plan_no_metric_claim",
        ),
        receipt_row(
            receipt_id="time_extractor_surface_coverage",
            status="pass" if extractor_ready else "blocked",
            observed_state=(
                f"extractor rows {extractor_summary.get('extractor_rows', 0)}; "
                f"ready rows {extractor_summary.get('ready_time_metric_rows', 0)}; "
                f"missing output rows {extractor_summary.get('missing_output_rows', 0)}"
            ),
            success_gate="all extractor surfaces are ready and no output rows are missing",
            blocker="" if extractor_ready else "time_extractor_waiting_live_outputs",
            next_action="rerun extractor after live output JSONL files exist",
            source_artifacts=["outputs/research_progress_snapshot/post_live_time_metric_extractor.md"],
            claim_boundary="time_extractor_requires_live_output_rows",
        ),
        receipt_row(
            receipt_id="time_metric_computation_receipt",
            status="pass" if metrics_computed else "blocked",
            observed_state=(
                f"computed rows {extractor_summary.get('computed_time_metric_rows', 0)}; "
                f"successful rows {extractor_summary.get('successful_rows_total', 0)}; "
                f"expected rows {extractor_summary.get('expected_rows_total', 0)}"
            ),
            success_gate="computed time metric rows cover all planned live rows",
            blocker="" if metrics_computed else "time_metrics_not_computed_from_live_outputs",
            next_action="wait for complete live outputs before promoting time statistics",
            source_artifacts=["outputs/research_progress_snapshot/post_live_time_metric_extractor.md"],
            claim_boundary="computed_time_metrics_required_before_latency_claim_promotion",
        ),
        receipt_row(
            receipt_id="time_metric_parse_retry_quality",
            status="pass" if parse_clean else "blocked",
            observed_state=(
                f"parse error rows {extractor_summary.get('parse_error_rows', 0)}; "
                f"retry rows {extractor_summary.get('retry_rows_total', 0)}; "
                f"latency claim rows {latency_summary.get('latency_claim_rows', 0)}"
            ),
            success_gate="time metric extraction has zero parse errors and retry rows are accounted for",
            blocker="" if parse_clean else "time_metric_parse_quality_not_reviewable",
            next_action="review parse errors and retry distribution after extractor observes rows",
            source_artifacts=[
                "outputs/research_progress_snapshot/post_live_time_metric_extractor.md",
                "outputs/research_progress_snapshot/post_live_latency_claim_matrix.md",
            ],
            claim_boundary="parse_clean_time_metrics_required_before_report_claim",
        ),
        receipt_row(
            receipt_id="scoring_receipt_dependency",
            status="pass" if scoring_ready else "blocked",
            observed_state=(
                f"scoring receipt ready {scoring_receipt_summary.get('ready_for_promotion_review', False)}; "
                f"scoring execute record {scoring_receipt_summary.get('scoring_execute_record_exists', False)}; "
                f"promotion-ready scoring rows {scoring_output_summary.get('promotion_ready_rows', 0)}"
            ),
            success_gate="scoring receipt and scoring output audit are promotion-ready before time claim promotion",
            blocker="" if scoring_ready else "scoring_receipt_not_ready_for_time_claim_promotion",
            next_action="run ready scoring commands after live output audit passes",
            source_artifacts=[
                "outputs/research_progress_snapshot/post_live_scoring_receipt_audit.md",
                "outputs/research_progress_snapshot/post_live_scoring_output_audit.md",
            ],
            claim_boundary="time_claim_promotion_depends_on_scoring_receipt",
        ),
        receipt_row(
            receipt_id="promotion_preflight_after_time_metrics",
            status="pass" if promotion_ready else "blocked",
            observed_state=(
                f"promotion preflight ready {preflight_summary.get('ready_for_promotion_review', False)}; "
                f"ready time metric rows {preflight_summary.get('ready_time_metric_rows', 0)}; "
                f"traceability {trace_summary.get('fully_covered_rows', 0)}/{trace_summary.get('traceability_rows', 0)}"
            ),
            success_gate="promotion preflight is ready after time metrics and scoring receipts",
            blocker="" if promotion_ready else "promotion_preflight_not_ready_after_time_metrics",
            next_action="keep time claims preserved until promotion preflight and traceability pass",
            source_artifacts=["outputs/research_progress_snapshot/post_live_promotion_preflight_audit.md"],
            claim_boundary="no_time_metric_claim_promotion_without_preflight",
        ),
    ]

    pass_rows = [row for row in rows if row["status"] == "pass"]
    blocked_rows = [row for row in rows if row["status"] == "blocked"]
    missing_source_rows = [row for row in rows if not row["source_artifacts_exist"]]
    ready_for_time_claim_promotion = (
        plan_aligned
        and extractor_ready
        and metrics_computed
        and parse_clean
        and scoring_ready
        and promotion_ready
        and not missing_source_rows
    )

    return {
        "runtime_contract": "post_live_time_metric_receipt_audit_no_live_or_scoring_calls_no_secret_values",
        "status": "ready_for_time_claim_promotion" if ready_for_time_claim_promotion else "blocked_waiting_time_metric_evidence",
        "source_contracts": {
            "post_live_time_metric_statistics_plan": stats_plan.get("runtime_contract", ""),
            "post_live_time_metric_extractor": extractor.get("runtime_contract", ""),
            "post_live_scoring_receipt_audit": scoring_receipt.get("runtime_contract", ""),
            "post_live_scoring_output_audit": scoring_output.get("runtime_contract", ""),
            "post_live_latency_claim_matrix": latency_matrix.get("runtime_contract", ""),
            "post_live_promotion_preflight_audit": promotion_preflight.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "summary": {
            "receipt_rows": len(rows),
            "pass_rows": len(pass_rows),
            "blocked_rows": len(blocked_rows),
            "missing_source_rows": len(missing_source_rows),
            "time_stat_rows": as_int(stats_summary.get("time_stat_rows")),
            "post_live_stat_rows": as_int(stats_summary.get("post_live_stat_rows")),
            "formula_count": as_int(stats_summary.get("formula_count")),
            "extractor_rows": as_int(extractor_summary.get("extractor_rows")),
            "ready_time_metric_rows": as_int(extractor_summary.get("ready_time_metric_rows")),
            "computed_time_metric_rows": as_int(extractor_summary.get("computed_time_metric_rows")),
            "missing_output_rows": as_int(extractor_summary.get("missing_output_rows")),
            "expected_rows_total": as_int(extractor_summary.get("expected_rows_total")),
            "observed_rows_total": as_int(extractor_summary.get("observed_rows_total")),
            "successful_rows_total": as_int(extractor_summary.get("successful_rows_total")),
            "parse_error_rows": as_int(extractor_summary.get("parse_error_rows")),
            "retry_rows_total": as_int(extractor_summary.get("retry_rows_total")),
            "expected_live_calls": as_int(extractor_summary.get("expected_live_calls")),
            "missing_output_surfaces": as_int(extractor_summary.get("missing_output_surfaces")),
            "scoring_receipt_ready_for_promotion_review": bool(scoring_receipt_summary.get("ready_for_promotion_review")),
            "scoring_execute_record_exists": bool(scoring_receipt_summary.get("scoring_execute_record_exists")),
            "scoring_output_promotion_ready_rows": as_int(scoring_output_summary.get("promotion_ready_rows")),
            "promotion_preflight_ready": bool(preflight_summary.get("ready_for_promotion_review")),
            "ready_for_time_claim_promotion": ready_for_time_claim_promotion,
            "traceability_rows": as_int(trace_summary.get("traceability_rows")),
            "traceability_fully_covered_rows": as_int(trace_summary.get("fully_covered_rows")),
            "live_calls_performed_by_builder": 0,
            "no_live_calls_performed_by_auditor": True,
            "no_scoring_commands_executed_by_auditor": True,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(audit: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "receipt_id",
        "status",
        "observed_state",
        "success_gate",
        "blocker",
        "next_action",
        "source_artifacts_exist",
        "claim_boundary",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in audit["rows"]:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    lines = [
        "# Post-Live Time Metric Receipt Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Receipt rows: `{summary['receipt_rows']}`",
        f"- Pass rows: `{summary['pass_rows']}`",
        f"- Blocked rows: `{summary['blocked_rows']}`",
        f"- Missing source rows: `{summary['missing_source_rows']}`",
        f"- Time statistic rows: `{summary['time_stat_rows']}`",
        f"- Post-live statistic rows: `{summary['post_live_stat_rows']}`",
        f"- Formula count: `{summary['formula_count']}`",
        f"- Extractor rows: `{summary['extractor_rows']}`",
        f"- Ready time metric rows: `{summary['ready_time_metric_rows']}`",
        f"- Computed time metric rows: `{summary['computed_time_metric_rows']}`",
        f"- Missing output rows: `{summary['missing_output_rows']}`",
        f"- Expected rows total: `{summary['expected_rows_total']}`",
        f"- Observed rows total: `{summary['observed_rows_total']}`",
        f"- Successful rows total: `{summary['successful_rows_total']}`",
        f"- Parse error rows: `{summary['parse_error_rows']}`",
        f"- Retry rows total: `{summary['retry_rows_total']}`",
        f"- Scoring receipt ready: `{summary['scoring_receipt_ready_for_promotion_review']}`",
        f"- Scoring execute record exists: `{summary['scoring_execute_record_exists']}`",
        f"- Scoring output promotion-ready rows: `{summary['scoring_output_promotion_ready_rows']}`",
        f"- Promotion preflight ready: `{summary['promotion_preflight_ready']}`",
        f"- Ready for time claim promotion: `{summary['ready_for_time_claim_promotion']}`",
        f"- Traceability rows: `{summary['traceability_rows']}`",
        f"- Traceability fully covered rows: `{summary['traceability_fully_covered_rows']}`",
        f"- No live calls performed by auditor: `{summary['no_live_calls_performed_by_auditor']}`",
        f"- No scoring commands executed by auditor: `{summary['no_scoring_commands_executed_by_auditor']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Receipt | Status | Blocker | Observed state | Boundary |",
        "|---|---|---|---|---|",
    ]
    for row in audit["rows"]:
        lines.append(
            f"| `{row['receipt_id']}` | `{row['status']}` | `{row['blocker']}` | "
            f"{row['observed_state']} | `{row['claim_boundary']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This audit separates time metric formulas from computed post-live time evidence.",
            "- It does not execute live/API/model/scoring calls; it only reads the statistics plan, extractor output, scoring receipts, and promotion gates.",
            "- No latency/time claim should be promoted until extractor coverage, scoring receipts, parse quality, promotion preflight, and traceability all pass.",
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
    args.output_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(audit, args.output_md)
    write_csv(audit, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")
    print(json.dumps({"status": audit["status"], "summary": audit["summary"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
