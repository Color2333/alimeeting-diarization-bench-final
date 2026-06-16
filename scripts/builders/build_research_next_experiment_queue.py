#!/usr/bin/env python3
"""Build the next-experiment queue from current validated research claims."""

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
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_queue(root: Path) -> dict[str, Any]:
    manifest = read_json(root / "outputs/research_progress_snapshot/claims_manifest.json")
    snapshot = read_json(root / "outputs/research_progress_snapshot/snapshot.json")
    claims = {claim.get("claim_id"): claim for claim in manifest.get("claims", [])}
    selector = snapshot.get("selector_generalization", {})
    split20 = snapshot.get("runtime_safe_split20", {})
    omni = snapshot.get("omni_fusion", {})
    tuning = snapshot.get("runtime_safe_guard_tuning", {})
    audit = snapshot.get("runtime_evidence_audit", {})
    omni_expansion = read_json(root / "outputs/research_progress_snapshot/omni_expansion_manifest.json")
    memory_replay = read_json(root / "outputs/research_progress_snapshot/memory_update_replay.json")
    replay_manifest = read_json(root / "outputs/research_progress_snapshot/runtime_replay_manifest.json")
    live_readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    live_agent_plan = read_json(root / "outputs/research_progress_snapshot/live_agent_execution_plan.json")
    live_postrun_closure = read_json(root / "outputs/research_progress_snapshot/live_postrun_metrics_closure.json")
    live_output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    live_scoring_readiness = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    live_execution_runbook = read_json(root / "outputs/research_progress_snapshot/live_execution_runbook.json")
    split_policy_optimization = read_json(root / "outputs/research_progress_snapshot/split_policy_optimization.json")
    selector_candidate_scan = read_json(root / "outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.json")
    selector_split_validation = read_json(root / "outputs/research_progress_snapshot/selector_true_heldout_split_validation.json")
    selector_protocol = read_json(root / "outputs/research_progress_snapshot/selector_true_heldout_protocol.json")
    baseline_headroom = read_json(root / "outputs/baseline_headroom_audit/baseline_headroom_audit.json")
    baseline_leaderboard = read_json(root / "outputs/baseline_leaderboard_audit/baseline_leaderboard_audit.json")
    recording_stability_blockers = read_json(root / "outputs/recording_stability_blockers/recording_stability_blockers.json")
    external_candidate_surface = read_json(root / "outputs/external_candidate_surface_search/external_candidate_surface_search.json")
    external_candidate_reproduction = read_json(root / "outputs/external_candidate_reproduction_plan/external_candidate_reproduction_plan.json")
    split20_manifest = read_json(root / "outputs/research_progress_snapshot/split20_full_live_manifest.json")
    readiness_by_run = {row.get("run_id"): row for row in live_readiness.get("runs", [])}
    memory_replay_complete = (
        memory_replay.get("runtime_contract") == "memory_update_replay_review_signal_blocks_memory_only"
        and not memory_replay.get("summary", {}).get("failed_rows")
    )
    replay_complete = (
        replay_manifest.get("runtime_contract") == "end_to_end_runtime_replay_manifest_no_eval_context"
        and not replay_manifest.get("summary", {}).get("failed_rows")
    )
    omni_expansion_prepared = (
        omni_expansion.get("runtime_contract") == "omni_expansion_manifest_ready_no_live_calls_no_timeline_writeback"
        and int(omni_expansion.get("summary", {}).get("selected_windows", 0)) >= 48
        and int(omni_expansion.get("summary", {}).get("audio_missing_count", 1)) == 0
    )

    can_claim_now = [
        {
            "claim_id": claim_id,
            "contract_scope": claim.get("contract_scope"),
            "writeback_right": claim.get("writeback_right"),
            "claim": claim.get("claim"),
        }
        for claim_id, claim in claims.items()
        if str(claim.get("claim_strength", "")).startswith("claim_now")
    ]

    next_experiments = [
        {
            "experiment_id": "full_split20_live_104w",
            "priority": "P0",
            "status": "blocked_by_deepseek_top4_5_quota",
            "target_claim": "split20_latency_path_limited",
            "current_evidence": (
                f"top3 live wall {split20.get('live_top3_measured_wall', 'n/a')} vs original max "
                f"{split20.get('live_top3_original_max', 'n/a')}; harmful "
                f"{split20.get('live_top3_harmful_accepts', 0)}; deepseek top4/5 "
                f"{split20.get('deepseek_top45_failure', 'n/a')}; readiness "
                f"{readiness_by_run.get('split20_deepseek_full', {}).get('status', 'not_built')}; "
                f"manifest resume calls {split20_manifest.get('summary', {}).get('deepseek_resume_required_calls_min', 'n/a')}; "
                f"Agent plan calls {live_agent_plan.get('summary', {}).get('planned_live_calls', 'n/a')}; "
                f"postrun closure {live_postrun_closure.get('summary', {}).get('split20_latency_claim_status', 'not_built')}; "
                f"output audit missing {live_output_audit.get('summary', {}).get('missing_output_surfaces', 'n/a')} surfaces; "
                f"scoring readiness P0 steps {live_scoring_readiness.get('summary', {}).get('p0_scoring_steps', 'n/a')}; "
                f"split policy primary {split_policy_optimization.get('summary', {}).get('primary_policy', 'n/a')} "
                f"vs stretch {split_policy_optimization.get('summary', {}).get('stretch_policy', 'n/a')}; "
                f"runbook steps {live_execution_runbook.get('summary', {}).get('runbook_step_count', 'n/a')}."
            ),
            "why_next": "This is the direct path from latency smoke evidence to full-surface LLM guard latency evidence.",
            "success_gates": [
                "Run all 104 parent windows with split<=20 live parallel calls.",
                "Keep effective harmful_accepts at 0 after runtime-safe quarantine override.",
                "Show measured wall-time improvement over unsplit max-call baseline on the full surface.",
                "Record token multiplier and provider failure rate.",
            ],
            "required_inputs": [
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompts.jsonl",
                "outputs/research_progress_snapshot/split20_full_live_manifest.json",
                "outputs/research_progress_snapshot/live_agent_execution_plan.json",
                "outputs/research_progress_snapshot/live_postrun_metrics_closure.json",
                "outputs/research_progress_snapshot/live_output_audit.json",
                "outputs/research_progress_snapshot/live_scoring_readiness.json",
                "outputs/research_progress_snapshot/live_execution_runbook.json",
                "outputs/research_progress_snapshot/split_policy_optimization.json",
                "outputs/research_progress_snapshot/live_run_readiness.json",
                "DeepSeek quota or equivalent provider capacity for top4/5 high-risk windows",
            ],
            "report_surface": "LLM POLICY / next-step queue",
        },
        {
            "experiment_id": "true_heldout_selector_recordings",
            "priority": "P0",
            "status": "needs_new_recording_split",
            "target_claim": "selector_generalization_positive",
            "current_evidence": (
                f"recording holdout {selector.get('positive_splits', 0)}/{selector.get('splits', 0)} positive; "
                f"heldout DER {selector.get('heldout_der', 'n/a')} vs Fast {selector.get('fast_der', 'n/a')}; "
                f"bootstrap delta {selector.get('bootstrap_delta', 'n/a')}; protocol "
                f"{selector_protocol.get('protocol_status', 'not_built')}; candidate scan eligible "
                f"{selector_candidate_scan.get('summary', {}).get('eligible_true_heldout_recordings', 'n/a')} "
                f"/ missing {selector_candidate_scan.get('summary', {}).get('missing_new_recordings_to_minimum', 'n/a')}; "
                f"sealed split validation {selector_split_validation.get('status', 'not_built')}."
            ),
            "why_next": "The selector is promising, but it is still development validation and should not be promoted to runtime evidence.",
            "success_gates": [
                "Use recordings not involved in threshold selection.",
                "Keep weighted DER below Fast and below rule writeback fallback.",
                "Report DER/Miss/FA/Conf plus arrival latency for each recording.",
                "Keep all selector prompt/runtime surfaces free of DER, GT support, and oracle labels.",
            ],
            "required_inputs": [
                "New AliMeeting recordings or a sealed split file",
                "outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.json",
                "outputs/research_progress_snapshot/selector_true_heldout_split_validation.json",
                "outputs/research_progress_snapshot/selector_true_heldout_protocol.json",
                "outputs/realtime_contract_recording_stability_120/per_recording.csv",
            ],
            "report_surface": "EXPERIMENT PROTOCOL / selector validation",
        },
        {
            "experiment_id": "new_candidate_surface_for_non_positive_recordings",
            "priority": "P0",
            "status": "ready_to_design_from_blocker_audit",
            "target_claim": "recording_level_stability_positive",
            "current_evidence": (
                f"recording stability blocker status {recording_stability_blockers.get('status', 'not_built')}; "
                f"non-positive recordings "
                f"{recording_stability_blockers.get('summary', {}).get('non_positive_recordings', 'n/a')}/"
                f"{recording_stability_blockers.get('summary', {}).get('recordings', 'n/a')}; "
                f"non-positive candidate-pool oracle gain "
                f"{recording_stability_blockers.get('summary', {}).get('non_positive_oracle_delta_vs_baseline_pp', 'n/a')}pp; "
                f"global candidate oracle gap "
                f"{recording_stability_blockers.get('summary', {}).get('global_oracle_gap_vs_current_pp', baseline_headroom.get('final_gap_to_oracle_pp', 'n/a'))}pp; "
                f"full baseline leaderboard "
                f"{baseline_leaderboard.get('summary', {}).get('full_coverage_baselines', 'n/a')} baselines, "
                f"beats all {baseline_leaderboard.get('summary', {}).get('beats_all_full_coverage_baselines', 'n/a')}; "
                f"external candidate surface {external_candidate_surface.get('status', 'not_built')} with best delta "
                f"{external_candidate_surface.get('best_policy', {}).get('delta_vs_current_pp', 'n/a')}pp, "
                f"coverage {external_candidate_surface.get('best_policy', {}).get('source_coverage_windows', 'n/a')} windows, "
                f"positive recordings {external_candidate_surface.get('best_policy', {}).get('positive_recordings_vs_clipped_slow', 'n/a')}/8; "
                f"reproduction plan {external_candidate_reproduction.get('status', 'not_built')}, missing "
                f"{external_candidate_reproduction.get('summary', {}).get('missing_windows', 'n/a')} windows, "
                f"resume supported {external_candidate_reproduction.get('summary', {}).get('resume_supported_by_checkpoint', 'n/a')}."
            ),
            "why_next": (
                "The current Fast/Slow/rule candidate pool is exhausted on the three non-positive recordings, "
                "so more threshold search is unlikely to make the recording-level gain robust."
            ),
            "success_gates": [
                "Create at least one new runtime-eligible candidate timeline for R8001_M8004, R8008_M8013, or R8009_M8020.",
                "Use prediction/audio/runtime features only; do not use DER, GT speaker labels, oracle support, or evaluation-only abnormal flags at selection time.",
                "Show candidate-level clipped DER improves at least one currently non-positive recording without adding negative overlay windows elsewhere.",
                "Promote to default runtime only after all-cached DER still beats the full-coverage baseline leaderboard and recording-level stability improves.",
            ],
            "required_inputs": [
                "outputs/recording_stability_blockers/recording_stability_blockers.json",
                "outputs/baseline_headroom_audit/baseline_headroom_audit.json",
                "outputs/baseline_leaderboard_audit/baseline_leaderboard_audit.json",
                "outputs/external_candidate_surface_search/external_candidate_surface_search.json",
                "outputs/external_candidate_reproduction_plan/external_candidate_reproduction_plan.json",
                "outputs/audio_window_features/audio_window_features.csv",
                "New candidate source: stronger VAD/speaker activity, pyannote/diarization rerun, or constrained segment repair",
            ],
            "report_surface": "OPTIMIZATION / candidate generation",
        },
        {
            "experiment_id": "omni_fusion_expand_48_or_120",
            "priority": "P1",
            "status": "prepared_manifest_pending_live_calls" if omni_expansion_prepared else "ready_to_run_from_existing_audio",
            "target_claim": "omni_fusion_label_only",
            "current_evidence": (
                f"{omni.get('windows', 0)} windows; high sentinel recall {omni.get('high_sentinel_recall', 'n/a')}; "
                f"clean sentinel FP {omni.get('clean_high_sentinel_fp', 'n/a')}; review FP {omni.get('clean_review_fp', 'n/a')}; "
                f"expansion manifest {omni_expansion.get('summary', {}).get('selected_windows', 'n/a')} windows; "
                f"readiness {readiness_by_run.get('omni48_live', {}).get('status', 'not_built')}; "
                f"Agent plan label-only calls {live_agent_plan.get('summary', {}).get('omni_label_only_calls', 'n/a')}; "
                f"postrun closure {live_postrun_closure.get('summary', {}).get('omni48_latency_claim_status', 'not_built')}; "
                f"output audit claim-ready {live_output_audit.get('summary', {}).get('claim_ready_surfaces', 'n/a')} surfaces; "
                f"scoring readiness blocked {live_scoring_readiness.get('summary', {}).get('blocked_steps', 'n/a')} steps."
            ),
            "why_next": "The current 12-window smoke proves fusion wiring and no-writeback safety, not final recall or precision.",
            "success_gates": [
                "Expand to at least 48 windows, preferably 120.",
                "Keep Omni output label-only with no timeline writeback.",
                "Separate high sentinel precision/recall from ordinary review hint false positives.",
                "Report first text latency, total latency, and acoustic-fusion arrival time.",
            ],
            "required_inputs": [
                "outputs/omni_guard/omni_flash_plus_window_batch_12.csv",
                "outputs/research_progress_snapshot/omni_expansion_manifest.csv",
                "outputs/research_progress_snapshot/live_agent_execution_plan.json",
                "outputs/research_progress_snapshot/live_postrun_metrics_closure.json",
                "outputs/research_progress_snapshot/live_output_audit.json",
                "outputs/research_progress_snapshot/live_scoring_readiness.json",
                "outputs/research_progress_snapshot/live_run_readiness.json",
                "audio windows selected from runtime-safe proxy buckets",
            ],
            "report_surface": "PARETO ROUTE / Omni fusion",
        },
        {
            "experiment_id": "memory_update_audit_replay",
            "priority": "P1",
            "status": "completed_validated_artifact" if memory_replay_complete else "ready_to_replay_from_existing_cases",
            "target_claim": "llm_review_memory_not_timeline",
            "current_evidence": (
                "4 review cases; timeline writeback blocks 0; memory update blocks 4; "
                f"replay blocked {memory_replay.get('summary', {}).get('memory_updates_blocked', 'n/a')}."
            ),
            "why_next": "Memory protection is the long-term contamination boundary; it needs a replay artifact, not just an audit count.",
            "success_gates": [
                "Replay all review/defer/repeatability-drift cases through the memory update gate.",
                "Show memory updates are blocked without changing timeline writeback.",
                "Emit before/after memory candidate counts and blocked reasons.",
                "Keep prompt/runtime surface free of GT and DER fields.",
            ],
            "required_inputs": [
                "outputs/timeline_review_audit/llm_review_signal_timeline_audit.csv",
                "outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_disagreement_cases.csv",
                "outputs/research_progress_snapshot/memory_update_replay.json",
            ],
            "report_surface": "ROUTE VALIDATION / speaker memory",
        },
        {
            "experiment_id": "end_to_end_runtime_replay_manifest",
            "priority": "P1",
            "status": "completed_validated_artifact" if replay_complete else "ready_to_build_from_existing_artifacts",
            "target_claim": "runtime_evidence_contract_clean",
            "current_evidence": (
                f"runtime evidence audit {audit.get('status', 'unknown')}; "
                f"{audit.get('artifact_count', 0)} artifacts; blocking {audit.get('runtime_blocking_count', 0)}; "
                f"replay stages {replay_manifest.get('summary', {}).get('stage_count', 'n/a')}."
            ),
            "why_next": "The current pieces pass separately; an end-to-end replay manifest would prove stage ordering and artifact lineage in one place.",
            "success_gates": [
                "Emit one manifest row per stage: Fast, Rule, LLM guard, LLM review, Omni label, memory gate.",
                "For each row, include arrival time, writeback right, source artifact, and validation check.",
                "Verify no runtime row references DER, GT support, oracle labels, or eval-only abnormal flags.",
                "Keep report/PPT derived from this manifest or explicitly linked to it.",
            ],
            "required_inputs": [
                "outputs/research_progress_snapshot/claims_manifest.json",
                "outputs/research_progress_snapshot/runtime_replay_manifest.json",
                "outputs/runtime_evidence_audit/runtime_evidence_audit.json",
                "outputs/system_timeline/summary.json",
            ],
            "report_surface": "SYSTEM TIMELINE / runtime contract",
        },
    ]

    do_not_deploy = [
        {
            "item_id": "boundary_auto_writeback",
            "source_claim": "boundary_auto_writeback_negative_control",
            "reason": (
                f"negative-control DER {tuning.get('boundary_negative_der', 'n/a')} vs recover-best "
                f"{tuning.get('recover_best_der', 'n/a')}; claim strength is do_not_deploy."
            ),
        }
    ]

    return {
        "runtime_contract": "research_next_experiment_queue_from_validated_claims",
        "can_claim_now": can_claim_now,
        "next_experiments": next_experiments,
        "do_not_deploy": do_not_deploy,
        "summary": {
            "claim_now_count": len(can_claim_now),
            "next_experiment_count": len(next_experiments),
            "p0_count": sum(1 for item in next_experiments if item["priority"] == "P0"),
            "blocked_count": sum(1 for item in next_experiments if str(item["status"]).startswith("blocked")),
            "ready_count": sum(1 for item in next_experiments if str(item["status"]).startswith("ready")),
            "prepared_count": sum(1 for item in next_experiments if str(item["status"]).startswith("prepared")),
            "completed_count": sum(1 for item in next_experiments if str(item["status"]).startswith("completed")),
            "do_not_deploy_count": len(do_not_deploy),
        },
    }


def write_markdown(queue: dict[str, Any], path: Path) -> None:
    lines = [
        "# Research Next Experiment Queue",
        "",
        f"- Runtime contract: `{queue['runtime_contract']}`",
        f"- Can claim now: `{queue['summary']['claim_now_count']}`",
        f"- Next experiments: `{queue['summary']['next_experiment_count']}`",
        f"- P0 experiments: `{queue['summary']['p0_count']}`",
        f"- Blocked experiments: `{queue['summary']['blocked_count']}`",
        f"- Ready experiments: `{queue['summary']['ready_count']}`",
        f"- Prepared experiments: `{queue['summary']['prepared_count']}`",
        f"- Completed experiments: `{queue['summary']['completed_count']}`",
        f"- Do-not-deploy items: `{queue['summary']['do_not_deploy_count']}`",
        "",
        "## Can Claim Now",
        "",
        "| Claim ID | Contract | Writeback right | Claim |",
        "|---|---|---|---|",
    ]
    for claim in queue["can_claim_now"]:
        text = str(claim["claim"]).replace("|", "/")
        lines.append(
            f"| `{claim['claim_id']}` | `{claim['contract_scope']}` | `{claim['writeback_right']}` | {text} |"
        )

    lines.extend(
        [
            "",
            "## Next Experiments",
            "",
            "| Experiment | Priority | Status | Target claim | Current evidence | Success gates |",
            "|---|---|---|---|---|---|",
        ]
    )
    for item in queue["next_experiments"]:
        gates = "<br>".join(item["success_gates"])
        evidence = str(item["current_evidence"]).replace("|", "/")
        lines.append(
            f"| `{item['experiment_id']}` | `{item['priority']}` | `{item['status']}` | "
            f"`{item['target_claim']}` | {evidence} | {gates} |"
        )

    lines.extend(["", "## Do Not Deploy", "", "| Item | Source claim | Reason |", "|---|---|---|"])
    for item in queue["do_not_deploy"]:
        reason = str(item["reason"]).replace("|", "/")
        lines.append(f"| `{item['item_id']}` | `{item['source_claim']}` | {reason} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=Path("outputs/research_progress_snapshot/next_experiment_queue.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/research_progress_snapshot/next_experiment_queue.md"))
    args = parser.parse_args()

    queue = build_queue(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(queue, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
