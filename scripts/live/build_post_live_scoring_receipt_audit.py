#!/usr/bin/env python3
"""Audit the latest explicit post-live scoring receipt without running scoring commands."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_scoring_receipt_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_scoring_receipt_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_scoring_receipt_audit.csv")
EXECUTE_RECORD_JSON = Path("outputs/research_progress_snapshot/post_live_scoring_launcher_execute_latest.json")


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
    scoring_launcher = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_launcher.json")
    scoring_plan = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_execution_plan.json")
    scoring_output = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_output_audit.json")
    time_extractor = read_json(root / "outputs/research_progress_snapshot/post_live_time_metric_extractor.json")
    promotion_preflight = read_json(root / "outputs/research_progress_snapshot/post_live_promotion_preflight_audit.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")
    execute_record = read_json(root / EXECUTE_RECORD_JSON)

    launcher_summary = scoring_launcher.get("summary", {})
    plan_summary = scoring_plan.get("summary", {})
    output_summary = scoring_output.get("summary", {})
    time_summary = time_extractor.get("summary", {})
    preflight_summary = promotion_preflight.get("summary", {})
    trace_summary = traceability.get("summary", {})
    record_summary = execute_record.get("summary", {})

    record_exists = bool((root / EXECUTE_RECORD_JSON).exists() and execute_record)
    record_contract = str(execute_record.get("runtime_contract", ""))
    record_status = str(execute_record.get("status", ""))
    record_scope = str(record_summary.get("scoring_scope", ""))
    executed_rows = as_int(record_summary.get("executed_scoring_rows"))
    passed_rows = as_int(record_summary.get("passed_scoring_rows"))
    failed_rows = as_int(record_summary.get("failed_scoring_rows"))
    expected_ready_rows = as_int(launcher_summary.get("ready_scoring_rows"))
    selected_rows = as_int(record_summary.get("selected_scoring_rows"))
    missing_scoring_artifacts = as_int(output_summary.get("missing_output_artifacts"))
    promotion_ready_rows = as_int(output_summary.get("promotion_ready_rows"))
    computed_time_rows = as_int(time_summary.get("computed_time_metric_rows"))
    ready_time_rows = as_int(time_summary.get("ready_time_metric_rows"))
    preflight_ready = bool(preflight_summary.get("ready_for_promotion_review"))

    receipt_present = record_exists and record_contract == "post_live_scoring_launcher_execute_scoring_explicit"
    scope_ok = receipt_present and record_scope in {"p0", "deepseek", "omni", "qwen", "all"}
    result_clean = receipt_present and executed_rows > 0 and failed_rows == 0 and passed_rows == executed_rows
    scoring_outputs_ready = receipt_present and promotion_ready_rows > 0 and missing_scoring_artifacts == 0
    time_metrics_ready = receipt_present and computed_time_rows > 0 and ready_time_rows > 0
    promotion_ready = receipt_present and preflight_ready

    rows = [
        receipt_row(
            receipt_id="scoring_execute_record_presence",
            status="pass" if receipt_present else "blocked",
            observed_state=f"record exists {record_exists}; contract {record_contract or 'none'}; status {record_status or 'none'}",
            success_gate="execute_latest record exists and runtime contract is explicit scoring execution",
            blocker="" if receipt_present else "no_scoring_execute_record",
            next_action="run post-live scoring launcher with --execute-scoring after live outputs are ready",
            source_artifacts=["outputs/research_progress_snapshot/post_live_scoring_launcher.md"],
            claim_boundary="scoring_receipt_required_before_scoring_output_claim",
        ),
        receipt_row(
            receipt_id="scoring_scope_alignment",
            status="pass" if scope_ok else "blocked",
            observed_state=f"record scope {record_scope or 'none'}; launcher ready rows {expected_ready_rows}; selected rows {selected_rows}",
            success_gate="scoring execute scope is recorded and selected rows are nonzero",
            blocker="" if scope_ok else "missing_or_invalid_scoring_scope",
            next_action="preserve scoring execute_latest record after explicit scoring run",
            source_artifacts=["outputs/research_progress_snapshot/post_live_scoring_launcher.md"],
            claim_boundary="scoring_scope_receipt_required_before_metric_promotion",
        ),
        receipt_row(
            receipt_id="scoring_command_result_receipt",
            status="pass" if result_clean else "blocked",
            observed_state=f"executed {executed_rows}; passed {passed_rows}; failed {failed_rows}",
            success_gate="executed scoring rows > 0 and failed rows are zero",
            blocker="" if result_clean else "no_successful_scoring_execution_receipt",
            next_action="if execute record exists with failures, repair scoring commands before promotion",
            source_artifacts=["outputs/research_progress_snapshot/post_live_scoring_launcher.md"],
            claim_boundary="scoring_result_receipt_required_before_output_promotion",
        ),
        receipt_row(
            receipt_id="scoring_output_audit_after_execute",
            status="pass" if scoring_outputs_ready else "blocked",
            observed_state=(
                f"promotion-ready rows {promotion_ready_rows}; "
                f"missing scoring artifacts {missing_scoring_artifacts}; "
                f"existing artifacts {output_summary.get('existing_output_artifacts', 0)}"
            ),
            success_gate="scoring output audit observes promotion-ready rows after scoring execution",
            blocker="" if scoring_outputs_ready else "scoring_outputs_not_promotion_ready",
            next_action="wait for explicit scoring run before scoring output promotion",
            source_artifacts=["outputs/research_progress_snapshot/post_live_scoring_output_audit.md"],
            claim_boundary="scoring_output_audit_required_before_time_and_claim_promotion",
        ),
        receipt_row(
            receipt_id="time_metric_extractor_after_scoring",
            status="pass" if time_metrics_ready else "blocked",
            observed_state=(
                f"computed time metric rows {computed_time_rows}; "
                f"ready time rows {ready_time_rows}; "
                f"observed rows total {time_summary.get('observed_rows_total', 0)}"
            ),
            success_gate="time metric extractor computes ready rows from live/scoring evidence",
            blocker="" if time_metrics_ready else "time_metrics_not_computed",
            next_action="rerun time extractor after live and scoring output artifacts exist",
            source_artifacts=["outputs/research_progress_snapshot/post_live_time_metric_extractor.md"],
            claim_boundary="time_metric_receipt_required_before_latency_claim_promotion",
        ),
        receipt_row(
            receipt_id="promotion_preflight_after_scoring",
            status="pass" if promotion_ready else "blocked",
            observed_state=(
                f"promotion preflight ready {preflight_ready}; "
                f"blocked rows {preflight_summary.get('blocked_rows', 0)}; "
                f"traceability {trace_summary.get('fully_covered_rows', 0)}/{trace_summary.get('traceability_rows', 0)}"
            ),
            success_gate="post-live promotion preflight is ready after scoring receipts and time metrics",
            blocker="" if promotion_ready else "post_live_promotion_preflight_not_ready_after_scoring",
            next_action="keep claims preserved until scoring/time evidence closes",
            source_artifacts=["outputs/research_progress_snapshot/post_live_promotion_preflight_audit.md"],
            claim_boundary="no_claim_promotion_without_scoring_receipt_and_time_evidence",
        ),
    ]

    pass_receipts = [row for row in rows if row["status"] == "pass"]
    blocked_receipts = [row for row in rows if row["status"] == "blocked"]
    missing_source_rows = [row for row in rows if not row["source_artifacts_exist"]]
    ready_for_promotion_review = (
        receipt_present
        and result_clean
        and scoring_outputs_ready
        and time_metrics_ready
        and promotion_ready
        and not missing_source_rows
    )

    return {
        "runtime_contract": "post_live_scoring_receipt_audit_no_live_or_scoring_calls_no_secret_values",
        "status": "ready_for_promotion_review" if ready_for_promotion_review else "blocked_no_scoring_receipt_or_outputs",
        "source_contracts": {
            "post_live_scoring_launcher": scoring_launcher.get("runtime_contract", ""),
            "post_live_scoring_execution_plan": scoring_plan.get("runtime_contract", ""),
            "post_live_scoring_output_audit": scoring_output.get("runtime_contract", ""),
            "post_live_time_metric_extractor": time_extractor.get("runtime_contract", ""),
            "post_live_promotion_preflight_audit": promotion_preflight.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "summary": {
            "receipt_rows": len(rows),
            "pass_rows": len(pass_receipts),
            "blocked_rows": len(blocked_receipts),
            "missing_source_rows": len(missing_source_rows),
            "scoring_execute_record_exists": record_exists,
            "scoring_execute_record_path": str(EXECUTE_RECORD_JSON),
            "latest_scoring_execute_status": record_status,
            "latest_scoring_execute_runtime_contract": record_contract,
            "latest_scoring_execute_scope": record_scope,
            "executed_scoring_rows": executed_rows,
            "passed_scoring_rows": passed_rows,
            "failed_scoring_rows": failed_rows,
            "expected_ready_scoring_rows": expected_ready_rows,
            "selected_scoring_rows": selected_rows,
            "available_scoring_rows": as_int(launcher_summary.get("available_scoring_rows")),
            "plan_scoring_execution_steps": as_int(plan_summary.get("scoring_execution_steps")),
            "readiness_ready_to_score_steps": as_int(launcher_summary.get("readiness_ready_to_score_steps")),
            "scoring_output_promotion_ready_rows": promotion_ready_rows,
            "scoring_output_missing_artifacts": missing_scoring_artifacts,
            "computed_time_metric_rows": computed_time_rows,
            "ready_time_metric_rows": ready_time_rows,
            "ready_for_promotion_review": ready_for_promotion_review,
            "promotion_preflight_ready": preflight_ready,
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
        "# Post-Live Scoring Receipt Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Receipt rows: `{summary['receipt_rows']}`",
        f"- Pass rows: `{summary['pass_rows']}`",
        f"- Blocked rows: `{summary['blocked_rows']}`",
        f"- Missing source rows: `{summary['missing_source_rows']}`",
        f"- Scoring execute record exists: `{summary['scoring_execute_record_exists']}`",
        f"- Scoring execute record path: `{summary['scoring_execute_record_path']}`",
        f"- Latest scoring execute status: `{summary['latest_scoring_execute_status']}`",
        f"- Latest scoring execute scope: `{summary['latest_scoring_execute_scope']}`",
        f"- Executed scoring rows: `{summary['executed_scoring_rows']}`",
        f"- Passed scoring rows: `{summary['passed_scoring_rows']}`",
        f"- Failed scoring rows: `{summary['failed_scoring_rows']}`",
        f"- Ready scoring rows: `{summary['expected_ready_scoring_rows']}`",
        f"- Scoring output promotion-ready rows: `{summary['scoring_output_promotion_ready_rows']}`",
        f"- Scoring output missing artifacts: `{summary['scoring_output_missing_artifacts']}`",
        f"- Computed time metric rows: `{summary['computed_time_metric_rows']}`",
        f"- Ready time metric rows: `{summary['ready_time_metric_rows']}`",
        f"- Ready for promotion review: `{summary['ready_for_promotion_review']}`",
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
            "- This audit is the first post-scoring receipt check after `run_post_live_scoring_sequence.py --execute-scoring`.",
            "- It does not execute scoring/live/API/model calls; it only reads the persistent scoring execute record and downstream artifacts.",
            "- No time metric or claim promotion should proceed without a clean scoring receipt, promotion-ready scoring outputs, and computed time metrics.",
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
