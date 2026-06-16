#!/usr/bin/env python3
"""Inventory historical summary outputs as GT-filtered candidate sources.

This is an analysis-only audit. It scans existing `summary.json` files, checks
whether each same-key result matches the current runtime window via GT
fingerprint, and reports how much usable coverage remains for the current
120-window pool and for recording-level blocker recordings.
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
from collections import defaultdict
from pathlib import Path
from typing import Any

from .search_external_candidate_surfaces import gt_fingerprint, key_from_summary_result, source_id
from .search_system_selector_policies import WindowKey, as_float, key_from_row


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def average(values: list[float]) -> float | None:
    values = [value for value in values if value == value]
    return sum(values) / len(values) if values else None


def window_id(key: WindowKey) -> str:
    return f"{key[0]}:{key[1]}:{key[2]}"


def load_current_final(path: Path) -> dict[WindowKey, dict[str, Any]]:
    out = {}
    for row in read_csv(path):
        key = key_from_row(row)
        out[key] = {
            "window_id": row.get("window_id") or window_id(key),
            "recording_id": key[0],
            "final_der": as_float(row.get("final_der"), default=float("nan")),
            "final_source": row.get("final_source", ""),
        }
    return out


def load_reference_gt(path: Path) -> dict[WindowKey, str]:
    payload = read_json(path)
    return {
        key: gt_fingerprint(row)
        for row in payload.get("results", [])
        if isinstance(row, dict)
        for key in [key_from_summary_result(row)]
        if key is not None
    }


def load_non_positive_recordings(path: Path) -> set[str]:
    payload = read_json(path)
    rows = payload.get("non_positive_recordings", [])
    return {str(row.get("recording_id")) for row in rows if row.get("recording_id")}


def scan_source(
    path: Path,
    allowed_keys: set[WindowKey],
    reference_gt: dict[WindowKey, str],
    current_final: dict[WindowKey, dict[str, Any]],
    non_positive_recordings: set[str],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError):
        return None, []
    results = payload.get("results", [])
    if not isinstance(results, list):
        return None, []

    valid_rows = []
    stale_rows = []
    matching_success = 0
    valid_by_recording: dict[str, int] = defaultdict(int)
    stale_by_recording: dict[str, int] = defaultdict(int)
    deltas = []
    non_positive_deltas = []
    non_positive_valid = 0
    wins = losses = ties = 0

    for row in results:
        if not isinstance(row, dict) or row.get("success") is False:
            continue
        key = key_from_summary_result(row)
        der = as_float(row.get("der"), default=float("nan"))
        if key not in allowed_keys or not math.isfinite(der):
            continue
        matching_success += 1
        if reference_gt.get(key) != gt_fingerprint(row):
            stale_by_recording[key[0]] += 1
            stale_rows.append(
                {
                    "source_path": str(path),
                    "recording_id": key[0],
                    "window_id": window_id(key),
                    "reason": "gt_fingerprint_mismatch",
                }
            )
            continue
        current_der = as_float(current_final[key]["final_der"], default=float("nan"))
        delta_pp = (current_der - der) * 100
        deltas.append(delta_pp)
        valid_by_recording[key[0]] += 1
        wins += int(der < current_der)
        losses += int(der > current_der)
        ties += int(abs(der - current_der) <= 1e-12)
        if key[0] in non_positive_recordings:
            non_positive_valid += 1
            non_positive_deltas.append(delta_pp)
        valid_rows.append(
            {
                "source_path": str(path),
                "recording_id": key[0],
                "window_id": window_id(key),
                "candidate_der": der,
                "current_der": current_der,
                "delta_vs_current_pp": delta_pp,
                "pred_segments": len(row.get("pred_segments", [])) if isinstance(row.get("pred_segments"), list) else None,
            }
        )

    if matching_success == 0:
        return None, stale_rows

    sid = source_id(path, payload)
    summary = {
        "source_id": sid,
        "source_path": str(path),
        "model_name": payload.get("model_name"),
        "speaker_count_mode": payload.get("speaker_count_mode"),
        "matching_success_windows": matching_success,
        "valid_windows": len(valid_rows),
        "stale_gt_mismatch_windows": len(stale_rows),
        "missing_windows": max(0, len(allowed_keys) - len(valid_rows)),
        "valid_coverage_ratio": len(valid_rows) / len(allowed_keys) if allowed_keys else 0.0,
        "valid_recordings": len(valid_by_recording),
        "stale_recordings": len(stale_by_recording),
        "non_positive_valid_windows": non_positive_valid,
        "wins_vs_current": wins,
        "losses_vs_current": losses,
        "ties_vs_current": ties,
        "mean_delta_vs_current_pp": average(deltas),
        "positive_delta_windows": sum(1 for value in deltas if value > 0),
        "negative_delta_windows": sum(1 for value in deltas if value < 0),
        "non_positive_mean_delta_vs_current_pp": average(non_positive_deltas),
        "non_positive_positive_delta_windows": sum(1 for value in non_positive_deltas if value > 0),
        "valid_by_recording": dict(sorted(valid_by_recording.items())),
        "stale_by_recording": dict(sorted(stale_by_recording.items())),
    }
    return summary, stale_rows


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# External Candidate Source Inventory",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Sources scanned: `{payload['summary']['sources_scanned']}`",
        f"- Sources with valid windows: `{payload['summary']['sources_with_valid_windows']}`",
        f"- Full-coverage clean sources: `{payload['summary']['full_coverage_clean_sources']}`",
        f"- Sources with stale GT mismatch: `{payload['summary']['sources_with_stale_gt_mismatch']}`",
        f"- Non-positive recordings: `{', '.join(payload['non_positive_recordings'])}`",
        "",
        "## Top Sources",
        "",
        "| Source | Valid | Stale | Missing | Wins/Losses | Mean Delta | Non-positive Delta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["top_sources"]:
        lines.append(
            "| `{source_path}` | {valid_windows} | {stale_gt_mismatch_windows} | {missing_windows} | "
            "{wins_vs_current}/{losses_vs_current} | {mean_delta:.4f}pp | {np_delta:.4f}pp |".format(
                source_path=row["source_path"],
                valid_windows=row["valid_windows"],
                stale_gt_mismatch_windows=row["stale_gt_mismatch_windows"],
                missing_windows=row["missing_windows"],
                wins_vs_current=row["wins_vs_current"],
                losses_vs_current=row["losses_vs_current"],
                mean_delta=as_float(row.get("mean_delta_vs_current_pp")),
                np_delta=as_float(row.get("non_positive_mean_delta_vs_current_pp")),
            )
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Valid windows match the current runtime pool by recording/window key and GT fingerprint.",
            "- Stale windows share a key but belong to a different sampled segment; they must not be used for promotion or policy search.",
            "- Sources with weak non-positive-recording delta are poor candidates for improving recording-level robustness.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-root", type=Path, default=Path("outputs"))
    parser.add_argument("--window-metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/window_metrics.csv"))
    parser.add_argument("--reference-summary", type=Path, default=Path("outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json"))
    parser.add_argument("--recording-stability-blockers", type=Path, default=Path("outputs/recording_stability_blockers/recording_stability_blockers.json"))
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/external_candidate_source_inventory"))
    args = parser.parse_args()

    current_final = load_current_final(args.window_metrics)
    reference_gt = load_reference_gt(args.reference_summary)
    allowed_keys = set(current_final) & set(reference_gt)
    non_positive_recordings = load_non_positive_recordings(args.recording_stability_blockers)

    source_rows = []
    stale_rows = []
    scanned = 0
    for path in sorted(args.scan_root.rglob("summary.json")):
        scanned += 1
        summary, stale = scan_source(path, allowed_keys, reference_gt, current_final, non_positive_recordings)
        stale_rows.extend(stale)
        if summary is not None:
            source_rows.append(summary)

    source_rows.sort(
        key=lambda row: (
            -row["valid_windows"],
            row["stale_gt_mismatch_windows"],
            -as_float(row.get("non_positive_mean_delta_vs_current_pp")),
            -as_float(row.get("mean_delta_vs_current_pp")),
            row["source_path"],
        )
    )
    full_clean = [
        row
        for row in source_rows
        if row["valid_windows"] == len(allowed_keys) and row["stale_gt_mismatch_windows"] == 0
    ]
    payload = {
        "runtime_contract": "external_candidate_source_inventory_no_live_calls_gt_fingerprint_filtered",
        "status": "pass",
        "window_metrics": str(args.window_metrics),
        "reference_summary": str(args.reference_summary),
        "recording_stability_blockers": str(args.recording_stability_blockers),
        "non_positive_recordings": sorted(non_positive_recordings),
        "summary": {
            "runtime_windows": len(allowed_keys),
            "sources_scanned": scanned,
            "sources_with_matching_windows": len(source_rows),
            "sources_with_valid_windows": sum(1 for row in source_rows if row["valid_windows"] > 0),
            "full_coverage_clean_sources": len(full_clean),
            "sources_with_stale_gt_mismatch": sum(1 for row in source_rows if row["stale_gt_mismatch_windows"] > 0),
            "stale_gt_mismatch_windows": sum(row["stale_gt_mismatch_windows"] for row in source_rows),
        },
        "top_sources": source_rows[: args.top_n],
        "full_coverage_clean_sources": full_clean,
        "metric_claim_boundary": "source_inventory_only_not_runtime_policy_not_true_heldout",
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "external_candidate_source_inventory.json"
    md_path = args.output_dir / "external_candidate_source_inventory.md"
    csv_path = args.output_dir / "external_candidate_source_inventory.csv"
    stale_csv_path = args.output_dir / "external_candidate_source_stale_windows.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    write_csv(csv_path, source_rows)
    write_csv(stale_csv_path, stale_rows)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {stale_csv_path}")
    print(
        "status={status} sources={sources} full_clean={full_clean} stale_sources={stale_sources} stale_windows={stale_windows}".format(
            status=payload["status"],
            sources=payload["summary"]["sources_with_matching_windows"],
            full_clean=payload["summary"]["full_coverage_clean_sources"],
            stale_sources=payload["summary"]["sources_with_stale_gt_mismatch"],
            stale_windows=payload["summary"]["stale_gt_mismatch_windows"],
        )
    )


if __name__ == "__main__":
    main()
