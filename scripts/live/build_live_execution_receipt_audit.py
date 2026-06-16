#!/usr/bin/env python3
"""Audit the latest explicit live execution receipt without running live calls."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_execution_receipt_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_execution_receipt_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_execution_receipt_audit.csv")
EXECUTE_RECORD_JSON = Path("outputs/research_progress_snapshot/live_execution_launcher_execute_latest.json")


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
    launcher = read_json(root / "outputs/research_progress_snapshot/live_execution_launcher.json")
    eligibility = read_json(root / "outputs/research_progress_snapshot/live_execution_eligibility_gate.json")
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    promotion_preflight = read_json(root / "outputs/research_progress_snapshot/post_live_promotion_preflight_audit.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")
    execute_record = read_json(root / EXECUTE_RECORD_JSON)

    launcher_summary = launcher.get("summary", {})
    eligibility_summary = eligibility.get("summary", {})
    output_summary = output_audit.get("summary", {})
    preflight_summary = promotion_preflight.get("summary", {})
    trace_summary = traceability.get("summary", {})
    record_summary = execute_record.get("summary", {})
    record_exists = bool((root / EXECUTE_RECORD_JSON).exists() and execute_record)
    record_contract = str(execute_record.get("runtime_contract", ""))
    record_status = str(execute_record.get("status", ""))
    record_scope = str(record_summary.get("live_scope", ""))
    started_calls = as_int(record_summary.get("started_live_command_calls"))
    passed_calls = as_int(record_summary.get("passed_live_command_calls"))
    failed_calls = as_int(record_summary.get("failed_live_command_calls"))
    failed_rows = as_int(record_summary.get("failed_live_command_rows"))
    postrun_refresh = bool(record_summary.get("postrun_refresh_executed", False))
    live_calls_performed = as_int(record_summary.get("live_calls_performed_by_launcher"))
    expected_selected_calls = as_int(launcher_summary.get("selected_live_calls"))

    receipt_present = record_exists and record_contract == "live_execution_launcher_execute_live_explicit"
    scope_ok = receipt_present and record_scope in {"p0", "deepseek", "omni", "qwen", "all"}
    result_clean = receipt_present and started_calls > 0 and failed_calls == 0 and failed_rows == 0
    output_advanced = receipt_present and as_int(output_summary.get("observed_live_output_rows")) > 0
    postrun_ok = receipt_present and postrun_refresh
    promotion_ready = bool(preflight_summary.get("ready_for_promotion_review"))

    rows = [
        receipt_row(
            receipt_id="execute_record_presence",
            status="pass" if receipt_present else "blocked",
            observed_state=f"record exists {record_exists}; contract {record_contract or 'none'}; status {record_status or 'none'}",
            success_gate="execute_latest record exists and runtime contract is explicit live execution",
            blocker="" if receipt_present else "no_execute_record",
            next_action="run live launcher with --execute-live after credential/quota readiness",
            source_artifacts=["outputs/research_progress_snapshot/live_execution_launcher.md"],
            claim_boundary="receipt_required_before_live_output_claim",
        ),
        receipt_row(
            receipt_id="execute_scope_alignment",
            status="pass" if scope_ok else "blocked",
            observed_state=f"record scope {record_scope or 'none'}; dry-run selected calls {expected_selected_calls}",
            success_gate="execute scope is recorded and selected live calls are nonzero",
            blocker="" if scope_ok else "missing_or_invalid_execute_scope",
            next_action="preserve execute_latest record after explicit run",
            source_artifacts=["outputs/research_progress_snapshot/live_execution_launcher.md"],
            claim_boundary="scope_receipt_required_before_scoring",
        ),
        receipt_row(
            receipt_id="live_command_result_receipt",
            status="pass" if result_clean else "blocked",
            observed_state=f"started {started_calls}; passed {passed_calls}; failed {failed_calls}; failed rows {failed_rows}",
            success_gate="started calls > 0 and failed calls/rows are zero",
            blocker="" if result_clean else "no_successful_live_execution_receipt",
            next_action="if execute record exists with failures, use repair plan before scoring",
            source_artifacts=["outputs/research_progress_snapshot/live_execution_launcher.md"],
            claim_boundary="result_receipt_required_before_output_promotion",
        ),
        receipt_row(
            receipt_id="postrun_refresh_receipt",
            status="pass" if postrun_ok else "blocked",
            observed_state=f"postrun refresh executed {postrun_refresh}; live calls performed {live_calls_performed}",
            success_gate="postrun refresh ran after successful explicit live execution",
            blocker="" if postrun_ok else "postrun_refresh_not_executed",
            next_action="rerun refresh after live outputs appear, unless launcher already did it",
            source_artifacts=["outputs/research_progress_snapshot/refresh_latest_artifacts.md"],
            claim_boundary="refresh_receipt_required_before_report_ppt_promotion",
        ),
        receipt_row(
            receipt_id="output_audit_after_execute",
            status="pass" if output_advanced else "blocked",
            observed_state=(
                f"observed rows {output_summary.get('observed_live_output_rows', 0)}; "
                f"claim-ready surfaces {output_summary.get('claim_ready_surfaces', 0)}; "
                f"missing surfaces {output_summary.get('missing_output_surfaces', 0)}"
            ),
            success_gate="output audit observes live rows after execute receipt",
            blocker="" if output_advanced else "no_live_output_rows_observed",
            next_action="wait for explicit live run before scoring/output promotion",
            source_artifacts=["outputs/research_progress_snapshot/live_output_audit.md"],
            claim_boundary="output_audit_required_before_scoring",
        ),
        receipt_row(
            receipt_id="promotion_preflight_after_execute",
            status="pass" if promotion_ready else "blocked",
            observed_state=(
                f"promotion preflight ready {preflight_summary.get('ready_for_promotion_review', False)}; "
                f"blocked rows {preflight_summary.get('blocked_rows', 0)}; "
                f"traceability {trace_summary.get('fully_covered_rows', 0)}/{trace_summary.get('traceability_rows', 0)}"
            ),
            success_gate="post-live promotion preflight is ready after receipt/output/scoring/time metrics",
            blocker="" if promotion_ready else "post_live_promotion_preflight_not_ready",
            next_action="keep claims preserved until live/scoring/time evidence closes",
            source_artifacts=["outputs/research_progress_snapshot/post_live_promotion_preflight_audit.md"],
            claim_boundary="no_claim_promotion_without_execute_receipt_and_postrun_evidence",
        ),
    ]

    pass_rows = [row for row in rows if row["status"] == "pass"]
    blocked_rows = [row for row in rows if row["status"] == "blocked"]
    missing_source_rows = [row for row in rows if not row["source_artifacts_exist"]]
    ready_for_postrun_scoring = receipt_present and result_clean and output_advanced and not missing_source_rows

    return {
        "runtime_contract": "live_execution_receipt_audit_no_live_calls_no_secret_values",
        "status": "ready_for_postrun_scoring_review" if ready_for_postrun_scoring else "blocked_no_execute_receipt_or_outputs",
        "source_contracts": {
            "live_execution_launcher": launcher.get("runtime_contract", ""),
            "live_execution_eligibility_gate": eligibility.get("runtime_contract", ""),
            "live_output_audit": output_audit.get("runtime_contract", ""),
            "post_live_promotion_preflight_audit": promotion_preflight.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "summary": {
            "receipt_rows": len(rows),
            "pass_rows": len(pass_rows),
            "blocked_rows": len(blocked_rows),
            "missing_source_rows": len(missing_source_rows),
            "execute_record_exists": record_exists,
            "execute_record_path": str(EXECUTE_RECORD_JSON),
            "latest_execute_status": record_status,
            "latest_execute_runtime_contract": record_contract,
            "latest_execute_live_scope": record_scope,
            "started_live_command_calls": started_calls,
            "passed_live_command_calls": passed_calls,
            "failed_live_command_calls": failed_calls,
            "failed_live_command_rows": failed_rows,
            "postrun_refresh_executed": postrun_refresh,
            "live_calls_performed_by_launcher": live_calls_performed,
            "expected_selected_live_calls": expected_selected_calls,
            "eligibility_ready_to_execute_live": bool(eligibility_summary.get("ready_to_execute_live")),
            "observed_live_output_rows": as_int(output_summary.get("observed_live_output_rows")),
            "claim_ready_surfaces": as_int(output_summary.get("claim_ready_surfaces")),
            "missing_output_surfaces": as_int(output_summary.get("missing_output_surfaces")),
            "ready_for_postrun_scoring_review": ready_for_postrun_scoring,
            "traceability_rows": as_int(trace_summary.get("traceability_rows")),
            "traceability_fully_covered_rows": as_int(trace_summary.get("fully_covered_rows")),
            "live_calls_performed_by_builder": 0,
            "no_live_calls_performed_by_auditor": True,
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
        "# Live Execution Receipt Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Receipt rows: `{summary['receipt_rows']}`",
        f"- Pass rows: `{summary['pass_rows']}`",
        f"- Blocked rows: `{summary['blocked_rows']}`",
        f"- Missing source rows: `{summary['missing_source_rows']}`",
        f"- Execute record exists: `{summary['execute_record_exists']}`",
        f"- Execute record path: `{summary['execute_record_path']}`",
        f"- Latest execute status: `{summary['latest_execute_status']}`",
        f"- Latest execute scope: `{summary['latest_execute_live_scope']}`",
        f"- Started live command calls: `{summary['started_live_command_calls']}`",
        f"- Passed live command calls: `{summary['passed_live_command_calls']}`",
        f"- Failed live command calls: `{summary['failed_live_command_calls']}`",
        f"- Failed live command rows: `{summary['failed_live_command_rows']}`",
        f"- Postrun refresh executed: `{summary['postrun_refresh_executed']}`",
        f"- Observed live output rows: `{summary['observed_live_output_rows']}`",
        f"- Claim-ready surfaces: `{summary['claim_ready_surfaces']}`",
        f"- Ready for postrun scoring review: `{summary['ready_for_postrun_scoring_review']}`",
        f"- Traceability rows: `{summary['traceability_rows']}`",
        f"- Traceability fully covered rows: `{summary['traceability_fully_covered_rows']}`",
        f"- No live calls performed by auditor: `{summary['no_live_calls_performed_by_auditor']}`",
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
            "- This audit is the first post-execute receipt check after `run_live_execution_sequence.py --execute-live`.",
            "- It does not execute live/API/model calls; it only reads the persistent execute record and postrun artifacts.",
            "- No post-live scoring or claim promotion should proceed without a clean execute receipt and observed live output rows.",
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
