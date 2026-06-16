#!/usr/bin/env python3
"""Audit final-system margin against baselines and oracle headroom.

This is an analysis-only script. It uses scored cached outputs to estimate how
much DER remains if a runtime selector could pick the best available candidate
per window. It does not define or use a runtime policy.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


WindowKey = tuple[str, int, int]


DEFAULT_VARIANTS = [
    "fast_base",
    "slow_base",
    "rule_recover_policy_sweep_best",
    "rule_recover_matched_label",
    "rule_recover_uncovered_only",
]


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def average(values: list[float]) -> float | None:
    values = [value for value in values if value == value]
    return sum(values) / len(values) if values else None


def key_from_row(row: dict[str, Any]) -> WindowKey:
    return (str(row["recording_id"]), int(row["window_size"]), int(row["segment_idx"]))


def load_variant_scores(path: Path, variants: list[str]) -> dict[WindowKey, dict[str, float]]:
    scores: dict[WindowKey, dict[str, float]] = defaultdict(dict)
    variant_set = set(variants)
    for row in read_csv(path):
        if row.get("success") != "True":
            continue
        variant = row.get("variant", "")
        if variant not in variant_set:
            continue
        scores[key_from_row(row)][variant] = as_float(row.get("der"), default=float("nan"))
    return scores


def load_final_scores(path: Path) -> dict[WindowKey, dict[str, Any]]:
    out = {}
    for row in read_csv(path):
        key = key_from_row(row)
        out[key] = {
            "final_der": as_float(row.get("final_der"), default=float("nan")),
            "fast_der": as_float(row.get("fast_der"), default=float("nan")),
            "final_source": row.get("final_source"),
            "fast_latency": as_float(row.get("fast_latency")),
            "slow_latency": as_float(row.get("slow_latency")),
        }
    return out


def summarize_by_recording(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["recording_id"])].append(row)
    out = []
    for recording_id, items in sorted(grouped.items()):
        final_der = average([as_float(row["final_der"]) for row in items])
        oracle_der = average([as_float(row["oracle_der"]) for row in items])
        slow_der = average([as_float(row.get("slow_base")) for row in items if row.get("slow_base") is not None])
        out.append(
            {
                "recording_id": recording_id,
                "windows": len(items),
                "final_der": final_der,
                "oracle_der": oracle_der,
                "slow_der": slow_der,
                "final_delta_vs_oracle_pp": (final_der - oracle_der) * 100 if final_der is not None and oracle_der is not None else None,
                "final_delta_vs_slow_pp": (slow_der - final_der) * 100 if final_der is not None and slow_der is not None else None,
            }
        )
    return out


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Baseline Headroom Audit",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Windows: `{payload['windows']}`",
        f"- Final DER: `{payload['final_der']:.2%}`",
        f"- Best baseline DER: `{payload['best_baseline']['der']:.2%}` (`{payload['best_baseline']['variant']}`)",
        f"- Beats all baselines: `{payload['beats_all_baselines']}`",
        f"- Oracle DER: `{payload['oracle_der']:.2%}`",
        f"- Final gap to oracle: `{payload['final_gap_to_oracle_pp']:.2f}pp`",
        "",
        "## Baselines",
        "",
        "| Variant | DER | Delta vs Final |",
        "|---|---:|---:|",
    ]
    for row in payload["baseline_summary"]:
        lines.append(f"| `{row['variant']}` | {row['der']:.2%} | {row['delta_vs_final_pp']:.2f} pp |")
    lines.extend(
        [
            "",
            "## Oracle Variant Counts",
            "",
            "| Variant | Windows |",
            "|---|---:|",
        ]
    )
    for variant, count in payload["oracle_variant_counts"].items():
        lines.append(f"| `{variant}` | {count} |")
    lines.extend(
        [
            "",
            "## Top Opportunity Windows",
            "",
            "| Window | Final DER | Oracle DER | Gap | Oracle Variant |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for row in payload["top_opportunity_windows"]:
        lines.append(
            f"| `{row['window_id']}` | {row['final_der']:.2%} | {row['oracle_der']:.2%} | {row['final_gap_to_oracle_pp']:.2f} pp | `{row['oracle_variant']}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline-results", type=Path, default=Path("outputs/rule_writeback_timeline_120/rule_writeback_timeline_results.csv"))
    parser.add_argument("--window-metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/window_metrics.csv"))
    parser.add_argument("--variants", nargs="*", default=DEFAULT_VARIANTS)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/baseline_headroom_audit"))
    args = parser.parse_args()

    variant_scores = load_variant_scores(args.timeline_results, args.variants)
    final_scores = load_final_scores(args.window_metrics)
    keys = sorted(set(variant_scores) & set(final_scores))

    rows = []
    oracle_counts = Counter()
    for key in keys:
        candidates = variant_scores[key]
        oracle_variant, oracle_der = min(candidates.items(), key=lambda item: (item[1], item[0]))
        oracle_counts[oracle_variant] += 1
        final_der = final_scores[key]["final_der"]
        row = {
            "recording_id": key[0],
            "window_size": key[1],
            "segment_idx": key[2],
            "window_id": f"{key[0]}:{key[1]}:{key[2]}",
            "final_der": final_der,
            "final_source": final_scores[key]["final_source"],
            "oracle_variant": oracle_variant,
            "oracle_der": oracle_der,
            "final_gap_to_oracle_pp": (final_der - oracle_der) * 100,
        }
        row.update(candidates)
        rows.append(row)

    baseline_summary = []
    for variant in args.variants:
        der = average([variant_scores[key][variant] for key in keys if variant in variant_scores[key]])
        if der is None:
            continue
        final_der = average([row["final_der"] for row in rows])
        baseline_summary.append(
            {
                "variant": variant,
                "der": der,
                "delta_vs_final_pp": (der - final_der) * 100 if final_der is not None else None,
                "beats_final": der < final_der if final_der is not None else False,
            }
        )
    baseline_summary.sort(key=lambda row: (row["der"], row["variant"]))
    best_baseline = baseline_summary[0] if baseline_summary else {"variant": None, "der": None}
    final_der = average([row["final_der"] for row in rows])
    oracle_der = average([row["oracle_der"] for row in rows])
    recording_summary = summarize_by_recording(rows)
    top_opportunity = sorted(rows, key=lambda row: row["final_gap_to_oracle_pp"], reverse=True)[: args.top_n]
    payload = {
        "runtime_contract": "analysis_only_cached_scores_no_runtime_policy_no_live_calls",
        "windows": len(rows),
        "variants": args.variants,
        "final_der": final_der,
        "oracle_der": oracle_der,
        "final_gap_to_oracle_pp": (final_der - oracle_der) * 100 if final_der is not None and oracle_der is not None else None,
        "baseline_summary": baseline_summary,
        "best_baseline": best_baseline,
        "beats_all_baselines": all(row["der"] > final_der for row in baseline_summary) if final_der is not None else False,
        "oracle_variant_counts": dict(oracle_counts),
        "top_opportunity_windows": top_opportunity,
        "metric_claim_boundary": "oracle_uses_der_for_analysis_only_not_runtime",
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "baseline_headroom_audit.json"
    md_path = args.output_dir / "baseline_headroom_audit.md"
    rows_csv = args.output_dir / "baseline_headroom_windows.csv"
    recording_csv = args.output_dir / "baseline_headroom_recordings.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    write_csv(rows_csv, rows)
    write_csv(recording_csv, recording_summary)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "windows={windows} final={final:.2%} oracle={oracle:.2%} gap={gap:.2f}pp beats_all_baselines={beats}".format(
            windows=len(rows),
            final=final_der,
            oracle=oracle_der,
            gap=(final_der - oracle_der) * 100,
            beats=payload["beats_all_baselines"],
        )
    )


if __name__ == "__main__":
    main()
