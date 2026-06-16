#!/usr/bin/env python3
"""Bootstrap stability checks for realtime diarization contract metrics.

This is a development-set uncertainty check, not a held-out result. It resamples
materialized windows with replacement and reports the mean DER/Miss/FA/Conf plus
the paired DER delta against the Fast provisional baseline.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path


WindowKey = tuple[str, int, int]


def as_float(value: object, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def key_from_row(row: dict[str, str]) -> WindowKey:
    return (row["recording_id"], int(float(row["window_size"])), int(float(row["segment_idx"])))


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def index_by_window(rows: list[dict[str, str]]) -> dict[WindowKey, dict[str, dict[str, str]]]:
    indexed: dict[WindowKey, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        if row.get("success") not in ("True", "true", "1", True):
            continue
        indexed[key_from_row(row)][row["variant"]] = row
    return indexed


def mean_metric(rows: list[dict[str, str]], field: str) -> float:
    return sum(as_float(row.get(field)) for row in rows) / len(rows) if rows else 0.0


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def bootstrap_variant(
    windows: list[WindowKey],
    indexed: dict[WindowKey, dict[str, dict[str, str]]],
    baseline: str,
    variant: str,
    iterations: int,
    rng: random.Random,
) -> dict[str, object]:
    observed_rows = [indexed[key][variant] for key in windows]
    observed_fast = [indexed[key][baseline] for key in windows]
    observed = {
        "der": mean_metric(observed_rows, "der"),
        "miss": mean_metric(observed_rows, "miss_rate"),
        "fa": mean_metric(observed_rows, "fa_rate"),
        "conf": mean_metric(observed_rows, "conf_rate"),
        "delta_vs_fast": mean_metric(observed_fast, "der") - mean_metric(observed_rows, "der"),
    }

    ders: list[float] = []
    misses: list[float] = []
    fas: list[float] = []
    confs: list[float] = []
    deltas: list[float] = []
    n = len(windows)
    for _ in range(iterations):
        sample_keys = [windows[rng.randrange(n)] for _ in range(n)]
        variant_rows = [indexed[key][variant] for key in sample_keys]
        fast_rows = [indexed[key][baseline] for key in sample_keys]
        der = mean_metric(variant_rows, "der")
        ders.append(der)
        misses.append(mean_metric(variant_rows, "miss_rate"))
        fas.append(mean_metric(variant_rows, "fa_rate"))
        confs.append(mean_metric(variant_rows, "conf_rate"))
        deltas.append(mean_metric(fast_rows, "der") - der)

    return {
        "variant": variant,
        "windows": len(windows),
        "observed_der": observed["der"],
        "der_ci_low": quantile(ders, 0.025),
        "der_ci_high": quantile(ders, 0.975),
        "observed_miss": observed["miss"],
        "miss_ci_low": quantile(misses, 0.025),
        "miss_ci_high": quantile(misses, 0.975),
        "observed_fa": observed["fa"],
        "fa_ci_low": quantile(fas, 0.025),
        "fa_ci_high": quantile(fas, 0.975),
        "observed_conf": observed["conf"],
        "conf_ci_low": quantile(confs, 0.025),
        "conf_ci_high": quantile(confs, 0.975),
        "delta_vs_fast": observed["delta_vs_fast"],
        "delta_ci_low": quantile(deltas, 0.025),
        "delta_ci_high": quantile(deltas, 0.975),
        "prob_beats_fast": sum(1 for value in deltas if value > 0) / len(deltas),
    }


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, object]], path: Path, iterations: int, baseline: str) -> None:
    lines = [
        "# Realtime Contract Bootstrap",
        "",
        f"Development-set bootstrap over materialized windows. Iterations: `{iterations}`. Baseline: `{baseline}`.",
        "",
        "| Variant | DER | 95% CI | Miss | FA | Conf | Delta vs Fast | Delta 95% CI | P(beats Fast) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {variant} | {der} | {der_low} - {der_high} | {miss} | {fa} | {conf} | {delta} | {delta_low} - {delta_high} | {prob:.1%} |".format(
                variant=row["variant"],
                der=pct(float(row["observed_der"])),
                der_low=pct(float(row["der_ci_low"])),
                der_high=pct(float(row["der_ci_high"])),
                miss=pct(float(row["observed_miss"])),
                fa=pct(float(row["observed_fa"])),
                conf=pct(float(row["observed_conf"])),
                delta=pct(float(row["delta_vs_fast"])),
                delta_low=pct(float(row["delta_ci_low"])),
                delta_high=pct(float(row["delta_ci_high"])),
                prob=float(row["prob_beats_fast"]),
            )
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This is not a held-out score; it measures how sensitive the current 48-window result is to window sampling.",
            "- A positive paired delta means the variant improves mean DER over Fast provisional on the same resampled windows.",
            "- The next protocol step is to run the same selector on new windows before treating the threshold as fixed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("outputs/rule_writeback_timeline/rule_writeback_timeline_results.csv"))
    parser.add_argument("--baseline", default="fast_base")
    parser.add_argument(
        "--variants",
        nargs="+",
        default=[
            "fast_base",
            "slow_base",
            "rule_recover_policy_sweep_best",
            "rule_recover_identity_selector",
            "rule_recover_uncovered_only",
            "rule_boundary_recover",
        ],
    )
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260604)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/realtime_contract_bootstrap"))
    args = parser.parse_args()

    rows = read_rows(args.results)
    indexed = index_by_window(rows)
    available_windows = [
        key
        for key, variants in indexed.items()
        if args.baseline in variants and all(variant in variants for variant in args.variants)
    ]
    available_windows.sort()
    if not available_windows:
        raise SystemExit("No complete windows found for requested variants.")

    rng = random.Random(args.seed)
    summaries = [
        bootstrap_variant(available_windows, indexed, args.baseline, variant, args.iterations, rng)
        for variant in args.variants
    ]
    summaries.sort(key=lambda row: float(row["observed_der"]))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "realtime_contract_bootstrap.csv"
    md_path = args.output_dir / "realtime_contract_bootstrap.md"
    json_path = args.output_dir / "realtime_contract_bootstrap.json"
    write_csv(summaries, csv_path)
    write_markdown(summaries, md_path, args.iterations, args.baseline)
    json_path.write_text(
        json.dumps(
            {
                "results": str(args.results),
                "baseline": args.baseline,
                "iterations": args.iterations,
                "seed": args.seed,
                "windows": len(available_windows),
                "summaries": summaries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
