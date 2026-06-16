#!/usr/bin/env python3
"""Build a compact snapshot of the current diarization research progress."""

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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def fmt_sec(value: object) -> str:
    try:
        return f"{float(value):.2f}s"
    except (TypeError, ValueError):
        return "n/a"


def fmt_pct(value: object, already_ratio: bool = True) -> str:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if already_ratio:
        val *= 100.0
    return f"{val:.1f}%"


def first_run_wall_seconds(data: dict[str, Any]) -> object:
    runs = data.get("runs") or []
    if runs and isinstance(runs[0], dict):
        return runs[0].get("wall_seconds")
    return data.get("wall_seconds")


def find_summary_variant(data: dict[str, Any], variant: str) -> dict[str, Any]:
    for row in data.get("summary", data.get("summaries", [])):
        if row.get("variant") == variant:
            return row
    return {}


def count_positive(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if str(row.get("beats_fast", "")).lower() in {"true", "1", "yes"})


def build_snapshot(root: Path) -> dict[str, Any]:
    timeline = read_json(root / "outputs/system_timeline/summary.json")
    runtime_audit = read_json(root / "outputs/runtime_evidence_audit/runtime_evidence_audit.json").get("summary", {})
    writeback = read_json(root / "outputs/writeback_gate_120/writeback_impact_summary.json")
    selector_holdout = read_json(root / "outputs/recover_selector_split_120/recording_holdout_summary.json")
    selector_bootstrap = read_json(root / "outputs/realtime_contract_bootstrap_120/realtime_contract_bootstrap.json")
    selector_bootstrap_best = find_summary_variant(selector_bootstrap, "rule_recover_policy_sweep_best")
    selector_per_recording = read_csv(root / "outputs/realtime_contract_recording_stability_120/per_recording.csv")
    selector_loo = read_csv(root / "outputs/realtime_contract_recording_stability_120/leave_one_recording_out.csv")
    llm_guard = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_safety_summary.json")
    clean_llm = read_json(root / "outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_full_agreement.json")
    timeline_review = read_json(root / "outputs/timeline_review_audit/llm_review_signal_timeline_audit_summary.json")
    omni = read_json(root / "outputs/omni_guard/omni_acoustic_fusion_summary.json")
    voiceprint = read_json(root / "outputs/voiceprint_patch_evidence/clean_candidate_120_summary.json")
    split_top3 = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_comparison.json")
    split_attempt = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top4_5_parallel_attempt_summary.json")
    qwen_split = read_json(root / "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json")
    split_prompts = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompt_summary.json")
    split_sim = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation_summary.json")
    recommended_split = split_sim.get("recommended_policy", {})
    guard_tuning = read_json(root / "outputs/runtime_safe_llm_window_batch/llm_guard_tuning_104w_summary.json")
    tuned_guard = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_passthrough_safety_summary.json")
    tuned_timeline = read_json(root / "outputs/runtime_safe_llm_window_batch/tuned_v2_writeback_timeline/rule_writeback_timeline_summary.json")
    tuned_boundary = find_summary_variant(tuned_timeline, "rule_boundary_recover")
    tuned_recover = find_summary_variant(tuned_timeline, "rule_recover_policy_sweep_best")

    return {
        "runtime_contract": "research_progress_snapshot_from_existing_artifacts",
        "system_timeline": {
            "fast_first_output": fmt_sec(timeline.get("fast_avg_delay_sec")),
            "rule_writeback": fmt_sec(timeline.get("rule_writeback_avg_delay_sec")),
            "llm_guard": fmt_sec(timeline.get("llm_guard_avg_delay_sec")),
            "llm_review_signal": fmt_sec(timeline.get("llm_review_avg_delay_sec")),
            "rule_writeback_patches": int(timeline.get("rule_writeback_patches", 0)),
            "llm_guard_patches": int(timeline.get("llm_guard_patches", 0)),
            "llm_review_cases": int(timeline.get("llm_review_cases", 0)),
        },
        "runtime_evidence_audit": {
            "status": runtime_audit.get("overall_status", "unknown"),
            "artifact_count": int(runtime_audit.get("artifact_count", 0)),
            "runtime_blocking_count": int(runtime_audit.get("runtime_blocking_count", 0)),
            "status_counts": runtime_audit.get("status_counts", {}),
        },
        "rule_writeback": {
            "patches": int(writeback.get("writeback_patches", 0)),
            "fast_miss_recovered": fmt_pct(writeback.get("rule_recover_vs_fast_miss_rate")),
            "unique_fast_miss_recovered_sec": f"{float(writeback.get('rule_recover_unique_fast_miss_sec', 0.0)):.2f}s",
        },
        "selector_generalization": {
            "splits": int(selector_holdout.get("splits", 0)),
            "positive_splits": int(selector_holdout.get("positive_splits", 0)),
            "heldout_der": fmt_pct(selector_holdout.get("weighted_heldout_der")),
            "fast_der": fmt_pct(selector_holdout.get("weighted_fast_der")),
            "delta_vs_fast": fmt_pct(selector_holdout.get("weighted_delta_vs_fast")),
            "top_policy": selector_holdout.get("top_policy", "n/a"),
            "top_policy_count": int(selector_holdout.get("top_policy_count", 0)),
            "fixed_policy": selector_holdout.get("fixed_policy", "n/a"),
            "fixed_policy_der": fmt_pct(selector_holdout.get("fixed_policy_der")),
            "bootstrap_delta": fmt_pct(selector_bootstrap_best.get("delta_vs_fast")),
            "bootstrap_delta_ci_low": fmt_pct(selector_bootstrap_best.get("delta_ci_low")),
            "bootstrap_delta_ci_high": fmt_pct(selector_bootstrap_best.get("delta_ci_high")),
            "bootstrap_prob_beats_fast": fmt_pct(selector_bootstrap_best.get("prob_beats_fast")),
            "per_recording_positive": count_positive(selector_per_recording),
            "per_recording_total": len(selector_per_recording),
            "loo_positive": count_positive(selector_loo),
            "loo_total": len(selector_loo),
        },
        "runtime_safe_llm_guard": {
            "windows": int(llm_guard.get("windows", 0)),
            "patches": int(llm_guard.get("patches", 0)),
            "harmful_accepts": int(llm_guard.get("harmful_accepts", 0)),
            "conservative_blocks": int(llm_guard.get("conservative_blocks", 0)),
            "avg_delay": fmt_sec(llm_guard.get("avg_correction_delay_seconds")),
            "p95_delay": fmt_sec(llm_guard.get("p95_correction_delay_seconds")),
        },
        "runtime_safe_split20": {
            "prompts": int(split_prompts.get("prompts", 0)),
            "parent_windows": int(split_prompts.get("parent_windows", 0)),
            "split_parent_windows": int(split_prompts.get("split_parent_windows", 0)),
            "max_subcalls_per_window": int(split_prompts.get("max_subcalls_per_window", 0)),
            "recommended_max_patches": int(recommended_split.get("max_patches_per_call", 0)),
            "estimated_p95_call": fmt_sec(recommended_split.get("p95_call_seconds")),
            "estimated_token_multiplier": f"{float(recommended_split.get('token_multiplier', 0.0)):.2f}x"
            if recommended_split
            else "n/a",
            "live_top3_parents": int(split_top3.get("parent_windows", 0)),
            "live_top3_patches": int(split_top3.get("patches", 0)),
            "live_top3_measured_wall": fmt_sec(split_top3.get("measured_wall_seconds")),
            "live_top3_original_max": fmt_sec(split_top3.get("original_max_call_seconds")),
            "live_top3_split_max": fmt_sec(split_top3.get("split_max_call_seconds")),
            "live_top3_token_multiplier": f"{float(split_top3.get('token_multiplier', 0.0)):.2f}x"
            if split_top3
            else "n/a",
            "live_top3_harmful_accepts": int(split_top3.get("harmful_accepts", 0)),
            "deepseek_top45_failure": split_attempt.get("failure_type", "n/a"),
            "qwen_top45_wall": fmt_sec(first_run_wall_seconds(qwen_split)),
            "qwen_top45_split_max": fmt_sec(qwen_split.get("split_max_call_seconds")),
            "qwen_top45_harmful_accepts": int(qwen_split.get("harmful_accepts", 0)),
        },
        "runtime_safe_guard_tuning": {
            "best_policy": guard_tuning.get("best_zero_harm_policy", "n/a"),
            "conservative_recovered": int(guard_tuning.get("best_zero_harm_conservative_recovered", 0)),
            "safe_accepts_after": int(guard_tuning.get("best_zero_harm_safe_accepts_after", 0)),
            "conservative_after": int(guard_tuning.get("best_zero_harm_conservative_blocks_after", 0)),
            "harmful_after": int(guard_tuning.get("best_zero_harm_harmful_accepts", 0)),
            "materialized_safe_accepts": int(tuned_guard.get("safe_accepts", 0)),
            "materialized_conservative_blocks": int(tuned_guard.get("conservative_blocks", 0)),
            "materialized_harmful_accepts": int(tuned_guard.get("harmful_accepts", 0)),
            "runtime_contract": tuned_guard.get("runtime_contract", "n/a"),
            "boundary_negative_der": fmt_pct(tuned_boundary.get("avg_der")),
            "boundary_negative_fa": fmt_pct(tuned_boundary.get("avg_fa_rate")),
            "boundary_replaced": int(tuned_boundary.get("fast_boundary_replaced", 0)),
            "recover_best_der": fmt_pct(tuned_recover.get("avg_der")),
        },
        "clean_high_llm_audit": {
            "windows": int(clean_llm.get("windows", 0)),
            "patches": int(clean_llm.get("patches", 0)),
            "accepts": int(clean_llm.get("llm_accepts", 0)),
            "non_accepts": int(clean_llm.get("llm_non_accepts", 0)),
            "agreement": fmt_pct(clean_llm.get("rule_auto_agreement_rate")),
            "avg_call": fmt_sec(clean_llm.get("avg_call_seconds")),
        },
        "timeline_review_audit": {
            "review_cases": int(timeline_review.get("review_cases", 0)),
            "blocks_timeline_writeback": int(timeline_review.get("blocks_timeline_writeback", 0)),
            "blocks_memory_update": int(timeline_review.get("blocks_memory_update", 0)),
            "avg_arrival": fmt_sec(timeline_review.get("llm_review_arrival_avg_sec")),
        },
        "omni_fusion": {
            "windows": int(omni.get("windows", 0)),
            "high_sentinel_recall": omni.get("high_sentinel_recall", "n/a"),
            "clean_high_sentinel_fp": omni.get("clean_high_sentinel_fp", "n/a"),
            "clean_review_fp": omni.get("clean_review_priority_fp", "n/a"),
            "flash_avg_call": fmt_sec(omni.get("avg_flash_call_seconds")),
            "flash_p95_call": fmt_sec(omni.get("p95_flash_call_seconds")),
        },
        "voiceprint_gate": {
            "clean_patches": int(voiceprint.get("clean_patches", 0)),
            "with_voiceprint": int(voiceprint.get("with_voiceprint", 0)),
            "high_bucket": int(voiceprint.get("high_bucket", 0)),
            "llm_candidates": int(voiceprint.get("llm_candidates", 0)),
            "high_rule_auto": int(voiceprint.get("candidate_class_counts", {}).get("voiceprint_high_rule_auto", 0)),
        },
    }


def write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    timeline = snapshot["system_timeline"]
    audit = snapshot["runtime_evidence_audit"]
    rule = snapshot["rule_writeback"]
    selector = snapshot["selector_generalization"]
    guard = snapshot["runtime_safe_llm_guard"]
    split20 = snapshot["runtime_safe_split20"]
    tuning = snapshot["runtime_safe_guard_tuning"]
    clean = snapshot["clean_high_llm_audit"]
    review = snapshot["timeline_review_audit"]
    omni = snapshot["omni_fusion"]
    voiceprint = snapshot["voiceprint_gate"]
    lines = [
        "# Research Progress Snapshot",
        "",
        "| Area | Current evidence |",
        "|---|---|",
        (
            "| Four-stage timeline | "
            f"{timeline['fast_first_output']} first output; {timeline['rule_writeback']} rule writeback; "
            f"{timeline['llm_guard']} LLM guard; {timeline['llm_review_signal']} LLM review |"
        ),
        (
            "| Runtime evidence audit | "
            f"{audit['status']}; {audit['artifact_count']} artifacts; blocking {audit['runtime_blocking_count']} |"
        ),
        (
            "| Rule writeback | "
            f"{rule['patches']} patches; recovers {rule['fast_miss_recovered']} Fast miss; "
            f"{rule['unique_fast_miss_recovered_sec']} unique miss recovered |"
        ),
        (
            "| Selector generalization | "
            f"holdout {selector['positive_splits']}/{selector['splits']} positive; "
            f"DER {selector['heldout_der']} vs Fast {selector['fast_der']}; delta {selector['delta_vs_fast']}; "
            f"fixed {selector['fixed_policy']} {selector['fixed_policy_der']}; "
            f"bootstrap delta {selector['bootstrap_delta']} ({selector['bootstrap_delta_ci_low']} - {selector['bootstrap_delta_ci_high']}) |"
        ),
        (
            "| Runtime-safe LLM guard | "
            f"{guard['windows']} windows / {guard['patches']} patches; harmful accept {guard['harmful_accepts']}; "
            f"delay {guard['avg_delay']} / P95 {guard['p95_delay']} |"
        ),
        (
            "| Split20 LLM guard optimization | "
            f"{split20['prompts']} prompts / {split20['parent_windows']} parent windows; "
            f"top3 live wall {split20['live_top3_measured_wall']} vs original max {split20['live_top3_original_max']}; "
            f"split max {split20['live_top3_split_max']}; harmful {split20['live_top3_harmful_accepts']}; "
            f"qwen backup wall {split20['qwen_top45_wall']} slower; deepseek top4/5 {split20['deepseek_top45_failure']} |"
        ),
        (
            "| Guard tuning contract | "
            f"{tuning['best_policy']} recovers {tuning['conservative_recovered']} conservative blocks; "
            f"materialized safe {tuning['materialized_safe_accepts']} / harmful {tuning['materialized_harmful_accepts']}; "
            f"boundary auto-writeback DER {tuning['boundary_negative_der']} vs recover-best {tuning['recover_best_der']} |"
        ),
        (
            "| Clean high LLM audit | "
            f"{clean['accepts']}/{clean['patches']} accept; {clean['non_accepts']} non-accept; "
            f"agreement {clean['agreement']} |"
        ),
        (
            "| Timeline review audit | "
            f"{review['review_cases']} review cases; blocks writeback {review['blocks_timeline_writeback']}; "
            f"blocks memory {review['blocks_memory_update']}; arrival {review['avg_arrival']} |"
        ),
        (
            "| Omni fusion | "
            f"{omni['windows']} windows; high sentinel recall {omni['high_sentinel_recall']}; "
            f"clean sentinel FP {omni['clean_high_sentinel_fp']}; review FP {omni['clean_review_fp']} |"
        ),
        (
            "| Voiceprint gate | "
            f"{voiceprint['with_voiceprint']}/{voiceprint['clean_patches']} clean patches with voiceprint; "
            f"high {voiceprint['high_bucket']}; high rule-auto {voiceprint['high_rule_auto']}; "
            f"LLM candidates {voiceprint['llm_candidates']} |"
        ),
        "",
        "## Reading",
        "",
        "- Current deployable route is staged: Fast output first, Rule writes bounded corrections, LLM/Omni only guard or review.",
        "- Selector gain is development-set evidence, but recording holdout and bootstrap checks reduce concentration-risk concerns.",
        "- Split20 is the current latency optimization path for LLM guard: top3 live parallel smoke is faster, but full 104-window rerun is still not proven.",
        "- Guard tuning can reduce conservative blocking under a review/passthrough contract, but boundary auto-writeback remains a negative control.",
        "- Clean high voiceprint patches are already handled by deterministic Rule writeback; LLM remains an audit/explanation layer.",
        "- Review signals block memory update, not timeline writeback.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=Path("outputs/research_progress_snapshot/snapshot.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/research_progress_snapshot/snapshot.md"))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    snapshot = build_snapshot(root)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(snapshot, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
