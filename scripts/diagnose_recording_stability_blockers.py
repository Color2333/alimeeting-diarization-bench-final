#!/usr/bin/env python3
"""Diagnose why recording-level stability has not reached promotion quality.

This is an evidence report, not a runtime selector. It compares current final
windows with clipped same-window candidates to determine whether non-positive
recordings can still be improved by the existing candidate pool.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_VARIANTS = [
    "fast_base",
    "slow_base",
    "rule_recover_policy_sweep_best",
    "rule_recover_matched_label",
    "rule_recover_uncovered_only",
]


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def average(values: list[float]) -> float | None:
    values = [value for value in values if value == value]
    return sum(values) / len(values) if values else None


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def window_key(row: dict[str, Any]) -> tuple[str, int, int]:
    return (str(row["recording_id"]), int(float(row["window_size"])), int(float(row["segment_idx"])))


def window_id(key: tuple[str, int, int]) -> str:
    return f"{key[0]}:{key[1]}:{key[2]}"


def load_final_windows(path: Path) -> dict[tuple[str, int, int], dict[str, Any]]:
    out = {}
    for row in read_csv(path):
        key = window_key(row)
        out[key] = {
            "window_id": row.get("window_id") or window_id(key),
            "recording_id": key[0],
            "final_der": as_float(row.get("final_der"), default=float("nan")),
            "final_source": row.get("final_source", ""),
        }
    return out


def load_candidate_scores(path: Path, variants: set[str]) -> dict[tuple[str, int, int], dict[str, float]]:
    scores: dict[tuple[str, int, int], dict[str, float]] = defaultdict(dict)
    for row in read_csv(path):
        variant = row.get("baseline_id", "")
        if variant not in variants:
            continue
        scores[window_key(row)][variant] = as_float(row.get("der"), default=float("nan"))
    return scores


def summarize_recordings(
    final: dict[tuple[str, int, int], dict[str, Any]],
    scores: dict[tuple[str, int, int], dict[str, float]],
    variants: list[str],
    baseline_id: str,
    epsilon_pp: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for key in sorted(set(final) & set(scores)):
        if baseline_id in scores[key]:
            grouped[key[0]].append(key)

    rec_rows = []
    opportunity_rows = []
    epsilon = epsilon_pp / 100
    for recording_id, keys in sorted(grouped.items()):
        final_ders = []
        slow_ders = []
        oracle_ders = []
        oracle_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        better_than_current = 0
        better_than_baseline = 0
        for key in keys:
            final_der = final[key]["final_der"]
            baseline_der = scores[key][baseline_id]
            candidates = {variant: scores[key][variant] for variant in variants if variant in scores[key]}
            oracle_variant, oracle_der = min(candidates.items(), key=lambda item: (item[1], item[0]))
            final_ders.append(final_der)
            slow_ders.append(baseline_der)
            oracle_ders.append(oracle_der)
            oracle_counts[oracle_variant] += 1
            source_counts[final[key]["final_source"]] += 1
            if final_der - oracle_der > epsilon:
                better_than_current += 1
                opportunity_rows.append(
                    {
                        "recording_id": recording_id,
                        "window_id": window_id(key),
                        "final_der": final_der,
                        "baseline_der": baseline_der,
                        "oracle_der": oracle_der,
                        "oracle_variant": oracle_variant,
                        "gap_vs_current_pp": (final_der - oracle_der) * 100,
                        "gap_vs_baseline_pp": (baseline_der - oracle_der) * 100,
                        "final_source": final[key]["final_source"],
                    }
                )
            if baseline_der - oracle_der > epsilon:
                better_than_baseline += 1

        mean_final = average(final_ders) or 0.0
        mean_baseline = average(slow_ders) or 0.0
        mean_oracle = average(oracle_ders) or 0.0
        delta_vs_baseline_pp = (mean_baseline - mean_final) * 100
        oracle_delta_vs_baseline_pp = (mean_baseline - mean_oracle) * 100
        rec_rows.append(
            {
                "recording_id": recording_id,
                "windows": len(keys),
                "final_der": mean_final,
                "baseline_der": mean_baseline,
                "oracle_der": mean_oracle,
                "delta_vs_baseline_pp": delta_vs_baseline_pp,
                "oracle_delta_vs_baseline_pp": oracle_delta_vs_baseline_pp,
                "oracle_gap_vs_current_pp": (mean_final - mean_oracle) * 100,
                "beats_baseline": delta_vs_baseline_pp > epsilon_pp,
                "non_positive_vs_baseline": delta_vs_baseline_pp <= epsilon_pp,
                "windows_with_candidate_better_than_current": better_than_current,
                "windows_with_candidate_better_than_baseline": better_than_baseline,
                "source_counts": dict(source_counts),
                "oracle_variant_counts": dict(oracle_counts),
            }
        )
    opportunity_rows.sort(key=lambda row: row["gap_vs_current_pp"], reverse=True)
    return rec_rows, opportunity_rows


def overlay_summary(path: Path) -> dict[str, Any]:
    data = read_json(path)
    current = data.get("current_policy", {})
    best = data.get("best_policy", {})
    return {
        "path": str(path),
        "exists": bool(data),
        "status": data.get("status", "missing"),
        "feature_context": data.get("feature_context"),
        "current_positive_recordings": current.get("positive_recordings_vs_clipped_slow"),
        "best_positive_recordings": best.get("positive_recordings_vs_clipped_slow"),
        "best_negative_recordings": best.get("negative_recordings_vs_clipped_slow"),
        "best_delta_vs_current_pp": best.get("delta_vs_current_pp"),
        "best_policy_id": best.get("policy_id"),
        "best_selected_windows": best.get("selected_windows"),
    }


def external_candidate_summary(path: Path) -> dict[str, Any]:
    data = read_json(path)
    best = data.get("best_policy", {})
    oracle = data.get("external_candidate_oracle", {})
    gates = data.get("deployability_gates", {})
    return {
        "path": str(path),
        "exists": bool(data),
        "status": data.get("status", "missing"),
        "candidate_sources": data.get("candidate_sources"),
        "candidate_policies": data.get("candidate_policies"),
        "current_positive_recordings": data.get("current_positive_recordings"),
        "best_positive_recordings": best.get("positive_recordings_vs_clipped_slow"),
        "best_negative_recordings": best.get("negative_recordings_vs_clipped_slow"),
        "best_delta_vs_current_pp": best.get("delta_vs_current_pp"),
        "best_selected_windows": best.get("selected_windows"),
        "best_source_full_coverage": best.get("source_full_coverage"),
        "best_source_stale_gt_mismatch_windows": best.get("source_stale_gt_mismatch_windows"),
        "oracle_gain_vs_current_pp": oracle.get("oracle_gain_vs_current_pp"),
        "oracle_positive_recordings_vs_clipped_slow": oracle.get("positive_recordings_vs_clipped_slow"),
        "oracle_negative_recordings_vs_clipped_slow": oracle.get("negative_recordings_vs_clipped_slow"),
        "deployable": gates.get("deployable"),
        "promising_not_default_runtime": gates.get("promising_not_default_runtime"),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Recording Stability Blocker Diagnosis",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Non-positive recordings: `{payload['summary']['non_positive_recordings']}/{payload['summary']['recordings']}`",
        f"- Non-positive candidate-pool oracle gain: `{payload['summary']['non_positive_oracle_delta_vs_baseline_pp']:.4f}pp`",
        f"- Global clipped-candidate oracle gap: `{payload['summary']['global_oracle_gap_vs_current_pp']:.4f}pp`",
        "",
        "## Non-Positive Recordings",
        "",
        "| Recording | Final DER | Baseline DER | Oracle DER | Delta vs baseline | Oracle gain vs baseline | Better windows | Sources | Oracle variants |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in payload["non_positive_recordings"]:
        lines.append(
            "| `{recording_id}` | {final_der:.2%} | {baseline_der:.2%} | {oracle_der:.2%} | {delta:.4f}pp | {oracle_delta:.4f}pp | {better} | `{sources}` | `{oracle}` |".format(
                recording_id=row["recording_id"],
                final_der=as_float(row["final_der"]),
                baseline_der=as_float(row["baseline_der"]),
                oracle_der=as_float(row["oracle_der"]),
                delta=as_float(row["delta_vs_baseline_pp"]),
                oracle_delta=as_float(row["oracle_delta_vs_baseline_pp"]),
                better=row["windows_with_candidate_better_than_baseline"],
                sources=json.dumps(row["source_counts"], sort_keys=True),
                oracle=json.dumps(row["oracle_variant_counts"], sort_keys=True),
            )
        )
    lines.extend(
        [
            "",
            "## Remaining Search Surface",
            "",
            "| Search | Status | Current positive | Best positive | Best delta | Negatives |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in payload["overlay_searches"]:
        lines.append(
            f"| `{row['feature_context']}` | `{row['status']}` | {row['current_positive_recordings']} | "
            f"{row['best_positive_recordings']} | {as_float(row['best_delta_vs_current_pp']):.4f}pp | {row['best_negative_recordings']} |"
        )
    external = payload["external_candidate_surface"]
    lines.extend(
        [
            "",
            "## GT-Filtered External Candidate Surface",
            "",
            f"- Status: `{external['status']}`",
            f"- Best delta vs current: `{as_float(external['best_delta_vs_current_pp']):.4f}pp`",
            f"- Best positive recordings: `{external['best_positive_recordings']}/{payload['summary']['recordings']}`",
            f"- Best source stale GT-mismatch windows: `{external['best_source_stale_gt_mismatch_windows']}`",
            f"- Oracle gain vs current: `{as_float(external['oracle_gain_vs_current_pp']):.4f}pp`",
        ]
    )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- If non-positive recordings have near-zero clipped-candidate oracle gain, existing Fast/Slow/rule variants cannot make recording-level robustness true.",
            "- The next useful optimization should create new correction candidates or stronger speaker/activity evidence, rather than only retuning current thresholds.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/window_metrics.csv"))
    parser.add_argument("--clipped-baseline-scores", type=Path, default=Path("outputs/clipped_baseline_audit/clipped_baseline_scores.csv"))
    parser.add_argument("--recording-balanced-overlay-search", type=Path, default=Path("outputs/recording_balanced_overlay_search/recording_balanced_overlay_search.json"))
    parser.add_argument("--recording-context-overlay-search", type=Path, default=Path("outputs/recording_context_overlay_search/recording_balanced_overlay_search.json"))
    parser.add_argument("--external-candidate-surface-search", type=Path, default=Path("outputs/external_candidate_surface_search/external_candidate_surface_search.json"))
    parser.add_argument("--variants", nargs="*", default=DEFAULT_VARIANTS)
    parser.add_argument("--baseline-id", default="slow_base")
    parser.add_argument("--epsilon-pp", type=float, default=0.001)
    parser.add_argument("--candidate-exhausted-oracle-gain-pp", type=float, default=0.01)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/recording_stability_blockers"))
    args = parser.parse_args()

    variants = list(dict.fromkeys(args.variants))
    final = load_final_windows(args.window_metrics)
    scores = load_candidate_scores(args.clipped_baseline_scores, set(variants))
    per_recording, opportunities = summarize_recordings(
        final,
        scores,
        variants,
        args.baseline_id,
        args.epsilon_pp,
    )
    if not per_recording:
        raise SystemExit("No shared final/candidate windows found")

    non_positive = [row for row in per_recording if row["non_positive_vs_baseline"]]
    non_positive_oracle_delta = average([row["oracle_delta_vs_baseline_pp"] for row in non_positive]) or 0.0
    global_oracle_gap = average([row["oracle_gap_vs_current_pp"] for row in per_recording]) or 0.0
    overlay_searches = [
        overlay_summary(args.recording_balanced_overlay_search),
        overlay_summary(args.recording_context_overlay_search),
    ]
    external_surface = external_candidate_summary(args.external_candidate_surface_search)
    no_remaining_deployable_search = all(
        row["status"] == "no_deployable_recording_balanced_candidate_found" for row in overlay_searches if row["exists"]
    ) and external_surface.get("status") != "deployable_external_candidate_surface_found"
    external_oracle_gain = as_float(external_surface.get("oracle_gain_vs_current_pp"), default=0.0)
    external_best_delta = as_float(external_surface.get("best_delta_vs_current_pp"), default=0.0)
    candidate_pool_exhausted = (
        bool(non_positive)
        and non_positive_oracle_delta <= args.candidate_exhausted_oracle_gain_pp
        and no_remaining_deployable_search
        and external_best_delta <= args.candidate_exhausted_oracle_gain_pp
    )
    if not non_positive:
        status = "recording_level_stability_ready"
    elif candidate_pool_exhausted:
        status = "candidate_pool_exhausted_for_non_positive_recordings"
    else:
        status = "candidate_pool_headroom_remaining"

    payload = {
        "runtime_contract": "analysis_only_recording_stability_blocker_diagnosis_no_live_calls",
        "status": status,
        "baseline_id": args.baseline_id,
        "variants": variants,
        "summary": {
            "recordings": len(per_recording),
            "non_positive_recordings": len(non_positive),
            "non_positive_oracle_delta_vs_baseline_pp": non_positive_oracle_delta,
            "global_oracle_gap_vs_current_pp": global_oracle_gap,
            "candidate_exhausted_oracle_gain_pp": args.candidate_exhausted_oracle_gain_pp,
            "no_remaining_deployable_search": no_remaining_deployable_search,
            "external_candidate_best_delta_vs_current_pp": external_best_delta,
            "external_candidate_oracle_gain_vs_current_pp": external_oracle_gain,
        },
        "non_positive_recordings": non_positive,
        "per_recording": per_recording,
        "top_opportunity_windows": opportunities[:20],
        "overlay_searches": overlay_searches,
        "external_candidate_surface": external_surface,
        "recommended_next_actions": [
            "generate_new_correction_candidates_for_non_positive_recordings",
            "add_stronger_speaker_activity_or_speaker_count_evidence",
            "avoid_claiming_generalization_until_true_heldout_or_all_recording_positive_evidence_exists",
        ],
        "metric_claim_boundary": "development_pool_diagnosis_not_runtime_policy_not_true_heldout",
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "recording_stability_blockers.json"
    md_path = args.output_dir / "recording_stability_blockers.md"
    csv_path = args.output_dir / "recording_stability_blockers.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    write_csv(csv_path, per_recording)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    print(
        "status={status} non_positive={non_positive}/{recordings} non_positive_oracle_gain={gain:.4f}pp global_gap={gap:.4f}pp".format(
            status=status,
            non_positive=len(non_positive),
            recordings=len(per_recording),
            gain=non_positive_oracle_delta,
            gap=global_oracle_gap,
        )
    )


if __name__ == "__main__":
    main()
