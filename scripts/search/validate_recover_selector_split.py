#!/usr/bin/env python3
"""Validate recover selector policies with recording-level holdout splits.

The search script ranks policies on all available windows. This script adds a
more conservative check: for each held-out recording, choose the best policy on
the remaining recordings, then score that fixed policy on the held-out
recording. Ground truth is used only for train-side ranking and final scoring,
not as a policy feature.
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
import sys
from collections import Counter
from pathlib import Path
from typing import Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from search_recover_selector_policies import (  # noqa: E402
    WindowKey,
    as_float,
    index_results,
    load_csv,
    policy_functions,
    recover_windows,
    window_features,
)


Policy = Callable[[dict[str, float]], str]


def mean(rows: list[dict[str, str]], field: str) -> float:
    values = [as_float(row.get(field)) for row in rows if row.get(field) not in (None, "")]
    return sum(values) / len(values) if values else 0.0


def score_policy_on_keys(
    keys: list[WindowKey],
    name: str,
    policy: Policy,
    by_key: dict[WindowKey, dict[str, dict[str, str]]],
    features: dict[WindowKey, dict[str, float]],
    recover_by_key: dict[WindowKey, list[dict[str, str]]],
) -> dict[str, object]:
    chosen_rows: list[dict[str, str]] = []
    choices: Counter[str] = Counter()
    for key in keys:
        variants = by_key[key]
        if key not in recover_by_key:
            choice = "fast_base"
        else:
            choice = policy(features[key])
        if choice not in variants:
            raise RuntimeError(f"Missing materialized variant {choice} for {key}")
        choices[choice] += 1
        chosen_rows.append(variants[choice])
    return {
        "policy": name,
        "windows": len(chosen_rows),
        "avg_der": mean(chosen_rows, "der"),
        "avg_miss_rate": mean(chosen_rows, "miss_rate"),
        "avg_fa_rate": mean(chosen_rows, "fa_rate"),
        "avg_conf_rate": mean(chosen_rows, "conf_rate"),
        "matched_windows": choices["rule_recover_matched_label"],
        "uncovered_windows": choices["rule_recover_uncovered_only"],
        "fast_windows": choices["fast_base"],
        "choice_counts": " / ".join(f"{key} {value}" for key, value in sorted(choices.items())),
    }


def baseline_score(keys: list[WindowKey], by_key: dict[WindowKey, dict[str, dict[str, str]]], variant: str) -> dict[str, float]:
    rows = [by_key[key][variant] for key in keys]
    return {
        "der": mean(rows, "der"),
        "miss": mean(rows, "miss_rate"),
        "fa": mean(rows, "fa_rate"),
        "conf": mean(rows, "conf_rate"),
    }


def fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def select_best_policy(
    keys: list[WindowKey],
    policies: list[tuple[str, Policy]],
    by_key: dict[WindowKey, dict[str, dict[str, str]]],
    features: dict[WindowKey, dict[str, float]],
    recover_by_key: dict[WindowKey, list[dict[str, str]]],
) -> dict[str, object]:
    rows = [
        score_policy_on_keys(keys, name, policy, by_key, features, recover_by_key)
        for name, policy in policies
    ]
    rows.sort(key=lambda row: (float(row["avg_der"]), float(row["avg_fa_rate"]), float(row["avg_conf_rate"])))
    return rows[0]


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, object]], summary: dict[str, object], path: Path) -> None:
    lines = [
        "# Recover Selector Recording-Holdout Validation",
        "",
        "Each row trains the selector on all other recordings, then applies the selected policy unchanged to the held-out recording.",
        "",
        "| Held-out | Windows | Train best policy | Train DER | Held-out DER | Fast DER | Delta vs Fast | Miss | FA | Conf | Choices |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {heldout_recording} | {heldout_windows} | {train_best_policy} | {train_der} | {heldout_der} | {fast_der} | {delta} | {miss} | {fa} | {conf} | {choices} |".format(
                heldout_recording=row["heldout_recording"],
                heldout_windows=row["heldout_windows"],
                train_best_policy=row["train_best_policy"],
                train_der=fmt_pct(float(row["train_avg_der"])),
                heldout_der=fmt_pct(float(row["heldout_avg_der"])),
                fast_der=fmt_pct(float(row["heldout_fast_der"])),
                delta=fmt_pct(float(row["heldout_delta_vs_fast"])),
                miss=fmt_pct(float(row["heldout_miss_rate"])),
                fa=fmt_pct(float(row["heldout_fa_rate"])),
                conf=fmt_pct(float(row["heldout_conf_rate"])),
                choices=row["heldout_choice_counts"],
            )
        )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Held-out positive splits: `{summary['positive_splits']}/{summary['splits']}`.",
            f"- Window-weighted held-out DER: `{fmt_pct(float(summary['weighted_heldout_der']))}` vs Fast `{fmt_pct(float(summary['weighted_fast_der']))}`; delta `{fmt_pct(float(summary['weighted_delta_vs_fast']))}`.",
            f"- Most frequent train-selected policy: `{summary['top_policy']}` (`{summary['top_policy_count']}` splits).",
            f"- Fixed full-sample best policy `{summary['fixed_policy']}` scores `{fmt_pct(float(summary['fixed_policy_der']))}` on all windows.",
            "",
            "## Reading",
            "",
            "- This is still development data because the recordings come from the same sampled pool.",
            "- It is stronger than a single full-sample sweep because the threshold is selected without seeing the held-out recording.",
            "- A policy is ready for final reporting only after this fixed rule is run on newly sampled windows or a held-out meeting set.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline-results", type=Path, default=Path("outputs/rule_writeback_timeline_120/rule_writeback_timeline_results.csv"))
    parser.add_argument("--window-features", type=Path, default=Path("outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv"))
    parser.add_argument("--gate-decisions", type=Path, default=Path("outputs/writeback_gate_120/gate_decisions.csv"))
    parser.add_argument("--fixed-policy", default="ratio_le_0.65_else_uncovered")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/recover_selector_split_120"))
    args = parser.parse_args()

    by_key = index_results(load_csv(args.timeline_results))
    recover_by_key = recover_windows(load_csv(args.gate_decisions))
    features = window_features(load_csv(args.window_features), recover_by_key)
    policies = policy_functions()
    policy_by_name = dict(policies)
    if args.fixed_policy not in policy_by_name:
        raise SystemExit(f"Unknown fixed policy: {args.fixed_policy}")

    keys = sorted(key for key, variants in by_key.items() if "fast_base" in variants)
    recordings = sorted({key[0] for key in keys})
    if len(recordings) < 2:
        raise SystemExit("Need at least two recordings for holdout validation.")

    rows: list[dict[str, object]] = []
    selected_counter: Counter[str] = Counter()
    for heldout in recordings:
        train_keys = [key for key in keys if key[0] != heldout]
        heldout_keys = [key for key in keys if key[0] == heldout]
        best = select_best_policy(train_keys, policies, by_key, features, recover_by_key)
        selected_counter[str(best["policy"])] += 1
        heldout_score = score_policy_on_keys(
            heldout_keys,
            str(best["policy"]),
            policy_by_name[str(best["policy"])],
            by_key,
            features,
            recover_by_key,
        )
        fast = baseline_score(heldout_keys, by_key, "fast_base")
        slow = baseline_score(heldout_keys, by_key, "slow_base")
        rows.append(
            {
                "heldout_recording": heldout,
                "heldout_windows": len(heldout_keys),
                "train_windows": len(train_keys),
                "train_best_policy": best["policy"],
                "train_avg_der": round(float(best["avg_der"]), 6),
                "heldout_avg_der": round(float(heldout_score["avg_der"]), 6),
                "heldout_fast_der": round(fast["der"], 6),
                "heldout_slow_der": round(slow["der"], 6),
                "heldout_delta_vs_fast": round(fast["der"] - float(heldout_score["avg_der"]), 6),
                "heldout_miss_rate": round(float(heldout_score["avg_miss_rate"]), 6),
                "heldout_fa_rate": round(float(heldout_score["avg_fa_rate"]), 6),
                "heldout_conf_rate": round(float(heldout_score["avg_conf_rate"]), 6),
                "heldout_matched_windows": heldout_score["matched_windows"],
                "heldout_uncovered_windows": heldout_score["uncovered_windows"],
                "heldout_fast_windows": heldout_score["fast_windows"],
                "heldout_choice_counts": heldout_score["choice_counts"],
                "beats_fast": float(heldout_score["avg_der"]) < fast["der"],
            }
        )

    total_windows = sum(int(row["heldout_windows"]) for row in rows)
    weighted_heldout_der = sum(float(row["heldout_avg_der"]) * int(row["heldout_windows"]) for row in rows) / total_windows
    weighted_fast_der = sum(float(row["heldout_fast_der"]) * int(row["heldout_windows"]) for row in rows) / total_windows
    fixed_score = score_policy_on_keys(keys, args.fixed_policy, policy_by_name[args.fixed_policy], by_key, features, recover_by_key)
    top_policy, top_policy_count = selected_counter.most_common(1)[0]
    summary = {
        "splits": len(rows),
        "positive_splits": sum(1 for row in rows if row["beats_fast"]),
        "weighted_heldout_der": round(weighted_heldout_der, 6),
        "weighted_fast_der": round(weighted_fast_der, 6),
        "weighted_delta_vs_fast": round(weighted_fast_der - weighted_heldout_der, 6),
        "top_policy": top_policy,
        "top_policy_count": top_policy_count,
        "selected_policy_counts": dict(selected_counter),
        "fixed_policy": args.fixed_policy,
        "fixed_policy_der": round(float(fixed_score["avg_der"]), 6),
        "fixed_policy_miss_rate": round(float(fixed_score["avg_miss_rate"]), 6),
        "fixed_policy_fa_rate": round(float(fixed_score["avg_fa_rate"]), 6),
        "fixed_policy_conf_rate": round(float(fixed_score["avg_conf_rate"]), 6),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "recording_holdout.csv"
    summary_json = args.output_dir / "recording_holdout_summary.json"
    md_path = args.output_dir / "recording_holdout.md"
    write_csv(rows, csv_path)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(rows, summary, md_path)
    print(f"Wrote {csv_path}")
    print(f"Wrote {summary_json}")
    print(f"Wrote {md_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
