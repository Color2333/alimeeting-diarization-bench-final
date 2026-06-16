#!/usr/bin/env python3
"""Build a no-live-call gate for promoting post-live results into claims."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_claim_promotion_gate.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_claim_promotion_gate.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def source_paths_exist(root: Path, sources: list[str]) -> bool:
    return all((root / source).exists() for source in sources if source.startswith("outputs/"))


def build_gate(root: Path) -> dict[str, Any]:
    slo = read_json(root / "outputs/research_progress_snapshot/stage_latency_slo_audit.json")
    live_readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    live_output = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    scoring = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    postrun = read_json(root / "outputs/research_progress_snapshot/live_postrun_metrics_closure.json")
    runbook = read_json(root / "outputs/research_progress_snapshot/live_execution_runbook.json")
    selector_split = read_json(root / "outputs/research_progress_snapshot/selector_true_heldout_split_validation.json")
    split_policy = read_json(root / "outputs/research_progress_snapshot/split_policy_optimization.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")
    latency_risk = read_json(root / "outputs/research_progress_snapshot/latency_risk_margin_audit.json")

    live_output_summary = live_output.get("summary", {})
    scoring_summary = scoring.get("summary", {})
    postrun_summary = postrun.get("summary", {})
    runbook_summary = runbook.get("summary", {})
    selector_split_summary = selector_split.get("summary", {})
    split_policy_summary = split_policy.get("summary", {})
    slo_summary = slo.get("summary", {})
    traceability_summary = traceability.get("summary", {})
    latency_risk_summary = latency_risk.get("summary", {})

    rows = [
        {
            "gate_id": "current_latency_slo_claims",
            "claim_surface": "current reportable latency SLO rows",
            "promotion_decision": "preserve_current_claim",
            "claim_effect": "keeps four claim-now latency rows in report/PPT",
            "blocking_gate": "none",
            "success_gate": "claim_now_slo_pass == claim_now_slo_rows == 4",
            "observed_state": (
                f"{slo_summary.get('claim_now_slo_pass', 0)}/{slo_summary.get('claim_now_slo_rows', 0)} SLO pass; "
                f"guard risk {latency_risk_summary.get('guard_risk_level', 'pending_risk_audit')}"
            ),
            "next_action": "preserve while post-live rows remain pending",
            "source_artifacts": [
                "outputs/research_progress_snapshot/stage_latency_slo_audit.json",
                "outputs/research_progress_snapshot/runtime_latency_budget_ledger.json",
                "outputs/research_progress_snapshot/latency_risk_margin_audit.json",
            ],
        },
        {
            "gate_id": "deepseek_split20_resume_latency",
            "claim_surface": "DeepSeek split20 104-window full-surface latency",
            "promotion_decision": "blocked_missing_live_output",
            "claim_effect": "would promote split20 from top3 smoke/offline budget to full-surface latency evidence",
            "blocking_gate": postrun_summary.get("split20_latency_claim_status", "blocked_by_quota_or_missing_resume"),
            "success_gate": "deepseek resume output complete, safety scoring pass, comparison summary present",
            "observed_state": (
                f"resume expected {postrun_summary.get('deepseek_resume_expected_calls', 139)} calls; "
                f"successful {postrun_summary.get('deepseek_resume_successful_calls', 0)}; "
                f"missing output surfaces {live_output_summary.get('missing_output_surfaces', 3)}"
            ),
            "next_action": "run P0 DeepSeek max20 resume after credentials/quota are ready",
            "source_artifacts": [
                "outputs/research_progress_snapshot/split20_full_live_manifest.json",
                "outputs/research_progress_snapshot/live_postrun_metrics_closure.json",
                "outputs/research_progress_snapshot/live_output_audit.json",
                "outputs/research_progress_snapshot/live_scoring_readiness.json",
            ],
        },
        {
            "gate_id": "deepseek_split20_resume_safety",
            "claim_surface": "DeepSeek split20 resume zero-harm safety",
            "promotion_decision": "blocked_waiting_scoring",
            "claim_effect": "would promote resumed split20 guard decisions into safety evidence",
            "blocking_gate": "blocked_missing_output",
            "success_gate": "deepseek_resume_safety scoring step ready and harmful_accepts == 0",
            "observed_state": (
                f"ready to score {scoring_summary.get('ready_to_score_steps', 0)}/"
                f"{scoring_summary.get('scoring_step_count', 5)}; "
                f"P0 scoring steps {scoring_summary.get('p0_scoring_steps', 2)}"
            ),
            "next_action": "wait for resume JSONL, then run planned safety scoring command",
            "source_artifacts": [
                "outputs/research_progress_snapshot/live_scoring_readiness.json",
                "outputs/research_progress_snapshot/live_output_audit.json",
            ],
        },
        {
            "gate_id": "omni48_label_metrics",
            "claim_surface": "Omni48 label-only recall/precision/latency",
            "promotion_decision": "blocked_missing_live_output",
            "claim_effect": "would promote Omni from 12-window smoke/fusion to 48-window label metrics",
            "blocking_gate": postrun_summary.get("omni48_latency_claim_status", "pending_omni48_live_outputs"),
            "success_gate": "96 Omni calls complete and omni48_label_summary scoring is ready",
            "observed_state": (
                f"expected {postrun_summary.get('omni48_expected_calls', 96)} calls; "
                f"successful {postrun_summary.get('omni48_successful_calls', 0)}"
            ),
            "next_action": "run Omni48 label-only live calls after credentials are present",
            "source_artifacts": [
                "outputs/research_progress_snapshot/omni48_live_call_manifest.json",
                "outputs/research_progress_snapshot/live_postrun_metrics_closure.json",
                "outputs/research_progress_snapshot/live_scoring_readiness.json",
            ],
        },
        {
            "gate_id": "qwen_full_backup_claim",
            "claim_surface": "Qwen full-surface backup LLM guard",
            "promotion_decision": "fallback_only_not_primary_latency_claim",
            "claim_effect": "can support execution fallback/safety only, not the primary latency claim",
            "blocking_gate": "backup surface missing and prior top4/5 wall slower than original max",
            "success_gate": "full backup output exists and safety/comparison scoring passes",
            "observed_state": (
                f"backup expected {scoring_summary.get('qwen_full_expected_calls', 147)} calls; "
                f"split policy primary {split_policy_summary.get('primary_policy', 'max20')}"
            ),
            "next_action": "keep as P1 fallback after DeepSeek primary path",
            "source_artifacts": [
                "outputs/research_progress_snapshot/split_policy_optimization.json",
                "outputs/research_progress_snapshot/live_scoring_readiness.json",
            ],
        },
        {
            "gate_id": "selector_true_heldout_claim",
            "claim_surface": "selector true-heldout generalization",
            "promotion_decision": "blocked_waiting_valid_sealed_split",
            "claim_effect": "would promote selector from dev-only validation to true-heldout evidence",
            "blocking_gate": selector_split.get("status", "blocked_waiting_for_valid_sealed_split"),
            "success_gate": "sealed split exists, >=8 true-heldout recordings, no development overlap",
            "observed_state": (
                f"true-heldout recordings {selector_split_summary.get('true_heldout_recordings', 0)}; "
                f"missing new recordings {selector_split_summary.get('missing_new_recordings_to_minimum', 8)}"
            ),
            "next_action": "add a sealed split with new recordings before scoring",
            "source_artifacts": [
                "outputs/research_progress_snapshot/selector_true_heldout_split_validation.json",
                "outputs/research_progress_snapshot/selector_true_heldout_protocol.json",
            ],
        },
        {
            "gate_id": "live_execution_handoff",
            "claim_surface": "operator handoff for live LLM/Omni execution",
            "promotion_decision": "blocked_waiting_credentials_or_outputs",
            "claim_effect": "does not promote metrics; keeps the execution sequence auditable",
            "blocking_gate": runbook.get("status", "blocked_waiting_for_credentials_or_live_outputs"),
            "success_gate": "credential preflight ready, P0 resume run completed, output audit and scoring pass",
            "observed_state": (
                f"runbook steps {runbook_summary.get('runbook_step_count', 7)}; "
                f"P0 planned calls {runbook_summary.get('p0_planned_live_calls', 139)}; "
                f"ready runs {runbook_summary.get('ready_runs', 0)}"
            ),
            "next_action": "start from runbook step 1 when credentials/quota are available",
            "source_artifacts": [
                "outputs/research_progress_snapshot/live_execution_runbook.json",
                "outputs/research_progress_snapshot/live_run_readiness.json",
            ],
        },
        {
            "gate_id": "report_ppt_sync_after_promotion",
            "claim_surface": "report/PPT synchronization after any claim promotion",
            "promotion_decision": "preserve_sync_gate",
            "claim_effect": "ensures promoted or blocked states are visible in both report and PPT",
            "blocking_gate": "none",
            "success_gate": "traceability fully covered rows == traceability rows",
            "observed_state": (
                f"fully covered {traceability_summary.get('fully_covered_rows', 0)}/"
                f"{traceability_summary.get('traceability_rows', 0)}"
            ),
            "next_action": "rerun refresh after any live output/scoring artifact appears",
            "source_artifacts": [
                "outputs/research_progress_snapshot/report_ppt_traceability.json",
                "outputs/research_progress_snapshot/latest_artifact_validation.json",
            ],
        },
    ]

    for row in rows:
        row["source_artifacts_exist"] = source_paths_exist(root, row["source_artifacts"])
        row["live_calls_performed_by_builder"] = 0
        row["ready_to_promote"] = row["promotion_decision"] == "ready_to_promote"

    missing_source_rows = [row["gate_id"] for row in rows if not row["source_artifacts_exist"]]
    ready_to_promote = [row["gate_id"] for row in rows if row["ready_to_promote"]]
    blocked_rows = [row["gate_id"] for row in rows if row["promotion_decision"].startswith("blocked")]
    preserve_rows = [
        row["gate_id"]
        for row in rows
        if row["promotion_decision"].startswith("preserve")
    ]
    fallback_rows = [row["gate_id"] for row in rows if "fallback_only" in row["promotion_decision"]]

    status = "pass" if not ready_to_promote and not missing_source_rows else "needs_promotion_review"
    return {
        "runtime_contract": "post_live_claim_promotion_gate_no_live_calls",
        "status": status,
        "promotion_policy": "promote_only_after_output_audit_scoring_slo_and_traceability_pass",
        "summary": {
            "gate_count": len(rows),
            "ready_to_promote_count": len(ready_to_promote),
            "blocked_count": len(blocked_rows),
            "preserve_count": len(preserve_rows),
            "fallback_only_count": len(fallback_rows),
            "missing_source_rows": len(missing_source_rows),
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
            "claim_now_slo_pass": as_int(slo_summary.get("claim_now_slo_pass")),
            "claim_now_slo_rows": as_int(slo_summary.get("claim_now_slo_rows")),
            "ready_runs": as_int(live_readiness.get("summary", {}).get("ready_count")),
            "missing_output_surfaces": as_int(live_output_summary.get("missing_output_surfaces")),
            "ready_to_score_steps": as_int(scoring_summary.get("ready_to_score_steps")),
            "traceability_fully_covered_rows": as_int(traceability_summary.get("fully_covered_rows")),
            "traceability_rows": as_int(traceability_summary.get("traceability_rows")),
        },
        "ready_to_promote_gate_ids": ready_to_promote,
        "blocked_gate_ids": blocked_rows,
        "preserve_gate_ids": preserve_rows,
        "fallback_only_gate_ids": fallback_rows,
        "missing_source_gate_ids": missing_source_rows,
        "gates": rows,
    }


def write_csv(gate: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "gate_id",
        "claim_surface",
        "promotion_decision",
        "claim_effect",
        "blocking_gate",
        "success_gate",
        "observed_state",
        "next_action",
        "source_artifacts_exist",
        "ready_to_promote",
        "source_artifacts",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in gate["gates"]:
            out = dict(row)
            out["source_artifacts"] = "; ".join(out["source_artifacts"])
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def write_markdown(gate: dict[str, Any], path: Path) -> None:
    summary = gate["summary"]
    lines = [
        "# Post-Live Claim Promotion Gate",
        "",
        f"- Runtime contract: `{gate['runtime_contract']}`",
        f"- Status: `{gate['status']}`",
        f"- Promotion policy: `{gate['promotion_policy']}`",
        f"- Gates: `{summary['gate_count']}`",
        f"- Ready to promote: `{summary['ready_to_promote_count']}`",
        f"- Blocked: `{summary['blocked_count']}`",
        f"- Preserve/current sync gates: `{summary['preserve_count']}`",
        f"- Fallback-only gates: `{summary['fallback_only_count']}`",
        f"- Missing source rows: `{summary['missing_source_rows']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "## Gates",
        "",
        "| Gate | Claim surface | Decision | Blocking gate | Observed state | Next action |",
        "|---|---|---|---|---|---|",
    ]
    for row in gate["gates"]:
        lines.append(
            f"| `{row['gate_id']}` | {row['claim_surface']} | `{row['promotion_decision']}` | "
            f"`{row['blocking_gate']}` | {row['observed_state']} | {row['next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- A gate can become `ready_to_promote` only after live output coverage, scoring readiness/results, SLO status, and report/PPT traceability all pass.",
            "- Current reportable claims are preserved, while post-live DeepSeek, Omni48, and true-heldout selector claims remain blocked or pending.",
            "- This builder only reads local artifacts; it writes no secrets and performs no live/API/model calls.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    gate = build_gate(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(gate, args.output_md)
    write_csv(gate, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
