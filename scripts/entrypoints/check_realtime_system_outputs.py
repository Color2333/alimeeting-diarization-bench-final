#!/usr/bin/env python3
"""Self-check generated realtime diarization system artifacts."""

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


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def csv_row_count(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def check(condition: bool, severity: str, code: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "pass" if condition else severity,
        "code": code,
        "message": message,
        "detail": detail or {},
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Realtime System Self Check",
        "",
        f"- Status: `{payload['status']}`",
        f"- Checks: `{payload['pass_count']}` pass, `{payload['warn_count']}` warn, `{payload['fail_count']}` fail",
        f"- Metrics: `{payload['inputs']['metrics']}`",
        "",
        "| Status | Code | Message |",
        "|---|---|---|",
    ]
    for row in payload["checks"]:
        lines.append(f"| `{row['status']}` | `{row['code']}` | {row['message']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/metrics.json"))
    parser.add_argument("--selector-validation", type=Path, default=Path("outputs/system_selector_validation/guarded_slow_selector_validation.json"))
    parser.add_argument("--selector-search", type=Path, default=Path("outputs/system_selector_search/system_selector_policy_search.json"))
    parser.add_argument("--rare-selector-search", type=Path, default=Path("outputs/rare_selector_search/rare_selector_policy_search.json"))
    parser.add_argument("--slow-sanitization-search", type=Path, default=Path("outputs/slow_sanitization_search/slow_sanitization_policy_search.json"))
    parser.add_argument("--speaker-track-sanitization-search", type=Path, default=Path("outputs/speaker_track_sanitization_search/speaker_track_sanitization_policy_search.json"))
    parser.add_argument("--audio-guided-sanitization-search", type=Path, default=Path("outputs/audio_guided_sanitization_search/audio_guided_sanitization_policy_search.json"))
    parser.add_argument("--audio-boundary-adjustment-search", type=Path, default=Path("outputs/audio_boundary_adjustment_search/audio_boundary_adjustment_policy_search.json"))
    parser.add_argument("--timeline-integrity", type=Path, default=Path("outputs/timeline_integrity/final_timeline_integrity.json"))
    parser.add_argument("--clipped-baseline-audit", type=Path, default=Path("outputs/clipped_baseline_audit/clipped_baseline_audit.json"))
    parser.add_argument("--baseline-leaderboard-audit", type=Path, default=Path("outputs/baseline_leaderboard_audit/baseline_leaderboard_audit.json"))
    parser.add_argument("--runtime-overlay-contributions", type=Path, default=Path("outputs/runtime_overlay_contributions/runtime_overlay_contributions.json"))
    parser.add_argument("--headroom-audit", type=Path, default=Path("outputs/baseline_headroom_audit/baseline_headroom_audit.json"))
    parser.add_argument("--promotion-gate", type=Path, default=Path("outputs/system_promotion_gate/system_promotion_gate.json"))
    parser.add_argument("--true-heldout-readiness", type=Path, default=Path("outputs/true_heldout_readiness/true_heldout_readiness.json"))
    parser.add_argument("--selector-robustness-diagnosis", type=Path, default=Path("outputs/selector_robustness_diagnosis/selector_robustness_diagnosis.json"))
    parser.add_argument("--batch-smoke", type=Path, default=Path("outputs/realtime_batch/smoke/batch_summary.json"))
    parser.add_argument("--batch-all-cached", type=Path, default=Path("outputs/realtime_batch/all_cached/batch_summary.json"))
    parser.add_argument("--batch-consistency", type=Path, default=Path("outputs/realtime_batch/audit/realtime_batch_consistency.json"))
    parser.add_argument("--recording-level-stability", type=Path, default=Path("outputs/recording_level_stability/recording_level_stability.json"))
    parser.add_argument("--recording-balanced-overlay-search", type=Path, default=Path("outputs/recording_balanced_overlay_search/recording_balanced_overlay_search.json"))
    parser.add_argument("--recording-context-overlay-search", type=Path, default=Path("outputs/recording_context_overlay_search/recording_balanced_overlay_search.json"))
    parser.add_argument("--external-candidate-surface-search", type=Path, default=Path("outputs/external_candidate_surface_search/external_candidate_surface_search.json"))
    parser.add_argument("--external-candidate-source-inventory", type=Path, default=Path("outputs/external_candidate_source_inventory/external_candidate_source_inventory.json"))
    parser.add_argument("--external-candidate-reproduction-plan", type=Path, default=Path("outputs/external_candidate_reproduction_plan/external_candidate_reproduction_plan.json"))
    parser.add_argument("--recording-stability-blockers", type=Path, default=Path("outputs/recording_stability_blockers/recording_stability_blockers.json"))
    parser.add_argument("--max-headroom-gap-pp", type=float, default=0.2)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/system_self_check"))
    args = parser.parse_args()

    metrics = read_json(args.metrics)
    validation = read_json(args.selector_validation)
    selector_search = read_json(args.selector_search)
    rare_selector = read_json(args.rare_selector_search)
    sanitizer = read_json(args.slow_sanitization_search)
    speaker_track_sanitizer = read_json(args.speaker_track_sanitization_search)
    audio_sanitizer = read_json(args.audio_guided_sanitization_search)
    audio_boundary = read_json(args.audio_boundary_adjustment_search)
    timeline_integrity = read_json(args.timeline_integrity)
    clipped_baseline = read_json(args.clipped_baseline_audit)
    baseline_leaderboard = read_json(args.baseline_leaderboard_audit)
    runtime_overlay_contributions = read_json(args.runtime_overlay_contributions)
    headroom = read_json(args.headroom_audit)
    promotion_gate = read_json(args.promotion_gate)
    true_heldout_readiness = read_json(args.true_heldout_readiness)
    robustness_diagnosis = read_json(args.selector_robustness_diagnosis)
    batch_smoke = read_json(args.batch_smoke)
    batch_all_cached = read_json(args.batch_all_cached)
    batch_consistency = read_json(args.batch_consistency)
    recording_stability = read_json(args.recording_level_stability)
    balanced_overlay_search = read_json(args.recording_balanced_overlay_search)
    context_overlay_search = read_json(args.recording_context_overlay_search)
    external_candidate_surface = read_json(args.external_candidate_surface_search)
    external_candidate_inventory = read_json(args.external_candidate_source_inventory)
    external_candidate_reproduction = read_json(args.external_candidate_reproduction_plan)
    stability_blockers = read_json(args.recording_stability_blockers)
    external_reproduction_summary = external_candidate_reproduction.get("summary", {})
    external_manifest_path = Path(str(external_candidate_reproduction.get("missing_window_manifest") or ""))
    external_manifest_rows = csv_row_count(external_manifest_path) if str(external_manifest_path) else None
    manifest_resume_command = external_candidate_reproduction.get("manifest_resume_command", [])
    full_resume_command = external_candidate_reproduction.get("full_resume_command", [])

    m = metrics.get("metrics", {})
    checks = [
        check(bool(metrics), "fail", "metrics_exists", "metrics.json exists and is readable", {"path": str(args.metrics)}),
        check(
            metrics.get("evaluation_status") == "scored_with_cached_reference",
            "fail",
            "scored_with_reference",
            "system run is scored with cached AliMeeting reference windows",
            {"evaluation_status": metrics.get("evaluation_status")},
        ),
        check(
            metrics.get("windows_processed") == metrics.get("cached_windows_available") and metrics.get("windows_processed", 0) > 0,
            "fail",
            "cached_window_coverage",
            "selected windows are fully covered by cached Fast/Slow outputs",
            {
                "windows_processed": metrics.get("windows_processed"),
                "cached_windows_available": metrics.get("cached_windows_available"),
            },
        ),
        check(
            m.get("deepseek_api_calls") == 0 and m.get("qwen_api_calls") == 0 and m.get("omni_api_calls") == 0,
            "fail",
            "no_live_api_calls",
            "offline system path performs zero live DeepSeek/Qwen/Omni calls",
            {
                "deepseek": m.get("deepseek_api_calls"),
                "qwen": m.get("qwen_api_calls"),
                "omni": m.get("omni_api_calls"),
            },
        ),
        check(
            metrics.get("baseline_win_summary", {}).get("beats_all_baselines") is True,
            "fail",
            "beats_all_baselines",
            "final DER beats every tracked same-window baseline",
            metrics.get("baseline_win_summary", {}),
        ),
        check(
            m.get("beats_best_baseline") is True and as_float(m.get("der_delta_vs_best_baseline_pp")) > 0,
            "fail",
            "positive_best_baseline_margin",
            "final DER has positive margin against the best baseline",
            {
                "final_der": m.get("final_der"),
                "best_baseline": metrics.get("best_baseline"),
                "delta_pp": m.get("der_delta_vs_best_baseline_pp"),
            },
        ),
        check(
            metrics.get("variant") == "slow_guarded_fast_fallback_rare_audio_rule_recover",
            "warn",
            "expected_default_variant",
            "default system variant is rare audio rule overlay on speaker-count-safe guarded fallback",
            {"variant": metrics.get("variant")},
        ),
        check(
            validation.get("policy_id") == "slow_guarded_fast_fallback_speaker_count_safe"
            and validation.get("fixed_policy", {}).get("beats_slow") is True,
            "fail",
            "base_selector_validation_matches_runtime",
            "selector validation covers the base fallback policy and beats Slow on the development pool",
            {
                "policy_id": validation.get("policy_id"),
                "status": validation.get("status"),
                "fixed_policy": validation.get("fixed_policy"),
            },
        ),
        check(
            validation.get("status") == "pass_robust_dev_validation",
            "warn",
            "selector_robust_validation",
            "selector has robust bootstrap evidence; warn until this becomes true",
            {
                "status": validation.get("status"),
                "bootstrap": validation.get("bootstrap"),
                "recording_holdout_summary": validation.get("recording_holdout_summary"),
            },
        ),
        check(
            selector_search.get("best_full_policy", {}).get("policy_id", "").endswith("then_fast_base_else_slow_base")
            and "fast_spk_>=_slow_spk" in selector_search.get("best_full_policy", {}).get("policy_id", ""),
            "warn",
            "selector_search_tracks_base_fallback_rule",
            "selector search identifies the speaker-count-safe guard family as the best full-pool base fallback policy",
            {"best_full_policy": selector_search.get("best_full_policy", {})},
        ),
        check(
            rare_selector.get("status") in {"weak_dev_gain_not_robust", "robust_rare_overlay_found"},
            "warn",
            "rare_selector_overlay_search_present",
            "rare selector overlay search artifact is present and reports a known status",
            {"status": rare_selector.get("status"), "best_policy": rare_selector.get("best_policy", {})},
        ),
        check(
            rare_selector.get("runtime_policy", {}).get("true_variant") == "rule_recover_uncovered_only"
            and as_float(rare_selector.get("runtime_policy", {}).get("delta_vs_base_pp")) > 0,
            "warn",
            "rare_selector_overlay_matches_runtime",
            "rare selector overlay search supports the runtime stacked rare rule candidates on the development pool",
            {"runtime_policy": rare_selector.get("runtime_policy", {})},
        ),
        check(
            rare_selector.get("status") == "robust_rare_overlay_found",
            "warn",
            "rare_selector_robust_validation",
            "rare selector overlay has robust bootstrap/recording-holdout evidence; warn until this becomes true",
            {
                "status": rare_selector.get("status"),
                "bootstrap": rare_selector.get("bootstrap"),
                "runtime_bootstrap": rare_selector.get("runtime_bootstrap"),
                "holdout_summary": rare_selector.get("holdout_summary"),
            },
        ),
        check(
            sanitizer.get("status") in {"no_robust_sanitizer_found", "robust_sanitizer_found"},
            "warn",
            "slow_sanitization_search_present",
            "Slow sanitizer search artifact is present and reports a known status",
            {"status": sanitizer.get("status"), "best_policy": sanitizer.get("best_policy", {})},
        ),
        check(
            speaker_track_sanitizer.get("status")
            in {"no_robust_speaker_track_sanitizer_found", "robust_speaker_track_sanitizer_found"},
            "warn",
            "speaker_track_sanitization_search_present",
            "speaker-track sanitizer search artifact is present and reports whether low-evidence speaker-track pruning is robust",
            {
                "status": speaker_track_sanitizer.get("status"),
                "best_policy": speaker_track_sanitizer.get("best_policy", {}),
                "holdout_summary": speaker_track_sanitizer.get("holdout_summary", {}),
            },
        ),
        check(
            bool(speaker_track_sanitizer.get("score_cache", {}).get("enabled"))
            and Path(str(speaker_track_sanitizer.get("score_cache", {}).get("path", ""))).exists()
            and "hits" in speaker_track_sanitizer.get("score_cache", {})
            and "misses" in speaker_track_sanitizer.get("score_cache", {}),
            "warn",
            "speaker_track_score_cache_present",
            "speaker-track sanitizer search records score-cache state so repeated regression runs stay fast",
            {"score_cache": speaker_track_sanitizer.get("score_cache", {})},
        ),
        check(
            audio_sanitizer.get("status") in {"no_robust_audio_sanitizer_found", "robust_audio_sanitizer_found"},
            "warn",
            "audio_guided_sanitization_search_present",
            "audio-guided sanitizer search artifact is present and reports a known status",
            {"status": audio_sanitizer.get("status"), "best_policy": audio_sanitizer.get("best_policy", {})},
        ),
        check(
            audio_boundary.get("status") in {"no_robust_audio_boundary_policy_found", "robust_audio_boundary_policy_found"},
            "warn",
            "audio_boundary_adjustment_search_present",
            "audio-guided boundary adjustment search artifact is present and reports a known status",
            {"status": audio_boundary.get("status"), "best_policy": audio_boundary.get("best_policy", {})},
        ),
        check(
            timeline_integrity.get("status") == "pass",
            "fail",
            "final_timeline_integrity_pass",
            "final timeline artifacts are internally consistent and contain no same-speaker self-overlap",
            {
                "status": timeline_integrity.get("status"),
                "summary": timeline_integrity.get("summary"),
                "issues": timeline_integrity.get("issues", [])[:5],
            },
        ),
        check(
            clipped_baseline.get("status") == "pass"
            and clipped_baseline.get("beats_all_clipped_baselines") is True
            and as_float(clipped_baseline.get("delta_vs_best_clipped_baseline_pp")) > 0,
            "fail",
            "beats_all_clipped_baselines",
            "final DER beats every tracked same-window baseline after applying the same runtime window clipping",
            {
                "status": clipped_baseline.get("status"),
                "final_der": clipped_baseline.get("final_der"),
                "best_clipped_baseline": clipped_baseline.get("best_clipped_baseline"),
                "delta_pp": clipped_baseline.get("delta_vs_best_clipped_baseline_pp"),
            },
        ),
        check(
            baseline_leaderboard.get("status") == "pass"
            and baseline_leaderboard.get("summary", {}).get("beats_all_full_coverage_baselines") is True
            and as_float(baseline_leaderboard.get("summary", {}).get("delta_vs_best_full_coverage_pp")) > 0,
            "fail",
            "beats_all_full_coverage_baselines",
            "final DER beats every discovered baseline artifact that covers the full current 120-window pool",
            {
                "status": baseline_leaderboard.get("status"),
                "summary": baseline_leaderboard.get("summary"),
                "stronger_full_coverage_baselines": baseline_leaderboard.get("summary", {}).get("stronger_full_coverage_baselines"),
            },
        ),
        check(
            runtime_overlay_contributions.get("status") == "pass"
            and runtime_overlay_contributions.get("summary", {}).get("negative_overlay_windows_vs_slow") == 0
            and as_float(runtime_overlay_contributions.get("summary", {}).get("overlay_contribution_vs_slow_pp")) > 0,
            "fail",
            "runtime_overlay_contributions_pass",
            "active runtime overlays have positive clipped-Slow contribution and no negative overlay windows",
            {
                "status": runtime_overlay_contributions.get("status"),
                "summary": runtime_overlay_contributions.get("summary"),
                "source_summary": runtime_overlay_contributions.get("source_summary"),
            },
        ),
        check(
            bool(headroom) and as_float(headroom.get("final_gap_to_oracle_pp"), default=999.0) <= args.max_headroom_gap_pp,
            "warn",
            "headroom_audit_gap",
            "current final path is close to analysis-only oracle over existing candidates",
            {
                "final_der": headroom.get("final_der"),
                "oracle_der": headroom.get("oracle_der"),
                "gap_pp": headroom.get("final_gap_to_oracle_pp"),
                "max_headroom_gap_pp": args.max_headroom_gap_pp,
            },
        ),
        check(
            promotion_gate.get("development_metric_status") == "pass",
            "fail",
            "promotion_gate_dev_metric_pass",
            "promotion gate confirms the development-pool metric beats tracked baselines",
            {"status": promotion_gate.get("status"), "summary": promotion_gate.get("summary")},
        ),
        check(
            promotion_gate.get("promotion_status") == "pass",
            "warn",
            "promotion_gate_generalization_pass",
            "promotion gate confirms robust selector evidence and true-heldout readiness; warn until this becomes true",
            {"status": promotion_gate.get("status"), "gates": promotion_gate.get("gates")},
        ),
        check(
            true_heldout_readiness.get("status")
            in {
                "blocked_missing_sealed_split_and_new_recordings",
                "blocked_missing_sealed_split",
                "blocked_invalid_sealed_split",
                "ready_for_true_heldout_scoring",
            }
            and true_heldout_readiness.get("summary", {}).get("no_metric_claim") is True,
            "fail",
            "true_heldout_readiness_present",
            "true-heldout readiness diagnosis exists, reports a known state, and makes no metric claim",
            {
                "status": true_heldout_readiness.get("status"),
                "summary": true_heldout_readiness.get("summary"),
                "blockers": true_heldout_readiness.get("blockers"),
                "recommended_next_actions": true_heldout_readiness.get("recommended_next_actions"),
            },
        ),
        check(
            robustness_diagnosis.get("status") in {"diagnosed_not_robust", "promotion_ready"},
            "fail",
            "selector_robustness_diagnosis_present",
            "selector robustness diagnosis explains current promotion blockers or confirms readiness",
            {
                "status": robustness_diagnosis.get("status"),
                "blocking_reasons": robustness_diagnosis.get("blocking_reasons"),
                "base_selector": robustness_diagnosis.get("base_selector"),
                "rare_overlay": robustness_diagnosis.get("rare_overlay"),
            },
        ),
        check(
            batch_smoke.get("status") == "pass"
            and batch_smoke.get("summary", {}).get("passed_items") == batch_smoke.get("summary", {}).get("items")
            and batch_smoke.get("summary", {}).get("timeline_integrity_passed_items") == batch_smoke.get("summary", {}).get("items")
            and batch_smoke.get("summary", {}).get("deepseek_api_calls") == 0
            and batch_smoke.get("summary", {}).get("qwen_api_calls") == 0
            and batch_smoke.get("summary", {}).get("omni_api_calls") == 0,
            "fail",
            "realtime_batch_smoke_pass",
            "manifest-style batch runner processes multiple recordings with per-item integrity checks and zero live API calls",
            {
                "status": batch_smoke.get("status"),
                "summary": batch_smoke.get("summary"),
                "items": [
                    {
                        "recording_id": row.get("recording_id"),
                        "status": row.get("status"),
                        "timeline_integrity_status": row.get("timeline_integrity_status"),
                        "windows_processed": row.get("windows_processed"),
                    }
                    for row in batch_smoke.get("items", [])
                ],
            },
        ),
        check(
            batch_all_cached.get("status") == "pass"
            and batch_all_cached.get("summary", {}).get("passed_items") == 8
            and batch_all_cached.get("summary", {}).get("windows_processed") == 120
            and batch_all_cached.get("summary", {}).get("timeline_integrity_passed_items")
            == batch_all_cached.get("summary", {}).get("items")
            and batch_all_cached.get("summary", {}).get("deepseek_api_calls") == 0
            and batch_all_cached.get("summary", {}).get("qwen_api_calls") == 0
            and batch_all_cached.get("summary", {}).get("omni_api_calls") == 0
            and batch_all_cached.get("summary", {}).get("aggregation") == "window_weighted_by_windows_processed",
            "fail",
            "realtime_batch_all_cached_pass",
            "all-cached batch runner processes every cached recording with per-item integrity checks and zero live API calls",
            {"status": batch_all_cached.get("status"), "summary": batch_all_cached.get("summary")},
        ),
        check(
            batch_consistency.get("status") == "pass",
            "fail",
            "realtime_batch_consistency_pass",
            "all-cached batch weighted DER matches the corpus-level all-cached system demo",
            {
                "status": batch_consistency.get("status"),
                "summary": batch_consistency.get("summary"),
                "checks": batch_consistency.get("checks"),
            },
        ),
        check(
            recording_stability.get("status") in {"weak_recording_level_gain_not_robust", "robust_recording_level_gain"},
            "fail",
            "recording_level_stability_present",
            "recording-level stability audit exists and reports final-vs-clipped-baseline resampling evidence",
            {
                "status": recording_stability.get("status"),
                "summary": recording_stability.get("summary"),
                "recording_bootstrap": recording_stability.get("recording_bootstrap"),
            },
        ),
        check(
            recording_stability.get("status") == "robust_recording_level_gain",
            "warn",
            "recording_level_stability_robust",
            "recording-level gain is positive across recordings with a positive recording-bootstrap lower bound; warn until this becomes true",
            {
                "status": recording_stability.get("status"),
                "summary": recording_stability.get("summary"),
                "recording_bootstrap": recording_stability.get("recording_bootstrap"),
            },
        ),
        check(
            balanced_overlay_search.get("status")
            in {"deployable_recording_balanced_candidate_found", "no_deployable_recording_balanced_candidate_found"},
            "fail",
            "recording_balanced_overlay_search_present",
            "recording-balanced overlay search exists and reports whether another deployable stability candidate remains",
            {
                "status": balanced_overlay_search.get("status"),
                "current_policy": balanced_overlay_search.get("current_policy"),
                "best_policy": balanced_overlay_search.get("best_policy"),
            },
        ),
        check(
            context_overlay_search.get("status")
            in {"deployable_recording_balanced_candidate_found", "no_deployable_recording_balanced_candidate_found"},
            "fail",
            "recording_context_overlay_search_present",
            "previous-window context overlay search exists and reports whether another deployable stability candidate remains",
            {
                "status": context_overlay_search.get("status"),
                "current_policy": context_overlay_search.get("current_policy"),
                "best_policy": context_overlay_search.get("best_policy"),
            },
        ),
        check(
            external_candidate_surface.get("status")
            in {
                "deployable_external_candidate_surface_found",
                "promising_external_candidate_surface_found_not_default_runtime",
                "external_candidate_surface_not_deployable",
            }
            and external_candidate_surface.get("runtime_contract")
            == "external_candidate_surface_search_no_live_calls_runtime_features_only",
            "fail",
            "external_candidate_surface_search_present",
            "external candidate surface search exists and reports whether historical model outputs can create a new candidate surface",
            {
                "status": external_candidate_surface.get("status"),
                "candidate_sources": external_candidate_surface.get("candidate_sources"),
                "best_policy": {
                    key: external_candidate_surface.get("best_policy", {}).get(key)
                    for key in [
                        "source_id",
                        "source_coverage_windows",
                        "selected_windows",
                        "delta_vs_current_pp",
                        "positive_recordings_vs_clipped_slow",
                        "overlay_losses_vs_current",
                    ]
                },
                "deployability_gates": external_candidate_surface.get("deployability_gates"),
            },
        ),
        check(
            as_float(external_candidate_surface.get("best_policy", {}).get("source_stale_gt_mismatch_windows"), default=0.0) == 0.0,
            "fail",
            "external_candidate_search_gt_filtered",
            "external candidate search excludes stale same-key windows whose GT fingerprint does not match the current runtime pool",
            {
                "status": external_candidate_surface.get("status"),
                "best_policy": {
                    key: external_candidate_surface.get("best_policy", {}).get(key)
                    for key in [
                        "source_path",
                        "source_coverage_windows",
                        "source_stale_gt_mismatch_windows",
                        "delta_vs_current_pp",
                    ]
                },
                "inputs": external_candidate_surface.get("inputs"),
            },
        ),
        check(
            external_candidate_surface.get("inputs", {}).get("include_oracle_sources") is False
            and external_candidate_surface.get("eval_only_oracle_sources_excluded") is not None,
            "fail",
            "external_candidate_oracle_sources_excluded",
            "default external candidate deployability search excludes speaker_count_mode=oracle summaries as eval-only upper bounds",
            {
                "include_oracle_sources": external_candidate_surface.get("inputs", {}).get("include_oracle_sources"),
                "eval_only_oracle_sources_excluded": external_candidate_surface.get("eval_only_oracle_sources_excluded"),
                "candidate_sources": external_candidate_surface.get("candidate_sources"),
            },
        ),
        check(
            external_candidate_inventory.get("status") == "pass"
            and external_candidate_inventory.get("runtime_contract")
            == "external_candidate_source_inventory_no_live_calls_gt_fingerprint_filtered"
            and external_candidate_inventory.get("summary", {}).get("runtime_windows") == metrics.get("windows_processed"),
            "fail",
            "external_candidate_source_inventory_present",
            "external candidate source inventory exists and uses GT-fingerprint filtering over the current runtime window pool",
            {
                "status": external_candidate_inventory.get("status"),
                "summary": external_candidate_inventory.get("summary"),
                "non_positive_recordings": external_candidate_inventory.get("non_positive_recordings"),
            },
        ),
        check(
            external_candidate_reproduction.get("status")
            in {
                "needs_external_candidate_source_completion",
                "ready_for_default_runtime_promotion_check",
            }
            and external_candidate_reproduction.get("runtime_contract") == "external_candidate_reproduction_plan_no_inference",
            "fail",
            "external_candidate_reproduction_plan_present",
            "external candidate reproduction plan exists and records the missing-window/resume gate before default runtime promotion",
            {
                "status": external_candidate_reproduction.get("status"),
                "summary": external_candidate_reproduction.get("summary"),
                "promotion_gates": external_candidate_reproduction.get("promotion_gates"),
            },
        ),
        check(
            "--segments-manifest" in manifest_resume_command
            and "--summary-name" in manifest_resume_command
            and "--results-name" in manifest_resume_command
            and external_candidate_reproduction.get("missing_window_manifest") in manifest_resume_command,
            "fail",
            "external_candidate_manifest_resume_command_ready",
            "external candidate reproduction plan exposes a manifest-only resume command with distinct summary/results filenames",
            {
                "manifest_resume_command": manifest_resume_command,
                "missing_window_manifest": external_candidate_reproduction.get("missing_window_manifest"),
            },
        ),
        check(
            "--segments-manifest" not in full_resume_command
            and full_resume_command
            and full_resume_command[-2:] != ["--summary-name", "missing_external_candidate_windows_summary.json"],
            "fail",
            "external_candidate_full_refresh_command_ready",
            "external candidate reproduction plan also exposes a full 120-window refresh command for promotion scoring",
            {"full_resume_command": full_resume_command},
        ),
        check(
            external_manifest_rows == external_reproduction_summary.get("missing_windows")
            and external_reproduction_summary.get("expected_windows", 0) > 0
            and external_reproduction_summary.get("covered_windows", -1)
            + external_reproduction_summary.get("missing_windows", -999)
            == external_reproduction_summary.get("expected_windows"),
            "fail",
            "external_candidate_missing_manifest_consistent",
            "missing-window manifest row count matches the reproduction-plan coverage gap",
            {
                "manifest_path": str(external_manifest_path),
                "manifest_rows": external_manifest_rows,
                "summary": external_reproduction_summary,
            },
        ),
        check(
            (
                as_float(external_reproduction_summary.get("stale_checkpoint_windows"), default=0.0) == 0.0
                or "--force-reprocess" in manifest_resume_command
            ),
            "fail",
            "external_candidate_stale_reprocess_command_ready",
            "external candidate reproduction plan requires force reprocess whenever stale checkpoint windows are present",
            {
                "stale_checkpoint_windows": external_reproduction_summary.get("stale_checkpoint_windows"),
                "manifest_resume_command": manifest_resume_command,
            },
        ),
        check(
            stability_blockers.get("status")
            in {
                "candidate_pool_exhausted_for_non_positive_recordings",
                "candidate_pool_headroom_remaining",
                "recording_level_stability_ready",
            },
            "fail",
            "recording_stability_blockers_present",
            "recording stability blocker diagnosis exists and explains whether current candidate pools can improve non-positive recordings",
            {
                "status": stability_blockers.get("status"),
                "summary": stability_blockers.get("summary"),
                "recommended_next_actions": stability_blockers.get("recommended_next_actions"),
            },
        ),
    ]

    fail_count = sum(1 for row in checks if row["status"] == "fail")
    warn_count = sum(1 for row in checks if row["status"] == "warn")
    pass_count = sum(1 for row in checks if row["status"] == "pass")
    payload = {
        "status": "fail" if fail_count else ("warn" if warn_count else "pass"),
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "checks": checks,
        "inputs": {
            "metrics": str(args.metrics),
            "selector_validation": str(args.selector_validation),
            "selector_search": str(args.selector_search),
            "rare_selector_search": str(args.rare_selector_search),
            "slow_sanitization_search": str(args.slow_sanitization_search),
            "speaker_track_sanitization_search": str(args.speaker_track_sanitization_search),
            "audio_guided_sanitization_search": str(args.audio_guided_sanitization_search),
            "audio_boundary_adjustment_search": str(args.audio_boundary_adjustment_search),
            "timeline_integrity": str(args.timeline_integrity),
            "clipped_baseline_audit": str(args.clipped_baseline_audit),
            "baseline_leaderboard_audit": str(args.baseline_leaderboard_audit),
            "runtime_overlay_contributions": str(args.runtime_overlay_contributions),
            "headroom_audit": str(args.headroom_audit),
            "promotion_gate": str(args.promotion_gate),
            "true_heldout_readiness": str(args.true_heldout_readiness),
            "selector_robustness_diagnosis": str(args.selector_robustness_diagnosis),
            "batch_smoke": str(args.batch_smoke),
            "batch_all_cached": str(args.batch_all_cached),
            "batch_consistency": str(args.batch_consistency),
            "recording_level_stability": str(args.recording_level_stability),
            "recording_balanced_overlay_search": str(args.recording_balanced_overlay_search),
            "recording_context_overlay_search": str(args.recording_context_overlay_search),
            "external_candidate_surface_search": str(args.external_candidate_surface_search),
            "external_candidate_source_inventory": str(args.external_candidate_source_inventory),
            "external_candidate_reproduction_plan": str(args.external_candidate_reproduction_plan),
            "external_candidate_missing_manifest": str(external_manifest_path),
            "recording_stability_blockers": str(args.recording_stability_blockers),
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "realtime_system_self_check.json"
    md_path = args.output_dir / "realtime_system_self_check.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"status={payload['status']} pass={pass_count} warn={warn_count} fail={fail_count}")
    raise SystemExit(1 if fail_count else 0)


if __name__ == "__main__":
    main()
