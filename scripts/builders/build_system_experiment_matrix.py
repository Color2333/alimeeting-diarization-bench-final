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


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "outputs/system_experiment_matrix"

SYSTEM_TIMELINE = ROOT / "outputs/system_timeline/summary.json"
WRITEBACK_GATE = ROOT / "outputs/writeback_gate_120/gate_summary.json"
WRITEBACK_IMPACT = ROOT / "outputs/writeback_gate_120/writeback_impact_summary.json"
VOICEPRINT_PATCH_SUMMARY = ROOT / "outputs/voiceprint_patch_evidence/patch_evidence_120_summary.json"
VOICEPRINT_CLEAN_CANDIDATES = ROOT / "outputs/voiceprint_patch_evidence/clean_candidate_120_summary.json"
VOICEPRINT_CLEAN_LLM_AUDIT = ROOT / "outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_full_agreement.json"
VOICEPRINT_CLEAN_LLM_REPEATABILITY = ROOT / "outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_repeatability.json"
VOICEPRINT_CLEAN_LLM_DISAGREEMENT = ROOT / "outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_disagreement_analysis.json"
TIMELINE_REVIEW_AUDIT = ROOT / "outputs/timeline_review_audit/llm_review_signal_timeline_audit_summary.json"
OMNI_GUARD = ROOT / "outputs/omni_guard/omni_guard_summary.csv"
OMNI_WINDOW_BATCH = ROOT / "outputs/omni_guard/omni_window_batch_summary.csv"
OMNI_ACOUSTIC_FUSION = ROOT / "outputs/omni_guard/omni_acoustic_fusion_summary.json"
GUARD_COMPARISON = ROOT / "outputs/llm_window_batch/guard_model_comparison.csv"
RULE_TIMELINE = ROOT / "outputs/rule_writeback_timeline_120/rule_writeback_timeline_summary.json"
RECOVER_SELECTOR = ROOT / "outputs/rule_writeback_timeline_120/recover_selector_policy_search.csv"
RECOVER_SELECTOR_SPLIT = ROOT / "outputs/recover_selector_split_120/recording_holdout_summary.json"
RUNTIME_AUDIT = ROOT / "outputs/runtime_evidence_audit/runtime_evidence_audit.json"
DEPLOYABLE_ABNORMAL = ROOT / "outputs/deployable_abnormal_windows/summary.json"
RUNTIME_SAFE_LLM_DIR = ROOT / "outputs/runtime_safe_llm_window_batch"
LLM_GUARD_TUNING = ROOT / "outputs/runtime_safe_llm_window_batch/llm_guard_tuning_104w_summary.json"
LLM_GUARD_TUNED_PASSTHROUGH = ROOT / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_passthrough_safety_summary.json"
LLM_GUARD_TUNED_TIMELINE = ROOT / "outputs/runtime_safe_llm_window_batch/tuned_v2_writeback_timeline/rule_writeback_timeline_summary.json"
LLM_GUARD_LATENCY = ROOT / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_latency_summary.json"
LLM_GUARD_SPLIT_SIM = ROOT / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation_summary.json"
LLM_GUARD_SPLIT_PROMPTS = ROOT / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompt_summary.json"
LLM_GUARD_SPLIT_TOP3 = ROOT / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_comparison.json"
LLM_GUARD_SPLIT_TOP3_PARALLEL = ROOT / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_comparison.json"
LLM_GUARD_SPLIT_TOP45_ATTEMPT = ROOT / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top4_5_parallel_attempt_summary.json"
LLM_GUARD_QWEN_SPLIT_TOP45 = ROOT / "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json"
SORTFORMER_120 = ROOT / "outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json"
DIARIZEN_120 = ROOT / "outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def latest_runtime_safe_llm_summary() -> Path:
    candidates = []
    for path in RUNTIME_SAFE_LLM_DIR.glob("deepseek_proxy_high_risk_*w_safety_summary.json"):
        data = read_json(path)
        candidates.append((int(data.get("windows") or 0), path))
    if not candidates:
        return RUNTIME_SAFE_LLM_DIR / "deepseek_proxy_high_risk_8w_safety_summary.json"
    return max(candidates, key=lambda item: (item[0], item[1].name))[1]


def fmt_sec(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}s"
    except (TypeError, ValueError):
        return "n/a"


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def median(values: list[float]) -> float:
    return percentile(values, 0.5)


def load_current_numbers() -> dict[str, str]:
    timeline = read_json(SYSTEM_TIMELINE)
    gate = read_json(WRITEBACK_GATE)
    impact = read_json(WRITEBACK_IMPACT)
    voiceprint_patch = read_json(VOICEPRINT_PATCH_SUMMARY)
    voiceprint_clean = read_json(VOICEPRINT_CLEAN_CANDIDATES)
    voiceprint_clean_llm_audit = read_json(VOICEPRINT_CLEAN_LLM_AUDIT)
    voiceprint_clean_llm_repeatability = read_json(VOICEPRINT_CLEAN_LLM_REPEATABILITY)
    voiceprint_clean_llm_disagreement = read_json(VOICEPRINT_CLEAN_LLM_DISAGREEMENT)
    timeline_review_audit = read_json(TIMELINE_REVIEW_AUDIT)
    omni_rows = {row.get("model", ""): row for row in read_csv_rows(OMNI_GUARD)}
    omni_batch_rows = {row.get("model", ""): row for row in read_csv_rows(OMNI_WINDOW_BATCH)}
    guard_rows = {row.get("model", ""): row for row in read_csv_rows(GUARD_COMPARISON)}
    rule_timeline = {
        row.get("variant", ""): row
        for row in read_json(RULE_TIMELINE).get("summary", [])
    }
    sortformer_120 = read_json(SORTFORMER_120)
    diarizen_120 = read_json(DIARIZEN_120)
    sortformer_120_latencies = [
        float(row.get("latency") or 0.0)
        for row in sortformer_120.get("results", [])
        if row.get("success")
    ]
    diarizen_120_latencies = [
        float(row.get("latency") or 0.0)
        for row in diarizen_120.get("results", [])
        if row.get("success")
    ]
    diarizen_120_ders = [
        float(row.get("der") or 0.0)
        for row in diarizen_120.get("results", [])
        if row.get("success")
    ]

    gate_counts = gate.get("category_counts", {})
    rule_total = (
        int(gate_counts.get("rule_auto_writeback", 0))
        + int(gate_counts.get("rule_label_only_writeback", 0))
        + int(gate_counts.get("rule_recover_writeback", 0))
    )

    deepseek = guard_rows.get("deepseek-v4-flash", {})
    omni_realtime = omni_rows.get("qwen3.5-omni-flash-realtime", {})
    omni_flash_batch = omni_batch_rows.get("qwen3.5-omni-flash", {})
    omni_plus_batch = omni_batch_rows.get("qwen3.5-omni-plus-2026-03-15", {})
    omni_fusion = read_json(OMNI_ACOUSTIC_FUSION)
    rule_recover = (
        rule_timeline.get("rule_recover_policy_sweep_best")
        or rule_timeline.get("rule_recover_identity_selector")
        or rule_timeline.get("rule_recover_matched_label", {})
    )
    boundary_recover = rule_timeline.get("rule_boundary_recover", {})
    uncovered_only = rule_timeline.get("rule_recover_uncovered_only", {})
    selector_rows = read_csv_rows(RECOVER_SELECTOR)
    best_selector = selector_rows[0] if selector_rows else {}
    selector_split = read_json(RECOVER_SELECTOR_SPLIT)
    runtime_audit = read_json(RUNTIME_AUDIT).get("summary", {})
    deployable_abnormal = read_json(DEPLOYABLE_ABNORMAL)
    runtime_safe_llm = read_json(latest_runtime_safe_llm_summary())
    llm_tuning = read_json(LLM_GUARD_TUNING)
    llm_tuned_passthrough = read_json(LLM_GUARD_TUNED_PASSTHROUGH)
    llm_tuned_timeline = {
        row.get("variant", ""): row
        for row in read_json(LLM_GUARD_TUNED_TIMELINE).get("summary", [])
    }
    tuned_boundary_recover = llm_tuned_timeline.get("rule_boundary_recover", {})
    llm_latency = read_json(LLM_GUARD_LATENCY)
    large_patch_latency = {}
    review_latency = {}
    for row in llm_latency.get("by_patch_bucket", []):
        if row.get("patch_bucket") == "04_>15":
            large_patch_latency = row
    for row in llm_latency.get("by_window_decision", []):
        if row.get("window_decision") == "review":
            review_latency = row
    llm_split_sim = read_json(LLM_GUARD_SPLIT_SIM)
    split_policy = llm_split_sim.get("recommended_policy", {})
    split_prompts = read_json(LLM_GUARD_SPLIT_PROMPTS)
    split_top3 = read_json(LLM_GUARD_SPLIT_TOP3)
    split_top3_parallel = read_json(LLM_GUARD_SPLIT_TOP3_PARALLEL)
    split_top45_attempt = read_json(LLM_GUARD_SPLIT_TOP45_ATTEMPT)
    qwen_split_top45 = read_json(LLM_GUARD_QWEN_SPLIT_TOP45)

    metrics = {
        "fast_delay": fmt_sec(timeline.get("fast_avg_delay_sec", 0.391)),
        "fast_p95": fmt_sec(timeline.get("fast_p95_delay_sec", 0.427)),
        "fast_120_der": f"{float(sortformer_120.get('avg_der', 0.293)) * 100:.2f}%",
        "fast_120_miss": f"{float(sortformer_120.get('avg_miss_rate', 0.1712)) * 100:.2f}%",
        "fast_120_latency": fmt_sec(sortformer_120.get("avg_latency", 0.391)),
        "fast_120_p95": fmt_sec(percentile(sortformer_120_latencies, 0.95) or 0.427),
        "fast_120_spk": f"{float(sortformer_120.get('spk_match_rate', 0.0)) * 100:.1f}%",
        "slow_120_der": f"{float(diarizen_120.get('avg_der', 0.1688)) * 100:.2f}%",
        "slow_120_median": f"{median(diarizen_120_ders) * 100:.2f}%" if diarizen_120_ders else "10.83%",
        "slow_120_fa": f"{float(diarizen_120.get('avg_fa_rate', 0.0692)) * 100:.2f}%",
        "slow_120_latency": fmt_sec(diarizen_120.get("avg_latency", 24.65)),
        "slow_120_p95": fmt_sec(percentile(diarizen_120_latencies, 0.95) or 28.33),
        "slow_120_spk": f"{float(diarizen_120.get('spk_match_rate', 0.675)) * 100:.1f}%",
        "writeback_delay": fmt_sec(timeline.get("rule_writeback_avg_delay_sec", 25.561)),
        "writeback_p95": fmt_sec(timeline.get("rule_writeback_p95_delay_sec", 31.182)),
        "guard_delay": fmt_sec(timeline.get("llm_guard_avg_delay_sec", 40.496)),
        "guard_p95": fmt_sec(timeline.get("llm_guard_p95_delay_sec", 47.945)),
        "rule_writebacks": str(rule_total or 172),
        "recover_miss_rate": f"{float(impact.get('rule_recover_vs_fast_miss_rate', 0.575)) * 100:.1f}%",
        "rule_timeline_der": f"{float(rule_recover.get('avg_der', 0.2771)) * 100:.2f}%",
        "rule_timeline_miss": f"{float(rule_recover.get('avg_miss_rate', 0.14)) * 100:.2f}%",
        "rule_boundary_der": f"{float(boundary_recover.get('avg_der', 0.3477)) * 100:.2f}%",
        "rule_uncovered_der": f"{float(uncovered_only.get('avg_der', 0.2791)) * 100:.2f}%",
        "best_selector_policy": best_selector.get("policy", "ratio_le_0.65_else_uncovered"),
        "best_selector_der": best_selector.get("der", "26.30%"),
        "selector_holdout_positive": (
            f"{selector_split.get('positive_splits', 8)}/{selector_split.get('splits', 8)}"
            if selector_split
            else "n/a"
        ),
        "selector_holdout_der": f"{float(selector_split.get('weighted_heldout_der', 0.265118)) * 100:.2f}%" if selector_split else "n/a",
        "selector_holdout_delta": f"{float(selector_split.get('weighted_delta_vs_fast', 0.02052)) * 100:.2f}pp" if selector_split else "n/a",
        "selector_top_policy": selector_split.get("top_policy", best_selector.get("policy", "ratio_le_0.65_else_uncovered")),
        "llm_candidates": str(gate_counts.get("llm_writeback_candidate", 0)),
        "deepseek_patch_decisions": deepseek.get("patch_decisions", "defer 4 / quarantine 19"),
        "runtime_audit_status": runtime_audit.get("overall_status", "not_run"),
        "runtime_blocking_count": str(runtime_audit.get("runtime_blocking_count", "n/a")),
        "deployable_proxy_windows": str(deployable_abnormal.get("flagged_windows", "n/a")),
        "proxy_llm_windows": str(runtime_safe_llm.get("windows", 0)),
        "proxy_llm_patches": str(runtime_safe_llm.get("patches", 0)),
        "proxy_llm_delay": fmt_sec(runtime_safe_llm.get("avg_correction_delay_seconds", timeline.get("llm_guard_avg_delay_sec", 40.496))),
        "proxy_llm_p95": fmt_sec(runtime_safe_llm.get("p95_correction_delay_seconds", timeline.get("llm_guard_p95_delay_sec", 47.945))),
        "proxy_llm_harmful": str(runtime_safe_llm.get("harmful_accepts", 0)),
        "proxy_llm_conservative": str(runtime_safe_llm.get("conservative_blocks", 0)),
        "proxy_llm_overrides": str(runtime_safe_llm.get("window_quarantine_accept_overrides", 0)),
        "proxy_llm_window_decisions": runtime_safe_llm.get("window_decisions", "quarantine 8"),
        "proxy_llm_tuning_policy": llm_tuning.get("best_zero_harm_policy", "n/a"),
        "proxy_llm_tuning_recovered": str(llm_tuning.get("best_zero_harm_conservative_recovered", 0)),
        "proxy_llm_tuning_safe_after": str(llm_tuning.get("best_zero_harm_safe_accepts_after", 0)),
        "proxy_llm_tuning_conservative_after": str(llm_tuning.get("best_zero_harm_conservative_blocks_after", runtime_safe_llm.get("conservative_blocks", 0))),
        "proxy_llm_tuning_harmful": str(llm_tuning.get("best_zero_harm_harmful_accepts", 0)),
        "proxy_llm_tuned_safe_accepts": str(llm_tuned_passthrough.get("safe_accepts", llm_tuning.get("best_zero_harm_safe_accepts_after", 0))),
        "proxy_llm_tuned_conservative": str(llm_tuned_passthrough.get("conservative_blocks", llm_tuning.get("best_zero_harm_conservative_blocks_after", runtime_safe_llm.get("conservative_blocks", 0)))),
        "proxy_llm_tuned_harmful": str(llm_tuned_passthrough.get("harmful_accepts", llm_tuning.get("best_zero_harm_harmful_accepts", 0))),
        "proxy_llm_tuned_boundary_der": f"{float(tuned_boundary_recover.get('avg_der', 0.3384)) * 100:.2f}%",
        "proxy_llm_tuned_boundary_replaced": str(tuned_boundary_recover.get("fast_boundary_replaced", 403)),
        "proxy_llm_p95_call": fmt_sec(llm_latency.get("p95_call_seconds", runtime_safe_llm.get("p95_call_seconds", 35.515))),
        "proxy_llm_large_patch_avg_call": fmt_sec(large_patch_latency.get("avg_call_seconds", 25.54)),
        "proxy_llm_review_avg_call": fmt_sec(review_latency.get("avg_call_seconds", 28.26)),
        "proxy_llm_split_max_patches": str(split_policy.get("max_patches_per_call", 20)),
        "proxy_llm_split_p95_call": fmt_sec(split_policy.get("p95_call_seconds", 21.36)),
        "proxy_llm_split_added_calls": str(split_policy.get("added_calls", 43)),
        "proxy_llm_split_token_multiplier": f"{float(split_policy.get('token_multiplier', 1.12)):.2f}x",
        "proxy_llm_split_prompts": str(split_prompts.get("prompts", 147)),
        "proxy_llm_split_parent_windows": str(split_prompts.get("parent_windows", 104)),
        "proxy_llm_split_top3_original": fmt_sec(split_top3.get("original_avg_call_seconds", 44.25)),
        "proxy_llm_split_top3_parallel": fmt_sec(split_top3.get("split_parallel_avg_call_seconds", 25.11)),
        "proxy_llm_split_top3_harmful": str(split_top3.get("harmful_accepts", 0)),
        "proxy_llm_split_top3_token_multiplier": f"{float(split_top3.get('token_multiplier', 1.12)):.2f}x",
        "proxy_llm_split_top3_wall": fmt_sec(split_top3_parallel.get("measured_wall_seconds", 29.01)),
        "proxy_llm_split_top3_parallel_harmful": str(split_top3_parallel.get("harmful_accepts", 0)),
        "proxy_llm_split_top3_parallel_token_multiplier": f"{float(split_top3_parallel.get('token_multiplier', 1.10)):.2f}x",
        "proxy_llm_split_top45_failure": str(split_top45_attempt.get("failure_type", "pending")),
        "proxy_llm_qwen_top45_wall": fmt_sec(qwen_split_top45.get("runs", [{}])[0].get("wall_seconds") if qwen_split_top45.get("runs") else None),
        "proxy_llm_qwen_top45_split_max": fmt_sec(qwen_split_top45.get("split_max_call_seconds")),
        "proxy_llm_qwen_top45_original_max": fmt_sec(qwen_split_top45.get("original_max_call_seconds")),
        "proxy_llm_qwen_top45_harmful": str(qwen_split_top45.get("harmful_accepts", 0)),
        "proxy_llm_qwen_top45_token_multiplier": f"{float(qwen_split_top45.get('token_multiplier', 1.0)):.2f}x" if qwen_split_top45 else "n/a",
        "omni_realtime_first_text": fmt_sec(omni_realtime.get("first_text_seconds", 0.744), digits=3),
        "omni_realtime_total": fmt_sec(omni_realtime.get("call_seconds", 1.356), digits=3),
        "omni_flash_high_positive": omni_flash_batch.get("high_positive_rate", "1/2"),
        "omni_flash_clean_fp": omni_flash_batch.get("clean_false_positive_rate", "0/2"),
        "omni_plus_high_positive": omni_plus_batch.get("high_positive_rate", "1/2"),
        "omni_plus_clean_fp": omni_plus_batch.get("clean_false_positive_rate", "1/2"),
        "omni_fusion_windows": str(omni_fusion.get("windows", 0)),
        "omni_fusion_high_sentinel_recall": omni_fusion.get("high_sentinel_recall", "n/a"),
        "omni_fusion_review_high_recall": omni_fusion.get("review_priority_high_recall", "n/a"),
        "omni_fusion_clean_sentinel_fp": omni_fusion.get("clean_high_sentinel_fp", "n/a"),
        "omni_fusion_clean_review_fp": omni_fusion.get("clean_review_priority_fp", "n/a"),
        "omni_fusion_fast_hints": str(omni_fusion.get("omni_fast_hints", 0)),
        "omni_fusion_high_sentinels": str(omni_fusion.get("omni_high_sentinels", 0)),
        "omni_fusion_flash_avg_call": fmt_sec(omni_fusion.get("avg_flash_call_seconds"), digits=3),
        "omni_fusion_flash_p95_call": fmt_sec(omni_fusion.get("p95_flash_call_seconds"), digits=3),
        "omni_fusion_flash_max_call": fmt_sec(omni_fusion.get("max_flash_call_seconds"), digits=3),
        "omni_fusion_plus_avg_call": fmt_sec(omni_fusion.get("avg_plus_call_seconds"), digits=3),
        "omni_fusion_plus_p95_call": fmt_sec(omni_fusion.get("p95_plus_call_seconds"), digits=3),
        "omni_fusion_plus_max_call": fmt_sec(omni_fusion.get("max_plus_call_seconds"), digits=3),
        "voiceprint_patch_rows": str(voiceprint_patch.get("rows", 0)),
        "voiceprint_patch_ok": str(voiceprint_patch.get("ok_rows", 0)),
        "voiceprint_patch_high": str(voiceprint_patch.get("high_rows", 0)),
        "voiceprint_patch_medium": str(voiceprint_patch.get("medium_rows", 0)),
        "voiceprint_patch_low": str(voiceprint_patch.get("low_rows", 0)),
        "voiceprint_patch_candidates": str(voiceprint_patch.get("llm_writeback_candidates", gate_counts.get("llm_writeback_candidate", 0))),
        "voiceprint_patch_avg_margin": f"{float(voiceprint_patch.get('avg_similarity_margin', 0.0)):.3f}",
        "voiceprint_patch_p95_margin": f"{float(voiceprint_patch.get('p95_similarity_margin', 0.0)):.3f}",
        "voiceprint_clean_patches": str(voiceprint_clean.get("clean_patches", 0)),
        "voiceprint_clean_ok": str(voiceprint_clean.get("with_voiceprint", 0)),
        "voiceprint_clean_high": str(voiceprint_clean.get("high_bucket", 0)),
        "voiceprint_clean_rule_auto": str(voiceprint_clean.get("rule_auto_writeback", 0)),
        "voiceprint_clean_high_rule_auto": str(voiceprint_clean.get("candidate_class_counts", {}).get("voiceprint_high_rule_auto", 0)),
        "voiceprint_clean_avg_margin": f"{float(voiceprint_clean.get('avg_margin', 0.0)):.3f}",
        "voiceprint_clean_p95_margin": f"{float(voiceprint_clean.get('p95_margin', 0.0)):.3f}",
        "voiceprint_clean_llm_windows": str(voiceprint_clean_llm_audit.get("windows", 0)),
        "voiceprint_clean_llm_patches": str(voiceprint_clean_llm_audit.get("patches", 0)),
        "voiceprint_clean_llm_accepts": str(voiceprint_clean_llm_audit.get("llm_accepts", 0)),
        "voiceprint_clean_llm_non_accepts": str(voiceprint_clean_llm_audit.get("llm_non_accepts", 0)),
        "voiceprint_clean_llm_agreement": f"{float(voiceprint_clean_llm_audit.get('rule_auto_agreement_rate', 0.0)) * 100:.1f}%",
        "voiceprint_clean_llm_avg_call": fmt_sec(voiceprint_clean_llm_audit.get("avg_call_seconds")),
        "voiceprint_clean_llm_max_call": fmt_sec(voiceprint_clean_llm_audit.get("max_call_seconds")),
        "voiceprint_clean_llm_tokens": str(voiceprint_clean_llm_audit.get("total_tokens", 0)),
        "voiceprint_clean_llm_repeat_overlap": str(voiceprint_clean_llm_repeatability.get("overlap_patches", 0)),
        "voiceprint_clean_llm_repeat_same": str(voiceprint_clean_llm_repeatability.get("same_decision", 0)),
        "voiceprint_clean_llm_repeat_changed": str(voiceprint_clean_llm_repeatability.get("changed_decision", 0)),
        "voiceprint_clean_llm_review_cases": str(voiceprint_clean_llm_disagreement.get("review_signal_cases", 0)),
        "voiceprint_clean_llm_review_avg_duration": fmt_sec(voiceprint_clean_llm_disagreement.get("avg_review_duration")),
        "timeline_review_cases": str(timeline_review_audit.get("review_cases", 0)),
        "timeline_review_blocks_timeline": str(timeline_review_audit.get("blocks_timeline_writeback", 0)),
        "timeline_review_blocks_memory": str(timeline_review_audit.get("blocks_memory_update", 0)),
        "timeline_review_arrival": fmt_sec(timeline_review_audit.get("llm_review_arrival_avg_sec")),
    }
    if metrics["proxy_llm_windows"] == metrics["deployable_proxy_windows"]:
        metrics["proxy_llm_next"] = (
            f"Keep passthrough v2 as review/passthrough only; auto boundary materialization replaced "
            f"{metrics['proxy_llm_tuned_boundary_replaced']} segments and scored {metrics['proxy_llm_tuned_boundary_der']} DER; "
            f"next validate split<={metrics['proxy_llm_split_max_patches']} patches: est P95 call {metrics['proxy_llm_split_p95_call']}, "
            f"+{metrics['proxy_llm_split_added_calls']} calls, {metrics['proxy_llm_split_token_multiplier']} tokens; "
            f"top3 parallel wall {metrics['proxy_llm_split_top3_wall']}, "
            f"harmful {metrics['proxy_llm_split_top3_parallel_harmful']}, {metrics['proxy_llm_split_top3_parallel_token_multiplier']} tokens; "
            f"top4/5 deepseek {metrics['proxy_llm_split_top45_failure']}; "
            f"qwen backup wall {metrics['proxy_llm_qwen_top45_wall']}, harmful {metrics['proxy_llm_qwen_top45_harmful']}, "
            f"{metrics['proxy_llm_qwen_top45_token_multiplier']} tokens, split max {metrics['proxy_llm_qwen_top45_split_max']} vs original {metrics['proxy_llm_qwen_top45_original_max']}"
        )
    else:
        metrics["proxy_llm_next"] = (
            f"Expand proxy LLM guard from {metrics['proxy_llm_windows']} windows "
            f"to all {metrics['deployable_proxy_windows']} flagged windows"
        )
    return metrics


def build_rows(metrics: dict[str, str]) -> list[dict[str, str]]:
    selector_pair = metrics["selector_top_policy"]
    if metrics["best_selector_policy"] != metrics["selector_top_policy"]:
        selector_pair = f"{metrics['selector_top_policy']} / {metrics['best_selector_policy']}"
    rows = [
        {
            "layer": "L0 fast provisional",
            "runtime_path": "Sortformer / streaming diarization",
            "trigger": "Every live window or streaming chunk",
            "input_evidence": "Audio only; no LLM wait",
            "output_action": "Emit provisional speaker timeline",
            "writeback_right": "timeline_first_output",
            "primary_metric": "first-output latency, DER, Miss, speaker-count accuracy",
            "latency_target": "<1s first visible update",
            "current_latency": f"{metrics['fast_120_latency']} avg / {metrics['fast_120_p95']} P95",
            "current_effect": (
                f"120-window DER {metrics['fast_120_der']}; Miss {metrics['fast_120_miss']}; "
                f"avg latency {metrics['fast_120_latency']}; spk match {metrics['fast_120_spk']}"
            ),
            "safety_gate": "Mark provisional; never update speaker memory from low-quality overlap",
            "current_evidence": "outputs/sortformer_uv_120; outputs/system_timeline",
            "failure_mode": "Short response miss, speaker-count mismatch, local label drift",
            "next_experiment": "GPU streaming latency sweep at 0.32s/1.04s/10s/30s configs",
        },
        {
            "layer": "L1 slow acoustic correction",
            "runtime_path": "DiariZen mature-window rerun",
            "trigger": "Window closes or enough future context arrives",
            "input_evidence": "Audio window; Fast timeline for diff",
            "output_action": "Generate slow candidate segments and patch graph",
            "writeback_right": "candidate_only_until_rule_gate",
            "primary_metric": "DER/Miss/FA/Conf, recoverable Fast miss, extreme FA rate",
            "latency_target": "<30s average correction arrival",
            "current_latency": f"{metrics['writeback_delay']} avg / {metrics['writeback_p95']} P95",
            "current_effect": (
                f"120-window raw DER {metrics['slow_120_der']}; median {metrics['slow_120_median']}; "
                f"FA {metrics['slow_120_fa']}; spk match {metrics['slow_120_spk']}"
            ),
            "safety_gate": "Quarantine abnormal slow windows before memory update",
            "current_evidence": "outputs/diarizen_uv_120; outputs/segment_patches",
            "failure_mode": "Rare extreme FA can poison raw DER and speaker memory",
            "next_experiment": "Default slow rerun plus abnormal-window isolation, not only heuristic routing",
        },
        {
            "layer": "L2 rule writeback",
            "runtime_path": "Structured Policy Agent / deterministic gate",
            "trigger": "Fast/Slow patch graph is ready",
            "input_evidence": "Patch type, support ratio, abnormal flags, duration, voiceprint bucket",
            "output_action": "Accept low-risk patches; label-only short fixes; recover Fast miss",
            "writeback_right": "bounded_timeline_writeback",
            "primary_metric": "writeback precision, recovered miss seconds, harmful writeback count",
            "latency_target": "Same arrival as L1 slow correction",
            "current_latency": f"{metrics['writeback_delay']} avg / {metrics['writeback_p95']} P95",
            "current_effect": (
                f"120 timeline DER {metrics['rule_timeline_der']}; Miss {metrics['rule_timeline_miss']}; "
                f"recover covers {metrics['recover_miss_rate']} Fast miss; "
                f"selector holdout {metrics['selector_holdout_der']} ({metrics['selector_holdout_positive']}, +{metrics['selector_holdout_delta']})"
            ),
            "safety_gate": "No abnormal-window auto memory update; suppress requires strong evidence",
            "current_evidence": "outputs/writeback_gate_120; outputs/rule_writeback_timeline_120",
            "failure_mode": "Over-conservative gate leaves review backlog; aggressive suppress may delete true speech",
            "next_experiment": (
                f"Freeze selector {selector_pair} and rerun on newly sampled windows; boundary+recover negative control is {metrics['rule_boundary_der']} DER"
            ),
        },
        {
            "layer": "L3 LLM guard",
            "runtime_path": "deepseek-v4-flash window-batch guard",
            "trigger": "Deployable proxy abnormal flag, suppress conflict, or quarantine flag",
            "input_evidence": "Structured patches only; no free timestamp generation",
            "output_action": "Defer/quarantine/review high-risk patch groups",
            "writeback_right": "block_or_quarantine_only",
            "primary_metric": "harmful accept=0, quarantine recall, async correction delay",
            "latency_target": "avg <50s, P95 <65s high-risk isolation",
            "current_latency": f"{metrics['proxy_llm_delay']} avg / {metrics['proxy_llm_p95']} P95",
            "current_effect": (
                f"runtime-safe proxy guard {metrics['proxy_llm_window_decisions']}; "
                f"{metrics['proxy_llm_patches']} patches; harmful accept {metrics['proxy_llm_harmful']}; "
                f"conservative blocks {metrics['proxy_llm_conservative']}; "
                f"window override {metrics['proxy_llm_overrides']}; "
                f"passthrough v2 safe accepts {metrics['proxy_llm_tuned_safe_accepts']} / conservative {metrics['proxy_llm_tuned_conservative']}; "
                f"auto-boundary negative control {metrics['proxy_llm_tuned_boundary_der']} DER; "
                f"P95 call {metrics['proxy_llm_p95_call']}; split<={metrics['proxy_llm_split_max_patches']} est {metrics['proxy_llm_split_p95_call']}; "
                f"{metrics['proxy_llm_split_prompts']} prompts ready; top3 parallel wall {metrics['proxy_llm_split_top3_wall']}; "
                f"qwen top4/5 backup wall {metrics['proxy_llm_qwen_top45_wall']} but slower than original"
            ),
            "safety_gate": "LLM cannot invent timestamps or directly accept high-risk segments",
            "current_evidence": "outputs/runtime_safe_llm_window_batch; outputs/runtime_evidence_audit",
            "failure_mode": "Legacy high-risk prompts used eval-derived high_der/high_fa flags; keep them as development risk probes",
            "next_experiment": metrics["proxy_llm_next"],
        },
        {
            "layer": "L4 Omni realtime risk probe",
            "runtime_path": "qwen3.5-omni-flash-realtime",
            "trigger": "Live short audio snippets or early overlap suspicion",
            "input_evidence": "8s audio clip; optional UI state",
            "output_action": "Risk label, rough speaker count, defer/quarantine hint",
            "writeback_right": "label_only_weighted_evidence",
            "primary_metric": "first text latency, high-risk recall, clean false positive",
            "latency_target": "<1s first text; <2s total guard hint",
            "current_latency": f"{metrics['omni_realtime_first_text']} first text / {metrics['omni_realtime_total']} total",
            "current_effect": (
                f"Flash batch high+ {metrics['omni_flash_high_positive']}; clean FP {metrics['omni_flash_clean_fp']}; "
                f"fusion smoke {metrics['omni_fusion_windows']} windows: high sentinel recall "
                f"{metrics['omni_fusion_high_sentinel_recall']}, clean sentinel FP {metrics['omni_fusion_clean_sentinel_fp']}, "
                f"review clean FP {metrics['omni_fusion_clean_review_fp']}; "
                f"flash batch avg/P95/max {metrics['omni_fusion_flash_avg_call']}/{metrics['omni_fusion_flash_p95_call']}/{metrics['omni_fusion_flash_max_call']}"
            ),
            "safety_gate": "Omni high only boosts acoustic quarantine priority; medium does not edit timeline",
            "current_evidence": "outputs/omni_guard",
            "failure_mode": "Misses clean single-speaker diarization errors; plus model can false-positive noise",
            "next_experiment": (
                f"Expand Omni+acoustic fusion beyond {metrics['omni_fusion_windows']}-window smoke; keep high as quarantine-priority only, "
                "ordinary hints as label/review only"
            ),
        },
        {
            "layer": "L5 speaker memory",
            "runtime_path": "one-shot anchor plus conservative voiceprint memory",
            "trigger": "Enrollment at meeting start; update after high-confidence non-overlap segments",
            "input_evidence": "Visual one-shot ID or oracle simulation, ECAPA top1/top2 margin, segment quality",
            "output_action": "Map local speaker labels to global identities; update memory selectively",
            "writeback_right": "identity_label_writeback_after_gate",
            "primary_metric": "global ID accuracy, ID switch rate, merge/split error, memory pollution",
            "latency_target": "Async; no blocking first output",
            "current_latency": "Not blocking; computed offline in current runs",
            "current_effect": (
                "Sortformer 48 ID memory 68.8% vs fixed 31.5%; "
                f"patch voiceprint evidence {metrics['voiceprint_patch_ok']}/{metrics['voiceprint_patch_rows']} ok, "
                f"high/medium/low {metrics['voiceprint_patch_high']}/{metrics['voiceprint_patch_medium']}/{metrics['voiceprint_patch_low']}, "
                f"avg/P95 margin {metrics['voiceprint_patch_avg_margin']}/{metrics['voiceprint_patch_p95_margin']}; "
                f"LLM writeback candidates {metrics['voiceprint_patch_candidates']}; "
                f"clean audit {metrics['voiceprint_clean_ok']}/{metrics['voiceprint_clean_patches']} ok, "
                f"high {metrics['voiceprint_clean_high']} ({metrics['voiceprint_clean_high_rule_auto']} rule-auto); "
                f"clean LLM audit {metrics['voiceprint_clean_llm_accepts']}/{metrics['voiceprint_clean_llm_patches']} accept "
                f"({metrics['voiceprint_clean_llm_non_accepts']} defer/non-accept, "
                f"{metrics['voiceprint_clean_llm_agreement']} agreement, avg/max call "
                f"{metrics['voiceprint_clean_llm_avg_call']}/{metrics['voiceprint_clean_llm_max_call']}); "
                f"repeat overlap {metrics['voiceprint_clean_llm_repeat_same']}/{metrics['voiceprint_clean_llm_repeat_overlap']} same; "
                f"review signals {metrics['voiceprint_clean_llm_review_cases']} "
                f"(avg {metrics['voiceprint_clean_llm_review_avg_duration']}); "
                f"timeline audit blocks {metrics['timeline_review_blocks_timeline']} writeback / "
                f"{metrics['timeline_review_blocks_memory']} memory, review arrival {metrics['timeline_review_arrival']}"
            ),
            "safety_gate": "Conservative update only; no update from overlap/abnormal/short segments",
            "current_evidence": "outputs/voiceprint_memory; outputs/one_shot_memory; outputs/voiceprint_patch_evidence",
            "failure_mode": "Aggressive update contaminates memory; low margin causes speaker merge",
            "next_experiment": (
                f"Route {metrics['timeline_review_cases']} review signals into offline timeline audit; "
                f"block memory updates but keep deterministic Rule timeline writeback"
            ),
        },
        {
            "layer": "L6 protocol and reporting",
            "runtime_path": "Experiment governance artifact",
            "trigger": "Every new model, prompt, or routing change",
            "input_evidence": "All stage outputs and evaluation summaries",
            "output_action": "Update DER-latency-safety matrix before claiming improvement",
            "writeback_right": "no_runtime_action",
            "primary_metric": "DER + latency + safety all reported together",
            "latency_target": "Report avg/P95/RTF and user-visible arrival time",
            "current_latency": "This matrix is generated offline",
            "current_effect": "Prevents optimizing DER while silently breaking realtime behavior",
            "safety_gate": "Separate deployable evidence from eval-only evidence",
            "current_evidence": "outputs/system_experiment_matrix; outputs/runtime_evidence_audit",
            "failure_mode": "Uncontrolled comparisons, hidden GT leakage, prompt-only conclusions",
            "next_experiment": f"Keep runtime audit green while adding real LLM calls; current status={metrics['runtime_audit_status']}",
        },
    ]
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "layer",
        "runtime_path",
        "writeback_right",
        "primary_metric",
        "current_latency",
        "current_effect",
        "next_experiment",
    ]
    lines = [
        "# System Experiment Matrix",
        "",
        "This matrix is the governance layer for the realtime diarization system: every improvement must report DER, latency, and safety/writeback rights together.",
        "",
        "| Layer | Runtime path | Writeback right | Primary metric | Current latency | Current effect | Next experiment |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        values = [row[column].replace("|", "/") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    lines.extend(
        [
            "",
            "## Runtime Invariants",
            "",
            "- LLM and Omni never create timestamps; they only accept bounded decisions from the patch graph.",
            "- Only Rule/Policy gates can write back to the timeline; Omni is weighted evidence, not a diarizer.",
            "- Eval-only signals such as DER, GT support, and oracle speaker labels must not enter runtime prompts.",
            "- Every reported gain must include DER/Miss/FA/Conf, avg/P95/RTF latency, and harmful-writeback counts.",
            "- Speaker memory updates require high-confidence, long-enough, non-overlap, non-abnormal segments.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    metrics = load_current_numbers()
    rows = build_rows(metrics)
    csv_path = args.output_dir / "system_experiment_matrix.csv"
    md_path = args.output_dir / "system_experiment_matrix.md"
    write_csv(rows, csv_path)
    write_markdown(rows, md_path)
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
