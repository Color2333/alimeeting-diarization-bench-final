#!/usr/bin/env python3
"""Search runtime-safe overlays optimized for recording-level stability."""

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
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from search_system_selector_policies import WindowKey, as_float, key_from_row, load_features


TRUE_VARIANTS = [
    "fast_base",
    "rule_recover_matched_label",
    "rule_recover_uncovered_only",
    "rule_recover_policy_sweep_best",
]


def average(values: list[float]) -> float:
    values = [value for value in values if value == value]
    return sum(values) / len(values) if values else 0.0


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def window_id(key: WindowKey) -> str:
    return f"{key[0]}:{key[1]}:{key[2]}"


def load_final(path: Path) -> dict[WindowKey, dict[str, Any]]:
    out = {}
    for row in read_csv(path):
        key = key_from_row(row)
        out[key] = {
            "window_id": row["window_id"],
            "recording_id": row["recording_id"],
            "final_der": as_float(row.get("final_der"), default=float("nan")),
            "final_source": row.get("final_source", ""),
        }
    return out


def load_clipped_scores(path: Path) -> dict[WindowKey, dict[str, float]]:
    scores: dict[WindowKey, dict[str, float]] = defaultdict(dict)
    for row in read_csv(path):
        key = key_from_row(row)
        scores[key][row["baseline_id"]] = as_float(row.get("der"), default=float("nan"))
    return scores


def candidate_thresholds(values: list[float], max_thresholds: int) -> list[float]:
    uniq = sorted(set(values))
    thresholds = uniq + [(a + b) / 2 for a, b in zip(uniq, uniq[1:])]
    if len(thresholds) > max_thresholds:
        step = max(1, len(thresholds) // max_thresholds)
        thresholds = thresholds[::step]
    return thresholds


def condition_mask(keys: list[WindowKey], features: dict[WindowKey, dict[str, float]], feature: str, op: str, threshold: float) -> int:
    mask = 0
    for idx, key in enumerate(keys):
        value = features[key][feature]
        ok = value >= threshold if op == ">=" else value <= threshold
        if ok:
            mask |= 1 << idx
    return mask


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
                    atom = {
                        "mask": mask,
                        "description": desc,
                        "feature_a": feature,
                        "op_a": op,
                        "threshold_a": threshold,
                        "selected": selected,
                    }
                    if mask not in atoms_by_mask or len(desc) < len(atoms_by_mask[mask]["description"]):
                        atoms_by_mask[mask] = atom
    return list(atoms_by_mask.values())


def build_candidate_masks(atoms: list[dict[str, Any]], max_selected: int) -> dict[int, dict[str, Any]]:
    masks: dict[int, dict[str, Any]] = {}
    for atom in atoms:
        masks.setdefault(int(atom["mask"]), atom)
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


def add_previous_window_context(features: dict[WindowKey, dict[str, float]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = sorted({name for row in features.values() for name in row})
    by_recording_idx = {(key[0], key[2]): key for key in features}
    for key in sorted(features):
        prev_key = by_recording_idx.get((key[0], key[2] - 1))
        features[key]["has_prev_window"] = 1.0 if prev_key is not None else 0.0
        for field in fields:
            if field.startswith("prev_"):
                continue
            features[key][f"prev_{field}"] = features[prev_key][field] if prev_key is not None and field in features[prev_key] else 0.0


def recording_summary(
    keys: list[WindowKey],
    final_ders: dict[WindowKey, float],
    slow_ders: dict[WindowKey, float],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[WindowKey]] = defaultdict(list)
    for key in keys:
        grouped[key[0]].append(key)
    rows = []
    for recording_id, recording_keys in sorted(grouped.items()):
        final_der = average([final_ders[key] for key in recording_keys])
        slow_der = average([slow_ders[key] for key in recording_keys])
        delta = slow_der - final_der
        rows.append(
            {
                "recording_id": recording_id,
                "windows": len(recording_keys),
                "final_der": final_der,
                "slow_der": slow_der,
                "delta_vs_slow_pp": delta * 100,
                "beats_slow": delta > 1e-12,
                "negative_vs_slow": delta < -1e-12,
            }
        )
    return rows


def evaluate_mask(
    keys: list[WindowKey],
    current_final: dict[WindowKey, dict[str, Any]],
    clipped_scores: dict[WindowKey, dict[str, float]],
    mask: int,
    true_variant: str,
    description: str,
) -> dict[str, Any]:
    final_ders = {}
    selected = []
    current_ders = []
    new_ders = []
    slow_ders = {}
    choices: Counter[str] = Counter()
    overlay_wins = 0
    overlay_losses = 0
    for idx, key in enumerate(keys):
        use_overlay = bool((mask >> idx) & 1)
        current_der = as_float(current_final[key]["final_der"], default=float("nan"))
        new_der = clipped_scores[key][true_variant] if use_overlay else current_der
        slow_der = clipped_scores[key]["slow_base"]
        final_ders[key] = new_der
        slow_ders[key] = slow_der
        current_ders.append(current_der)
        new_ders.append(new_der)
        choices[true_variant if use_overlay else "current_final"] += 1
        if use_overlay:
            overlay_wins += int(new_der < current_der)
            overlay_losses += int(new_der > current_der)
            selected.append(
                {
                    "window_id": window_id(key),
                    "recording_id": key[0],
                    "current_der": current_der,
                    "overlay_der": new_der,
                    "delta_vs_current_pp": (current_der - new_der) * 100,
                }
            )
    per_recording = recording_summary(keys, final_ders, slow_ders)
    current_mean = average(current_ders)
    new_mean = average(new_ders)
    slow_mean = average(list(slow_ders.values()))
    positive_recordings = sum(1 for row in per_recording if row["beats_slow"])
    negative_recordings = sum(1 for row in per_recording if row["negative_vs_slow"])
    return {
        "policy_kind": "recording_balanced_overlay",
        "policy_id": f"if_{description.replace(' ', '_')}_then_{true_variant}_else_current_final",
        "description": description,
        "true_variant": true_variant,
        "windows": len(keys),
        "selected_windows": len(selected),
        "overlay_wins_vs_current": overlay_wins,
        "overlay_losses_vs_current": overlay_losses,
        "current_final_der": current_mean,
        "final_der": new_mean,
        "clipped_slow_der": slow_mean,
        "delta_vs_current": current_mean - new_mean,
        "delta_vs_current_pp": (current_mean - new_mean) * 100,
        "delta_vs_clipped_slow": slow_mean - new_mean,
        "delta_vs_clipped_slow_pp": (slow_mean - new_mean) * 100,
        "positive_recordings_vs_clipped_slow": positive_recordings,
        "negative_recordings_vs_clipped_slow": negative_recordings,
        "choice_counts": dict(choices),
        "selected_window_details": selected,
        "per_recording": per_recording,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    best = payload["best_policy"]
    current = payload["current_policy"]
    lines = [
        "# Recording-Balanced Overlay Search",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Current positive recordings: `{current['positive_recordings_vs_clipped_slow']}/{payload['recordings']}`",
        f"- Best positive recordings: `{best['positive_recordings_vs_clipped_slow']}/{payload['recordings']}`",
        f"- Best policy: `{best['policy_id']}`",
        f"- Best final DER: `{best['final_der']:.2%}`",
        f"- Delta vs current final: `{best['delta_vs_current_pp']:.3f}pp`",
        f"- Negative recordings vs clipped Slow: `{best['negative_recordings_vs_clipped_slow']}`",
        "",
        "## Top Policies",
        "",
        "| Rank | Policy | Final DER | Delta vs current | Positive recs | Negative recs | Selected | Wins/Losses |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(payload["top_policies"], start=1):
        lines.append(
            f"| {idx} | `{row['policy_id']}` | {row['final_der']:.2%} | {row['delta_vs_current_pp']:.3f}pp | "
            f"{row['positive_recordings_vs_clipped_slow']} | {row['negative_recordings_vs_clipped_slow']} | "
            f"{row['selected_windows']} | {row['overlay_wins_vs_current']}/{row['overlay_losses_vs_current']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This search optimizes recording-level stability over the current final runtime output.",
            "- DER is used only after runtime-safe condition materialization for offline ranking.",
            "- A deployable candidate must improve the recording-positive count without hurting the current final DER or creating negative recordings.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/window_metrics.csv"))
    parser.add_argument("--clipped-baseline-scores", type=Path, default=Path("outputs/clipped_baseline_audit/clipped_baseline_scores.csv"))
    parser.add_argument("--window-features", type=Path, default=Path("outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv"))
    parser.add_argument("--gate-decisions", type=Path, default=Path("outputs/writeback_gate_120/gate_decisions.csv"))
    parser.add_argument("--audio-features", type=Path, default=Path("outputs/audio_window_features/audio_window_features_120.csv"))
    parser.add_argument("--max-thresholds", type=int, default=80)
    parser.add_argument("--min-selected-windows", type=int, default=1)
    parser.add_argument("--max-selected-windows", type=int, default=12)
    parser.add_argument("--previous-window-context", action="store_true", help="Add deployable prev_* features from the previous completed window in the same recording.")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/recording_balanced_overlay_search"))
    args = parser.parse_args()

    current_final = load_final(args.window_metrics)
    clipped_scores = load_clipped_scores(args.clipped_baseline_scores)
    features = load_features(args.window_features, args.gate_decisions, args.audio_features)
    if args.previous_window_context:
        add_previous_window_context(features)
    keys = sorted(
        key
        for key in current_final
        if key in clipped_scores
        and key in features
        and {"slow_base", *TRUE_VARIANTS}.issubset(clipped_scores[key])
    )
    current_policy = evaluate_mask(keys, current_final, clipped_scores, 0, "slow_base", "never")
    atoms = build_atomic_conditions(keys, features, args.max_thresholds, args.max_selected_windows)
    masks = build_candidate_masks(atoms, args.max_selected_windows)
    rows = []
    for mask, meta in masks.items():
        if int(meta["selected"]) < args.min_selected_windows:
            continue
        for variant in TRUE_VARIANTS:
            row = evaluate_mask(keys, current_final, clipped_scores, int(mask), variant, meta["description"])
            row.update({key: value for key, value in meta.items() if key != "mask"})
            if row["delta_vs_clipped_slow"] > 0:
                rows.append(row)
    rows.sort(
        key=lambda row: (
            -row["positive_recordings_vs_clipped_slow"],
            row["negative_recordings_vs_clipped_slow"],
            -row["delta_vs_current"],
            row["final_der"],
            row["overlay_losses_vs_current"],
            row["policy_id"],
        )
    )
    if not rows:
        raise SystemExit("No positive recording-balanced overlay policies found")
    best = rows[0]
    current_positive = current_policy["positive_recordings_vs_clipped_slow"]
    deployable = (
        best["positive_recordings_vs_clipped_slow"] > current_positive
        and best["negative_recordings_vs_clipped_slow"] == 0
        and best["delta_vs_current"] >= 0
    )
    status = "deployable_recording_balanced_candidate_found" if deployable else "no_deployable_recording_balanced_candidate_found"
    payload = {
        "runtime_contract": "recording_balanced_overlay_search_no_live_calls_runtime_features_only",
        "status": status,
        "windows": len(keys),
        "recordings": len({key[0] for key in keys}),
        "current_positive_recordings": current_policy["positive_recordings_vs_clipped_slow"],
        "best_positive_recordings": best["positive_recordings_vs_clipped_slow"],
        "best_negative_recordings": best["negative_recordings_vs_clipped_slow"],
        "best_delta_vs_current_pp": best["delta_vs_current_pp"],
        "best_selected_windows": best["selected_windows"],
        "current_policy": current_policy,
        "best_policy": best,
        "top_policies": rows[: args.top_n],
        "candidate_policies": len(rows),
        "feature_context": "current_plus_previous_window" if args.previous_window_context else "current_window_only",
        "metric_claim_boundary": "development_pool_search_not_true_heldout",
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "recording_balanced_overlay_search.json"
    md_path = args.output_dir / "recording_balanced_overlay_search.md"
    csv_path = args.output_dir / "recording_balanced_overlay_search.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    flat_rows = []
    for row in rows[: max(args.top_n, 100)]:
        flat_rows.append({key: value for key, value in row.items() if key not in {"selected_window_details", "per_recording"}})
    write_csv(csv_path, flat_rows)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    print(
        "status={status} best_positive={best_pos}/{recs} current_positive={current_pos}/{recs} delta={delta:.3f}pp negatives={neg}".format(
            status=status,
            best_pos=best["positive_recordings_vs_clipped_slow"],
            current_pos=current_positive,
            recs=payload["recordings"],
            delta=best["delta_vs_current_pp"],
            neg=best["negative_recordings_vs_clipped_slow"],
        )
    )


if __name__ == "__main__":
    main()
