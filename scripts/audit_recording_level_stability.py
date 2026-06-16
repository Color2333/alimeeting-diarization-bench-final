#!/usr/bin/env python3
"""Audit final-system stability with recording-level resampling.

Window-level bootstrap can overstate confidence when gains are concentrated in
a small number of meetings. This audit compares the final runtime output against
the clipped Slow baseline per recording, then bootstraps recordings rather than
individual windows.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def average(values: list[float]) -> float | None:
    values = [value for value in values if value == value]
    return sum(values) / len(values) if values else None


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]


def load_final_windows(path: Path) -> dict[str, dict[str, Any]]:
    out = {}
    for row in read_csv(path):
        out[str(row["window_id"])] = {
            "recording_id": row["recording_id"],
            "window_id": row["window_id"],
            "final_der": as_float(row.get("final_der"), default=float("nan")),
            "final_source": row.get("final_source", ""),
        }
    return out


def load_clipped_baseline(path: Path, baseline_id: str) -> dict[str, float]:
    out = {}
    for row in read_csv(path):
        if row.get("baseline_id") == baseline_id:
            out[str(row["window_id"])] = as_float(row.get("der"), default=float("nan"))
    return out


def group_recordings(final: dict[str, dict[str, Any]], baseline: dict[str, float]) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for window_id, row in final.items():
        if window_id not in baseline:
            continue
        grouped[str(row["recording_id"])].append((as_float(row["final_der"], default=float("nan")), baseline[window_id], row["final_source"]))

    rows = []
    for recording_id, items in sorted(grouped.items()):
        final_der = average([item[0] for item in items])
        baseline_der = average([item[1] for item in items])
        source_counts: dict[str, int] = {}
        for _, _, source in items:
            source_counts[source] = source_counts.get(source, 0) + 1
        delta = baseline_der - final_der if final_der is not None and baseline_der is not None else None
        rows.append(
            {
                "recording_id": recording_id,
                "windows": len(items),
                "final_der": final_der,
                "baseline_der": baseline_der,
                "delta_vs_baseline": delta,
                "delta_vs_baseline_pp": delta * 100 if delta is not None else None,
                "beats_baseline": final_der < baseline_der if final_der is not None and baseline_der is not None else False,
                "ties_or_no_gain": abs(delta or 0.0) <= 1e-12,
                "source_counts": source_counts,
            }
        )
    return rows


def bootstrap_recordings(rows: list[dict[str, Any]], samples: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    deltas = []
    final_ders = []
    baseline_ders = []
    for _ in range(samples):
        sample = [rng.choice(rows) for _ in rows]
        final_der = average([as_float(row["final_der"], default=float("nan")) for row in sample]) or 0.0
        baseline_der = average([as_float(row["baseline_der"], default=float("nan")) for row in sample]) or 0.0
        final_ders.append(final_der)
        baseline_ders.append(baseline_der)
        deltas.append(baseline_der - final_der)
    return {
        "samples": samples,
        "seed": seed,
        "mean_delta_vs_baseline": average(deltas),
        "mean_delta_vs_baseline_pp": (average(deltas) or 0.0) * 100,
        "delta_ci_low": percentile(deltas, 0.025),
        "delta_ci_high": percentile(deltas, 0.975),
        "delta_ci_low_pp": percentile(deltas, 0.025) * 100,
        "delta_ci_high_pp": percentile(deltas, 0.975) * 100,
        "prob_beats_baseline": sum(1 for value in deltas if value > 0) / len(deltas) if deltas else 0.0,
        "mean_final_der": average(final_ders),
        "mean_baseline_der": average(baseline_ders),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    b = payload["recording_bootstrap"]
    lines = [
        "# Recording-Level Stability Audit",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Baseline: `{payload['baseline_id']}`",
        f"- Recordings: `{payload['summary']['recordings']}`",
        f"- Positive recordings: `{payload['summary']['positive_recordings']}/{payload['summary']['recordings']}`",
        f"- Mean final DER: `{payload['summary']['mean_final_der']:.2%}`",
        f"- Mean baseline DER: `{payload['summary']['mean_baseline_der']:.2%}`",
        f"- Mean delta: `{payload['summary']['mean_delta_vs_baseline_pp']:.3f}pp`",
        f"- Recording bootstrap P(beats baseline): `{b['prob_beats_baseline']:.1%}`",
        f"- Recording bootstrap delta CI: `{b['delta_ci_low_pp']:.3f}pp` to `{b['delta_ci_high_pp']:.3f}pp`",
        "",
        "## Per Recording",
        "",
        "| Recording | Windows | Final DER | Baseline DER | Delta | Beats | Sources |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["per_recording"]:
        lines.append(
            "| `{recording_id}` | {windows} | {final:.2%} | {baseline:.2%} | {delta:.3f}pp | {beats} | `{sources}` |".format(
                recording_id=row["recording_id"],
                windows=row["windows"],
                final=as_float(row["final_der"]),
                baseline=as_float(row["baseline_der"]),
                delta=as_float(row["delta_vs_baseline_pp"]),
                beats=row["beats_baseline"],
                sources=json.dumps(row["source_counts"], sort_keys=True),
            )
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This is stricter than window bootstrap because each sample resamples whole recordings.",
            "- `weak_recording_level_gain_not_robust` means the development-pool mean still improves, but the gain is not stable enough for promotion.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/window_metrics.csv"))
    parser.add_argument("--clipped-baseline-scores", type=Path, default=Path("outputs/clipped_baseline_audit/clipped_baseline_scores.csv"))
    parser.add_argument("--baseline-id", default="slow_base")
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/recording_level_stability"))
    args = parser.parse_args()

    final = load_final_windows(args.window_metrics)
    baseline = load_clipped_baseline(args.clipped_baseline_scores, args.baseline_id)
    per_recording = group_recordings(final, baseline)
    if not per_recording:
        raise SystemExit("No shared final/baseline windows found")

    bootstrap = bootstrap_recordings(per_recording, args.bootstrap_samples, args.seed)
    final_der = average([as_float(row["final_der"], default=float("nan")) for row in per_recording]) or 0.0
    baseline_der = average([as_float(row["baseline_der"], default=float("nan")) for row in per_recording]) or 0.0
    positive = sum(1 for row in per_recording if row["beats_baseline"])
    delta_pp = (baseline_der - final_der) * 100
    robust = delta_pp > 0 and positive == len(per_recording) and bootstrap["delta_ci_low"] > 0 and bootstrap["prob_beats_baseline"] >= 0.95
    status = "robust_recording_level_gain" if robust else ("weak_recording_level_gain_not_robust" if delta_pp > 0 else "no_recording_level_gain")

    payload = {
        "runtime_contract": "recording_level_stability_no_live_calls_no_new_model_inference",
        "status": status,
        "baseline_id": args.baseline_id,
        "summary": {
            "recordings": len(per_recording),
            "windows": sum(int(row["windows"]) for row in per_recording),
            "positive_recordings": positive,
            "mean_final_der": final_der,
            "mean_baseline_der": baseline_der,
            "mean_delta_vs_baseline": baseline_der - final_der,
            "mean_delta_vs_baseline_pp": delta_pp,
            "all_recordings_positive": positive == len(per_recording),
        },
        "recording_bootstrap": bootstrap,
        "per_recording": per_recording,
        "metric_claim_boundary": "development_recording_level_resampling_not_true_heldout",
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "recording_level_stability.json"
    md_path = args.output_dir / "recording_level_stability.md"
    csv_path = args.output_dir / "recording_level_stability.csv"
    write_json(json_path, payload)
    write_markdown(md_path, payload)
    write_csv(
        csv_path,
        per_recording,
        ["recording_id", "windows", "final_der", "baseline_der", "delta_vs_baseline", "delta_vs_baseline_pp", "beats_baseline", "ties_or_no_gain", "source_counts"],
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    print(
        "status={status} positive={positive}/{total} delta={delta:.3f}pp prob={prob:.1%} ci={ci_low:.3f}..{ci_high:.3f}pp".format(
            status=status,
            positive=positive,
            total=len(per_recording),
            delta=delta_pp,
            prob=bootstrap["prob_beats_baseline"],
            ci_low=bootstrap["delta_ci_low_pp"],
            ci_high=bootstrap["delta_ci_high_pp"],
        )
    )


if __name__ == "__main__":
    main()
