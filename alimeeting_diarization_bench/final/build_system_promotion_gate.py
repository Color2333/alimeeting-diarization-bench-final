#!/usr/bin/env python3
"""Build promotion gates for the current offline realtime system.

This separates development-pool metric improvement from evidence required to
promote the selector as robust/generalizable. It performs no live calls and does
not score new metrics.
"""

from __future__ import annotations

# Keep final modules import-compatible when executed with python -m.
import sys as _sys
from pathlib import Path as _Path
_SCRIPT_ROOT = _Path(__file__).resolve().parent
_REPO_ROOT = _Path(__file__).resolve().parents[2]
for _candidate in [_REPO_ROOT, _SCRIPT_ROOT, *_SCRIPT_ROOT.iterdir()]:
    if _candidate.is_dir():
        _value = str(_candidate)
        if _value not in _sys.path:
            _sys.path.insert(0, _value)

import argparse
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


def gate(gate_id: str, passed: bool, evidence: dict[str, Any], required_for: str = "promotion") -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "pass" if passed else "blocked",
        "required_for": required_for,
        "evidence": evidence,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# System Promotion Gate",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Development metric status: `{payload['development_metric_status']}`",
        f"- Promotion status: `{payload['promotion_status']}`",
        f"- Final DER: `{payload['summary']['final_der_pct']}`",
        f"- Best-baseline margin: `{payload['summary']['delta_vs_best_baseline_pp']}` pp",
        f"- Best clipped-baseline margin: `{payload['summary']['delta_vs_best_clipped_baseline_pp']}` pp",
        f"- Timeline integrity status: `{payload['summary']['timeline_integrity_status']}`",
        f"- Recording-level stability: `{payload['summary']['recording_level_stability_status']}` "
        f"(`{payload['summary']['recording_level_positive_recordings']}/{payload['summary']['recording_level_recordings']}` positive recordings)",
        f"- True-heldout status: `{payload['summary']['true_heldout_status']}`",
        "",
        "## Gates",
        "",
        "| Status | Gate | Required for | Evidence |",
        "|---|---|---|---|",
    ]
    for row in payload["gates"]:
        lines.append(
            f"| `{row['status']}` | `{row['gate_id']}` | `{row['required_for']}` | `{json.dumps(row['evidence'], sort_keys=True)}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- `development_metric_status=pass` means the current cached development pool beats the tracked baselines.",
            "- `promotion_status=blocked` means the selector should not be claimed as robust/generalized yet.",
            "- This artifact does not run model inference, live APIs, or new DER scoring.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/metrics.json"))
    parser.add_argument("--base-selector-validation", type=Path, default=Path("outputs/system_selector_validation/guarded_slow_selector_validation.json"))
    parser.add_argument("--rare-selector-search", type=Path, default=Path("outputs/rare_selector_search/rare_selector_policy_search.json"))
    parser.add_argument("--timeline-integrity", type=Path, default=Path("outputs/timeline_integrity/final_timeline_integrity.json"))
    parser.add_argument("--clipped-baseline-audit", type=Path, default=Path("outputs/clipped_baseline_audit/clipped_baseline_audit.json"))
    parser.add_argument("--recording-level-stability", type=Path, default=Path("outputs/recording_level_stability/recording_level_stability.json"))
    parser.add_argument("--headroom-audit", type=Path, default=Path("outputs/baseline_headroom_audit/baseline_headroom_audit.json"))
    parser.add_argument("--true-heldout-scan", type=Path, default=Path("outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.json"))
    parser.add_argument("--true-heldout-split-validation", type=Path, default=Path("outputs/research_progress_snapshot/selector_true_heldout_split_validation.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/system_promotion_gate"))
    args = parser.parse_args()

    metrics = read_json(args.metrics)
    base_validation = read_json(args.base_selector_validation)
    rare_selector = read_json(args.rare_selector_search)
    timeline_integrity = read_json(args.timeline_integrity)
    clipped_baseline = read_json(args.clipped_baseline_audit)
    recording_stability = read_json(args.recording_level_stability)
    headroom = read_json(args.headroom_audit)
    true_heldout_scan = read_json(args.true_heldout_scan)
    true_heldout_split = read_json(args.true_heldout_split_validation)

    m = metrics.get("metrics", {})
    beats_all = metrics.get("baseline_win_summary", {}).get("beats_all_baselines") is True
    positive_margin = as_float(m.get("der_delta_vs_best_baseline_pp")) > 0
    timeline_clean = timeline_integrity.get("status") == "pass"
    beats_clipped = (
        clipped_baseline.get("status") == "pass"
        and clipped_baseline.get("beats_all_clipped_baselines") is True
        and as_float(clipped_baseline.get("delta_vs_best_clipped_baseline_pp")) > 0
    )
    no_live_calls = (
        m.get("deepseek_api_calls") == 0
        and m.get("qwen_api_calls") == 0
        and m.get("omni_api_calls") == 0
    )
    base_robust = base_validation.get("status") == "pass_robust_dev_validation"
    rare_used = metrics.get("variant") == "slow_guarded_fast_fallback_rare_audio_rule_recover"
    rare_robust = (not rare_used) or rare_selector.get("status") == "robust_rare_overlay_found"
    recording_level_robust = recording_stability.get("status") == "robust_recording_level_gain"
    true_heldout_ready = true_heldout_split.get("status") in {"pass", "ready_for_selector_true_heldout_scoring"}
    headroom_close = as_float(headroom.get("final_gap_to_oracle_pp"), default=999.0) <= 0.2

    gates = [
        gate(
            "beats_all_tracked_baselines",
            beats_all and positive_margin,
            {
                "beats_all_baselines": beats_all,
                "delta_vs_best_baseline_pp": m.get("der_delta_vs_best_baseline_pp"),
            },
            required_for="development_metric",
        ),
        gate(
            "offline_no_live_calls",
            no_live_calls,
            {
                "deepseek": m.get("deepseek_api_calls"),
                "qwen": m.get("qwen_api_calls"),
                "omni": m.get("omni_api_calls"),
            },
            required_for="development_metric",
        ),
        gate(
            "final_timeline_integrity",
            timeline_clean,
            {
                "status": timeline_integrity.get("status"),
                "summary": timeline_integrity.get("summary"),
                "issues": timeline_integrity.get("issues", [])[:5],
            },
            required_for="development_metric",
        ),
        gate(
            "beats_all_clipped_baselines",
            beats_clipped,
            {
                "status": clipped_baseline.get("status"),
                "beats_all_clipped_baselines": clipped_baseline.get("beats_all_clipped_baselines"),
                "best_clipped_baseline": clipped_baseline.get("best_clipped_baseline"),
                "delta_vs_best_clipped_baseline_pp": clipped_baseline.get("delta_vs_best_clipped_baseline_pp"),
            },
            required_for="development_metric",
        ),
        gate(
            "base_selector_robust_dev_validation",
            base_robust,
            {
                "status": base_validation.get("status"),
                "bootstrap": base_validation.get("bootstrap"),
                "recording_holdout_summary": base_validation.get("recording_holdout_summary"),
            },
        ),
        gate(
            "rare_selector_robust_dev_validation",
            rare_robust,
            {
                "runtime_uses_rare_overlay": rare_used,
                "status": rare_selector.get("status"),
                "bootstrap": rare_selector.get("bootstrap"),
                "runtime_bootstrap": rare_selector.get("runtime_bootstrap"),
                "holdout_summary": rare_selector.get("holdout_summary"),
                "runtime_policy": rare_selector.get("runtime_policy"),
            },
        ),
        gate(
            "recording_level_stability",
            recording_level_robust,
            {
                "status": recording_stability.get("status"),
                "summary": recording_stability.get("summary"),
                "recording_bootstrap": recording_stability.get("recording_bootstrap"),
            },
        ),
        gate(
            "true_heldout_split_ready",
            true_heldout_ready,
            {
                "split_status": true_heldout_split.get("status"),
                "split_summary": true_heldout_split.get("summary"),
                "candidate_scan_status": true_heldout_scan.get("status"),
                "candidate_scan_summary": true_heldout_scan.get("summary"),
            },
        ),
        gate(
            "current_candidate_oracle_gap_tracked",
            headroom_close,
            {
                "final_der": headroom.get("final_der"),
                "oracle_der": headroom.get("oracle_der"),
                "final_gap_to_oracle_pp": headroom.get("final_gap_to_oracle_pp"),
            },
            required_for="diagnostic",
        ),
    ]

    development_metric_pass = all(row["status"] == "pass" for row in gates if row["required_for"] == "development_metric")
    promotion_pass = all(row["status"] == "pass" for row in gates if row["required_for"] == "promotion")
    payload = {
        "runtime_contract": "system_promotion_gate_no_live_calls_no_new_scoring",
        "status": "promoted" if development_metric_pass and promotion_pass else ("dev_metric_pass_promotion_blocked" if development_metric_pass else "development_metric_blocked"),
        "development_metric_status": "pass" if development_metric_pass else "blocked",
        "promotion_status": "pass" if promotion_pass else "blocked",
        "summary": {
            "variant": metrics.get("variant"),
            "final_der": m.get("final_der"),
            "final_der_pct": f"{as_float(m.get('final_der')) * 100:.4f}%",
            "delta_vs_best_baseline_pp": m.get("der_delta_vs_best_baseline_pp"),
            "delta_vs_best_clipped_baseline_pp": clipped_baseline.get("delta_vs_best_clipped_baseline_pp"),
            "timeline_integrity_status": timeline_integrity.get("status"),
            "recording_level_stability_status": recording_stability.get("status"),
            "recording_level_positive_recordings": recording_stability.get("summary", {}).get("positive_recordings"),
            "recording_level_recordings": recording_stability.get("summary", {}).get("recordings"),
            "base_selector_status": base_validation.get("status"),
            "rare_selector_status": rare_selector.get("status"),
            "true_heldout_status": true_heldout_split.get("status"),
            "headroom_gap_pp": headroom.get("final_gap_to_oracle_pp"),
        },
        "gates": gates,
        "metric_claim_boundary": "development_pool_metric_improved_but_promotion_requires_robust_and_true_heldout_evidence",
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "system_promotion_gate.json"
    md_path = args.output_dir / "system_promotion_gate.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "status={status} dev_metric={dev} promotion={promo} final={final}".format(
            status=payload["status"],
            dev=payload["development_metric_status"],
            promo=payload["promotion_status"],
            final=payload["summary"]["final_der_pct"],
        )
    )


if __name__ == "__main__":
    main()
