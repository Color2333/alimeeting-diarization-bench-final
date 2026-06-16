#!/usr/bin/env python3
"""Build a no-live-call post-live acceptance scorecard."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_acceptance_scorecard.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_acceptance_scorecard.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_acceptance_scorecard.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def row(
    scorecard_id: str,
    priority: str,
    surface_id: str,
    acceptance_area: str,
    current_status: str,
    pass_condition: str,
    evidence_artifacts: list[str],
    claim_effect: str,
) -> dict[str, Any]:
    return {
        "scorecard_id": scorecard_id,
        "priority": priority,
        "surface_id": surface_id,
        "acceptance_area": acceptance_area,
        "current_status": current_status,
        "pass_condition": pass_condition,
        "evidence_artifacts": evidence_artifacts,
        "claim_effect": claim_effect,
    }


def build_scorecard(root: Path) -> dict[str, Any]:
    slo = read_json(root / "outputs/research_progress_snapshot/stage_latency_slo_audit.json")
    output = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    scoring = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    metric = read_json(root / "outputs/research_progress_snapshot/live_metric_extraction_contract.json")
    schema = read_json(root / "outputs/research_progress_snapshot/live_output_schema_contract.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    risk = read_json(root / "outputs/research_progress_snapshot/latency_risk_margin_audit.json")

    slo_summary = slo.get("summary", {})
    output_summary = output.get("summary", {})
    scoring_summary = scoring.get("summary", {})
    metric_summary = metric.get("summary", {})
    schema_summary = schema.get("summary", {})
    promotion_summary = promotion.get("summary", {})
    risk_summary = risk.get("summary", {})

    rows = [
        row(
            "current_claim_now_slo_preserve",
            "P0",
            "current_claim_now_surfaces",
            "current_latency_slo",
            "preserve_pass",
            "claim_now_slo_pass == claim_now_slo_rows == 4 and failed_claim_rows is empty",
            [
                "outputs/research_progress_snapshot/stage_latency_slo_audit.json",
                "outputs/research_progress_snapshot/latency_risk_margin_audit.json",
            ],
            "preserve current report/PPT latency claims while post-live surfaces remain blocked",
        ),
        row(
            "deepseek_resume_output_coverage",
            "P0",
            "deepseek_resume_after_top3",
            "output_coverage",
            "blocked_missing_output",
            "139 successful resume rows, 101 parent windows, zero parse errors, zero duplicate/extra/missing call ids",
            [
                "outputs/research_progress_snapshot/live_output_audit.json",
                "outputs/research_progress_snapshot/split20_resume_export_audit.json",
            ],
            "unblocks P0 DeepSeek safety and comparison scoring",
        ),
        row(
            "deepseek_resume_output_schema",
            "P0",
            "deepseek_resume_after_top3",
            "output_schema",
            "blocked_missing_output",
            "LLM success JSONL fields include window_id, parent_window_id, window_decision, patch_decisions, call_seconds, total_tokens, call_attempts, max_call_attempts",
            [
                "outputs/research_progress_snapshot/live_output_schema_contract.json",
                "outputs/research_progress_snapshot/live_metric_extraction_contract.json",
            ],
            "prevents incomplete output rows from entering safety or latency scoring",
        ),
        row(
            "deepseek_resume_safety_zero_harm",
            "P0",
            "deepseek_resume_after_top3",
            "safety_scoring",
            "blocked_waiting_live_output",
            "harmful_accepts == 0, missing_patch_eval == 0, parent_window_decision_override is true",
            [
                "outputs/research_progress_snapshot/live_scoring_readiness.json",
                "outputs/research_progress_snapshot/live_metric_extraction_contract.json",
            ],
            "enables DeepSeek split20 zero-harm safety claim after output coverage passes",
        ),
        row(
            "deepseek_split20_latency_evidence",
            "P0",
            "deepseek_resume_after_top3",
            "latency_scoring",
            "blocked_waiting_live_output",
            "104 parent windows, 147 split calls, split comparison summary present, harmful_accepts == 0, traceability covered",
            [
                "outputs/research_progress_snapshot/live_metric_extraction_contract.json",
                "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json",
            ],
            "can promote split20 from top3 smoke/planning into full-surface latency evidence",
        ),
        row(
            "omni48_output_schema",
            "P1",
            "omni48_label_only",
            "omni_output_schema",
            "blocked_missing_output",
            "96 Omni rows, 48 windows, schema_ok true, call_id/model/risk/quarantine/latency/retry fields present",
            [
                "outputs/research_progress_snapshot/live_output_audit.json",
                "outputs/research_progress_snapshot/live_output_schema_contract.json",
            ],
            "unblocks Omni48 label-only scoring without timeline writeback",
        ),
        row(
            "omni48_label_metrics",
            "P1",
            "omni48_label_only",
            "omni_label_scoring",
            "blocked_waiting_live_output",
            "high_positive_rate, clean_false_positive_rate, quarantines, defers, avg/P95/max call latency reported for both models",
            [
                "outputs/research_progress_snapshot/live_metric_extraction_contract.json",
                "outputs/research_progress_snapshot/omni48_live_call_manifest.json",
            ],
            "promotes Omni48 label-only metrics while preserving no timeline writeback",
        ),
        row(
            "qwen_backup_fallback_boundary",
            "P1",
            "qwen_full_backup",
            "fallback_boundary",
            "fallback_only",
            "full backup output and scoring can be reported only as fallback unless promotion gate changes primary boundary",
            [
                "outputs/research_progress_snapshot/live_metric_extraction_contract.json",
                "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json",
            ],
            "keeps Qwen out of primary latency claim by default",
        ),
        row(
            "report_ppt_promotion_sync",
            "P0",
            "report_ppt",
            "traceability_sync",
            "preserve_pass",
            "traceability fully covered rows == traceability rows and latest_artifact_validation passes after any promotion",
            [
                "outputs/research_progress_snapshot/report_ppt_traceability.json",
                "outputs/research_progress_snapshot/latest_artifact_validation.json",
            ],
            "ensures report and PPT show promoted, fallback-only, and blocked surfaces consistently",
        ),
    ]

    return {
        "runtime_contract": "post_live_acceptance_scorecard_no_live_calls",
        "status": "blocked_waiting_live_outputs",
        "source_contracts": {
            "stage_latency_slo_audit": slo.get("runtime_contract", ""),
            "live_output_audit": output.get("runtime_contract", ""),
            "live_scoring_readiness": scoring.get("runtime_contract", ""),
            "live_metric_extraction_contract": metric.get("runtime_contract", ""),
            "live_output_schema_contract": schema.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
            "latency_risk_margin_audit": risk.get("runtime_contract", ""),
        },
        "summary": {
            "scorecard_rows": len(rows),
            "p0_scorecard_rows": sum(1 for item in rows if item["priority"] == "P0"),
            "p1_scorecard_rows": sum(1 for item in rows if item["priority"] == "P1"),
            "preserve_pass_rows": sum(1 for item in rows if item["current_status"] == "preserve_pass"),
            "blocked_rows": sum(1 for item in rows if item["current_status"].startswith("blocked")),
            "fallback_only_rows": sum(1 for item in rows if item["current_status"] == "fallback_only"),
            "claim_now_slo_pass": as_int(slo_summary.get("claim_now_slo_pass")),
            "claim_now_slo_rows": as_int(slo_summary.get("claim_now_slo_rows")),
            "guard_p95_margin_seconds": risk_summary.get("guard_p95_margin_seconds", ""),
            "expected_live_calls": as_int(output_summary.get("expected_live_calls")),
            "missing_output_surfaces": as_int(output_summary.get("missing_output_surfaces")),
            "ready_to_score_steps": as_int(scoring_summary.get("ready_to_score_steps")),
            "metric_contract_count": as_int(metric_summary.get("metric_contract_count")),
            "schema_contract_count": as_int(schema_summary.get("schema_contract_count")),
            "ready_to_promote_count": as_int(promotion_summary.get("ready_to_promote_count")),
            "traceability_rows": as_int(promotion_summary.get("traceability_rows")),
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(scorecard: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "scorecard_id",
        "priority",
        "surface_id",
        "acceptance_area",
        "current_status",
        "pass_condition",
        "evidence_artifacts",
        "claim_effect",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in scorecard["rows"]:
            out = dict(item)
            out["evidence_artifacts"] = "; ".join(out["evidence_artifacts"])
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def write_markdown(scorecard: dict[str, Any], path: Path) -> None:
    summary = scorecard["summary"]
    lines = [
        "# Post-Live Acceptance Scorecard",
        "",
        f"- Runtime contract: `{scorecard['runtime_contract']}`",
        f"- Status: `{scorecard['status']}`",
        f"- Scorecard rows: `{summary['scorecard_rows']}`",
        f"- P0 rows: `{summary['p0_scorecard_rows']}`",
        f"- Blocked rows: `{summary['blocked_rows']}`",
        f"- Fallback-only rows: `{summary['fallback_only_rows']}`",
        f"- Claim-now SLO pass: `{summary['claim_now_slo_pass']}/{summary['claim_now_slo_rows']}`",
        f"- Guard P95 margin seconds: `{summary['guard_p95_margin_seconds']}`",
        f"- Expected live calls: `{summary['expected_live_calls']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- Ready to score: `{summary['ready_to_score_steps']}`",
        f"- Metric contracts: `{summary['metric_contract_count']}`",
        f"- Schema contracts: `{summary['schema_contract_count']}`",
        f"- Ready to promote: `{summary['ready_to_promote_count']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Scorecard | Surface | Priority | Area | Status | Pass condition | Claim effect |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in scorecard["rows"]:
        lines.append(
            f"| `{item['scorecard_id']}` | `{item['surface_id']}` | `{item['priority']}` | "
            f"`{item['acceptance_area']}` | `{item['current_status']}` | {item['pass_condition']} | {item['claim_effect']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This scorecard is the post-live acceptance entrypoint after output audit, schema contract, scoring readiness, and metric extraction.",
            "- Preserve rows keep current reportable claims; blocked rows cannot be promoted until live outputs and scoring artifacts exist.",
            "- Qwen remains fallback-only unless a future promotion gate explicitly changes its claim boundary.",
            "- The builder only reads local artifacts; it performs no live/API/model/scoring calls and writes no secrets.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    scorecard = build_scorecard(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(scorecard, args.output_md)
    write_csv(scorecard, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
