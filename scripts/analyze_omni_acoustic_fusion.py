#!/usr/bin/env python3
"""Summarize Omni early-risk signals fused with acoustic proxy flags."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def filter_model(rows: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("model") == model]


def window_key(row: dict[str, Any]) -> tuple[str, int, int]:
    return (str(row["recording_id"]), int(row["window_size"]), int(row["segment_idx"]))


def key_text(key: tuple[str, int, int]) -> str:
    recording_id, window_size, segment_idx = key
    return f"{recording_id}:{window_size}:{segment_idx}"


def is_fast_hint(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    risk = str(row.get("diarization_risk", "")).lower()
    overlap = str(row.get("overlap_or_crosstalk", "")).lower()
    speech = str(row.get("speech_activity", "")).lower()
    return risk in {"medium", "high", "unknown"} or overlap in {"possible", "strong"} or speech in {"low", "dense"}


def is_high_sentinel(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    risk = str(row.get("diarization_risk", "")).lower()
    overlap = str(row.get("overlap_or_crosstalk", "")).lower()
    return bool(row.get("should_quarantine")) or risk == "high" or overlap == "strong"


def pct(numer: int, denom: int) -> str:
    if denom == 0:
        return "n/a"
    return f"{numer}/{denom} ({numer / denom:.1%})"


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bucket_counts = Counter(row["bucket"] for row in rows)
    high_rows = [row for row in rows if row["bucket"] == "high"]
    clean_rows = [row for row in rows if row["bucket"] == "clean"]
    medium_rows = [row for row in rows if row["bucket"] == "medium"]
    flagged_rows = [row for row in rows if row["acoustic_proxy_flagged"]]
    high_sentinel_rows = [row for row in rows if row["omni_high_sentinel"]]
    fast_hint_rows = [row for row in rows if row["omni_fast_hint"]]
    review_rows = [row for row in rows if row["fusion_action"] != "no_action"]
    flash_calls = [float(row["flash_call_seconds"]) for row in rows if row["flash_call_seconds"] != ""]
    plus_calls = [float(row["plus_call_seconds"]) for row in rows if row["plus_call_seconds"] != ""]

    return {
        "windows": len(rows),
        "bucket_counts": dict(bucket_counts),
        "acoustic_proxy_flagged": len(flagged_rows),
        "omni_fast_hints": len(fast_hint_rows),
        "omni_high_sentinels": len(high_sentinel_rows),
        "review_priority": len(review_rows),
        "high_sentinel_recall": pct(sum(row["omni_high_sentinel"] for row in high_rows), len(high_rows)),
        "review_priority_high_recall": pct(sum(row["fusion_action"] != "no_action" for row in high_rows), len(high_rows)),
        "clean_high_sentinel_fp": pct(sum(row["omni_high_sentinel"] for row in clean_rows), len(clean_rows)),
        "clean_review_priority_fp": pct(sum(row["fusion_action"] != "no_action" for row in clean_rows), len(clean_rows)),
        "medium_review_priority": pct(sum(row["fusion_action"] != "no_action" for row in medium_rows), len(medium_rows)),
        "avg_flash_call_seconds": sum(flash_calls) / len(flash_calls) if flash_calls else 0.0,
        "p95_flash_call_seconds": percentile(flash_calls, 0.95),
        "avg_plus_call_seconds": sum(plus_calls) / len(plus_calls) if plus_calls else 0.0,
        "p95_plus_call_seconds": percentile(plus_calls, 0.95),
        "max_flash_call_seconds": max(flash_calls) if flash_calls else 0.0,
        "max_plus_call_seconds": max(plus_calls) if plus_calls else 0.0,
        "runtime_contract": "omni_audio_jsonl_joined_with_deployable_acoustic_proxy; no_timeline_writeback",
    }


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "window_id",
        "bucket",
        "acoustic_proxy_flagged",
        "acoustic_reasons",
        "flash_risk",
        "flash_overlap",
        "flash_defer",
        "flash_call_seconds",
        "plus_risk",
        "plus_overlap",
        "plus_quarantine",
        "plus_call_seconds",
        "omni_fast_hint",
        "omni_high_sentinel",
        "fusion_action",
        "fusion_reading",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, Any]], summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Omni + Acoustic Fusion Smoke",
        "",
        "| Windows | Acoustic flagged | Omni fast hints | Omni high sentinels | Review priority | High sentinel recall | High review recall | Clean sentinel FP | Clean review FP |",
        "|---:|---:|---:|---:|---:|---|---|---|---|",
        (
            "| {windows} | {acoustic_proxy_flagged} | {omni_fast_hints} | {omni_high_sentinels} | "
            "{review_priority} | {high_sentinel_recall} | {review_priority_high_recall} | "
            "{clean_high_sentinel_fp} | {clean_review_priority_fp} |"
        ).format(**summary),
        "",
        "## Window Decisions",
        "",
        "| Window | Bucket | Acoustic proxy | Flash risk | Plus risk | Fast hint | High sentinel | Fusion action |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {window_id} | {bucket} | {acoustic_proxy_flagged} | {flash_risk} | {plus_risk} | "
            "{omni_fast_hint} | {omni_high_sentinel} | {fusion_action} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
        "- `Omni high sentinel` is a conservative early quarantine candidate: model quarantine, high risk, or strong crosstalk.",
        "- `Fusion action` is review-priority only; this smoke does not grant timeline writeback rights.",
        "- Tail latency is part of the runtime contract: flash is the realtime hint path, while plus remains a slower sentinel or offline check.",
        f"- The sample has {summary['windows']} windows, so these numbers are readiness evidence for fusion logic, not final recall/precision claims.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined-jsonl", type=Path, default=Path("outputs/omni_guard/omni_flash_plus_window_batch_12.jsonl"))
    parser.add_argument("--flash-jsonl", type=Path, default=Path("outputs/omni_guard/omni_flash_window_batch_6.jsonl"))
    parser.add_argument("--plus-jsonl", type=Path, default=Path("outputs/omni_guard/omni_plus_dated_window_batch_6.jsonl"))
    parser.add_argument("--flash-model", default="qwen3.5-omni-flash")
    parser.add_argument("--plus-model", default="qwen3.5-omni-plus-2026-03-15")
    parser.add_argument("--acoustic-proxy", type=Path, default=Path("outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/omni_guard/omni_acoustic_fusion.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/omni_guard/omni_acoustic_fusion.md"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/omni_guard/omni_acoustic_fusion_summary.json"))
    args = parser.parse_args()

    if args.combined_jsonl.exists():
        combined_rows = load_jsonl(args.combined_jsonl)
        flash_rows = filter_model(combined_rows, args.flash_model)
        plus_rows = filter_model(combined_rows, args.plus_model)
    else:
        flash_rows = load_jsonl(args.flash_jsonl)
        plus_rows = load_jsonl(args.plus_jsonl)

    flash_by_key = {window_key(row): row for row in flash_rows}
    plus_by_key = {window_key(row): row for row in plus_rows}
    acoustic_reasons: dict[tuple[str, int, int], set[str]] = defaultdict(set)
    for row in load_csv(args.acoustic_proxy):
        key = (row["recording_id"], int(row["window_size"]), int(row["segment_idx"]))
        for reason in row.get("reason", "").split(","):
            if reason:
                acoustic_reasons[key].add(reason)

    keys = sorted(set(flash_by_key) | set(plus_by_key))
    rows = []
    for key in keys:
        flash = flash_by_key.get(key)
        plus = plus_by_key.get(key)
        source = flash or plus or {}
        fast_hint = is_fast_hint(flash)
        high_sentinel = is_high_sentinel(flash) or is_high_sentinel(plus)
        acoustic_flagged = key in acoustic_reasons
        if high_sentinel:
            action = "early_quarantine_candidate"
            reading = "Omni high/strong overlap should boost quarantine priority."
        elif fast_hint and acoustic_flagged:
            action = "early_review_priority"
            reading = "Omni hint agrees with deployable acoustic proxy."
        elif acoustic_flagged:
            action = "acoustic_proxy_review"
            reading = "Acoustic proxy flags risk even though Omni is not high."
        elif fast_hint:
            action = "omni_label_only_hint"
            reading = "Omni can add a label, but acoustic proxy is not flagged."
        else:
            action = "no_action"
            reading = "No early fusion action from this smoke."

        rows.append(
            {
                "window_id": key_text(key),
                "bucket": source.get("bucket", ""),
                "acoustic_proxy_flagged": acoustic_flagged,
                "acoustic_reasons": " / ".join(sorted(acoustic_reasons.get(key, []))),
                "flash_risk": flash.get("diarization_risk", "") if flash else "",
                "flash_overlap": flash.get("overlap_or_crosstalk", "") if flash else "",
                "flash_defer": bool(flash.get("should_defer_to_slow_agent")) if flash else "",
                "flash_call_seconds": f"{float(flash.get('call_seconds', 0.0)):.3f}" if flash else "",
                "plus_risk": plus.get("diarization_risk", "") if plus else "",
                "plus_overlap": plus.get("overlap_or_crosstalk", "") if plus else "",
                "plus_quarantine": bool(plus.get("should_quarantine")) if plus else "",
                "plus_call_seconds": f"{float(plus.get('call_seconds', 0.0)):.3f}" if plus else "",
                "omni_fast_hint": fast_hint,
                "omni_high_sentinel": high_sentinel,
                "fusion_action": action,
                "fusion_reading": reading,
            }
        )

    summary = summarize(rows)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(rows, args.output_csv)
    write_markdown(rows, summary, args.output_md)
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.summary_json}")


if __name__ == "__main__":
    main()
