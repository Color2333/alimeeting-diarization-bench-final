#!/usr/bin/env python3
"""Search external historical summary outputs as new candidate surfaces.

This is an offline development-pool search. It scans existing `summary.json`
artifacts, treats each model/run as an optional candidate timeline source, and
tests runtime-feature conditions for when that source should replace the current
final window. DER is used only after feature-policy materialization.
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
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .search_recording_balanced_overlays import (
    add_previous_window_context,
    average,
    build_atomic_conditions,
    build_candidate_masks,
    load_clipped_scores,
    load_final,
    recording_summary,
    window_id,
    write_csv,
)
from .search_system_selector_policies import WindowKey, as_float, load_features


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def key_from_summary_result(row: dict[str, Any]) -> WindowKey | None:
    if row.get("recording_id") is not None and row.get("window_size") is not None and row.get("segment_idx") is not None:
        return (str(row["recording_id"]), int(row["window_size"]), int(row["segment_idx"]))
    key = str(row.get("key", ""))
    parts = key.split("|")
    if len(parts) >= 3 and parts[1].startswith("ws") and parts[2].startswith("seg"):
        try:
            return (parts[0], int(parts[1][2:]), int(parts[2][3:]))
        except ValueError:
            return None
    return None


def gt_fingerprint(row: dict[str, Any]) -> str:
    return json.dumps(row.get("gt_segments", []), sort_keys=True, separators=(",", ":"))


def source_id(path: Path, payload: dict[str, Any]) -> str:
    root = path.parent.parent.name
    model = payload.get("model_name") or path.parent.name
    mode = payload.get("speaker_count_mode")
    mode_part = f"spk_{mode}" if mode not in (None, "") else "spk_unknown"
    return f"{root}/{model}/{mode_part}"


def load_candidate_sources(
    scan_root: Path,
    allowed_keys: set[WindowKey],
    reference_gt: dict[WindowKey, str],
    excluded_speaker_count_modes: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    excluded_speaker_count_modes = excluded_speaker_count_modes or set()
    sources: dict[str, dict[str, Any]] = {}
    for path in sorted(scan_root.rglob("summary.json")):
        try:
            payload = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            continue
        speaker_count_mode = str(payload.get("speaker_count_mode") or "")
        if speaker_count_mode in excluded_speaker_count_modes:
            continue
        scores: dict[WindowKey, dict[str, Any]] = {}
        stale_gt_mismatch = 0
        for row in payload["results"]:
            if not isinstance(row, dict) or row.get("success") is False:
                continue
            key = key_from_summary_result(row)
            der = as_float(row.get("der"), default=float("nan"))
            if key not in allowed_keys or not math.isfinite(der):
                continue
            if reference_gt.get(key) != gt_fingerprint(row):
                stale_gt_mismatch += 1
                continue
            scores[key] = {
                "der": der,
                "miss_rate": as_float(row.get("miss_rate"), default=float("nan")),
                "fa_rate": as_float(row.get("fa_rate"), default=float("nan")),
                "conf_rate": as_float(row.get("conf_rate"), default=float("nan")),
                "pred_segments": len(row.get("pred_segments", [])) if isinstance(row.get("pred_segments"), list) else None,
                "latency": as_float(row.get("latency"), default=float("nan")),
            }
        if not scores:
            continue
        sid = source_id(path, payload)
        # Keep same-label runs separate when they come from different experiment roots.
        unique_id = sid if sid not in sources else f"{sid}::{path.parent}"
        sources[unique_id] = {
            "source_id": unique_id,
            "path": str(path),
            "model_name": payload.get("model_name"),
            "speaker_count_mode": payload.get("speaker_count_mode"),
            "coverage_windows": len(scores),
            "stale_gt_mismatch_windows": stale_gt_mismatch,
            "scores": scores,
        }
    return sources


def evaluate_external_policy(
    keys: list[WindowKey],
    current_final: dict[WindowKey, dict[str, Any]],
    slow_scores: dict[WindowKey, float],
    source: dict[str, Any],
    mask: int,
    description: str,
) -> dict[str, Any]:
    candidate_scores: dict[WindowKey, dict[str, Any]] = source["scores"]
    final_ders = {}
    slow_ders = {}
    current_ders = []
    new_ders = []
    selected = []
    choices: Counter[str] = Counter()
    overlay_wins = 0
    overlay_losses = 0
    for idx, key in enumerate(keys):
        current_der = as_float(current_final[key]["final_der"], default=float("nan"))
        use_candidate = bool((mask >> idx) & 1) and key in candidate_scores
        new_der = candidate_scores[key]["der"] if use_candidate else current_der
        final_ders[key] = new_der
        slow_ders[key] = slow_scores[key]
        current_ders.append(current_der)
        new_ders.append(new_der)
        choices[source["source_id"] if use_candidate else "current_final"] += 1
        if use_candidate:
            delta_pp = (current_der - new_der) * 100
            overlay_wins += int(new_der < current_der)
            overlay_losses += int(new_der > current_der)
            selected.append(
                {
                    "window_id": window_id(key),
                    "recording_id": key[0],
                    "current_der": current_der,
                    "candidate_der": new_der,
                    "delta_vs_current_pp": delta_pp,
                    "candidate_pred_segments": candidate_scores[key].get("pred_segments"),
                    "candidate_latency": candidate_scores[key].get("latency"),
                }
            )
    per_recording = recording_summary(keys, final_ders, slow_ders)
    return {
        "policy_kind": "external_candidate_surface_overlay",
        "policy_id": f"if_{description.replace(' ', '_')}_then_{source['source_id'].replace('/', '__')}_else_current_final",
        "description": description,
        "source_id": source["source_id"],
        "source_path": source["path"],
        "source_coverage_windows": source["coverage_windows"],
        "windows": len(keys),
        "selected_windows": len(selected),
        "overlay_wins_vs_current": overlay_wins,
        "overlay_losses_vs_current": overlay_losses,
        "current_final_der": average(current_ders),
        "final_der": average(new_ders),
        "clipped_slow_der": average(list(slow_ders.values())),
        "delta_vs_current": average(current_ders) - average(new_ders),
        "delta_vs_current_pp": (average(current_ders) - average(new_ders)) * 100,
        "delta_vs_clipped_slow_pp": (average(list(slow_ders.values())) - average(new_ders)) * 100,
        "positive_recordings_vs_clipped_slow": sum(1 for row in per_recording if row["beats_slow"]),
        "negative_recordings_vs_clipped_slow": sum(1 for row in per_recording if row["negative_vs_slow"]),
        "choice_counts": dict(choices),
        "selected_window_details": selected,
        "per_recording": per_recording,
    }


def oracle_summary(
    keys: list[WindowKey],
    current_final: dict[WindowKey, dict[str, Any]],
    slow_scores: dict[WindowKey, float],
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    final_ders = {}
    slow_ders = {}
    selected = []
    for key in keys:
        current_der = as_float(current_final[key]["final_der"], default=float("nan"))
        best_source = "current_final"
        best_der = current_der
        for source in sources.values():
            score = source["scores"].get(key)
            if score and score["der"] < best_der:
                best_der = score["der"]
                best_source = source["source_id"]
        final_ders[key] = best_der
        slow_ders[key] = slow_scores[key]
        if best_source != "current_final":
            selected.append(
                {
                    "window_id": window_id(key),
                    "recording_id": key[0],
                    "source_id": best_source,
                    "current_der": current_der,
                    "oracle_der": best_der,
                    "delta_vs_current_pp": (current_der - best_der) * 100,
                }
            )
    per_recording = recording_summary(keys, final_ders, slow_ders)
    current_mean = average([as_float(current_final[key]["final_der"], default=float("nan")) for key in keys])
    oracle_mean = average(list(final_ders.values()))
    return {
        "oracle_der": oracle_mean,
        "current_final_der": current_mean,
        "oracle_gain_vs_current_pp": (current_mean - oracle_mean) * 100,
        "selected_windows": len(selected),
        "positive_recordings_vs_clipped_slow": sum(1 for row in per_recording if row["beats_slow"]),
        "negative_recordings_vs_clipped_slow": sum(1 for row in per_recording if row["negative_vs_slow"]),
        "selected_window_details": sorted(selected, key=lambda row: -row["delta_vs_current_pp"])[:30],
        "per_recording": per_recording,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    best = payload["best_policy"]
    oracle = payload["external_candidate_oracle"]
    lines = [
        "# External Candidate Surface Search",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Candidate sources: `{payload['candidate_sources']}`",
        f"- Eval-only oracle sources excluded: `{payload['eval_only_oracle_sources_excluded']}`",
        f"- Current positive recordings: `{payload['current_positive_recordings']}/{payload['recordings']}`",
        f"- Oracle positive recordings: `{oracle['positive_recordings_vs_clipped_slow']}/{payload['recordings']}`",
        f"- Oracle gain vs current: `{oracle['oracle_gain_vs_current_pp']:.3f}pp`",
        f"- Best policy: `{best.get('policy_id')}`",
        f"- Best final DER: `{best.get('final_der', 0.0):.2%}`",
        f"- Best delta vs current: `{best.get('delta_vs_current_pp', 0.0):.3f}pp`",
        f"- Best positive recordings: `{best.get('positive_recordings_vs_clipped_slow')}/{payload['recordings']}`",
        f"- Negative recordings: `{best.get('negative_recordings_vs_clipped_slow')}`",
        "",
        "## Top Policies",
        "",
        "| Rank | Policy | Source coverage | Selected | Wins/Losses | Final DER | Delta | Positive recs | Negative recs |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(payload["top_policies"], start=1):
        lines.append(
            f"| {idx} | `{row['policy_id']}` | {row['source_coverage_windows']} | {row['selected_windows']} | "
            f"{row['overlay_wins_vs_current']}/{row['overlay_losses_vs_current']} | {row['final_der']:.2%} | "
            f"{row['delta_vs_current_pp']:.3f}pp | {row['positive_recordings_vs_clipped_slow']} | "
            f"{row['negative_recordings_vs_clipped_slow']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This artifact searches new candidate surfaces from existing historical model outputs.",
            "- A deployable policy must improve current DER, improve recording-level positive count, and introduce no negative overlay windows or negative recordings.",
            "- External candidates with partial coverage are analysis surfaces until the candidate source can be reproduced for the full runtime path.",
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
    parser.add_argument("--reference-summary", type=Path, default=Path("outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json"))
    parser.add_argument("--scan-root", type=Path, default=Path("outputs"))
    parser.add_argument("--max-thresholds", type=int, default=80)
    parser.add_argument("--max-selected-windows", type=int, default=12)
    parser.add_argument("--min-deployable-delta-pp", type=float, default=0.05)
    parser.add_argument(
        "--include-oracle-sources",
        action="store_true",
        help="Include speaker_count_mode=oracle summaries in deployability search. Default excludes them as eval-only upper bounds.",
    )
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/external_candidate_surface_search"))
    args = parser.parse_args()

    current_final = load_final(args.window_metrics)
    clipped_scores = load_clipped_scores(args.clipped_baseline_scores)
    reference = read_json(args.reference_summary)
    reference_gt = {
        key: gt_fingerprint(row)
        for row in reference.get("results", [])
        if isinstance(row, dict)
        for key in [key_from_summary_result(row)]
        if key is not None
    }
    features = load_features(args.window_features, args.gate_decisions, args.audio_features)
    add_previous_window_context(features)
    keys = sorted(key for key in current_final if key in clipped_scores and key in features and "slow_base" in clipped_scores[key])
    slow_scores = {key: clipped_scores[key]["slow_base"] for key in keys}
    current_recordings = recording_summary(
        keys,
        {key: as_float(current_final[key]["final_der"], default=float("nan")) for key in keys},
        slow_scores,
    )
    current_positive = sum(1 for row in current_recordings if row["beats_slow"])
    eval_only_oracle_sources = load_candidate_sources(
        args.scan_root,
        set(keys),
        reference_gt,
        excluded_speaker_count_modes=set(),
    )
    eval_only_oracle_source_count = sum(
        1
        for source in eval_only_oracle_sources.values()
        if source.get("speaker_count_mode") == "oracle"
    )
    excluded_modes = set() if args.include_oracle_sources else {"oracle"}
    sources = load_candidate_sources(args.scan_root, set(keys), reference_gt, excluded_modes)
    oracle = oracle_summary(keys, current_final, slow_scores, sources)

    rows: list[dict[str, Any]] = []
    for source in sources.values():
        source_keys = sorted(key for key in source["scores"] if key in features)
        if not source_keys:
            continue
        atoms = build_atomic_conditions(source_keys, features, args.max_thresholds, args.max_selected_windows)
        masks = build_candidate_masks(atoms, args.max_selected_windows)
        for mask, meta in masks.items():
            row = evaluate_external_policy(keys, current_final, slow_scores, source, int(mask), meta["description"])
            if row["selected_windows"] <= 0 or row["selected_windows"] > args.max_selected_windows:
                continue
            if row["delta_vs_current"] <= 0:
                continue
            row["source_stale_gt_mismatch_windows"] = source.get("stale_gt_mismatch_windows", 0)
            row.update({k: v for k, v in meta.items() if k != "mask"})
            row["source_full_coverage"] = row["source_coverage_windows"] == len(keys)
            row["meaningful_delta"] = row["delta_vs_current_pp"] >= args.min_deployable_delta_pp
            row["improves_positive_recordings"] = row["positive_recordings_vs_clipped_slow"] > current_positive
            rows.append(row)

    rows.sort(
        key=lambda row: (
            not (row["improves_positive_recordings"] and row["meaningful_delta"]),
            row["negative_recordings_vs_clipped_slow"],
            row["overlay_losses_vs_current"],
            not row["source_full_coverage"],
            -row["positive_recordings_vs_clipped_slow"],
            -row["delta_vs_current"],
            row["final_der"],
            row["policy_id"],
        )
    )
    if rows:
        best = rows[0]
    else:
        best = {
            "policy_id": None,
            "final_der": average([as_float(current_final[key]["final_der"], default=float("nan")) for key in keys]),
            "delta_vs_current_pp": 0.0,
            "positive_recordings_vs_clipped_slow": current_positive,
            "negative_recordings_vs_clipped_slow": 0,
            "selected_windows": 0,
            "overlay_losses_vs_current": 0,
        }
    deployable = bool(rows) and (
        best["source_full_coverage"]
        and best["meaningful_delta"]
        and best["improves_positive_recordings"]
        and best["negative_recordings_vs_clipped_slow"] == 0
        and best["overlay_losses_vs_current"] == 0
        and best["delta_vs_current"] > 0
    )
    promising = bool(rows) and (
        best["meaningful_delta"]
        and best["improves_positive_recordings"]
        and best["positive_recordings_vs_clipped_slow"] > current_positive
        and best["negative_recordings_vs_clipped_slow"] == 0
        and best["overlay_losses_vs_current"] == 0
        and best["delta_vs_current"] > 0
    )
    if deployable:
        status = "deployable_external_candidate_surface_found"
    elif promising:
        status = "promising_external_candidate_surface_found_not_default_runtime"
    else:
        status = "external_candidate_surface_not_deployable"
    payload = {
        "runtime_contract": "external_candidate_surface_search_no_live_calls_runtime_features_only",
        "status": status,
        "windows": len(keys),
        "recordings": len({key[0] for key in keys}),
        "candidate_sources": len(sources),
        "eval_only_oracle_sources_excluded": 0
        if args.include_oracle_sources
        else eval_only_oracle_source_count,
        "current_positive_recordings": current_positive,
        "external_candidate_oracle": oracle,
        "best_policy": best,
        "top_policies": rows[: args.top_n],
        "candidate_policies": len(rows),
        "deployability_gates": {
            "min_deployable_delta_pp": args.min_deployable_delta_pp,
            "requires_source_full_coverage": True,
            "requires_positive_recording_gain": True,
            "requires_zero_overlay_losses": True,
            "requires_zero_negative_recordings": True,
            "deployable": deployable,
            "promising_not_default_runtime": promising and not deployable,
        },
        "metric_claim_boundary": "development_pool_candidate_surface_search_not_default_runtime",
        "inputs": {
            "window_metrics": str(args.window_metrics),
            "clipped_baseline_scores": str(args.clipped_baseline_scores),
            "window_features": str(args.window_features),
            "gate_decisions": str(args.gate_decisions),
            "audio_features": str(args.audio_features),
            "reference_summary": str(args.reference_summary),
            "scan_root": str(args.scan_root),
            "include_oracle_sources": args.include_oracle_sources,
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "external_candidate_surface_search.json"
    md_path = args.output_dir / "external_candidate_surface_search.md"
    csv_path = args.output_dir / "external_candidate_surface_search.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    flat = [{k: v for k, v in row.items() if k not in {"selected_window_details", "per_recording"}} for row in rows[: max(args.top_n, 100)]]
    write_csv(csv_path, flat)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    print(
        "status={status} sources={sources} policies={policies} best_positive={best_pos}/{recs} "
        "current_positive={current_pos}/{recs} delta={delta:.3f}pp losses={losses}".format(
            status=status,
            sources=len(sources),
            policies=len(rows),
            best_pos=best.get("positive_recordings_vs_clipped_slow"),
            current_pos=current_positive,
            recs=payload["recordings"],
            delta=best.get("delta_vs_current_pp", 0.0),
            losses=best.get("overlay_losses_vs_current", 0),
        )
    )


if __name__ == "__main__":
    main()
