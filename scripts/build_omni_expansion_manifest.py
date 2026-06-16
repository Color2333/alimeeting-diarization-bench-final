#!/usr/bin/env python3
"""Prepare a 48-window Omni fusion expansion manifest without live model calls."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIO_DIR = Path("/Users/haojiang/data/AliMeeting/Eval_Ali/Eval_Ali_far/audio_dir")
TARGET_MODELS = ["qwen3.5-omni-flash", "qwen3.5-omni-plus-2026-03-15"]
REASON_WEIGHTS = {
    "cross_model_disagreement_high": 5.0,
    "slow_speech_much_longer_than_fast": 4.0,
    "cross_model_segment_count_gap": 3.0,
    "cross_model_speaker_count_mismatch": 2.0,
    "pred_speech_too_long": 1.0,
}


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def audio_path(audio_dir: Path, recording_id: str) -> Path:
    matches = sorted(audio_dir.glob(f"{recording_id}_*.wav"))
    return matches[0] if matches else audio_dir / f"{recording_id}_MISSING.wav"


def key(row: dict[str, str]) -> tuple[str, int, int]:
    return (row["recording_id"], int(row["window_size"]), int(row["segment_idx"]))


def key_text(window: tuple[str, int, int]) -> str:
    return f"{window[0]}:{window[1]}:{window[2]}"


def split_reasons(value: str) -> set[str]:
    return {part.strip() for part in value.split(",") if part.strip()}


def proxy_score(item: dict[str, Any]) -> float:
    reasons = item["proxy_reasons"]
    score = sum(REASON_WEIGHTS.get(reason, 0.0) for reason in reasons)
    score += min(float(item.get("fast_slow_disagreement_sec", 0.0)) / 5.0, 5.0)
    score += max(float(item.get("max_pred_speech_ratio", 0.0)) - 1.0, 0.0)
    return score


def aggregate_proxy(rows: list[dict[str, str]]) -> dict[tuple[str, int, int], dict[str, Any]]:
    grouped: dict[tuple[str, int, int], dict[str, Any]] = {}
    for row in rows:
        window = key(row)
        item = grouped.setdefault(
            window,
            {
                "recording_id": row["recording_id"],
                "window_size": int(row["window_size"]),
                "segment_idx": int(row["segment_idx"]),
                "proxy_models": set(),
                "proxy_reasons": set(),
                "fast_slow_disagreement_sec": 0.0,
                "max_pred_speech_ratio": 0.0,
                "max_pred_segments": 0,
                "evidence_source": row.get("evidence_source", ""),
            },
        )
        item["proxy_models"].add(row.get("model_name", ""))
        item["proxy_reasons"].update(split_reasons(row.get("reason", "")))
        item["fast_slow_disagreement_sec"] = max(
            float(item["fast_slow_disagreement_sec"]),
            float(row.get("fast_slow_disagreement_sec") or 0.0),
        )
        item["max_pred_speech_ratio"] = max(
            float(item["max_pred_speech_ratio"]),
            float(row.get("pred_speech_ratio") or 0.0),
        )
        item["max_pred_segments"] = max(int(item["max_pred_segments"]), int(float(row.get("pred_segments") or 0)))
    for item in grouped.values():
        item["proxy_score"] = proxy_score(item)
    return grouped


def smoke_anchor_rows(rows: list[dict[str, str]], audio_dir: Path) -> list[dict[str, Any]]:
    anchors = {}
    for row in rows:
        window = key(row)
        anchor = anchors.setdefault(
            window,
            {
                "expansion_role": "anchor_smoke_window",
                "recording_id": row["recording_id"],
                "window_size": int(row["window_size"]),
                "segment_idx": int(row["segment_idx"]),
                "prior_bucket": row.get("bucket", ""),
                "existing_omni_result": "1",
                "proxy_reasons": set(),
                "proxy_score": 0.0,
                "source_artifacts": "outputs/omni_guard/omni_flash_plus_window_batch_12.csv",
            },
        )
        risk = row.get("diarization_risk", "")
        if risk:
            anchor.setdefault("prior_omni_risks", set()).add(risk)
    out = []
    for anchor in anchors.values():
        path = audio_path(audio_dir, anchor["recording_id"])
        anchor["audio"] = str(path)
        anchor["audio_exists"] = "1" if path.exists() else "0"
        anchor["clip_start_sec"] = float(anchor["segment_idx"] * anchor["window_size"])
        anchor["clip_sec"] = 8.0
        anchor["target_models"] = ";".join(TARGET_MODELS)
        anchor["proxy_reasons"] = ""
        anchor["prior_omni_risks"] = ";".join(sorted(anchor.get("prior_omni_risks", [])))
        out.append(anchor)
    return sorted(out, key=lambda row: (row["recording_id"], row["segment_idx"]))


def select_proxy_candidates(
    proxy: dict[tuple[str, int, int], dict[str, Any]],
    excluded: set[tuple[str, int, int]],
    audio_dir: Path,
    count: int,
) -> list[dict[str, Any]]:
    candidates = [item for window, item in proxy.items() if window not in excluded]
    candidates.sort(key=lambda item: (-float(item["proxy_score"]), item["recording_id"], item["segment_idx"]))
    selected = []
    per_recording = Counter()
    for item in candidates:
        if len(selected) >= count:
            break
        if per_recording[item["recording_id"]] >= 6:
            continue
        selected.append(item)
        per_recording[item["recording_id"]] += 1
    for item in candidates:
        if len(selected) >= count:
            break
        if item in selected:
            continue
        selected.append(item)

    rows = []
    for item in selected[:count]:
        path = audio_path(audio_dir, item["recording_id"])
        rows.append(
            {
                "expansion_role": "new_runtime_proxy_window",
                "recording_id": item["recording_id"],
                "window_size": item["window_size"],
                "segment_idx": item["segment_idx"],
                "prior_bucket": "runtime_proxy",
                "existing_omni_result": "0",
                "audio": str(path),
                "audio_exists": "1" if path.exists() else "0",
                "clip_start_sec": float(item["segment_idx"] * item["window_size"]),
                "clip_sec": 8.0,
                "target_models": ";".join(TARGET_MODELS),
                "proxy_reasons": ";".join(sorted(item["proxy_reasons"])),
                "proxy_score": f"{float(item['proxy_score']):.3f}",
                "prior_omni_risks": "",
                "source_artifacts": "outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv",
            }
        )
    return rows


def build_manifest(root: Path, audio_dir: Path, target_windows: int) -> dict[str, Any]:
    smoke = smoke_anchor_rows(load_csv(root / "outputs/omni_guard/omni_flash_plus_window_batch_12.csv"), audio_dir)
    proxy = aggregate_proxy(load_csv(root / "outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv"))
    anchor_keys = {(row["recording_id"], int(row["window_size"]), int(row["segment_idx"])) for row in smoke}
    new_count = max(target_windows - len(smoke), 0)
    new_rows = select_proxy_candidates(proxy, anchor_keys, audio_dir, new_count)
    rows = smoke + new_rows
    rows = rows[:target_windows]
    missing_audio = [key_text((row["recording_id"], int(row["window_size"]), int(row["segment_idx"]))) for row in rows if row["audio_exists"] != "1"]
    reason_counts = Counter(reason for row in rows for reason in str(row.get("proxy_reasons", "")).split(";") if reason)
    command = (
        "python scripts/omni_guard_window_batch.py "
        "--input-windows-csv outputs/research_progress_snapshot/omni_expansion_manifest.csv "
        "--model qwen3.5-omni-flash --model qwen3.5-omni-plus-2026-03-15 "
        "--skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 "
        "--output-jsonl outputs/omni_guard/omni_expansion_48_live.jsonl"
    )
    return {
        "runtime_contract": "omni_expansion_manifest_ready_no_live_calls_no_timeline_writeback",
        "rows": rows,
        "summary": {
            "target_windows": target_windows,
            "selected_windows": len(rows),
            "anchor_smoke_windows": sum(1 for row in rows if row["expansion_role"] == "anchor_smoke_window"),
            "new_runtime_proxy_windows": sum(1 for row in rows if row["expansion_role"] == "new_runtime_proxy_window"),
            "target_models": TARGET_MODELS,
            "planned_model_calls": len(rows) * len(TARGET_MODELS),
            "audio_missing_count": len(missing_audio),
            "audio_missing_windows": missing_audio,
            "proxy_reason_counts": dict(reason_counts),
            "live_call_status": "not_run_manifest_only",
            "no_timeline_writeback": True,
            "run_command": command,
        },
    }


def write_csv(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "expansion_role",
        "recording_id",
        "window_size",
        "segment_idx",
        "prior_bucket",
        "existing_omni_result",
        "audio",
        "audio_exists",
        "clip_start_sec",
        "clip_sec",
        "target_models",
        "proxy_reasons",
        "proxy_score",
        "prior_omni_risks",
        "source_artifacts",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest["rows"])


def write_markdown(manifest: dict[str, Any], path: Path) -> None:
    summary = manifest["summary"]
    lines = [
        "# Omni Expansion Manifest",
        "",
        f"- Runtime contract: `{manifest['runtime_contract']}`",
        f"- Selected windows: `{summary['selected_windows']}` / target `{summary['target_windows']}`",
        f"- Anchor smoke windows: `{summary['anchor_smoke_windows']}`",
        f"- New runtime-proxy windows: `{summary['new_runtime_proxy_windows']}`",
        f"- Planned model calls: `{summary['planned_model_calls']}`",
        f"- Audio missing: `{summary['audio_missing_count']}`",
        f"- Live call status: `{summary['live_call_status']}`",
        f"- No timeline writeback: `{summary['no_timeline_writeback']}`",
        "",
        "## Run Command",
        "",
        f"```bash\n{summary['run_command']}\n```",
        "",
        "## Selected Windows",
        "",
        "| Window | Role | Prior bucket | Proxy score | Proxy reasons | Audio |",
        "|---|---|---|---:|---|---|",
    ]
    for row in manifest["rows"]:
        window = key_text((row["recording_id"], int(row["window_size"]), int(row["segment_idx"])))
        lines.append(
            f"| `{window}` | `{row['expansion_role']}` | `{row['prior_bucket']}` | "
            f"{row.get('proxy_score', '')} | {row.get('proxy_reasons', '')} | `{row['audio_exists']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This manifest prepares the expanded Omni run; it does not perform live Omni/API calls.",
            "- Existing 12-window smoke rows are retained as anchors; new windows come from deployable acoustic proxy flags.",
            "- Omni output remains label/quarantine-priority only and does not receive timeline writeback rights.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    parser.add_argument("--target-windows", type=int, default=48)
    parser.add_argument("--output-json", type=Path, default=Path("outputs/research_progress_snapshot/omni_expansion_manifest.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/research_progress_snapshot/omni_expansion_manifest.md"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/research_progress_snapshot/omni_expansion_manifest.csv"))
    args = parser.parse_args()

    manifest = build_manifest(ROOT, args.audio_dir, args.target_windows)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(manifest, args.output_csv)
    write_markdown(manifest, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
