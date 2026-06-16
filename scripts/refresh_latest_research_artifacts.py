#!/usr/bin/env python3
"""Refresh lightweight report artifacts from existing experiment outputs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def command_plan() -> list[list[str]]:
    commands = [
        [sys.executable, "scripts/build_timeline_review_audit.py"],
        [sys.executable, "scripts/build_memory_update_replay.py"],
        [
            sys.executable,
            "scripts/build_system_timeline_summary.py",
            "--latencies",
            "outputs/latency_tradeoff/main_models.csv",
            "--segments",
            "120",
            "--writeback-impact",
            "outputs/writeback_gate_120/writeback_impact_summary.json",
            "--guard-summary",
            "outputs/llm_window_batch/window_batch_summary.csv",
            "--runtime-safe-guard-summary",
            "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_safety_summary.json",
            "--review-audit-summary",
            "outputs/timeline_review_audit/llm_review_signal_timeline_audit_summary.json",
            "--output-csv",
            "outputs/system_timeline/system_timeline.csv",
            "--output-md",
            "outputs/system_timeline/system_timeline.md",
            "--summary-json",
            "outputs/system_timeline/summary.json",
        ],
        [
            sys.executable,
            "scripts/evaluate_rule_writeback_timeline.py",
            "--fast-summary",
            "outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json",
            "--slow-summary",
            "outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json",
            "--gate-decisions",
            "outputs/writeback_gate_120/gate_decisions.csv",
            "--patches",
            "outputs/segment_patches/sortformer_diarizen_120_patches.csv",
            "--output-dir",
            "outputs/rule_writeback_timeline_120",
        ],
        [sys.executable, "scripts/validate_recover_selector_split.py"],
        [sys.executable, "scripts/build_selector_true_heldout_candidate_scan.py"],
        [sys.executable, "scripts/validate_selector_true_heldout_split_file.py"],
        [
            sys.executable,
            "scripts/bootstrap_realtime_contract_metrics.py",
            "--results",
            "outputs/rule_writeback_timeline_120/rule_writeback_timeline_results.csv",
            "--output-dir",
            "outputs/realtime_contract_bootstrap_120",
        ],
        [
            sys.executable,
            "scripts/analyze_realtime_contract_by_recording.py",
            "--results",
            "outputs/rule_writeback_timeline_120/rule_writeback_timeline_results.csv",
            "--output-dir",
            "outputs/realtime_contract_recording_stability_120",
        ],
        [sys.executable, "scripts/build_selector_true_heldout_protocol.py"],
        [sys.executable, "scripts/build_omni_guard_summary.py"],
        [
            sys.executable,
            "scripts/summarize_omni_window_batch.py",
            "outputs/omni_guard/omni_flash_plus_window_batch_12.csv",
        ],
        [sys.executable, "scripts/analyze_omni_acoustic_fusion.py"],
        [sys.executable, "scripts/build_omni_expansion_manifest.py"],
        [sys.executable, "scripts/build_omni48_live_call_manifest.py"],
        [sys.executable, "scripts/analyze_runtime_safe_llm_latency.py"],
        [sys.executable, "scripts/simulate_runtime_safe_llm_splitting.py"],
        [sys.executable, "scripts/analyze_llm_guard_tuning.py"],
        [sys.executable, "scripts/materialize_llm_guard_tuning.py"],
        [
            sys.executable,
            "scripts/analyze_runtime_safe_llm_guard.py",
            "--batch-jsonl",
            "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned.jsonl",
            "--output-csv",
            "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_passthrough_safety.csv",
            "--output-md",
            "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_passthrough_safety.md",
            "--summary-json",
            "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_passthrough_safety_summary.json",
            "--allow-keep-fast-passthrough-in-quarantine",
        ],
        [sys.executable, "scripts/materialize_tuned_writeback_gate.py"],
        [
            sys.executable,
            "scripts/evaluate_rule_writeback_timeline.py",
            "--fast-summary",
            "outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json",
            "--slow-summary",
            "outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json",
            "--gate-decisions",
            "outputs/runtime_safe_llm_window_batch/tuned_v2_writeback_gate_decisions.csv",
            "--patches",
            "outputs/segment_patches/sortformer_diarizen_120_patches.csv",
            "--output-dir",
            "outputs/runtime_safe_llm_window_batch/tuned_v2_writeback_timeline",
        ],
        [sys.executable, "scripts/audit_runtime_evidence_contract.py"],
        [sys.executable, "scripts/build_der_latency_pareto.py"],
        [sys.executable, "scripts/build_system_experiment_matrix.py"],
        [sys.executable, "scripts/build_runtime_latency_budget_ledger.py"],
        [sys.executable, "scripts/build_stage_latency_slo_audit.py"],
        [sys.executable, "scripts/build_research_progress_snapshot.py"],
        [sys.executable, "scripts/build_research_claims_manifest.py"],
        [sys.executable, "scripts/build_runtime_replay_manifest.py"],
        [sys.executable, "scripts/build_split20_full_live_manifest.py"],
        [sys.executable, "scripts/build_split20_resume_export_audit.py"],
        [sys.executable, "scripts/build_split_policy_optimization.py"],
        [sys.executable, "scripts/build_split15_stretch_reexport_audit.py"],
        [sys.executable, "scripts/build_live_run_readiness.py"],
        [sys.executable, "scripts/build_live_agent_execution_plan.py"],
        [sys.executable, "scripts/build_live_postrun_metrics_closure.py"],
        [sys.executable, "scripts/build_live_output_audit.py"],
        [sys.executable, "scripts/build_live_scoring_readiness.py"],
        [sys.executable, "scripts/build_live_input_integrity_audit.py"],
        [sys.executable, "scripts/build_live_execution_runbook.py"],
        [sys.executable, "scripts/build_live_command_surface_audit.py"],
        [sys.executable, "scripts/build_live_output_repair_plan.py"],
        [sys.executable, "scripts/run_live_execution_sequence.py"],
        [sys.executable, "scripts/build_live_execution_receipt_audit.py"],
        [sys.executable, "scripts/build_live_resume_state_audit.py"],
        [sys.executable, "scripts/build_live_runtime_environment_audit.py"],
        [sys.executable, "scripts/build_live_execution_timing_plan.py"],
        [sys.executable, "scripts/build_live_retry_budget_audit.py"],
        [sys.executable, "scripts/build_live_token_quota_budget_audit.py"],
        [sys.executable, "scripts/build_live_parallelism_sensitivity.py"],
        [sys.executable, "scripts/build_live_failure_recovery_playbook.py"],
        [sys.executable, "scripts/build_research_next_experiment_queue.py"],
        [sys.executable, "scripts/build_post_live_claim_promotion_gate.py"],
        [sys.executable, "scripts/build_live_metric_extraction_contract.py"],
        [sys.executable, "scripts/build_live_output_schema_contract.py"],
        [sys.executable, "scripts/build_latency_risk_margin_audit.py"],
        [sys.executable, "scripts/build_post_live_acceptance_scorecard.py"],
        [sys.executable, "scripts/build_live_execution_handoff_packet.py"],
        [sys.executable, "scripts/build_post_live_latency_claim_matrix.py"],
        [sys.executable, "scripts/build_post_live_scoring_execution_plan.py"],
        [sys.executable, "scripts/run_post_live_scoring_sequence.py"],
        [sys.executable, "scripts/build_post_live_scoring_output_audit.py"],
        [sys.executable, "scripts/build_post_live_evidence_dependency_dag.py"],
        [sys.executable, "scripts/build_live_execution_bundle.py"],
        [sys.executable, "scripts/build_post_live_time_metric_statistics_plan.py"],
        [sys.executable, "scripts/build_post_live_time_metric_extractor.py"],
        [sys.executable, "scripts/build_post_live_promotion_preflight_audit.py"],
        [sys.executable, "scripts/build_post_live_scoring_receipt_audit.py"],
        [sys.executable, "scripts/build_post_live_time_metric_receipt_audit.py"],
        [sys.executable, "scripts/build_post_live_claim_promotion_receipt_audit.py"],
        [sys.executable, "scripts/build_live_execution_eligibility_gate.py"],
        [sys.executable, "scripts/build_latency_risk_mitigation_plan.py"],
        [sys.executable, "scripts/build_phase_result_scorecard.py"],
        [sys.executable, "scripts/build_live_provider_routing_decision.py"],
    ]
    commands.append([sys.executable, "scripts/run_live_execution_sequence.py"])
    commands.append([sys.executable, "scripts/build_live_execution_receipt_audit.py"])
    commands.append([sys.executable, "scripts/build_post_live_claim_promotion_gate.py"])
    commands.append([sys.executable, "scripts/build_latency_risk_margin_audit.py"])
    commands.append([sys.executable, "scripts/build_post_live_acceptance_scorecard.py"])
    commands.append([sys.executable, "scripts/build_live_execution_handoff_packet.py"])
    commands.append([sys.executable, "scripts/build_post_live_latency_claim_matrix.py"])
    commands.append([sys.executable, "scripts/build_post_live_scoring_execution_plan.py"])
    commands.append([sys.executable, "scripts/run_post_live_scoring_sequence.py"])
    commands.append([sys.executable, "scripts/build_post_live_scoring_output_audit.py"])
    commands.append([sys.executable, "scripts/build_post_live_evidence_dependency_dag.py"])
    commands.append([sys.executable, "scripts/build_live_execution_bundle.py"])
    commands.append([sys.executable, "scripts/build_post_live_time_metric_statistics_plan.py"])
    commands.append([sys.executable, "scripts/build_post_live_time_metric_extractor.py"])
    commands.append([sys.executable, "scripts/build_post_live_promotion_preflight_audit.py"])
    commands.append([sys.executable, "scripts/build_post_live_scoring_receipt_audit.py"])
    commands.append([sys.executable, "scripts/build_post_live_time_metric_receipt_audit.py"])
    commands.append([sys.executable, "scripts/build_post_live_claim_promotion_receipt_audit.py"])
    commands.append([sys.executable, "scripts/build_live_execution_eligibility_gate.py"])
    commands.append([sys.executable, "scripts/build_latency_risk_mitigation_plan.py"])
    commands.append([sys.executable, "scripts/build_phase_result_scorecard.py"])
    commands.append([sys.executable, "scripts/build_live_provider_routing_decision.py"])
    commands.append([sys.executable, "scripts/validate_latest_research_artifacts.py"])
    return commands


def run_command(cmd: list[str], dry_run: bool) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {
        "command": cmd,
        "returncode": None,
        "elapsed_seconds": 0.0,
        "stdout_tail": "",
        "stderr_tail": "",
    }
    if dry_run:
        result["returncode"] = 0
        result["dry_run"] = True
        return result
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    result["returncode"] = proc.returncode
    result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    result["stdout_tail"] = "\n".join(proc.stdout.splitlines()[-8:])
    result["stderr_tail"] = "\n".join(proc.stderr.splitlines()[-8:])
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr}")
    return result


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Latest Research Artifact Refresh",
        "",
        f"- Status: `{summary['status']}`",
        f"- Commands: `{summary['commands']}`",
        f"- Total elapsed: `{summary['elapsed_seconds']:.2f}s`",
        "",
        "| Step | Return | Elapsed | Command |",
        "|---:|---:|---:|---|",
    ]
    for idx, row in enumerate(summary["steps"], start=1):
        lines.append(
            f"| {idx} | {row['returncode']} | {float(row['elapsed_seconds']):.2f}s | `{' '.join(row['command'])}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This refresh rebuilds derived analysis/reporting artifacts from existing experiment outputs.",
            "- It does not run new model inference or live LLM/API calls.",
            "- Use it before updating final reports to keep timeline, memory replay, selector validation, selector true-heldout candidate scan, selector true-heldout split validation, selector true-heldout protocol, Omni fusion, Omni expansion manifest, Omni48 call manifest, LLM guard latency, split simulation, split20 full-live manifest, split20 resume export audit, split policy optimization, tuning/materialization, Pareto, runtime-audit, matrix, latency budget ledger, latency SLO audit, latency risk margin audit, latency risk mitigation plan, snapshot, claims manifest, runtime replay manifest, live-run readiness, live Agent execution plan, live postrun metrics closure, live output audit, live scoring readiness, live input integrity audit, live execution runbook, live command surface audit, live execution eligibility gate, live execution receipt audit, live resume state audit, live runtime environment audit, live execution timing plan, live retry budget audit, live token/quota budget audit, live parallelism sensitivity, next-experiment queue, post-live claim promotion gate, post-live scoring output audit, post-live promotion preflight audit, post-live scoring receipt audit, post-live time metric receipt audit, post-live claim promotion receipt audit, phase result scorecard, live provider routing decision, and validation numbers aligned.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print and record commands without running them.")
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/research_progress_snapshot/refresh_latest_artifacts.json"))
    parser.add_argument("--summary-md", type=Path, default=Path("outputs/research_progress_snapshot/refresh_latest_artifacts.md"))
    args = parser.parse_args()

    started = time.perf_counter()
    commands = command_plan()
    steps = []
    for cmd in commands:
        print("+ " + " ".join(cmd))
        steps.append(run_command(cmd, dry_run=args.dry_run))

    summary = {
        "status": "dry_run" if args.dry_run else "pass",
        "commands": len(commands),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "steps": steps,
        "runtime_contract": "lightweight_refresh_no_model_or_live_llm_calls",
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, args.summary_md)
    print(f"Wrote {args.summary_json}")
    print(f"Wrote {args.summary_md}")


if __name__ == "__main__":
    main()
