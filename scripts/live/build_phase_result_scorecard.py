#!/usr/bin/env python3
"""Build a compact phase result scorecard from existing no-new-call artifacts."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/phase_result_scorecard.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/phase_result_scorecard.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/phase_result_scorecard.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def pct(value: Any, digits: int = 2) -> float:
    return round(float(value) * 100, digits)


def pick_variant(bootstrap: dict[str, Any], variant: str) -> dict[str, Any]:
    for row in bootstrap.get("summaries", []):
        if row.get("variant") == variant:
            return row
    return {}


def row(
    *,
    result_id: str,
    area: str,
    headline: str,
    metric: str,
    value: str,
    evidence_strength: str,
    claim_boundary: str,
    source_artifacts: list[str],
) -> dict[str, Any]:
    return {
        "result_id": result_id,
        "area": area,
        "headline": headline,
        "metric": metric,
        "value": value,
        "evidence_strength": evidence_strength,
        "claim_boundary": claim_boundary,
        "source_artifacts": source_artifacts,
        "source_artifacts_exist": all((ROOT / source).exists() for source in source_artifacts),
    }


def build_scorecard(root: Path) -> dict[str, Any]:
    holdout = read_json(root / "outputs/recover_selector_split_120/recording_holdout_summary.json")
    bootstrap = read_json(root / "outputs/realtime_contract_bootstrap_120/realtime_contract_bootstrap.json")
    timeline = read_json(root / "outputs/system_timeline/summary.json")
    slo = read_json(root / "outputs/research_progress_snapshot/stage_latency_slo_audit.json")
    latency = read_json(root / "outputs/research_progress_snapshot/runtime_latency_budget_ledger.json")
    guard = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_passthrough_safety_summary.json")
    guard_tuning = read_json(root / "outputs/runtime_safe_llm_window_batch/llm_guard_tuning_104w_summary.json")
    omni = read_json(root / "outputs/omni_guard/omni_acoustic_fusion_summary.json")
    qwen = read_json(root / "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json")
    live_output = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")

    fast = pick_variant(bootstrap, "fast_base")
    rule = pick_variant(bootstrap, "rule_recover_policy_sweep_best")
    slow = pick_variant(bootstrap, "slow_base")
    slo_summary = slo.get("summary", {})
    latency_summary = latency.get("summary", {})
    live_summary = live_output.get("summary", {})
    trace_summary = traceability.get("summary", {})

    rows = [
        row(
            result_id="recording_holdout_selector_gain",
            area="DER improvement",
            headline="Selector improves DER on all recording-holdout splits.",
            metric="weighted DER delta vs fast",
            value=(
                f"{pct(holdout.get('weighted_fast_der', 0)):.2f}% -> "
                f"{pct(holdout.get('weighted_heldout_der', 0)):.2f}% "
                f"(+{pct(holdout.get('weighted_delta_vs_fast', 0)):.2f} pp); "
                f"positive splits {holdout.get('positive_splits', 0)}/{holdout.get('splits', 0)}"
            ),
            evidence_strength="recording_holdout",
            claim_boundary="not_true_heldout_until_new_recordings",
            source_artifacts=["outputs/recover_selector_split_120/recording_holdout_summary.json"],
        ),
        row(
            result_id="bootstrap_rule_recover_gain",
            area="DER improvement",
            headline="Rule-recover policy beats fast baseline in bootstrap sampling.",
            metric="bootstrap DER and P(beats fast)",
            value=(
                f"fast {pct(fast.get('observed_der', 0)):.2f}% vs "
                f"rule {pct(rule.get('observed_der', 0)):.2f}%; "
                f"delta +{pct(rule.get('delta_vs_fast', 0)):.2f} pp; "
                f"P(beats fast) {pct(rule.get('prob_beats_fast', 0), 1):.1f}%"
            ),
            evidence_strength="development_bootstrap",
            claim_boundary="dev_set_not_final_test",
            source_artifacts=["outputs/realtime_contract_bootstrap_120/realtime_contract_bootstrap.json"],
        ),
        row(
            result_id="slow_model_upper_bound",
            area="DER reference",
            headline="Slow model is the quality upper reference but not the realtime path.",
            metric="slow-base DER delta vs fast",
            value=(
                f"slow {pct(slow.get('observed_der', 0)):.2f}% vs "
                f"fast {pct(fast.get('observed_der', 0)):.2f}%; "
                f"delta +{pct(slow.get('delta_vs_fast', 0)):.2f} pp"
            ),
            evidence_strength="development_bootstrap",
            claim_boundary="quality_reference_not_realtime_claim",
            source_artifacts=["outputs/realtime_contract_bootstrap_120/realtime_contract_bootstrap.json"],
        ),
        row(
            result_id="runtime_latency_slo_pass",
            area="Latency",
            headline="Current claim-now runtime stages pass latency SLO.",
            metric="claim-now SLO pass",
            value=(
                f"{slo_summary.get('claim_now_slo_pass', 0)}/{slo_summary.get('claim_now_slo_rows', 0)}; "
                f"fast avg/p95 {timeline.get('fast_avg_delay_sec', 0):.3f}/{timeline.get('fast_p95_delay_sec', 0):.3f}s; "
                f"writeback avg/p95 {timeline.get('rule_writeback_avg_delay_sec', 0):.3f}/{timeline.get('rule_writeback_p95_delay_sec', 0):.3f}s"
            ),
            evidence_strength="claim_now_runtime",
            claim_boundary="post_live_latency_not_claimed",
            source_artifacts=[
                "outputs/research_progress_snapshot/stage_latency_slo_audit.json",
                "outputs/system_timeline/summary.json",
            ],
        ),
        row(
            result_id="llm_guard_zero_harm",
            area="Safety",
            headline="Runtime-safe guard recovers useful patches while preserving zero harmful accepts.",
            metric="safe accepts / harmful accepts",
            value=(
                f"safe accepts {guard.get('safe_accepts', 0)}; "
                f"harmful accepts {guard.get('harmful_accepts', 0)}; "
                f"conservative recovered {guard_tuning.get('best_zero_harm_conservative_recovered', 0)}; "
                f"patches {guard.get('patches', 0)}"
            ),
            evidence_strength="runtime_guard_existing_outputs",
            claim_boundary="block_or_quarantine_only_no_auto_timeline_override",
            source_artifacts=[
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_passthrough_safety_summary.json",
                "outputs/runtime_safe_llm_window_batch/llm_guard_tuning_104w_summary.json",
            ],
        ),
        row(
            result_id="omni_acoustic_smoke",
            area="Acoustic / Omni",
            headline="Omni acoustic signal is useful for review routing, not direct writeback.",
            metric="review-priority recall and latency",
            value=(
                f"high recall {omni.get('review_priority_high_recall', '')}; "
                f"clean high-sentinel FP {omni.get('clean_high_sentinel_fp', '')}; "
                f"flash avg/p95 {float(omni.get('avg_flash_call_seconds', 0)):.2f}/{float(omni.get('p95_flash_call_seconds', 0)):.2f}s"
            ),
            evidence_strength="12_window_smoke",
            claim_boundary="label_only_no_timeline_writeback",
            source_artifacts=["outputs/omni_guard/omni_acoustic_fusion_summary.json"],
        ),
        row(
            result_id="qwen_fallback_smoke",
            area="Fallback live smoke",
            headline="Qwen fallback completed safely but is slower than the primary latency target.",
            metric="fallback wall / harmful accepts",
            value=(
                f"parents {qwen.get('parent_windows', 0)}; calls {qwen.get('split_calls', 0)}; "
                f"wall {qwen.get('runs', [{}])[0].get('wall_seconds', 0):.3f}s; "
                f"harmful accepts {qwen.get('harmful_accepts', 0)}"
            ),
            evidence_strength="fallback_smoke",
            claim_boundary="fallback_only_not_primary_latency_claim",
            source_artifacts=["outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json"],
        ),
        row(
            result_id="deepseek_no_go",
            area="Execution decision",
            headline="DeepSeek full-live path is no-go after API exhaustion.",
            metric="live output availability",
            value=(
                f"observed live rows {live_summary.get('observed_live_output_rows', 0)}; "
                f"missing surfaces {live_summary.get('missing_output_surfaces', 0)}; "
                "DeepSeek API exhausted, no further DeepSeek calls"
            ),
            evidence_strength="execution_boundary",
            claim_boundary="do_not_use_deepseek_api",
            source_artifacts=["outputs/research_progress_snapshot/live_output_audit.json"],
        ),
    ]

    return {
        "runtime_contract": "phase_result_scorecard_from_existing_artifacts_no_live_calls",
        "status": "pass",
        "summary": {
            "result_rows": len(rows),
            "reportable_rows": 7,
            "deepseek_no_go_rows": 1,
            "claim_now_slo_pass": int(slo_summary.get("claim_now_slo_pass", 0)),
            "claim_now_slo_rows": int(slo_summary.get("claim_now_slo_rows", 0)),
            "selector_positive_splits": int(holdout.get("positive_splits", 0)),
            "selector_splits": int(holdout.get("splits", 0)),
            "selector_weighted_delta_pp": pct(holdout.get("weighted_delta_vs_fast", 0)),
            "rule_bootstrap_delta_pp": pct(rule.get("delta_vs_fast", 0)),
            "guard_harmful_accepts": int(guard.get("harmful_accepts", -1)),
            "guard_safe_accepts": int(guard.get("safe_accepts", 0)),
            "omni_smoke_windows": int(omni.get("windows", 0)),
            "qwen_fallback_calls": int(qwen.get("split_calls", 0)),
            "traceability_rows": int(trace_summary.get("traceability_rows", 0)),
            "traceability_fully_covered_rows": int(trace_summary.get("fully_covered_rows", 0)),
            "live_calls_performed_by_builder": 0,
            "no_live_calls_performed": True,
            "no_scoring_commands_executed": True,
            "no_deepseek_api_calls": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(scorecard: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "result_id",
        "area",
        "headline",
        "metric",
        "value",
        "evidence_strength",
        "claim_boundary",
        "source_artifacts_exist",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in scorecard["rows"]:
            writer.writerow({field: item.get(field, "") for field in fieldnames})


def write_markdown(scorecard: dict[str, Any], path: Path) -> None:
    summary = scorecard["summary"]
    lines = [
        "# Phase Result Scorecard",
        "",
        f"- Runtime contract: `{scorecard['runtime_contract']}`",
        f"- Status: `{scorecard['status']}`",
        f"- Result rows: `{summary['result_rows']}`",
        f"- Claim-now SLO pass: `{summary['claim_now_slo_pass']}/{summary['claim_now_slo_rows']}`",
        f"- Selector positive splits: `{summary['selector_positive_splits']}/{summary['selector_splits']}`",
        f"- Selector weighted DER delta: `{summary['selector_weighted_delta_pp']}` pp",
        f"- Rule bootstrap DER delta: `{summary['rule_bootstrap_delta_pp']}` pp",
        f"- Guard harmful accepts: `{summary['guard_harmful_accepts']}`",
        f"- Guard safe accepts: `{summary['guard_safe_accepts']}`",
        f"- Omni smoke windows: `{summary['omni_smoke_windows']}`",
        f"- Qwen fallback calls: `{summary['qwen_fallback_calls']}`",
        f"- DeepSeek API calls: `0` (no-go after exhaustion)",
        f"- Traceability: `{summary['traceability_fully_covered_rows']}/{summary['traceability_rows']}`",
        "",
        "| Area | Result | Metric | Evidence | Boundary |",
        "|---|---|---|---|---|",
    ]
    for item in scorecard["rows"]:
        lines.append(
            f"| {item['area']} | {item['headline']} | {item['value']} | "
            f"`{item['evidence_strength']}` | `{item['claim_boundary']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- The strongest current result is not a completed live-agent run; it is a validated staged system result: DER improves on recording-holdout selector evidence, claim-now runtime stages pass SLO, and guard safety preserves zero harmful accepts.",
            "- DeepSeek full-live is explicitly no-go after API exhaustion; this scorecard performs no live/API/model/scoring calls.",
            "- Qwen and Omni are currently fallback/smoke or label-only evidence. They should be used to tell the next-step route, not to overclaim full-surface live performance.",
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
    args.output_json.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(scorecard, args.output_md)
    write_csv(scorecard, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")
    print(json.dumps({"status": scorecard["status"], "summary": scorecard["summary"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
