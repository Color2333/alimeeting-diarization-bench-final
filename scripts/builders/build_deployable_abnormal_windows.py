#!/usr/bin/env python3
"""Build deployment-compatible abnormal-window proxy flags.

The earlier abnormal-window detector uses DER/Miss/FA and GT speaker counts,
which is useful for offline analysis but cannot exist in a live system. This
script derives conservative proxy flags only from Fast/Slow predictions and the
cross-model patch window table.
"""

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


def as_float(value: object, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def reason_join(reasons: list[str]) -> str:
    return ",".join(dict.fromkeys(reason for reason in reasons if reason))


def proxy_rows(rows: list[dict[str, str]], args: argparse.Namespace) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        window_size = as_float(row.get("window_size"), 30.0)
        fast_speech = as_float(row.get("fast_speech"))
        slow_speech = as_float(row.get("slow_speech"))
        disagreement = as_float(row.get("fast_slow_disagreement_sec"))
        fast_spk = int(as_float(row.get("fast_spk_count_pred")))
        slow_spk = int(as_float(row.get("slow_spk_count_pred")))
        fast_segments = int(as_float(row.get("fast_segments")))
        slow_segments = int(as_float(row.get("slow_segments")))

        common = []
        if fast_spk != slow_spk:
            common.append("cross_model_speaker_count_mismatch")
        if disagreement >= args.disagreement_sec:
            common.append("cross_model_disagreement_high")
        if slow_speech and fast_speech / slow_speech >= args.speech_ratio_high:
            common.append("fast_speech_much_longer_than_slow")
        if fast_speech and slow_speech / fast_speech >= args.speech_ratio_high:
            common.append("slow_speech_much_longer_than_fast")
        if abs(fast_segments - slow_segments) >= args.segment_count_gap:
            common.append("cross_model_segment_count_gap")

        fast_reasons = list(common)
        slow_reasons = list(common)
        if fast_speech / window_size >= args.pred_speech_too_long_ratio:
            fast_reasons.append("pred_speech_too_long")
        if fast_speech / window_size <= args.pred_speech_too_short_ratio:
            fast_reasons.append("pred_speech_too_short")
        if slow_speech / window_size >= args.pred_speech_too_long_ratio:
            slow_reasons.append("pred_speech_too_long")
        if slow_speech / window_size <= args.pred_speech_too_short_ratio:
            slow_reasons.append("pred_speech_too_short")

        for model_name, speech, segments, reasons in [
            ("nemo-sortformer-4spk-v1-runtime-proxy", fast_speech, fast_segments, fast_reasons),
            ("diarizen-large-v2-runtime-proxy", slow_speech, slow_segments, slow_reasons),
        ]:
            reason = reason_join(reasons)
            if not reason:
                continue
            output.append(
                {
                    "model_name": model_name,
                    "recording_id": row["recording_id"],
                    "window_size": int(window_size),
                    "segment_idx": int(as_float(row["segment_idx"])),
                    "pred_speech": round(speech, 4),
                    "pred_speech_ratio": round(speech / window_size if window_size else 0.0, 4),
                    "pred_segments": segments,
                    "fast_spk_count_pred": fast_spk,
                    "slow_spk_count_pred": slow_spk,
                    "fast_speech": round(fast_speech, 4),
                    "slow_speech": round(slow_speech, 4),
                    "fast_slow_disagreement_sec": round(disagreement, 4),
                    "reason": reason,
                    "evidence_source": "deployable_prediction_proxy",
                }
            )
    output.sort(key=lambda item: (str(item["recording_id"]), int(item["segment_idx"]), str(item["model_name"])))
    return output


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model_name",
        "recording_id",
        "window_size",
        "segment_idx",
        "pred_speech",
        "pred_speech_ratio",
        "pred_segments",
        "fast_spk_count_pred",
        "slow_spk_count_pred",
        "fast_speech",
        "slow_speech",
        "fast_slow_disagreement_sec",
        "reason",
        "evidence_source",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, object]], summary: dict[str, object], path: Path) -> None:
    lines = [
        "# Deployable Abnormal Window Proxy",
        "",
        "These flags use only prediction-time evidence: Fast/Slow speaker counts, speech duration, segment counts, and cross-model disagreement.",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Flagged rows | {summary['flagged_rows']} |",
        f"| Flagged windows | {summary['flagged_windows']} |",
        f"| Fast proxy rows | {summary['fast_rows']} |",
        f"| Slow proxy rows | {summary['slow_rows']} |",
        "",
        "## Top Reasons",
        "",
        "| Reason | Count |",
        "|---|---:|",
    ]
    for reason, count in summary["reason_counts"].items():
        lines.append(f"| {reason} | {count} |")
    lines.extend(
        [
            "",
            "## Runtime Contract",
            "",
            "- No DER/Miss/FA/Conf, GT speech, or oracle speaker labels are used.",
            "- These flags can replace eval-derived `high_der/high_fa/high_miss` in runtime prompts.",
            "- Offline scoring can still join these flags with DER after the fact to estimate recall/precision.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-features", type=Path, default=Path("outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/deployable_abnormal_windows/deployable_abnormal_windows.md"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/deployable_abnormal_windows/summary.json"))
    parser.add_argument("--pred-speech-too-long-ratio", type=float, default=0.95)
    parser.add_argument("--pred-speech-too-short-ratio", type=float, default=0.05)
    parser.add_argument("--disagreement-sec", type=float, default=8.0)
    parser.add_argument("--speech-ratio-high", type=float, default=1.8)
    parser.add_argument("--segment-count-gap", type=int, default=8)
    args = parser.parse_args()

    rows = proxy_rows(load_csv(args.window_features), args)
    reason_counts: Counter[str] = Counter()
    for row in rows:
        for reason in str(row["reason"]).split(","):
            reason_counts[reason] += 1
    summary = {
        "window_features": str(args.window_features),
        "flagged_rows": len(rows),
        "flagged_windows": len({(row["recording_id"], row["window_size"], row["segment_idx"]) for row in rows}),
        "fast_rows": sum(1 for row in rows if str(row["model_name"]).startswith("nemo")),
        "slow_rows": sum(1 for row in rows if str(row["model_name"]).startswith("diarizen")),
        "reason_counts": dict(reason_counts.most_common()),
        "output_csv": str(args.output_csv),
        "output_md": str(args.output_md),
    }
    write_csv(rows, args.output_csv)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(rows, summary, args.output_md)
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.summary_json}")
    print(f"Wrote {args.output_md}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
