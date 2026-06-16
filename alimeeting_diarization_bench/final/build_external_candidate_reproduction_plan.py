#!/usr/bin/env python3
"""Build a reproduction plan for the best external candidate source.

The external candidate search may find a promising source that is not yet
usable as a default runtime candidate because it only covers part of the current
120-window development pool. This script turns that gap into a concrete,
resume-safe run plan and missing-window manifest. It performs no inference.
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
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alimeeting_diarization_bench.data.manifests import generate_stratified_segments, load_manifests


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def key_from_result(row: dict[str, Any]) -> tuple[str, int, int] | None:
    if row.get("recording_id") is not None and row.get("window_size") is not None and row.get("segment_idx") is not None:
        return (str(row["recording_id"]), int(row["window_size"]), int(row["segment_idx"]))
    key = str(row.get("key", ""))
    parts = key.split("|")
    if len(parts) >= 3 and parts[1].startswith("ws") and parts[2].startswith("seg"):
        return (parts[0], int(parts[1][2:]), int(parts[2][3:]))
    return None


def window_id(key: tuple[str, int, int]) -> str:
    return f"{key[0]}:{key[1]}:{key[2]}"


def gt_fingerprint(row: dict[str, Any]) -> str:
    return json.dumps(row.get("gt_segments", []), sort_keys=True, separators=(",", ":"))


def parse_window_id(value: str) -> tuple[str, int, int]:
    rec, ws, idx = value.split(":")
    return (rec, int(ws), int(idx))


def selected_key_metadata(window_size: int, total_samples: int, seed: int) -> dict[tuple[str, int, int], dict[str, Any]]:
    recordings, supervisions = load_manifests()
    segments = generate_stratified_segments(
        recordings,
        supervisions,
        window_size=window_size,
        total_samples=total_samples,
        seed=seed,
    )
    return {(str(seg["recording_id"]), int(seg["window_size"]), int(seg["segment_idx"])): seg for seg in segments}


def infer_run_base_dir(source_summary_path: Path) -> Path:
    # output_dir/model_name/variant/summary.json -> output_dir
    if source_summary_path.name == "summary.json" and len(source_summary_path.parents) >= 3:
        return source_summary_path.parents[2]
    return source_summary_path.parent


def command_for_resume(
    python_exe: str,
    model: str,
    output_dir: Path,
    window_size: int,
    total_samples: int,
    seed: int,
    speaker_count_mode: str,
    segments_manifest: Path | None = None,
    summary_name: str | None = None,
    results_name: str | None = None,
    force_reprocess: bool = False,
) -> list[str]:
    command = [
        python_exe,
        "-m",
        "alimeeting_diarization_bench.run",
        "--model",
        model,
        "--window-size",
        str(window_size),
        "--sampling-mode",
        "stratified",
        "--total-samples",
        str(total_samples),
        "--seed",
        str(seed),
        "--speaker-count-mode",
        speaker_count_mode,
        "--output-dir",
        str(output_dir),
    ]
    if segments_manifest is not None:
        command.extend(["--segments-manifest", str(segments_manifest)])
    if summary_name:
        command.extend(["--summary-name", summary_name])
    if results_name:
        command.extend(["--results-name", results_name])
    if force_reprocess:
        command.append("--force-reprocess")
    return command


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# External Candidate Reproduction Plan",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Source: `{summary['source_id']}`",
        f"- Source coverage: `{summary['covered_windows']}/{summary['expected_windows']}`",
        f"- Missing windows: `{summary['missing_windows']}`",
        f"- Stale checkpoint windows: `{summary['stale_checkpoint_windows']}`",
        f"- Best external-search delta: `{summary['best_delta_vs_current_pp']}` pp",
        f"- Resume supported: `{summary['resume_supported_by_checkpoint']}`",
        f"- Estimated remaining latency: `{summary['estimated_remaining_latency_sec']}` sec",
        "",
        "## Manifest Resume Command",
        "",
        "```bash",
        " ".join(payload["manifest_resume_command"]),
        "```",
        "",
        "## Full Summary Refresh Command",
        "",
        "```bash",
        " ".join(payload["full_resume_command"]),
        "```",
        "",
        "## Gates Before Default Runtime",
        "",
    ]
    for gate in payload["promotion_gates"]:
        lines.append(f"- `{gate['status']}` {gate['gate_id']}: {gate['evidence']}")
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This artifact does not run DiariZen or change default runtime metrics.",
            "- The explicit manifest command processes only missing windows and writes a separate missing-window summary.",
            "- The full summary refresh command reruns the 120-window selection and should mostly skip completed checkpoint entries, then writes `summary.json`.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-search", type=Path, default=Path("outputs/external_candidate_surface_search/external_candidate_surface_search.json"))
    parser.add_argument("--metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/metrics.json"))
    parser.add_argument("--reference-summary", type=Path, default=Path("outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json"))
    parser.add_argument("--source-summary", type=Path, default=None, help="Override best external-search source and build a repair plan for this summary.")
    parser.add_argument("--window-size", type=int, default=30)
    parser.add_argument("--total-samples", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--python-exe", default=".venv_diarizen/bin/python")
    parser.add_argument("--model", default="diarizen")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/external_candidate_reproduction_plan"))
    args = parser.parse_args()

    external = read_json(args.external_search)
    metrics = read_json(args.metrics)
    reference = read_json(args.reference_summary)
    best = external.get("best_policy", {})
    source_path = args.source_summary or Path(best.get("source_path") or "")
    if not source_path.exists():
        raise SystemExit(f"Best source summary does not exist: {source_path}")
    source = read_json(source_path)
    source_results = source.get("results", [])
    reference_gt = {
        key: gt_fingerprint(row)
        for row in reference.get("results", [])
        if isinstance(row, dict)
        for key in [key_from_result(row)]
        if key is not None
    }
    source_keys: set[tuple[str, int, int]] = set()
    valid_source_keys: set[tuple[str, int, int]] = set()
    stale_source_keys: set[tuple[str, int, int]] = set()
    for row in source_results:
        if not isinstance(row, dict) or row.get("success") is False:
            continue
        key = key_from_result(row)
        if key is None:
            continue
        source_keys.add(key)
        if reference_gt.get(key) == gt_fingerprint(row):
            valid_source_keys.add(key)
        else:
            stale_source_keys.add(key)
    selected_keys = {parse_window_id(value) for value in metrics.get("selected_window_ids", [])}
    segment_meta = selected_key_metadata(args.window_size, args.total_samples, args.seed)
    missing_keys = sorted(selected_keys - valid_source_keys)
    covered_keys = sorted(selected_keys & valid_source_keys)
    selected_policy_keys = {
        parse_window_id(row["window_id"])
        for row in best.get("selected_window_details", [])
        if isinstance(row, dict) and row.get("window_id")
    }
    missing_policy_keys = sorted(selected_policy_keys - valid_source_keys)
    source_output_base = infer_run_base_dir(source_path)
    checkpoint_path = source_path.parent / "checkpoint.json"
    checkpoint_entries = len(read_json(checkpoint_path)) if checkpoint_path.exists() else 0
    latencies = [
        float(row["latency"])
        for row in source_results
        if isinstance(row, dict) and row.get("success") is not False and row.get("latency") not in (None, "")
    ]
    avg_latency = sum(latencies) / len(latencies) if latencies else None
    estimated_remaining_latency_sec = round(avg_latency * len(missing_keys), 2) if avg_latency is not None else None

    missing_rows = []
    for key in missing_keys:
        meta = segment_meta.get(key, {})
        missing_rows.append(
            {
                "window_id": window_id(key),
                "recording_id": key[0],
                "window_size": key[1],
                "segment_idx": key[2],
                "offset": meta.get("offset"),
                "duration": meta.get("duration"),
                "audio_path": meta.get("audio_path"),
                "spk_count_gt": meta.get("spk_count_gt"),
                "needed_for_best_current_policy": key in selected_policy_keys,
                "reason": (
                    "stale_checkpoint_gt_mismatch"
                    if key in stale_source_keys
                    else "missing_from_best_external_candidate_source"
                ),
            }
        )

    csv_path = args.output_dir / "missing_external_candidate_windows.csv"
    manifest_resume_command = command_for_resume(
        python_exe=args.python_exe,
        model=args.model,
        output_dir=source_output_base,
        window_size=args.window_size,
        total_samples=args.total_samples,
        seed=args.seed,
        speaker_count_mode=str(source.get("speaker_count_mode") or "none"),
        segments_manifest=csv_path,
        summary_name="missing_external_candidate_windows_summary.json",
        results_name="missing_external_candidate_windows_results.csv",
        force_reprocess=bool(stale_source_keys & set(missing_keys)),
    )
    full_resume_command = command_for_resume(
        python_exe=args.python_exe,
        model=args.model,
        output_dir=source_output_base,
        window_size=args.window_size,
        total_samples=args.total_samples,
        seed=args.seed,
        speaker_count_mode=str(source.get("speaker_count_mode") or "none"),
    )
    full_coverage_ready = len(missing_keys) == 0 and len(covered_keys) == len(selected_keys)
    best_meaningful = bool(best.get("meaningful_delta")) and float(best.get("delta_vs_current_pp", 0.0)) >= 0.05
    payload = {
        "runtime_contract": "external_candidate_reproduction_plan_no_inference",
        "status": "ready_for_default_runtime_promotion_check" if full_coverage_ready else "needs_external_candidate_source_completion",
        "summary": {
            "source_id": best.get("source_id"),
            "source_path": str(source_path),
            "source_output_base": str(source_output_base),
            "expected_windows": len(selected_keys),
            "covered_windows": len(covered_keys),
            "missing_windows": len(missing_keys),
            "stale_checkpoint_windows": len(stale_source_keys & selected_keys),
            "best_policy_selected_windows": len(selected_policy_keys),
            "missing_best_policy_windows": len(missing_policy_keys),
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_exists": checkpoint_path.exists(),
            "checkpoint_entries": checkpoint_entries,
            "resume_supported_by_checkpoint": checkpoint_path.exists() and checkpoint_entries >= len(covered_keys),
            "avg_observed_latency_sec": round(avg_latency, 2) if avg_latency is not None else None,
            "estimated_remaining_latency_sec": estimated_remaining_latency_sec,
            "best_delta_vs_current_pp": best.get("delta_vs_current_pp"),
            "best_positive_recordings": best.get("positive_recordings_vs_clipped_slow"),
            "best_overlay_losses": best.get("overlay_losses_vs_current"),
            "source_full_coverage": full_coverage_ready,
        },
        "promotion_gates": [
            {
                "gate_id": "source_full_current_pool_coverage",
                "status": "pass" if full_coverage_ready else "blocked",
                "evidence": f"{len(covered_keys)}/{len(selected_keys)} windows covered",
            },
            {
                "gate_id": "best_policy_windows_available",
                "status": "pass" if not missing_policy_keys else "blocked",
                "evidence": f"{len(selected_policy_keys) - len(missing_policy_keys)}/{len(selected_policy_keys)} selected windows available",
            },
            {
                "gate_id": "meaningful_development_delta",
                "status": "pass" if best_meaningful else "blocked",
                "evidence": f"{best.get('delta_vs_current_pp')}pp vs minimum 0.05pp",
            },
            {
                "gate_id": "zero_overlay_losses",
                "status": "pass" if int(best.get("overlay_losses_vs_current", 999)) == 0 else "blocked",
                "evidence": str(best.get("overlay_losses_vs_current")),
            },
            {
                "gate_id": "zero_negative_recordings",
                "status": "pass" if int(best.get("negative_recordings_vs_clipped_slow", 999)) == 0 else "blocked",
                "evidence": str(best.get("negative_recordings_vs_clipped_slow")),
            },
        ],
        "manifest_resume_command": manifest_resume_command,
        "full_resume_command": full_resume_command,
        "resume_command": full_resume_command,
        "missing_window_manifest": str(csv_path),
        "inputs": {
            "external_search": str(args.external_search),
            "metrics": str(args.metrics),
            "reference_summary": str(args.reference_summary),
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "external_candidate_reproduction_plan.json"
    md_path = args.output_dir / "external_candidate_reproduction_plan.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    write_csv(
        csv_path,
        missing_rows,
        [
            "window_id",
            "recording_id",
            "window_size",
            "segment_idx",
            "offset",
            "duration",
            "audio_path",
            "spk_count_gt",
            "needed_for_best_current_policy",
            "reason",
        ],
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    print(
        "status={status} covered={covered}/{expected} missing={missing} resume={resume}".format(
            status=payload["status"],
            covered=payload["summary"]["covered_windows"],
            expected=payload["summary"]["expected_windows"],
            missing=payload["summary"]["missing_windows"],
            resume=payload["summary"]["resume_supported_by_checkpoint"],
        )
    )


if __name__ == "__main__":
    main()
