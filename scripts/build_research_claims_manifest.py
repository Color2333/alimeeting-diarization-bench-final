#!/usr/bin/env python3
"""Build a traceable manifest for headline research claims."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_claims(root: Path) -> dict[str, Any]:
    snapshot = read_json(root / "outputs/research_progress_snapshot/snapshot.json")
    timeline = snapshot.get("system_timeline", {})
    audit = snapshot.get("runtime_evidence_audit", {})
    rule = snapshot.get("rule_writeback", {})
    selector = snapshot.get("selector_generalization", {})
    guard = snapshot.get("runtime_safe_llm_guard", {})
    split20 = snapshot.get("runtime_safe_split20", {})
    tuning = snapshot.get("runtime_safe_guard_tuning", {})
    clean = snapshot.get("clean_high_llm_audit", {})
    review = snapshot.get("timeline_review_audit", {})
    omni = snapshot.get("omni_fusion", {})
    voiceprint = snapshot.get("voiceprint_gate", {})

    claims = [
        {
            "claim_id": "four_stage_realtime_route",
            "claim": (
                f"Fast first output arrives at {timeline.get('fast_first_output', 'n/a')}, "
                f"rule writeback at {timeline.get('rule_writeback', 'n/a')}, "
                f"LLM guard at {timeline.get('llm_guard', 'n/a')}, and LLM review at "
                f"{timeline.get('llm_review_signal', 'n/a')}."
            ),
            "contract_scope": "runtime_pass",
            "claim_strength": "claim_now",
            "writeback_right": "fast_first_output_and_rule_writeback_only",
            "source_artifacts": [
                "outputs/system_timeline/summary.json",
                "outputs/system_timeline/system_timeline.md",
            ],
            "validation_checks": ["four_stage_timeline", "ppt_references_latest_snapshot"],
            "report_section": "当前进展快照",
        },
        {
            "claim_id": "runtime_evidence_contract_clean",
            "claim": (
                f"Runtime evidence audit is {audit.get('status', 'unknown')} with "
                f"{audit.get('artifact_count', 0)} artifacts and "
                f"{audit.get('runtime_blocking_count', 0)} runtime-blocking artifacts."
            ),
            "contract_scope": "runtime_pass",
            "claim_strength": "claim_now",
            "writeback_right": "contract_audit_only",
            "source_artifacts": [
                "outputs/runtime_evidence_audit/runtime_evidence_audit.json",
                "outputs/runtime_evidence_audit/runtime_evidence_audit.md",
            ],
            "validation_checks": ["runtime_audit_pass", "report_references_snapshot_refresh"],
            "report_section": "Runtime evidence audit",
        },
        {
            "claim_id": "rule_writeback_primary_correction",
            "claim": (
                f"Rule writeback applies {rule.get('patches', 0)} patches and recovers "
                f"{rule.get('fast_miss_recovered', 'n/a')} of Fast miss "
                f"({rule.get('unique_fast_miss_recovered_sec', 'n/a')} unique miss seconds)."
            ),
            "contract_scope": "runtime_pass",
            "claim_strength": "claim_now",
            "writeback_right": "bounded_timeline_writeback",
            "source_artifacts": [
                "outputs/writeback_gate_120/writeback_impact_summary.json",
                "outputs/rule_writeback_timeline_120/rule_writeback_timeline_summary.json",
            ],
            "validation_checks": ["snapshot_contract", "four_stage_timeline"],
            "report_section": "当前进展快照",
        },
        {
            "claim_id": "selector_generalization_positive",
            "claim": (
                f"Selector recording holdout is {selector.get('positive_splits', 0)}/"
                f"{selector.get('splits', 0)} positive; held-out DER "
                f"{selector.get('heldout_der', 'n/a')} vs Fast {selector.get('fast_der', 'n/a')}; "
                f"bootstrap delta {selector.get('bootstrap_delta', 'n/a')} "
                f"({selector.get('bootstrap_delta_ci_low', 'n/a')} - "
                f"{selector.get('bootstrap_delta_ci_high', 'n/a')})."
            ),
            "contract_scope": "dev_only_validation",
            "claim_strength": "development_generalization_evidence",
            "writeback_right": "no_runtime_context",
            "source_artifacts": [
                "outputs/recover_selector_split_120/recording_holdout_summary.json",
                "outputs/realtime_contract_bootstrap_120/realtime_contract_bootstrap.json",
                "outputs/realtime_contract_recording_stability_120/per_recording.csv",
            ],
            "validation_checks": ["selector_holdout_bootstrap_generalization"],
            "report_section": "当前进展快照",
        },
        {
            "claim_id": "runtime_safe_llm_guard_zero_harm",
            "claim": (
                f"Runtime-safe LLM guard covers {guard.get('windows', 0)} windows / "
                f"{guard.get('patches', 0)} patches with harmful accept "
                f"{guard.get('harmful_accepts', 0)}, average delay {guard.get('avg_delay', 'n/a')} "
                f"and P95 {guard.get('p95_delay', 'n/a')}."
            ),
            "contract_scope": "runtime_pass",
            "claim_strength": "claim_now",
            "writeback_right": "block_or_quarantine_only",
            "source_artifacts": [
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_safety_summary.json",
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_safety.md",
            ],
            "validation_checks": ["runtime_audit_pass", "ppt_references_latest_snapshot"],
            "report_section": "当前进展快照",
        },
        {
            "claim_id": "split20_latency_path_limited",
            "claim": (
                f"Split20 uses {split20.get('prompts', 0)} prompts / "
                f"{split20.get('parent_windows', 0)} parent windows; top3 live wall "
                f"{split20.get('live_top3_measured_wall', 'n/a')} vs original max "
                f"{split20.get('live_top3_original_max', 'n/a')}, harmful "
                f"{split20.get('live_top3_harmful_accepts', 0)}; qwen backup "
                f"{split20.get('qwen_top45_wall', 'n/a')} is slower and deepseek top4/5 is "
                f"{split20.get('deepseek_top45_failure', 'n/a')}."
            ),
            "contract_scope": "runtime_smoke_plus_dev_prompt_audit",
            "claim_strength": "latency_path_not_full_surface_claim",
            "writeback_right": "guard_latency_optimization_only",
            "source_artifacts": [
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_comparison.json",
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top4_5_parallel_attempt_summary.json",
                "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json",
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompt_summary.json",
            ],
            "validation_checks": ["split20_live_top3_guard"],
            "report_section": "当前进展快照",
        },
        {
            "claim_id": "guard_tuning_passthrough_safe",
            "claim": (
                f"Guard tuning policy {tuning.get('best_policy', 'n/a')} recovers "
                f"{tuning.get('conservative_recovered', 0)} conservative blocks; materialized safe "
                f"{tuning.get('materialized_safe_accepts', 0)} / harmful "
                f"{tuning.get('materialized_harmful_accepts', 0)}."
            ),
            "contract_scope": "runtime_pass_with_passthrough_exception",
            "claim_strength": "claim_now_with_boundary",
            "writeback_right": "keep_fast_supported_passthrough_exception",
            "source_artifacts": [
                "outputs/runtime_safe_llm_window_batch/llm_guard_tuning_104w_summary.json",
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_passthrough_safety_summary.json",
            ],
            "validation_checks": ["guard_tuning_review_passthrough_contract"],
            "report_section": "当前进展快照",
        },
        {
            "claim_id": "boundary_auto_writeback_negative_control",
            "claim": (
                f"Boundary auto-writeback remains a negative control: DER "
                f"{tuning.get('boundary_negative_der', 'n/a')} vs recover-best "
                f"{tuning.get('recover_best_der', 'n/a')}."
            ),
            "contract_scope": "dev_only_negative_control",
            "claim_strength": "do_not_deploy",
            "writeback_right": "none",
            "source_artifacts": [
                "outputs/runtime_safe_llm_window_batch/tuned_v2_writeback_timeline/rule_writeback_timeline_summary.json",
            ],
            "validation_checks": ["guard_tuning_review_passthrough_contract"],
            "report_section": "当前进展快照",
        },
        {
            "claim_id": "clean_high_llm_audit_agrees_with_rule",
            "claim": (
                f"Clean high LLM audit accepts {clean.get('accepts', 0)}/"
                f"{clean.get('patches', 0)} rule-auto patches with "
                f"{clean.get('non_accepts', 0)} non-accepts and agreement "
                f"{clean.get('agreement', 'n/a')}."
            ),
            "contract_scope": "audit_only",
            "claim_strength": "audit_evidence",
            "writeback_right": "none_for_llm",
            "source_artifacts": [
                "outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_full_agreement.json",
                "outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_full_agreement.md",
            ],
            "validation_checks": ["clean_high_llm_full_surface", "ppt_references_latest_snapshot"],
            "report_section": "当前进展快照",
        },
        {
            "claim_id": "llm_review_memory_not_timeline",
            "claim": (
                f"LLM review has {review.get('review_cases', 0)} cases, blocks timeline writeback "
                f"{review.get('blocks_timeline_writeback', 0)}, and blocks memory update "
                f"{review.get('blocks_memory_update', 0)} at arrival {review.get('avg_arrival', 'n/a')}."
            ),
            "contract_scope": "runtime_pass",
            "claim_strength": "claim_now",
            "writeback_right": "memory_protection_only",
            "source_artifacts": [
                "outputs/timeline_review_audit/llm_review_signal_timeline_audit_summary.json",
                "outputs/timeline_review_audit/llm_review_signal_timeline_audit.md",
            ],
            "validation_checks": ["review_signal_no_timeline_block", "pareto_has_review_signal"],
            "report_section": "当前进展快照",
        },
        {
            "claim_id": "omni_fusion_label_only",
            "claim": (
                f"Omni fusion is label-only: {omni.get('windows', 0)} windows, high sentinel recall "
                f"{omni.get('high_sentinel_recall', 'n/a')}, clean sentinel FP "
                f"{omni.get('clean_high_sentinel_fp', 'n/a')}, and review FP "
                f"{omni.get('clean_review_fp', 'n/a')}."
            ),
            "contract_scope": "runtime_pass_no_timeline_writeback",
            "claim_strength": "limited_smoke_claim",
            "writeback_right": "label_and_quarantine_priority_only",
            "source_artifacts": [
                "outputs/omni_guard/omni_acoustic_fusion_summary.json",
                "outputs/omni_guard/omni_acoustic_fusion.md",
            ],
            "validation_checks": ["omni_fusion_label_only_contract", "report_references_snapshot_refresh"],
            "report_section": "当前进展快照",
        },
        {
            "claim_id": "voiceprint_rule_handles_clean_high",
            "claim": (
                f"Voiceprint gate has {voiceprint.get('with_voiceprint', 0)}/"
                f"{voiceprint.get('clean_patches', 0)} clean patches with voiceprint, "
                f"{voiceprint.get('high_bucket', 0)} high bucket, "
                f"{voiceprint.get('high_rule_auto', 0)} high rule-auto, and "
                f"{voiceprint.get('llm_candidates', 0)} LLM candidates."
            ),
            "contract_scope": "runtime_candidate_gate",
            "claim_strength": "claim_now",
            "writeback_right": "rule_auto_for_clean_high",
            "source_artifacts": [
                "outputs/voiceprint_patch_evidence/clean_candidate_120_summary.json",
                "outputs/voiceprint_patch_evidence/clean_candidate_120_summary.md",
            ],
            "validation_checks": ["snapshot_contract"],
            "report_section": "当前进展快照",
        },
    ]

    return {
        "runtime_contract": "research_claims_manifest_from_existing_artifacts",
        "claims": claims,
        "summary": {
            "claim_count": len(claims),
            "claim_now_count": sum(1 for claim in claims if str(claim["claim_strength"]).startswith("claim_now")),
            "runtime_pass_count": sum(1 for claim in claims if str(claim["contract_scope"]).startswith("runtime_pass")),
            "dev_only_count": sum(1 for claim in claims if "dev_only" in str(claim["contract_scope"])),
            "writeback_claims": [
                claim["claim_id"]
                for claim in claims
                if claim["writeback_right"] in {"fast_first_output_and_rule_writeback_only", "bounded_timeline_writeback"}
            ],
        },
    }


def write_markdown(manifest: dict[str, Any], path: Path) -> None:
    lines = [
        "# Research Claims Manifest",
        "",
        f"- Runtime contract: `{manifest['runtime_contract']}`",
        f"- Claims: `{manifest['summary']['claim_count']}`",
        f"- Claim-now entries: `{manifest['summary']['claim_now_count']}`",
        f"- Runtime-pass entries: `{manifest['summary']['runtime_pass_count']}`",
        f"- Dev-only entries: `{manifest['summary']['dev_only_count']}`",
        "",
        "| Claim ID | Contract | Strength | Writeback right | Source artifacts | Validation checks | Claim |",
        "|---|---|---|---|---|---|---|",
    ]
    for claim in manifest["claims"]:
        sources = "<br>".join(f"`{source}`" for source in claim["source_artifacts"])
        checks = ", ".join(f"`{check}`" for check in claim["validation_checks"])
        text = str(claim["claim"]).replace("|", "/")
        lines.append(
            f"| `{claim['claim_id']}` | `{claim['contract_scope']}` | `{claim['claim_strength']}` | "
            f"`{claim['writeback_right']}` | {sources} | {checks} | {text} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=Path("outputs/research_progress_snapshot/claims_manifest.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/research_progress_snapshot/claims_manifest.md"))
    args = parser.parse_args()

    manifest = build_claims(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(manifest, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
