#!/usr/bin/env python3
"""Recording-level stability analysis for realtime writeback variants.

The bootstrap script checks window resampling. This script checks whether a
variant's paired DER gain over the Fast provisional baseline is concentrated in
only one or two meetings by reporting per-recording and leave-one-recording-out
metrics.
"""

from __future__ import annotations

import argparse
import csv
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


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def key_from_row(row: dict[str, str]) -> WindowKey:
    return (row["recording_id"], int(float(row["window_size"])), int(float(row["segment_idx"])))


def index_rows(rows: list[dict[str, str]]) -> dict[WindowKey, dict[str, dict[str, str]]]:
    indexed: dict[WindowKey, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        if row.get("success") not in ("True", "true", "1", True):
            continue
        indexed[key_from_row(row)][row["variant"]] = row
    return indexed


def mean(rows: list[dict[str, str]], field: str) -> float:
    return sum(as_float(row.get(field)) for row in rows) / len(rows) if rows else 0.0


def summarize_keys(
    keys: list[WindowKey],
    indexed: dict[WindowKey, dict[str, dict[str, str]]],
    baseline: str,
    variant: str,
    label: str,
) -> dict[str, object]:
    fast_rows = [indexed[key][baseline] for key in keys]
    variant_rows = [indexed[key][variant] for key in keys]
    fast_der = mean(fast_rows, "der")
    variant_der = mean(variant_rows, "der")
    return {
        "group": label,
        "windows": len(keys),
        "fast_der": round(fast_der, 4),
        "variant_der": round(variant_der, 4),
        "delta_vs_fast": round(fast_der - variant_der, 4),
        "variant_miss": round(mean(variant_rows, "miss_rate"), 4),
        "variant_fa": round(mean(variant_rows, "fa_rate"), 4),
        "variant_conf": round(mean(variant_rows, "conf_rate"), 4),
        "beats_fast": variant_der < fast_der,
    }


def pct(value: object) -> str:
    return f"{float(value) * 100:.2f}%"


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(
    per_recording: list[dict[str, object]],
    loo: list[dict[str, object]],
    path: Path,
    variant: str,
    baseline: str,
) -> None:
    lines = [
        "# Realtime Contract Recording Stability",
        "",
        f"Variant: `{variant}`. Baseline: `{baseline}`.",
        "",
        "## Per Recording",
        "",
        "| Recording | Windows | Fast DER | Variant DER | Delta vs Fast | Miss | FA | Conf | Beats Fast |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in per_recording:
        lines.append(
            "| {group} | {windows} | {fast} | {variant} | {delta} | {miss} | {fa} | {conf} | {beats} |".format(
                group=row["group"],
                windows=row["windows"],
                fast=pct(row["fast_der"]),
                variant=pct(row["variant_der"]),
                delta=pct(row["delta_vs_fast"]),
                miss=pct(row["variant_miss"]),
                fa=pct(row["variant_fa"]),
                conf=pct(row["variant_conf"]),
                beats="yes" if row["beats_fast"] else "no",
            )
        )

    lines.extend(
        [
            "",
            "## Leave One Recording Out",
            "",
            "| Held-out recording | Train-like windows | Fast DER | Variant DER | Delta vs Fast | Beats Fast |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in loo:
        lines.append(
            "| {group} | {windows} | {fast} | {variant} | {delta} | {beats} |".format(
                group=row["group"],
                windows=row["windows"],
                fast=pct(row["fast_der"]),
                variant=pct(row["variant_der"]),
                delta=pct(row["delta_vs_fast"]),
                beats="yes" if row["beats_fast"] else "no",
            )
        )

    positive = sum(1 for row in per_recording if row["beats_fast"])
    total = len(per_recording)
    loo_positive = sum(1 for row in loo if row["beats_fast"])
    lines.extend(
        [
            "",
            "## Reading",
            "",
            f"- Per-recording gain is positive on `{positive}/{total}` recordings.",
            f"- Leave-one-recording-out gain remains positive on `{loo_positive}/{len(loo)}` splits.",
            "- This is still development-set evidence; it checks concentration risk, not true held-out generalization.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("outputs/rule_writeback_timeline/rule_writeback_timeline_results.csv"))
    parser.add_argument("--baseline", default="fast_base")
    parser.add_argument("--variant", default="rule_recover_policy_sweep_best")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/realtime_contract_recording_stability"))
    args = parser.parse_args()

    indexed = index_rows(read_rows(args.results))
    keys = [
        key
        for key, variants in indexed.items()
        if args.baseline in variants and args.variant in variants
    ]
    keys.sort()
    if not keys:
        raise SystemExit("No complete windows found for requested baseline/variant.")

    by_recording: dict[str, list[WindowKey]] = defaultdict(list)
    for key in keys:
        by_recording[key[0]].append(key)

    per_recording = [
        summarize_keys(group_keys, indexed, args.baseline, args.variant, recording_id)
        for recording_id, group_keys in sorted(by_recording.items())
    ]
    loo = [
        summarize_keys(
            [key for key in keys if key[0] != recording_id],
            indexed,
            args.baseline,
            args.variant,
            recording_id,
        )
        for recording_id in sorted(by_recording)
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    per_csv = args.output_dir / "per_recording.csv"
    loo_csv = args.output_dir / "leave_one_recording_out.csv"
    md_path = args.output_dir / "recording_stability.md"
    write_csv(per_recording, per_csv)
    write_csv(loo, loo_csv)
    write_markdown(per_recording, loo, md_path, args.variant, args.baseline)
    print(f"Wrote {per_csv}")
    print(f"Wrote {loo_csv}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
