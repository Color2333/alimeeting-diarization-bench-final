#!/usr/bin/env python3
"""Run the offline realtime diarization system over a recording manifest.

This is a batch orchestration layer. It does not run acoustic models or live
LLM/API calls; each item delegates to the final realtime system module and then
optionally checks the generated final timeline.
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
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SYSTEM_MODULE = "alimeeting_diarization_bench.final.realtime_system"
INTEGRITY_MODULE = "alimeeting_diarization_bench.final.timeline_integrity"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def average(values: list[float]) -> float | None:
    values = [value for value in values if value == value]
    return sum(values) / len(values) if values else None


def weighted_average(rows: list[dict[str, Any]], value_key: str, weight_key: str) -> float | None:
    total = 0.0
    total_weight = 0
    for row in rows:
        value = row.get(value_key)
        weight = int(row.get(weight_key) or 0)
        if value is None or weight <= 0:
            continue
        total += float(value) * weight
        total_weight += weight
    return total / total_weight if total_weight else None


def parse_recording_ids(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []
    return [{"recording_id": item.strip()} for item in value.split(",") if item.strip()]


def load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Manifest not found: {path}")
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("recordings"), list):
        return data["recordings"]
    raise SystemExit(f"Unsupported manifest shape: {path}")


def discover_cached_recordings() -> list[dict[str, Any]]:
    from .realtime_system import DEFAULT_FAST_SUMMARY, DEFAULT_SLOW_SUMMARY, load_summary, selected_keys

    _, fast_by_key = load_summary(DEFAULT_FAST_SUMMARY)
    _, slow_by_key = load_summary(DEFAULT_SLOW_SUMMARY)
    recording_ids = sorted({key[0] for key in selected_keys(fast_by_key, slow_by_key, None, 30, None)})
    return [{"recording_id": recording_id} for recording_id in recording_ids]


def normalize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    seen = set()
    for idx, item in enumerate(items):
        recording_id = str(item.get("recording_id") or item.get("id") or "").strip()
        audio = str(item.get("audio") or item.get("audio_path") or "").strip()
        if not recording_id and not audio:
            raise SystemExit(f"Batch item {idx} needs recording_id or audio/audio_path")
        key = recording_id or audio
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "recording_id": recording_id or None,
                "audio": audio or None,
                "label": recording_id or Path(audio).stem,
                "output_subdir": str(item.get("output_subdir") or recording_id or Path(audio).stem),
            }
        )
    return normalized


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "duration_sec": time.time() - started,
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-12:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-12:]),
    }


def item_command(item: dict[str, Any], output_dir: Path, args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        "-m",
        SYSTEM_MODULE,
        "--output-dir",
        str(output_dir),
        "--window-size",
        str(args.window_size),
        "--variant",
        args.variant,
        "--guard-quarantine-threshold",
        str(args.guard_quarantine_threshold),
        "--rare-audio-speech-sec-threshold",
        str(args.rare_audio_speech_sec_threshold),
        "--rare-slow-segments-max",
        str(args.rare_slow_segments_max),
        "--total-samples",
        str(args.total_samples),
        "--seed",
        str(args.seed),
    ]
    if args.segment_idx is not None:
        command.extend(["--segment-idx", str(args.segment_idx)])
    if item.get("audio"):
        command.extend(["--audio", str(item["audio"])])
    if item.get("recording_id"):
        command.extend(["--recording-id", str(item["recording_id"])])
    return command


def integrity_command(output_dir: Path, integrity_dir: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        INTEGRITY_MODULE,
        "--timeline-json",
        str(output_dir / "final_timeline.json"),
        "--timeline-csv",
        str(output_dir / "final_timeline.csv"),
        "--timeline-rttm",
        str(output_dir / "final_timeline.rttm"),
        "--window-metrics",
        str(output_dir / "window_metrics.json"),
        "--output-dir",
        str(integrity_dir),
    ]


def summarize_item(item: dict[str, Any], output_dir: Path, run_result: dict[str, Any], integrity_result: dict[str, Any] | None) -> dict[str, Any]:
    metrics = read_json(output_dir / "metrics.json")
    m = metrics.get("metrics", {})
    integrity = read_json(output_dir / "timeline_integrity/final_timeline_integrity.json")
    status = "pass" if run_result["returncode"] == 0 and (integrity_result is None or integrity_result["returncode"] == 0) else "fail"
    return {
        "status": status,
        "recording_id": item.get("recording_id") or metrics.get("recording_id"),
        "label": item.get("label"),
        "output_dir": str(output_dir),
        "run_returncode": run_result["returncode"],
        "integrity_returncode": integrity_result["returncode"] if integrity_result else None,
        "duration_sec": run_result["duration_sec"] + (integrity_result["duration_sec"] if integrity_result else 0.0),
        "windows_processed": metrics.get("windows_processed"),
        "recordings_processed": metrics.get("recordings_processed"),
        "evaluation_status": metrics.get("evaluation_status"),
        "final_der": m.get("final_der"),
        "fast_der": m.get("fast_der"),
        "delta_vs_fast_pp": m.get("der_delta_vs_fast_pp"),
        "beats_best_baseline": m.get("beats_best_baseline"),
        "deepseek_api_calls": m.get("deepseek_api_calls"),
        "qwen_api_calls": m.get("qwen_api_calls"),
        "omni_api_calls": m.get("omni_api_calls"),
        "timeline_integrity_status": integrity.get("status"),
        "timeline_rows": integrity.get("summary", {}).get("timeline_rows"),
        "same_speaker_overlap_count": integrity.get("summary", {}).get("same_speaker_overlap_count"),
        "run_stdout_tail": run_result["stdout_tail"],
        "run_stderr_tail": run_result["stderr_tail"],
        "integrity_stdout_tail": integrity_result["stdout_tail"] if integrity_result else "",
        "integrity_stderr_tail": integrity_result["stderr_tail"] if integrity_result else "",
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Realtime Batch Summary",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Items: `{summary['passed_items']}/{summary['items']}` passed",
        f"- Windows: `{summary['windows_processed']}`",
        f"- Final DER: `{summary['final_der_pct']}` (`{summary.get('aggregation', 'n/a')}`)",
        f"- Item-average Final DER: `{summary.get('final_der_item_avg_pct', 'n/a')}`",
        f"- Timeline integrity passed: `{summary['timeline_integrity_passed_items']}/{summary['items']}`",
        f"- Live API calls: DeepSeek `{summary['deepseek_api_calls']}`, Qwen `{summary['qwen_api_calls']}`, Omni `{summary['omni_api_calls']}`",
        "",
        "| Status | Recording | Windows | Final DER | Timeline | Output |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in payload["items"]:
        final_der = f"{float(row['final_der']) * 100:.2f}%" if row.get("final_der") is not None else "n/a"
        lines.append(
            f"| `{row['status']}` | `{row.get('recording_id') or row.get('label')}` | {row.get('windows_processed')} | "
            f"{final_der} | `{row.get('timeline_integrity_status')}` | `{row['output_dir']}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=None, help="CSV/JSON/JSONL manifest with recording_id and optional audio_path.")
    parser.add_argument("--recording-ids", default=None, help="Comma-separated recording ids for a quick batch run.")
    parser.add_argument("--all-cached-recordings", action="store_true", help="Build the batch from every shared cached recording id.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/realtime_batch"))
    parser.add_argument("--skip-integrity", action="store_true")
    parser.add_argument("--window-size", type=int, default=30)
    parser.add_argument("--segment-idx", type=int, default=None)
    parser.add_argument("--variant", default="slow_guarded_fast_fallback_rare_audio_rule_recover")
    parser.add_argument("--guard-quarantine-threshold", type=int, default=1)
    parser.add_argument("--rare-audio-speech-sec-threshold", type=float, default=18.605)
    parser.add_argument("--rare-slow-segments-max", type=int, default=3)
    parser.add_argument("--total-samples", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.manifest:
        raw_items = load_manifest(args.manifest)
        manifest_source = str(args.manifest)
    elif args.recording_ids:
        raw_items = parse_recording_ids(args.recording_ids)
        manifest_source = "recording_ids_arg"
    elif args.all_cached_recordings:
        raw_items = discover_cached_recordings()
        manifest_source = "shared_cached_recordings"
    else:
        raise SystemExit("Provide --manifest, --recording-ids, or --all-cached-recordings")

    items = normalize_items(raw_items)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "batch_manifest.json", {"manifest_source": manifest_source, "items": items})
    write_csv(args.output_dir / "batch_manifest.csv", items, ["recording_id", "audio", "label", "output_subdir"])

    started = time.time()
    rows = []
    for item in items:
        item_output_dir = args.output_dir / "items" / str(item["output_subdir"])
        item_output_dir.mkdir(parents=True, exist_ok=True)
        run_result = run_command(item_command(item, item_output_dir, args), ROOT)
        integrity_result = None
        if run_result["returncode"] == 0 and not args.skip_integrity:
            integrity_result = run_command(
                integrity_command(item_output_dir, item_output_dir / "timeline_integrity"),
                ROOT,
            )
        rows.append(summarize_item(item, item_output_dir, run_result, integrity_result))

    passed = sum(1 for row in rows if row["status"] == "pass")
    final_ders = [float(row["final_der"]) for row in rows if row.get("final_der") is not None]
    fast_ders = [float(row["fast_der"]) for row in rows if row.get("fast_der") is not None]
    final_der_weighted = weighted_average(rows, "final_der", "windows_processed")
    fast_der_weighted = weighted_average(rows, "fast_der", "windows_processed")
    final_der_item_avg = average(final_ders)
    fast_der_item_avg = average(fast_ders)
    summary = {
        "items": len(rows),
        "passed_items": passed,
        "failed_items": len(rows) - passed,
        "windows_processed": sum(int(row.get("windows_processed") or 0) for row in rows),
        "recordings_processed": sum(int(row.get("recordings_processed") or 0) for row in rows),
        "final_der": final_der_weighted,
        "final_der_pct": f"{final_der_weighted * 100:.2f}%" if final_der_weighted is not None else "n/a",
        "final_der_item_avg": final_der_item_avg,
        "final_der_item_avg_pct": f"{final_der_item_avg * 100:.2f}%" if final_der_item_avg is not None else "n/a",
        "fast_der": fast_der_weighted,
        "fast_der_item_avg": fast_der_item_avg,
        "aggregation": "window_weighted_by_windows_processed",
        "timeline_integrity_passed_items": sum(1 for row in rows if row.get("timeline_integrity_status") == "pass"),
        "deepseek_api_calls": sum(int(row.get("deepseek_api_calls") or 0) for row in rows),
        "qwen_api_calls": sum(int(row.get("qwen_api_calls") or 0) for row in rows),
        "omni_api_calls": sum(int(row.get("omni_api_calls") or 0) for row in rows),
        "duration_sec": time.time() - started,
    }
    payload = {
        "runtime_contract": "offline_realtime_batch_orchestration_no_live_calls",
        "status": "pass" if passed == len(rows) and rows else "fail",
        "manifest_source": manifest_source,
        "summary": summary,
        "items": rows,
    }
    write_json(args.output_dir / "batch_summary.json", payload)
    write_csv(
        args.output_dir / "batch_summary.csv",
        rows,
        [
            "status",
            "recording_id",
            "label",
            "output_dir",
            "windows_processed",
            "recordings_processed",
            "evaluation_status",
            "final_der",
            "fast_der",
            "delta_vs_fast_pp",
            "beats_best_baseline",
            "timeline_integrity_status",
            "timeline_rows",
            "same_speaker_overlap_count",
            "duration_sec",
            "deepseek_api_calls",
            "qwen_api_calls",
            "omni_api_calls",
        ],
    )
    write_markdown(args.output_dir / "batch_summary.md", payload)
    print(f"Wrote {args.output_dir / 'batch_manifest.json'}")
    print(f"Wrote {args.output_dir / 'batch_summary.json'}")
    print(
        "status={status} items={passed}/{total} windows={windows} final={final}".format(
            status=payload["status"],
            passed=passed,
            total=len(rows),
            windows=summary["windows_processed"],
            final=summary["final_der_pct"],
        )
    )
    raise SystemExit(0 if payload["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
