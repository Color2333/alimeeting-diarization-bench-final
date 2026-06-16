#!/usr/bin/env python3
"""Audit post-live claim promotion receipts without live, scoring, or claim promotion writes."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_claim_promotion_receipt_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_claim_promotion_receipt_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_claim_promotion_receipt_audit.csv")
SELF_VALIDATION_CHECK = "post_live_claim_promotion_receipt_audit_contract"


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
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    preflight = read_json(root / "outputs/research_progress_snapshot/post_live_promotion_preflight_audit.json")
    scoring_receipt = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_receipt_audit.json")
    time_receipt = read_json(root / "outputs/research_progress_snapshot/post_live_time_metric_receipt_audit.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")
    validation = read_json(root / "outputs/research_progress_snapshot/latest_artifact_validation.json")

    promotion_summary = promotion.get("summary", {})
    preflight_summary = preflight.get("summary", {})
    scoring_summary = scoring_receipt.get("summary", {})
    time_summary = time_receipt.get("summary", {})
    trace_summary = traceability.get("summary", {})
    failed_checks = validation.get("failed_checks", [])
    non_self_failed_checks = [check for check in failed_checks if check != SELF_VALIDATION_CHECK]

    promotion_gate_present = (
        promotion.get("runtime_contract") == "post_live_claim_promotion_gate_no_live_calls"
        and promotion.get("status") == "pass"
        and as_int(promotion_summary.get("gate_count")) == 8
        and as_int(promotion_summary.get("missing_source_rows"), -1) == 0
    )
    promotion_ready = (
        promotion_gate_present
        and as_int(promotion_summary.get("ready_to_promote_count")) > 0
        and bool(promotion.get("ready_to_promote_gate_ids"))
    )
    preflight_ready = (
        preflight.get("status") == "ready_for_promotion_review"
        and preflight_summary.get("ready_for_promotion_review") is True
    )
    scoring_ready = (
        scoring_receipt.get("status") == "ready_for_promotion_review"
        and scoring_summary.get("ready_for_promotion_review") is True
    )
    time_ready = (
        time_receipt.get("status") == "ready_for_time_claim_promotion"
        and time_summary.get("ready_for_time_claim_promotion") is True
    )
    report_ppt_synced = (
        traceability.get("status") == "pass"
        and as_int(trace_summary.get("traceability_rows")) == as_int(trace_summary.get("fully_covered_rows"))
        and as_int(trace_summary.get("missing_report_rows"), -1) == 0
        and as_int(trace_summary.get("missing_ppt_rows"), -1) == 0
        and as_int(trace_summary.get("missing_source_rows"), -1) == 0
    )
    validation_passed = validation.get("runtime_contract") == "latest_research_artifact_validation" and not non_self_failed_checks

    rows = [
        receipt_row(
            receipt_id="promotion_gate_presence",
            status="pass" if promotion_gate_present else "blocked",
            observed_state=(
                f"gate status {promotion.get('status', 'missing')}; "
                f"gates {promotion_summary.get('gate_count', 0)}; "
                f"missing sources {promotion_summary.get('missing_source_rows', 0)}"
            ),
            success_gate="promotion gate exists, sources are present, and policy is auditable",
            blocker="" if promotion_gate_present else "promotion_gate_missing_or_invalid",
            next_action="keep promotion gate in the refresh chain before any report/PPT promotion",
            source_artifacts=["outputs/research_progress_snapshot/post_live_claim_promotion_gate.md"],
            claim_boundary="promotion_gate_presence_no_claim_write",
        ),
        receipt_row(
            receipt_id="promotion_decision_receipt",
            status="pass" if promotion_ready else "blocked",
            observed_state=(
                f"ready to promote {promotion_summary.get('ready_to_promote_count', 0)}; "
                f"blocked {promotion_summary.get('blocked_count', 0)}; "
                f"fallback-only {promotion_summary.get('fallback_only_count', 0)}"
            ),
            success_gate="one or more gates are ready_to_promote after live/scoring/time evidence",
            blocker="" if promotion_ready else "no_post_live_gate_ready_to_promote",
            next_action="preserve current claims until live output, scoring, time metrics, and preflight pass",
            source_artifacts=["outputs/research_progress_snapshot/post_live_claim_promotion_gate.md"],
            claim_boundary="no_claim_promotion_without_ready_gate",
        ),
        receipt_row(
            receipt_id="promotion_preflight_receipt",
            status="pass" if preflight_ready else "blocked",
            observed_state=(
                f"preflight ready {preflight_summary.get('ready_for_promotion_review', False)}; "
                f"pass rows {preflight_summary.get('pass_rows', 0)}; "
                f"blocked rows {preflight_summary.get('blocked_rows', 0)}"
            ),
            success_gate="promotion preflight has no blocked rows and is ready for review",
            blocker="" if preflight_ready else "promotion_preflight_not_ready",
            next_action="clear live/scoring/time blockers before claim promotion",
            source_artifacts=["outputs/research_progress_snapshot/post_live_promotion_preflight_audit.md"],
            claim_boundary="preflight_required_before_claim_write",
        ),
        receipt_row(
            receipt_id="scoring_and_time_receipts",
            status="pass" if scoring_ready and time_ready else "blocked",
            observed_state=(
                f"scoring ready {scoring_summary.get('ready_for_promotion_review', False)}; "
                f"time ready {time_summary.get('ready_for_time_claim_promotion', False)}; "
                f"computed time rows {time_summary.get('computed_time_metric_rows', 0)}"
            ),
            success_gate="scoring receipt and time metric receipt are both promotion-ready",
            blocker="" if scoring_ready and time_ready else "scoring_or_time_receipts_not_ready",
            next_action="run scoring and time extraction only after live outputs are complete",
            source_artifacts=[
                "outputs/research_progress_snapshot/post_live_scoring_receipt_audit.md",
                "outputs/research_progress_snapshot/post_live_time_metric_receipt_audit.md",
            ],
            claim_boundary="scoring_and_time_receipts_required_before_claim_write",
        ),
        receipt_row(
            receipt_id="report_ppt_traceability_receipt",
            status="pass" if report_ppt_synced else "blocked",
            observed_state=(
                f"traceability {trace_summary.get('fully_covered_rows', 0)}/"
                f"{trace_summary.get('traceability_rows', 0)}; "
                f"missing report {trace_summary.get('missing_report_rows', 0)}; "
                f"missing PPT {trace_summary.get('missing_ppt_rows', 0)}"
            ),
            success_gate="report/PPT/source traceability is fully covered",
            blocker="" if report_ppt_synced else "report_ppt_traceability_not_synced",
            next_action="rerun report/PPT refresh after any promoted claim wording changes",
            source_artifacts=["outputs/research_progress_snapshot/report_ppt_traceability.md"],
            claim_boundary="report_ppt_sync_required_before_claim_write",
        ),
        receipt_row(
            receipt_id="validation_after_promotion_receipt",
            status="pass" if validation_passed else "blocked",
            observed_state=(
                f"validation status {validation.get('status', 'missing')}; "
                f"failed checks {len(failed_checks)}; non-self failed checks {len(non_self_failed_checks)}"
            ),
            success_gate="latest artifact validation passes after promotion state is represented",
            blocker="" if validation_passed else "latest_artifact_validation_failed",
            next_action="rerun validation after report/PPT and traceability changes",
            source_artifacts=["outputs/research_progress_snapshot/latest_artifact_validation.md"],
            claim_boundary="validation_required_before_claim_write",
        ),
    ]

    pass_rows = [row for row in rows if row["status"] == "pass"]
    blocked_rows = [row for row in rows if row["status"] == "blocked"]
    missing_source_rows = [row for row in rows if not row["source_artifacts_exist"]]
    ready_for_claim_write = (
        promotion_ready
        and preflight_ready
        and scoring_ready
        and time_ready
        and report_ppt_synced
        and validation_passed
        and not missing_source_rows
    )

    return {
        "runtime_contract": "post_live_claim_promotion_receipt_audit_no_live_or_scoring_or_claim_writes_no_secret_values",
        "status": "ready_for_claim_write" if ready_for_claim_write else "blocked_no_claim_promotion_receipt",
        "source_contracts": {
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
            "post_live_promotion_preflight_audit": preflight.get("runtime_contract", ""),
            "post_live_scoring_receipt_audit": scoring_receipt.get("runtime_contract", ""),
            "post_live_time_metric_receipt_audit": time_receipt.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
            "latest_artifact_validation": validation.get("runtime_contract", ""),
        },
        "summary": {
            "receipt_rows": len(rows),
            "pass_rows": len(pass_rows),
            "blocked_rows": len(blocked_rows),
            "missing_source_rows": len(missing_source_rows),
            "promotion_gate_count": as_int(promotion_summary.get("gate_count")),
            "ready_to_promote_count": as_int(promotion_summary.get("ready_to_promote_count")),
            "blocked_promotion_count": as_int(promotion_summary.get("blocked_count")),
            "fallback_only_count": as_int(promotion_summary.get("fallback_only_count")),
            "preflight_ready": preflight_ready,
            "promotion_preflight_pass_rows": as_int(preflight_summary.get("pass_rows")),
            "promotion_preflight_blocked_rows": as_int(preflight_summary.get("blocked_rows")),
            "scoring_receipt_ready": scoring_ready,
            "time_metric_receipt_ready": time_ready,
            "computed_time_metric_rows": as_int(time_summary.get("computed_time_metric_rows")),
            "report_ppt_synced": report_ppt_synced,
            "validation_passed": validation_passed,
            "validation_failed_checks": len(failed_checks),
            "validation_non_self_failed_checks": len(non_self_failed_checks),
            "ready_for_claim_write": ready_for_claim_write,
            "traceability_rows": as_int(trace_summary.get("traceability_rows")),
            "traceability_fully_covered_rows": as_int(trace_summary.get("fully_covered_rows")),
            "live_calls_performed_by_builder": 0,
            "no_live_calls_performed_by_auditor": True,
            "no_scoring_commands_executed_by_auditor": True,
            "no_claim_writes_performed_by_auditor": True,
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
        "# Post-Live Claim Promotion Receipt Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Receipt rows: `{summary['receipt_rows']}`",
        f"- Pass rows: `{summary['pass_rows']}`",
        f"- Blocked rows: `{summary['blocked_rows']}`",
        f"- Missing source rows: `{summary['missing_source_rows']}`",
        f"- Promotion gate count: `{summary['promotion_gate_count']}`",
        f"- Ready to promote count: `{summary['ready_to_promote_count']}`",
        f"- Blocked promotion count: `{summary['blocked_promotion_count']}`",
        f"- Fallback-only count: `{summary['fallback_only_count']}`",
        f"- Preflight ready: `{summary['preflight_ready']}`",
        f"- Scoring receipt ready: `{summary['scoring_receipt_ready']}`",
        f"- Time metric receipt ready: `{summary['time_metric_receipt_ready']}`",
        f"- Computed time metric rows: `{summary['computed_time_metric_rows']}`",
        f"- Report/PPT synced: `{summary['report_ppt_synced']}`",
        f"- Validation passed: `{summary['validation_passed']}`",
        f"- Ready for claim write: `{summary['ready_for_claim_write']}`",
        f"- Traceability rows: `{summary['traceability_rows']}`",
        f"- Traceability fully covered rows: `{summary['traceability_fully_covered_rows']}`",
        f"- No live calls performed by auditor: `{summary['no_live_calls_performed_by_auditor']}`",
        f"- No scoring commands executed by auditor: `{summary['no_scoring_commands_executed_by_auditor']}`",
        f"- No claim writes performed by auditor: `{summary['no_claim_writes_performed_by_auditor']}`",
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
            "- This audit is the final no-write receipt before promoting post-live claims into report/PPT wording.",
            "- It performs no live/API/model/scoring calls and writes no claim text; it only verifies whether promotion gates, receipts, traceability, and validation are ready.",
            "- Current post-live claims remain preserved or blocked until live outputs, scoring, time metrics, promotion preflight, traceability, and validation all pass together.",
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
