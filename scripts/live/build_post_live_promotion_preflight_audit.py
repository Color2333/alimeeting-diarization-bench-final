#!/usr/bin/env python3
"""Build a no-live-call preflight for post-live claim promotion."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_promotion_preflight_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_promotion_preflight_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_promotion_preflight_audit.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def preflight_row(
    *,
    row_id: str,
    stage: str,
    current_state: str,
    status: str,
    blocking_reason: str,
    observed_state: str,
    success_gate: str,
    next_action: str,
    source_artifacts: list[str],
    claim_boundary: str,
) -> dict[str, Any]:
    return {
        "preflight_id": row_id,
        "stage": stage,
        "current_state": current_state,
        "status": status,
        "blocking_reason": blocking_reason,
        "observed_state": observed_state,
        "success_gate": success_gate,
        "next_action": next_action,
        "source_artifacts": source_artifacts,
        "claim_boundary": claim_boundary,
        "source_artifacts_exist": all((ROOT / source).exists() for source in source_artifacts if source.startswith("outputs/")),
        "live_calls_performed_by_builder": 0,
    }


def build_preflight(root: Path) -> dict[str, Any]:
    live_launcher = read_json(root / "outputs/research_progress_snapshot/live_execution_launcher.json")
    scoring_launcher = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_launcher.json")
    scoring_output = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_output_audit.json")
    time_extractor = read_json(root / "outputs/research_progress_snapshot/post_live_time_metric_extractor.json")
    time_stats = read_json(root / "outputs/research_progress_snapshot/post_live_time_metric_statistics_plan.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")

    live_summary = live_launcher.get("summary", {})
    scoring_launcher_summary = scoring_launcher.get("summary", {})
    scoring_output_summary = scoring_output.get("summary", {})
    time_summary = time_extractor.get("summary", {})
    time_stats_summary = time_stats.get("summary", {})
    promotion_summary = promotion.get("summary", {})
    trace_summary = traceability.get("summary", {})

    traceability_synced = (
        traceability.get("status") == "pass"
        and as_int(trace_summary.get("traceability_rows")) == as_int(trace_summary.get("fully_covered_rows"))
        and as_int(trace_summary.get("missing_report_rows"), -1) == 0
        and as_int(trace_summary.get("missing_ppt_rows"), -1) == 0
        and as_int(trace_summary.get("missing_source_rows"), -1) == 0
    )
    boundary_clean = all(
        item is True
        for item in [
            live_summary.get("no_new_metric_claim"),
            scoring_launcher_summary.get("no_new_metric_claim"),
            scoring_output_summary.get("no_new_metric_claim"),
            time_summary.get("no_new_metric_claim"),
            time_stats_summary.get("no_new_metric_claim"),
            promotion_summary.get("no_new_metric_claim"),
            trace_summary.get("no_new_metric_claim"),
        ]
    )

    rows = [
        preflight_row(
            row_id="live_execution_preflight",
            stage="live_execution",
            current_state=live_launcher.get("status", ""),
            status="blocked",
            blocking_reason="credentials_or_execute_flag_missing",
            observed_state=(
                f"selected live calls {live_summary.get('selected_live_calls', 0)}; "
                f"started {live_summary.get('started_live_command_calls', 0)}; "
                f"credential ready {live_summary.get('credential_ready', False)}"
            ),
            success_gate="execute record exists and required P0 live calls complete",
            next_action="run live launcher with explicit execute flag after credentials/quota are ready",
            source_artifacts=["outputs/research_progress_snapshot/live_execution_launcher.md"],
            claim_boundary="no_claim_promotion_before_live_outputs",
        ),
        preflight_row(
            row_id="scoring_execution_preflight",
            stage="scoring_outputs",
            current_state=scoring_output.get("status", ""),
            status="blocked",
            blocking_reason="scoring_outputs_missing_or_blocked",
            observed_state=(
                f"promotion-ready scoring rows {scoring_output_summary.get('promotion_ready_rows', 0)}; "
                f"missing output artifacts {scoring_output_summary.get('missing_output_artifacts', 0)}; "
                f"executed scoring rows {scoring_launcher_summary.get('executed_scoring_rows', 0)}"
            ),
            success_gate="required scoring output rows are unblocked and promotion-ready",
            next_action="run ready scoring launcher after live output audit is clean",
            source_artifacts=[
                "outputs/research_progress_snapshot/post_live_scoring_launcher.md",
                "outputs/research_progress_snapshot/post_live_scoring_output_audit.md",
            ],
            claim_boundary="no_claim_promotion_before_scoring_outputs",
        ),
        preflight_row(
            row_id="time_metric_preflight",
            stage="time_metrics",
            current_state=time_extractor.get("status", ""),
            status="blocked",
            blocking_reason="time_metric_outputs_missing",
            observed_state=(
                f"ready time metric rows {time_summary.get('ready_time_metric_rows', 0)}; "
                f"computed rows {time_summary.get('computed_time_metric_rows', 0)}; "
                f"expected live rows {time_summary.get('expected_rows_total', 0)}"
            ),
            success_gate="post-live time metric extractor has ready rows and clean parse status",
            next_action="rerun time extractor after live output JSONL files exist",
            source_artifacts=[
                "outputs/research_progress_snapshot/post_live_time_metric_statistics_plan.md",
                "outputs/research_progress_snapshot/post_live_time_metric_extractor.md",
            ],
            claim_boundary="time_metrics_no_new_claim_until_promotion",
        ),
        preflight_row(
            row_id="claim_promotion_gate_preflight",
            stage="promotion_gate",
            current_state=promotion.get("status", ""),
            status="blocked",
            blocking_reason="no_post_live_gate_ready_to_promote",
            observed_state=(
                f"ready to promote {promotion_summary.get('ready_to_promote_count', 0)}; "
                f"blocked {promotion_summary.get('blocked_count', 0)}; "
                f"fallback-only {promotion_summary.get('fallback_only_count', 0)}"
            ),
            success_gate="at least one post-live gate is ready and all source rows exist",
            next_action="keep current claims preserved until live/scoring/time gates pass",
            source_artifacts=["outputs/research_progress_snapshot/post_live_claim_promotion_gate.md"],
            claim_boundary="promote_only_after_output_audit_scoring_slo_traceability_and_time_metrics",
        ),
        preflight_row(
            row_id="report_ppt_traceability_preflight",
            stage="report_ppt_traceability",
            current_state=traceability.get("status", ""),
            status="pass" if traceability_synced else "blocked",
            blocking_reason="" if traceability_synced else "report_ppt_traceability_not_fully_covered",
            observed_state=(
                f"covered {trace_summary.get('fully_covered_rows', 0)}/"
                f"{trace_summary.get('traceability_rows', 0)}; "
                f"missing report {trace_summary.get('missing_report_rows', 0)}; "
                f"missing PPT {trace_summary.get('missing_ppt_rows', 0)}"
            ),
            success_gate="traceability status pass and fully covered rows equal total rows",
            next_action="rerun report/PPT refresh after any artifact changes",
            source_artifacts=["outputs/research_progress_snapshot/report_ppt_traceability.md"],
            claim_boundary="report_ppt_sync_required_before_claim_promotion",
        ),
        preflight_row(
            row_id="claim_boundary_safety_preflight",
            stage="claim_boundary_safety",
            current_state="no_new_metric_claim" if boundary_clean else "boundary_attention_needed",
            status="pass" if boundary_clean else "blocked",
            blocking_reason="" if boundary_clean else "one_or_more_artifacts_allow_new_metric_claim",
            observed_state=(
                f"no_new_metric_claim chain {boundary_clean}; "
                f"live calls by builders {live_summary.get('live_calls_performed_by_launcher', 0)}"
            ),
            success_gate="all preflight source artifacts preserve no-new-metric-claim boundary",
            next_action="keep post-live rows blocked until real evidence exists",
            source_artifacts=[
                "outputs/research_progress_snapshot/live_execution_launcher.md",
                "outputs/research_progress_snapshot/post_live_scoring_output_audit.md",
                "outputs/research_progress_snapshot/post_live_time_metric_extractor.md",
                "outputs/research_progress_snapshot/post_live_claim_promotion_gate.md",
            ],
            claim_boundary="no_new_metric_claim_until_evidence_promotion",
        ),
    ]

    pass_rows = [row for row in rows if row["status"] == "pass"]
    blocked_rows = [row for row in rows if row["status"] == "blocked"]
    missing_source_rows = [row for row in rows if not row["source_artifacts_exist"]]
    ready_for_promotion_review = (
        not blocked_rows
        and not missing_source_rows
        and as_int(promotion_summary.get("ready_to_promote_count")) > 0
    )

    return {
        "runtime_contract": "post_live_promotion_preflight_audit_no_live_or_scoring_calls",
        "status": "ready_for_promotion_review" if ready_for_promotion_review else "blocked_waiting_post_live_evidence",
        "source_contracts": {
            "live_execution_launcher": live_launcher.get("runtime_contract", ""),
            "post_live_scoring_launcher": scoring_launcher.get("runtime_contract", ""),
            "post_live_scoring_output_audit": scoring_output.get("runtime_contract", ""),
            "post_live_time_metric_extractor": time_extractor.get("runtime_contract", ""),
            "post_live_time_metric_statistics_plan": time_stats.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "summary": {
            "preflight_rows": len(rows),
            "pass_rows": len(pass_rows),
            "blocked_rows": len(blocked_rows),
            "missing_source_rows": len(missing_source_rows),
            "ready_for_promotion_review": ready_for_promotion_review,
            "post_live_ready_to_promote_count": as_int(promotion_summary.get("ready_to_promote_count")),
            "promotion_blocked_count": as_int(promotion_summary.get("blocked_count")),
            "promotion_preserve_count": as_int(promotion_summary.get("preserve_count")),
            "promotion_fallback_only_count": as_int(promotion_summary.get("fallback_only_count")),
            "scoring_output_promotion_ready_rows": as_int(scoring_output_summary.get("promotion_ready_rows")),
            "ready_time_metric_rows": as_int(time_summary.get("ready_time_metric_rows")),
            "computed_time_metric_rows": as_int(time_summary.get("computed_time_metric_rows")),
            "traceability_rows": as_int(trace_summary.get("traceability_rows")),
            "traceability_fully_covered_rows": as_int(trace_summary.get("fully_covered_rows")),
            "live_calls_performed_by_builder": 0,
            "no_live_calls_performed": True,
            "no_scoring_commands_executed": True,
            "no_secret_values_written": True,
            "no_new_metric_claim": boundary_clean,
        },
        "rows": rows,
    }


def write_csv(preflight: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "preflight_id",
        "stage",
        "current_state",
        "status",
        "blocking_reason",
        "observed_state",
        "success_gate",
        "next_action",
        "source_artifacts_exist",
        "claim_boundary",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in preflight["rows"]:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_markdown(preflight: dict[str, Any], path: Path) -> None:
    summary = preflight["summary"]
    lines = [
        "# Post-Live Promotion Preflight Audit",
        "",
        f"- Runtime contract: `{preflight['runtime_contract']}`",
        f"- Status: `{preflight['status']}`",
        f"- Preflight rows: `{summary['preflight_rows']}`",
        f"- Pass rows: `{summary['pass_rows']}`",
        f"- Blocked rows: `{summary['blocked_rows']}`",
        f"- Missing source rows: `{summary['missing_source_rows']}`",
        f"- Ready for promotion review: `{summary['ready_for_promotion_review']}`",
        f"- Post-live ready-to-promote count: `{summary['post_live_ready_to_promote_count']}`",
        f"- Scoring output promotion-ready rows: `{summary['scoring_output_promotion_ready_rows']}`",
        f"- Ready time metric rows: `{summary['ready_time_metric_rows']}`",
        f"- Computed time metric rows: `{summary['computed_time_metric_rows']}`",
        f"- Traceability rows: `{summary['traceability_rows']}`",
        f"- Traceability fully covered rows: `{summary['traceability_fully_covered_rows']}`",
        f"- No live calls performed: `{summary['no_live_calls_performed']}`",
        f"- No scoring commands executed: `{summary['no_scoring_commands_executed']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Preflight | Stage | Status | Blocking reason | Observed state | Boundary |",
        "|---|---|---|---|---|---|",
    ]
    for row in preflight["rows"]:
        lines.append(
            f"| `{row['preflight_id']}` | `{row['stage']}` | `{row['status']}` | "
            f"`{row['blocking_reason']}` | {row['observed_state']} | `{row['claim_boundary']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This preflight is the final no-live/no-scoring check before any post-live claim promotion review.",
            "- Passing traceability and claim-boundary rows are not enough to promote; live outputs, scoring outputs, time metrics, and promotion gates must also pass.",
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

    preflight = build_preflight(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(preflight, args.output_md)
    write_csv(preflight, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")
    print(json.dumps({"status": preflight["status"], "summary": preflight["summary"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
