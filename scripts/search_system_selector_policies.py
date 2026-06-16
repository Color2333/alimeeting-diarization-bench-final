#!/usr/bin/env python3
"""Search runtime-safe system selector policies.

This searches simple deployable decision stumps for choosing a final timeline
variant per window. Runtime features come from Fast/Slow prediction surfaces and
gate counts only. DER is used only after selection to rank and validate policies.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


WindowKey = tuple[str, int, int]


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def key_from_row(row: dict[str, Any]) -> WindowKey:
    return (str(row["recording_id"]), int(float(row["window_size"])), int(float(row["segment_idx"])))


def load_scores(path: Path) -> dict[WindowKey, dict[str, dict[str, str]]]:
    out: dict[WindowKey, dict[str, dict[str, str]]] = defaultdict(dict)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            out[key_from_row(row)][row["variant"]] = row
    return out


def load_audio_features(path: Path | None) -> dict[WindowKey, dict[str, float]]:
    if path is None or not path.exists():
        return {}
    out: dict[WindowKey, dict[str, float]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = key_from_row(row)
            out[key] = {
                field: as_float(value)
                for field, value in row.items()
                if field.startswith("audio_") and field not in {"audio_path", "audio_exists"}
            }
    return out


def load_features(path: Path, gate_decisions: Path, audio_features: Path | None) -> dict[WindowKey, dict[str, float]]:
    features: dict[WindowKey, dict[str, float]] = {}
    audio_by_key = load_audio_features(audio_features)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = key_from_row(row)
            fast_speech = as_float(row.get("fast_speech"))
            slow_speech = as_float(row.get("slow_speech"))
            fast_segments = as_float(row.get("fast_segments"))
            slow_segments = as_float(row.get("slow_segments"))
            fast_spk = as_float(row.get("fast_spk_count_pred"))
            slow_spk = as_float(row.get("slow_spk_count_pred"))
            features[key] = {
                "fast_spk": fast_spk,
                "slow_spk": slow_spk,
                "spk_diff": slow_spk - fast_spk,
                "fast_segments": fast_segments,
                "slow_segments": slow_segments,
                "seg_diff": slow_segments - fast_segments,
                "fast_speech": fast_speech,
                "slow_speech": slow_speech,
                "slow_fast_speech_ratio": slow_speech / fast_speech if fast_speech else 999.0,
                "fast_slow_disagreement_sec": as_float(row.get("fast_slow_disagreement_sec")),
                "keep_fast_supported": as_float(row.get("keep_fast_supported")),
                "boundary_fix_or_relabel": as_float(row.get("boundary_fix_or_relabel")),
                "suppress_fast_candidate": as_float(row.get("suppress_fast_candidate")),
                "recover_slow_segment": as_float(row.get("recover_slow_segment")),
                "align_slow_segment": as_float(row.get("align_slow_segment")),
                "guard_count": 0.0,
            }
            if key in audio_by_key:
                features[key].update(audio_by_key[key])
                features[key]["slow_audio_speech_overrun_sec"] = features[key]["slow_speech"] - audio_by_key[key]["audio_speech_sec"]
                features[key]["fast_audio_speech_overrun_sec"] = features[key]["fast_speech"] - audio_by_key[key]["audio_speech_sec"]
                features[key]["slow_audio_speech_ratio"] = (
                    features[key]["slow_speech"] / audio_by_key[key]["audio_speech_sec"]
                    if audio_by_key[key]["audio_speech_sec"]
                    else 999.0
                )
                features[key]["fast_audio_speech_ratio"] = (
                    features[key]["fast_speech"] / audio_by_key[key]["audio_speech_sec"]
                    if audio_by_key[key]["audio_speech_sec"]
                    else 999.0
                )

    with gate_decisions.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = key_from_row(row)
            if key in features and row.get("gate_category") == "guard_or_quarantine":
                features[key]["guard_count"] += 1.0
    return features


def average(rows: list[dict[str, str]], field: str) -> float:
    values = [as_float(row.get(field), default=float("nan")) for row in rows]
    values = [value for value in values if value == value]
    return sum(values) / len(values) if values else 0.0


def candidate_thresholds(keys: list[WindowKey], features: dict[WindowKey, dict[str, float]], feature: str) -> list[float]:
    values = sorted({features[key][feature] for key in keys})
    thresholds = sorted(set(values + [(a + b) / 2 for a, b in zip(values, values[1:])]))
    if len(thresholds) > 100:
        step = max(1, len(thresholds) // 100)
        thresholds = thresholds[::step]
    return thresholds


def evaluate_policy(
    keys: list[WindowKey],
    scores: dict[WindowKey, dict[str, dict[str, str]]],
    features: dict[WindowKey, dict[str, float]],
    feature: str,
    op: str,
    threshold: float,
    true_variant: str,
    false_variant: str = "slow_base",
) -> dict[str, Any]:
    chosen = []
    choices: Counter[str] = Counter()
    for key in keys:
        value = features[key][feature]
        condition = value >= threshold if op == ">=" else value <= threshold
        variant = true_variant if condition else false_variant
        chosen.append(scores[key][variant])
        choices[variant] += 1
    slow_rows = [scores[key]["slow_base"] for key in keys]
    fast_rows = [scores[key]["fast_base"] for key in keys]
    final_der = average(chosen, "der")
    slow_der = average(slow_rows, "der")
    fast_der = average(fast_rows, "der")
    return {
        "policy_kind": "stump",
        "policy_id": f"if_{feature}_{op}_{threshold:g}_then_{true_variant}_else_{false_variant}",
        "feature": feature,
        "op": op,
        "threshold": threshold,
        "true_variant": true_variant,
        "false_variant": false_variant,
        "windows": len(keys),
        "final_der": final_der,
        "slow_der": slow_der,
        "fast_der": fast_der,
        "delta_vs_slow": slow_der - final_der,
        "delta_vs_slow_pp": (slow_der - final_der) * 100,
        "beats_slow": final_der < slow_der,
        "delta_vs_fast": fast_der - final_der,
        "delta_vs_fast_pp": (fast_der - final_der) * 100,
        "choice_counts": dict(choices),
    }


def evaluate_speaker_count_safe_guard(
    keys: list[WindowKey],
    scores: dict[WindowKey, dict[str, dict[str, str]]],
    features: dict[WindowKey, dict[str, float]],
    threshold: float,
) -> dict[str, Any]:
    chosen = []
    choices: Counter[str] = Counter()
    blocked = 0
    for key in keys:
        allow_fast = features[key]["guard_count"] >= threshold and features[key]["fast_spk"] >= features[key]["slow_spk"]
        if features[key]["guard_count"] >= threshold and not allow_fast:
            blocked += 1
        variant = "fast_base" if allow_fast else "slow_base"
        chosen.append(scores[key][variant])
        choices[variant] += 1
    slow_rows = [scores[key]["slow_base"] for key in keys]
    fast_rows = [scores[key]["fast_base"] for key in keys]
    final_der = average(chosen, "der")
    slow_der = average(slow_rows, "der")
    fast_der = average(fast_rows, "der")
    return {
        "policy_kind": "speaker_count_safe_guard",
        "policy_id": f"if_guard_count_>=_{threshold:g}_and_fast_spk_>=_slow_spk_then_fast_base_else_slow_base",
        "feature": "guard_count+speaker_count",
        "op": "speaker_count_safe_guard",
        "threshold": threshold,
        "true_variant": "fast_base",
        "false_variant": "slow_base",
        "windows": len(keys),
        "final_der": final_der,
        "slow_der": slow_der,
        "fast_der": fast_der,
        "delta_vs_slow": slow_der - final_der,
        "delta_vs_slow_pp": (slow_der - final_der) * 100,
        "beats_slow": final_der < slow_der,
        "delta_vs_fast": fast_der - final_der,
        "delta_vs_fast_pp": (fast_der - final_der) * 100,
        "choice_counts": dict(choices),
        "fallback_blocked_by_speaker_count": blocked,
    }


def search_policies(
    keys: list[WindowKey],
    scores: dict[WindowKey, dict[str, dict[str, str]]],
    features: dict[WindowKey, dict[str, float]],
    true_variants: list[str],
) -> list[dict[str, Any]]:
    rows = []
    feature_names = sorted(next(iter(features.values())).keys())
    for feature in feature_names:
        for op in [">=", "<="]:
            for threshold in candidate_thresholds(keys, features, feature):
                for variant in true_variants:
                    rows.append(evaluate_policy(keys, scores, features, feature, op, threshold, variant))
    for threshold in candidate_thresholds(keys, features, "guard_count"):
        rows.append(evaluate_speaker_count_safe_guard(keys, scores, features, threshold))
    rows.sort(key=lambda row: (row["final_der"], -row["delta_vs_slow"], row["policy_id"]))
    return rows


def recording_holdout(
    keys: list[WindowKey],
    scores: dict[WindowKey, dict[str, dict[str, str]]],
    features: dict[WindowKey, dict[str, float]],
    true_variants: list[str],
) -> list[dict[str, Any]]:
    rows = []
    for recording_id in sorted({key[0] for key in keys}):
        train = [key for key in keys if key[0] != recording_id]
        heldout = [key for key in keys if key[0] == recording_id]
        best = search_policies(train, scores, features, true_variants)[0]
        if best.get("policy_kind") == "speaker_count_safe_guard":
            heldout_score = evaluate_speaker_count_safe_guard(heldout, scores, features, float(best["threshold"]))
        else:
            heldout_score = evaluate_policy(
                heldout,
                scores,
                features,
                best["feature"],
                best["op"],
                float(best["threshold"]),
                best["true_variant"],
                best["false_variant"],
            )
        rows.append(
            {
                "heldout_recording_id": recording_id,
                "selected_policy_id": best["policy_id"],
                "train_final_der": best["final_der"],
                "train_slow_der": best["slow_der"],
                "heldout_windows": heldout_score["windows"],
                "heldout_final_der": heldout_score["final_der"],
                "heldout_slow_der": heldout_score["slow_der"],
                "heldout_delta_vs_slow": heldout_score["delta_vs_slow"],
                "heldout_delta_vs_slow_pp": heldout_score["delta_vs_slow_pp"],
                "heldout_beats_slow": heldout_score["beats_slow"],
                "heldout_choice_counts": json.dumps(heldout_score["choice_counts"], sort_keys=True),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# System Selector Policy Search",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Best full policy: `{payload['best_full_policy']['policy_id']}`",
        f"- Best full DER: `{payload['best_full_policy']['final_der']:.2%}` vs Slow `{payload['best_full_policy']['slow_der']:.2%}`",
        f"- Holdout positive splits: `{payload['holdout_summary']['positive_splits_vs_slow']}/{payload['holdout_summary']['splits']}`",
        f"- Holdout weighted delta vs Slow: `{payload['holdout_summary']['weighted_delta_vs_slow_pp']:.2f}pp`",
        "",
        "## Top Policies",
        "",
        "| Rank | Policy | Final DER | Slow DER | Delta | Choices |",
        "|---:|---|---:|---:|---:|---|",
    ]
    for idx, row in enumerate(payload["top_policies"], start=1):
        lines.append(
            f"| {idx} | `{row['policy_id']}` | {row['final_der']:.2%} | {row['slow_der']:.2%} | {row['delta_vs_slow_pp']:.2f}pp | `{json.dumps(row['choice_counts'], sort_keys=True)}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Policies use only deployable Fast/Slow prediction features and gate counts.",
            "- DER is used only after the policy chooses a timeline variant.",
            "- If holdout is weak, the policy should not be promoted beyond development-pool evidence.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline-results", type=Path, default=Path("outputs/rule_writeback_timeline_120/rule_writeback_timeline_results.csv"))
    parser.add_argument("--window-features", type=Path, default=Path("outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv"))
    parser.add_argument("--gate-decisions", type=Path, default=Path("outputs/writeback_gate_120/gate_decisions.csv"))
    parser.add_argument("--audio-features", type=Path, default=Path("outputs/audio_window_features/audio_window_features_120.csv"))
    parser.add_argument("--true-variants", default="fast_base,rule_recover_policy_sweep_best,rule_recover_matched_label,rule_recover_uncovered_only")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/system_selector_search"))
    args = parser.parse_args()

    scores = load_scores(args.timeline_results)
    features = load_features(args.window_features, args.gate_decisions, args.audio_features)
    keys = sorted(key for key in scores if key in features and {"fast_base", "slow_base"}.issubset(scores[key]))
    true_variants = [item.strip() for item in args.true_variants.split(",") if item.strip()]

    policies = search_policies(keys, scores, features, true_variants)
    holdout_rows = recording_holdout(keys, scores, features, true_variants)
    weighted_holdout_final = sum(row["heldout_final_der"] for row in holdout_rows) / len(holdout_rows)
    weighted_holdout_slow = sum(row["heldout_slow_der"] for row in holdout_rows) / len(holdout_rows)
    positive = sum(1 for row in holdout_rows if row["heldout_beats_slow"])
    status = (
        "robust_candidate_found"
        if positive == len(holdout_rows) and weighted_holdout_final < weighted_holdout_slow
        else "no_robust_candidate_found"
    )
    payload = {
        "runtime_contract": "system_selector_policy_search_no_live_calls_runtime_features_only",
        "status": status,
        "timeline_results": str(args.timeline_results),
        "window_features": str(args.window_features),
        "gate_decisions": str(args.gate_decisions),
        "audio_features": str(args.audio_features) if args.audio_features else None,
        "runtime_feature_surface": sorted(next(iter(features.values())).keys()),
        "true_variants": true_variants,
        "windows": len(keys),
        "no_live_calls_performed": True,
        "no_deepseek_api_calls": True,
        "metric_claim_boundary": "development_pool_search_not_true_heldout",
        "best_full_policy": policies[0],
        "top_policies": policies[: args.top_n],
        "holdout": holdout_rows,
        "holdout_summary": {
            "splits": len(holdout_rows),
            "positive_splits_vs_slow": positive,
            "weighted_holdout_final_der": weighted_holdout_final,
            "weighted_holdout_slow_der": weighted_holdout_slow,
            "weighted_delta_vs_slow": weighted_holdout_slow - weighted_holdout_final,
            "weighted_delta_vs_slow_pp": (weighted_holdout_slow - weighted_holdout_final) * 100,
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "system_selector_policy_search.json"
    md_path = args.output_dir / "system_selector_policy_search.md"
    policies_csv = args.output_dir / "system_selector_policy_search.csv"
    holdout_csv = args.output_dir / "system_selector_policy_holdout.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    write_csv(policies_csv, policies[: max(args.top_n, 100)])
    write_csv(holdout_csv, holdout_rows)

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"status={status} best={policies[0]['final_der']:.2%} holdout_delta={payload['holdout_summary']['weighted_delta_vs_slow_pp']:.2f}pp")


if __name__ == "__main__":
    main()
