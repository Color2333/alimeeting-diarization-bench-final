#!/usr/bin/env python3
"""Expand the Omni48 window manifest into a per-model call manifest without live calls."""

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
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUT_JSON = Path("outputs/research_progress_snapshot/omni_expansion_manifest.json")
INPUT_CSV = Path("outputs/research_progress_snapshot/omni_expansion_manifest.csv")
OUTPUT_JSON = Path("outputs/research_progress_snapshot/omni48_live_call_manifest.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/omni48_live_call_manifest.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/omni48_live_call_manifest.csv")
OUTPUT_JSONL = Path("outputs/omni_guard/omni_expansion_48_live.jsonl")
LABEL_ONLY_WRITEBACK = "label_only_no_timeline_writeback"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def target_models(manifest: dict[str, Any], rows: list[dict[str, str]]) -> list[str]:
    models = manifest.get("summary", {}).get("target_models") or []
    if models:
        return [str(model) for model in models]
    for row in rows:
        raw = row.get("target_models", "")
        if raw:
            return [part.strip() for part in raw.split(";") if part.strip()]
    return []


def window_id(row: dict[str, str]) -> str:
    return f"{row['recording_id']}:{row['window_size']}:{row['segment_idx']}"


def call_id(row: dict[str, str], model: str) -> str:
    model_slug = model.replace("/", "_").replace(":", "_")
    return f"{window_id(row)}:{model_slug}"


def build_manifest(root: Path, input_json: Path, input_csv: Path, output_jsonl: Path) -> dict[str, Any]:
    source_manifest = read_json(root / input_json)
    rows = read_csv(root / input_csv)
    models = target_models(source_manifest, rows)
    calls: list[dict[str, Any]] = []
    for row in rows:
        for model in models:
            calls.append(
                {
                    "call_index": len(calls) + 1,
                    "call_id": call_id(row, model),
                    "model": model,
                    "recording_id": row["recording_id"],
                    "window_size": int(row["window_size"]),
                    "segment_idx": int(row["segment_idx"]),
                    "window_id": window_id(row),
                    "expansion_role": row.get("expansion_role", ""),
                    "prior_bucket": row.get("prior_bucket", ""),
                    "existing_omni_result": row.get("existing_omni_result", ""),
                    "audio": row.get("audio", ""),
                    "audio_exists": row.get("audio_exists", ""),
                    "clip_start_sec": float(row.get("clip_start_sec") or 0.0),
                    "clip_sec": float(row.get("clip_sec") or 0.0),
                    "proxy_score": row.get("proxy_score", ""),
                    "proxy_reasons": row.get("proxy_reasons", ""),
                    "prior_omni_risks": row.get("prior_omni_risks", ""),
                    "source_artifacts": row.get("source_artifacts", ""),
                    "output_jsonl": str(output_jsonl),
                    "writeback_right": LABEL_ONLY_WRITEBACK,
                }
            )

    role_counts = Counter(call["expansion_role"] for call in calls)
    model_counts = Counter(call["model"] for call in calls)
    missing_audio = sorted({call["window_id"] for call in calls if call["audio_exists"] != "1"})
    clip_audio_seconds = sum(float(row.get("clip_sec") or 0.0) for row in rows)
    expected_call_count = len(rows) * len(models)
    failures = []
    if source_manifest.get("runtime_contract") != "omni_expansion_manifest_ready_no_live_calls_no_timeline_writeback":
        failures.append("source_manifest_contract_mismatch")
    if len(calls) != expected_call_count:
        failures.append("call_count_mismatch")
    if missing_audio:
        failures.append("audio_missing")
    if any(call["writeback_right"] != LABEL_ONLY_WRITEBACK for call in calls):
        failures.append("writeback_right_mismatch")

    run_command = source_manifest.get("summary", {}).get("run_command", "")
    return {
        "runtime_contract": "omni48_live_call_manifest_no_live_calls_label_only",
        "source_manifest": str(input_json),
        "source_windows_csv": str(input_csv),
        "output_jsonl": str(output_jsonl),
        "status": "pass" if not failures else "fail",
        "summary": {
            "window_count": len(rows),
            "call_count": len(calls),
            "expected_call_count": expected_call_count,
            "model_count": len(models),
            "target_models": models,
            "anchor_smoke_calls": int(role_counts.get("anchor_smoke_window", 0)),
            "new_runtime_proxy_calls": int(role_counts.get("new_runtime_proxy_window", 0)),
            "role_counts": dict(role_counts),
            "model_counts": dict(model_counts),
            "audio_missing_count": len(missing_audio),
            "audio_missing_windows": missing_audio,
            "clip_audio_seconds": round(clip_audio_seconds, 3),
            "clip_model_seconds_proxy": round(clip_audio_seconds * max(len(models), 1), 3),
            "no_timeline_writeback": True,
            "writeback_right": LABEL_ONLY_WRITEBACK,
            "live_calls_performed": 0,
            "run_command": run_command,
        },
        "failures": failures,
        "calls": calls,
    }


def write_csv(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "call_index",
        "call_id",
        "model",
        "recording_id",
        "window_size",
        "segment_idx",
        "window_id",
        "expansion_role",
        "prior_bucket",
        "existing_omni_result",
        "audio",
        "audio_exists",
        "clip_start_sec",
        "clip_sec",
        "proxy_score",
        "proxy_reasons",
        "prior_omni_risks",
        "source_artifacts",
        "output_jsonl",
        "writeback_right",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest["calls"])


def write_markdown(manifest: dict[str, Any], path: Path) -> None:
    summary = manifest["summary"]
    lines = [
        "# Omni48 Live Call Manifest",
        "",
        f"- Runtime contract: `{manifest['runtime_contract']}`",
        f"- Status: `{manifest['status']}`",
        f"- Source windows: `{summary['window_count']}`",
        f"- Omni48 call manifest: `{summary['call_count']}` calls / expected `{summary['expected_call_count']}`",
        f"- Target models: `{'; '.join(summary['target_models'])}`",
        f"- Anchor smoke calls: `{summary['anchor_smoke_calls']}`",
        f"- New runtime-proxy calls: `{summary['new_runtime_proxy_calls']}`",
        f"- Audio missing: `{summary['audio_missing_count']}`",
        f"- Clip audio seconds: `{summary['clip_audio_seconds']}`",
        f"- Clip model seconds proxy: `{summary['clip_model_seconds_proxy']}`",
        f"- Live calls performed: `{summary['live_calls_performed']}`",
        f"- Writeback right: `{summary['writeback_right']}`",
        f"- No timeline writeback: `{summary['no_timeline_writeback']}`",
        f"- Output JSONL: `{manifest['output_jsonl']}`",
        "",
        "## Run Command",
        "",
        "```bash",
        summary["run_command"],
        "```",
        "",
        "## First Calls",
        "",
        "| # | Window | Model | Role | Audio | Writeback |",
        "|---:|---|---|---|---|---|",
    ]
    for call in manifest["calls"][:16]:
        lines.append(
            f"| {call['call_index']} | `{call['window_id']}` | `{call['model']}` | "
            f"`{call['expansion_role']}` | `{call['audio_exists']}` | `{call['writeback_right']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This artifact expands the 48-window Omni manifest into per-model call rows only.",
            "- It does not call any model and does not read or write live Omni responses.",
            "- Every planned call is label-only and has no timeline writeback right.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", type=Path, default=INPUT_JSON)
    parser.add_argument("--input-csv", type=Path, default=INPUT_CSV)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--output-jsonl", type=Path, default=OUTPUT_JSONL)
    args = parser.parse_args()

    manifest = build_manifest(ROOT, args.input_json, args.input_csv, args.output_jsonl)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(manifest, args.output_csv)
    write_markdown(manifest, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
