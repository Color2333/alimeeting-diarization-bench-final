#!/usr/bin/env python3
"""Search rare runtime-safe selector overlays on top of the default system.

The base policy is the current speaker-count-safe guarded Fast fallback. This
script searches sparse two-condition overlays that choose a rule/fast candidate
only for a small number of windows. DER is used only after runtime-safe feature
selection for offline ranking and validation.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any

from search_system_selector_policies import WindowKey, as_float, key_from_row, load_features, load_scores


TRUE_VARIANTS = [
    "fast_base",
    "rule_recover_matched_label",
    "rule_recover_uncovered_only",
    "rule_recover_policy_sweep_best",
]
VARIANT_TIEBREAK = {
    "rule_recover_uncovered_only": 0,
    "fast_base": 1,
    "rule_recover_matched_label": 2,
    "rule_recover_policy_sweep_best": 3,
}


def average(values: list[float]) -> float:
    values = [value for value in values if value == value]
    return sum(values) / len(values) if values else 0.0


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def base_variant_for_key(features: dict[str, float], guard_threshold: float) -> str:
    if features["guard_count"] >= guard_threshold and features["fast_spk"] >= features["slow_spk"]:
        return "fast_base"
    return "slow_base"


def build_base_rows(
    keys: list[WindowKey],
    scores: dict[WindowKey, dict[str, dict[str, str]]],
    features: dict[WindowKey, dict[str, float]],
    guard_threshold: float,
) -> dict[WindowKey, str]:
    return {key: base_variant_for_key(features[key], guard_threshold) for key in keys}


def condition_mask(keys: list[WindowKey], features: dict[WindowKey, dict[str, float]], feature: str, op: str, threshold: float) -> int:
    mask = 0
    for idx, key in enumerate(keys):
        value = features[key][feature]
        ok = value >= threshold if op == ">=" else value <= threshold
        if ok:
            mask |= 1 << idx
    return mask


def candidate_thresholds(values: list[float], max_thresholds: int) -> list[float]:
    uniq = sorted(set(values))
    thresholds = uniq + [(a + b) / 2 for a, b in zip(uniq, uniq[1:])]
    if len(thresholds) > max_thresholds:
        step = max(1, len(thresholds) // max_thresholds)
        thresholds = thresholds[::step]
    return thresholds


def build_atomic_conditions(
    keys: list[WindowKey],
    features: dict[WindowKey, dict[str, float]],
    max_thresholds: int,
    max_selected: int,
) -> list[dict[str, Any]]:
    atoms_by_mask: dict[int, dict[str, Any]] = {}
    for feature in sorted(next(iter(features.values())).keys()):
        values = [features[key][feature] for key in keys]
        for op in [">=", "<="]:
            for threshold in candidate_thresholds(values, max_thresholds):
                mask = condition_mask(keys, features, feature, op, threshold)
                selected = mask.bit_count()
                if 1 <= selected <= max_selected:
                    desc = f"{feature} {op} {threshold:g}"
                    row = {
                        "mask": mask,
                        "description": desc,
                        "feature_a": feature,
                        "op_a": op,
                        "threshold_a": threshold,
                        "selected": selected,
                    }
                    if mask not in atoms_by_mask or len(desc) < len(atoms_by_mask[mask]["description"]):
                        atoms_by_mask[mask] = row
    return list(atoms_by_mask.values())


def build_candidate_masks(atoms: list[dict[str, Any]], max_selected: int) -> dict[int, dict[str, Any]]:
    masks: dict[int, dict[str, Any]] = {}
    for atom in atoms:
        if atom["selected"] <= max_selected:
            masks.setdefault(atom["mask"], atom)
    for idx, left in enumerate(atoms):
        for right in atoms[idx + 1 :]:
            mask = int(left["mask"]) & int(right["mask"])
            selected = mask.bit_count()
            if not (1 <= selected <= max_selected) or mask in masks:
                continue
            masks[mask] = {
                "mask": mask,
                "description": f"{left['description']} AND {right['description']}",
                "feature_a": left["feature_a"],
                "op_a": left["op_a"],
                "threshold_a": left["threshold_a"],
                "feature_b": right["feature_a"],
                "op_b": right["op_a"],
                "threshold_b": right["threshold_a"],
                "selected": selected,
            }
    return masks


def evaluate_mask(
    keys: list[WindowKey],
    scores: dict[WindowKey, dict[str, dict[str, str]]],
    base_variants: dict[WindowKey, str],
    mask: int,
    true_variant: str,
    description: str,
) -> dict[str, Any]:
    final_ders = []
    base_ders = []
    slow_ders = []
    choices: dict[str, int] = {}
    selected_windows = []
    wins = 0
    losses = 0
    for idx, key in enumerate(keys):
        use_overlay = bool((mask >> idx) & 1)
        variant = true_variant if use_overlay else base_variants[key]
        choices[variant] = choices.get(variant, 0) + 1
        final_der = as_float(scores[key][variant]["der"])
        base_der = as_float(scores[key][base_variants[key]]["der"])
        slow_der = as_float(scores[key]["slow_base"]["der"])
        final_ders.append(final_der)
        base_ders.append(base_der)
        slow_ders.append(slow_der)
        if use_overlay:
            wins += int(final_der < base_der)
            losses += int(final_der > base_der)
            selected_windows.append(
                {
                    "window_id": f"{key[0]}:{key[1]}:{key[2]}",
                    "base_variant": base_variants[key],
                    "base_der": base_der,
                    "overlay_der": final_der,
                    "delta_vs_base_pp": (base_der - final_der) * 100,
                }
            )
    final_mean = average(final_ders)
    base_mean = average(base_ders)
    slow_mean = average(slow_ders)
    return {
        "policy_kind": "rare_overlay",
        "policy_id": f"if_{description.replace(' ', '_')}_then_{true_variant}_else_default_guarded_selector",
        "description": description,
        "true_variant": true_variant,
        "windows": len(keys),
        "selected_windows": len(selected_windows),
        "overlay_wins_vs_base": wins,
        "overlay_losses_vs_base": losses,
        "final_der": final_mean,
        "base_der": base_mean,
        "slow_der": slow_mean,
        "delta_vs_base": base_mean - final_mean,
        "delta_vs_base_pp": (base_mean - final_mean) * 100,
        "delta_vs_slow": slow_mean - final_mean,
        "delta_vs_slow_pp": (slow_mean - final_mean) * 100,
        "beats_base": final_mean < base_mean,
        "beats_slow": final_mean < slow_mean,
        "choice_counts": choices,
        "selected_window_details": selected_windows,
    }


def search_policies(
    keys: list[WindowKey],
    scores: dict[WindowKey, dict[str, dict[str, str]]],
    features: dict[WindowKey, dict[str, float]],
    base_variants: dict[WindowKey, str],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    atoms = build_atomic_conditions(keys, features, args.max_thresholds, args.max_selected_windows)
    candidate_masks = build_candidate_masks(atoms, args.max_selected_windows)
    rows = []
    for mask, meta in candidate_masks.items():
        for variant in TRUE_VARIANTS:
            row = evaluate_mask(keys, scores, base_variants, mask, variant, meta["description"])
            if row["selected_windows"] >= args.min_selected_windows and row["delta_vs_base"] > 0:
                rows.append({**row, **{key: value for key, value in meta.items() if key != "mask"}})
    rows.sort(key=lambda row: (row["final_der"], row["overlay_losses_vs_base"], VARIANT_TIEBREAK.get(row["true_variant"], 99), row["policy_id"]))
    return rows


def recording_holdout(
    keys: list[WindowKey],
    scores: dict[WindowKey, dict[str, dict[str, str]]],
    features: dict[WindowKey, dict[str, float]],
    base_variants: dict[WindowKey, str],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    rows = []
    for recording_id in sorted({key[0] for key in keys}):
        train = [key for key in keys if key[0] != recording_id]
        heldout = [key for key in keys if key[0] == recording_id]
        train_policies = search_policies(train, scores, features, base_variants, args)
        if not train_policies:
            continue
        best = train_policies[0]
        mask = 0
        for idx, key in enumerate(heldout):
            ok_a = (
                features[key][best["feature_a"]] >= best["threshold_a"]
                if best["op_a"] == ">="
                else features[key][best["feature_a"]] <= best["threshold_a"]
            )
            ok_b = True
            if best.get("feature_b"):
                ok_b = (
                    features[key][best["feature_b"]] >= best["threshold_b"]
                    if best["op_b"] == ">="
                    else features[key][best["feature_b"]] <= best["threshold_b"]
                )
            if ok_a and ok_b:
                mask |= 1 << idx
        heldout_score = evaluate_mask(heldout, scores, base_variants, mask, best["true_variant"], best["description"])
        rows.append(
            {
                "heldout_recording_id": recording_id,
                "selected_policy_id": best["policy_id"],
                "train_final_der": best["final_der"],
                "train_base_der": best["base_der"],
                "heldout_windows": len(heldout),
                "heldout_selected_windows": heldout_score["selected_windows"],
                "heldout_final_der": heldout_score["final_der"],
                "heldout_base_der": heldout_score["base_der"],
                "heldout_slow_der": heldout_score["slow_der"],
                "heldout_delta_vs_base": heldout_score["delta_vs_base"],
                "heldout_delta_vs_base_pp": heldout_score["delta_vs_base_pp"],
                "heldout_beats_base": heldout_score["beats_base"],
            }
        )
    return rows


def bootstrap_delta(best: dict[str, Any], keys: list[WindowKey], scores: dict[WindowKey, dict[str, dict[str, str]]], features: dict[WindowKey, dict[str, float]], base_variants: dict[WindowKey, str], samples: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        sample = [rng.choice(keys) for _ in keys]
        mask = 0
        for idx, key in enumerate(sample):
            ok_a = features[key][best["feature_a"]] >= best["threshold_a"] if best["op_a"] == ">=" else features[key][best["feature_a"]] <= best["threshold_a"]
            ok_b = True
            if best.get("feature_b"):
                ok_b = features[key][best["feature_b"]] >= best["threshold_b"] if best["op_b"] == ">=" else features[key][best["feature_b"]] <= best["threshold_b"]
            if ok_a and ok_b:
                mask |= 1 << idx
        scored = evaluate_mask(sample, scores, base_variants, mask, best["true_variant"], best["description"])
        deltas.append(scored["delta_vs_base"])
    return {
        "samples": samples,
        "seed": seed,
        "mean_delta_vs_base": average(deltas),
        "delta_ci_low": percentile(deltas, 0.025),
        "delta_ci_high": percentile(deltas, 0.975),
        "prob_beats_base": sum(1 for value in deltas if value > 0) / len(deltas) if deltas else 0.0,
    }


def evaluate_runtime_stack(
    keys: list[WindowKey],
    scores: dict[WindowKey, dict[str, dict[str, str]]],
    features: dict[WindowKey, dict[str, float]],
    base_variants: dict[WindowKey, str],
) -> dict[str, Any]:
    mask = 0
    for idx, key in enumerate(keys):
        feature_row = features[key]
        if base_variants[key] != "slow_base":
            continue
        if feature_row.get("audio_speech_sec", 0.0) >= 18.605 or feature_row.get("slow_segments", 999.0) <= 3:
            mask |= 1 << idx
    row = evaluate_mask(
        keys,
        scores,
        base_variants,
        mask,
        "rule_recover_uncovered_only",
        "audio_speech_sec >= 18.605 OR slow_segments <= 3",
    )
    row["policy_id"] = "runtime_stack_audio_speech_ge_18p605_or_slow_segments_le_3_then_rule_recover_uncovered_only_else_default_guarded_selector"
    row["stacked_conditions"] = [
        "audio_speech_sec >= 18.605",
        "slow_segments <= 3",
    ]
    return row


def bootstrap_runtime_stack(
    keys: list[WindowKey],
    scores: dict[WindowKey, dict[str, dict[str, str]]],
    features: dict[WindowKey, dict[str, float]],
    base_variants: dict[WindowKey, str],
    samples: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        sample = [rng.choice(keys) for _ in keys]
        scored = evaluate_runtime_stack(sample, scores, features, base_variants)
        deltas.append(scored["delta_vs_base"])
    return {
        "samples": samples,
        "seed": seed,
        "mean_delta_vs_base": average(deltas),
        "delta_ci_low": percentile(deltas, 0.025),
        "delta_ci_high": percentile(deltas, 0.975),
        "prob_beats_base": sum(1 for value in deltas if value > 0) / len(deltas) if deltas else 0.0,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    best = payload["best_policy"]
    runtime_policy = payload["runtime_policy"]
    lines = [
        "# Rare Selector Overlay Search",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Windows: `{payload['windows']}`",
        f"- Best policy: `{best['policy_id']}`",
        f"- Final DER: `{best['final_der']:.2%}` vs base `{best['base_der']:.2%}`",
        f"- Delta vs base: `{best['delta_vs_base_pp']:.3f}pp`",
        f"- Selected windows: `{best['selected_windows']}`",
        f"- Bootstrap P(beats base): `{payload['bootstrap']['prob_beats_base']:.1%}`",
        f"- Holdout positive splits vs base: `{payload['holdout_summary']['positive_splits_vs_base']}/{payload['holdout_summary']['splits']}`",
        f"- Holdout weighted delta vs base: `{payload['holdout_summary']['weighted_delta_vs_base_pp']:.3f}pp`",
        f"- Runtime stacked policy DER: `{runtime_policy['final_der']:.2%}` vs base `{runtime_policy['base_der']:.2%}`",
        f"- Runtime stacked delta vs base: `{runtime_policy['delta_vs_base_pp']:.3f}pp`",
        f"- Runtime stacked selected windows: `{runtime_policy['selected_windows']}`",
        f"- Runtime stacked bootstrap P(beats base): `{payload['runtime_bootstrap']['prob_beats_base']:.1%}`",
        "",
        "## Top Policies",
        "",
        "| Rank | Policy | Final DER | Base DER | Delta | Selected | Wins/Losses |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(payload["top_policies"], start=1):
        lines.append(
            f"| {idx} | `{row['policy_id']}` | {row['final_der']:.2%} | {row['base_der']:.2%} | {row['delta_vs_base_pp']:.3f}pp | {row['selected_windows']} | {row['overlay_wins_vs_base']}/{row['overlay_losses_vs_base']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- The overlay uses only runtime-safe prediction, gate, and audio feature artifacts.",
            "- DER is used only after policy materialization for offline ranking and validation.",
            "- Weak holdout means this is a development-pool optimization, not a robust generalization claim.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline-results", type=Path, default=Path("outputs/rule_writeback_timeline_120/rule_writeback_timeline_results.csv"))
    parser.add_argument("--window-features", type=Path, default=Path("outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv"))
    parser.add_argument("--gate-decisions", type=Path, default=Path("outputs/writeback_gate_120/gate_decisions.csv"))
    parser.add_argument("--audio-features", type=Path, default=Path("outputs/audio_window_features/audio_window_features_120.csv"))
    parser.add_argument("--guard-threshold", type=float, default=1.0)
    parser.add_argument("--max-thresholds", type=int, default=80)
    parser.add_argument("--min-selected-windows", type=int, default=1)
    parser.add_argument("--max-selected-windows", type=int, default=12)
    parser.add_argument("--bootstrap-samples", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/rare_selector_search"))
    args = parser.parse_args()

    scores = load_scores(args.timeline_results)
    features = load_features(args.window_features, args.gate_decisions, args.audio_features)
    keys = sorted(key for key in scores if key in features and {"fast_base", "slow_base", *TRUE_VARIANTS}.issubset(scores[key]))
    base_variants = build_base_rows(keys, scores, features, args.guard_threshold)
    policies = search_policies(keys, scores, features, base_variants, args)
    if not policies:
        raise SystemExit("No positive rare overlay policies found")
    runtime_policy = evaluate_runtime_stack(keys, scores, features, base_variants)
    holdout_rows = recording_holdout(keys, scores, features, base_variants, args)
    weighted_holdout_final = average([row["heldout_final_der"] for row in holdout_rows])
    weighted_holdout_base = average([row["heldout_base_der"] for row in holdout_rows])
    bootstrap = bootstrap_delta(policies[0], keys, scores, features, base_variants, args.bootstrap_samples, args.seed)
    runtime_bootstrap = bootstrap_runtime_stack(keys, scores, features, base_variants, args.bootstrap_samples, args.seed)
    positive = sum(1 for row in holdout_rows if row["heldout_beats_base"])
    status = (
        "robust_rare_overlay_found"
        if policies[0]["delta_vs_base"] > 0 and bootstrap["delta_ci_low"] > 0 and positive == len(holdout_rows)
        else "weak_dev_gain_not_robust"
    )
    payload = {
        "runtime_contract": "rare_selector_overlay_no_live_calls_runtime_features_only",
        "status": status,
        "windows": len(keys),
        "base_policy": "slow_guarded_fast_fallback_speaker_count_safe",
        "guard_threshold": args.guard_threshold,
        "no_live_calls_performed": True,
        "no_deepseek_api_calls": True,
        "metric_claim_boundary": "development_pool_search_not_true_heldout",
        "candidate_policies": len(policies),
        "best_policy": policies[0],
        "runtime_policy": runtime_policy,
        "top_policies": policies[: args.top_n],
        "holdout": holdout_rows,
        "holdout_summary": {
            "splits": len(holdout_rows),
            "positive_splits_vs_base": positive,
            "weighted_holdout_final_der": weighted_holdout_final,
            "weighted_holdout_base_der": weighted_holdout_base,
            "weighted_delta_vs_base": weighted_holdout_base - weighted_holdout_final,
            "weighted_delta_vs_base_pp": (weighted_holdout_base - weighted_holdout_final) * 100,
        },
        "bootstrap": bootstrap,
        "runtime_bootstrap": runtime_bootstrap,
    }

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "rare_selector_policy_search.json"
    md_path = out_dir / "rare_selector_policy_search.md"
    csv_path = out_dir / "rare_selector_policy_search.csv"
    holdout_csv = out_dir / "rare_selector_policy_holdout.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    write_csv(csv_path, policies[: max(args.top_n, 100)])
    write_csv(holdout_csv, holdout_rows)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "status={status} best={best:.2%} base={base:.2%} delta={delta:.3f}pp holdout_delta={holdout:.3f}pp".format(
            status=status,
            best=policies[0]["final_der"],
            base=policies[0]["base_der"],
            delta=policies[0]["delta_vs_base_pp"],
            holdout=(weighted_holdout_base - weighted_holdout_final) * 100,
        )
    )


if __name__ == "__main__":
    main()
