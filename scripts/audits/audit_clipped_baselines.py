#!/usr/bin/env python3
"""Evaluate tracked baselines with the same window clipping used by runtime output."""

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
import contextlib
import csv
import io
import json
import logging
import os
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from evaluate_rule_writeback_timeline import materialize_variant
from run_realtime_diarization_system import (
    DEFAULT_FAST_SUMMARY,
    DEFAULT_GATE_DECISIONS,
    DEFAULT_PATCHES,
    DEFAULT_SLOW_SUMMARY,
    aggregate_metric,
    as_float,
    clip_segments_to_window,
    grouped_gate_rows,
    load_csv,
    load_summary,
    patch_id,
    score_window,
    selected_keys,
)


DEFAULT_VARIANTS = [
    "fast_base",
    "slow_base",
    "rule_recover_policy_sweep_best",
    "rule_recover_matched_label",
    "rule_recover_uncovered_only",
]

logging.disable(logging.CRITICAL)


@contextmanager
def suppress_process_output():
    sys.stdout.flush()
    sys.stderr.flush()
    stdout_fd = os.dup(1)
    stderr_fd = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(stdout_fd, 1)
        os.dup2(stderr_fd, 2)
        os.close(stdout_fd)
        os.close(stderr_fd)
        os.close(devnull)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Clipped Baseline Audit",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Windows: `{payload['windows']}`",
        f"- Final DER: `{payload['final_der']:.2%}`",
        f"- Best clipped baseline: `{payload['best_clipped_baseline']['baseline_id']}` / `{payload['best_clipped_baseline']['der']:.2%}`",
        f"- Delta vs best clipped baseline: `{payload['delta_vs_best_clipped_baseline_pp']:.3f}pp`",
        f"- Beats all clipped baselines: `{payload['beats_all_clipped_baselines']}`",
        "",
        "## Baselines",
        "",
        "| Baseline | DER | Delta vs Final | Adjusted | Dropped | Trimmed ms |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["baseline_summary"]:
        lines.append(
            "| `{baseline_id}` | {der:.2%} | {delta:.3f}pp | {adjusted} | {dropped} | {trimmed} |".format(
                baseline_id=row["baseline_id"],
                der=row["der"],
                delta=row["delta_vs_final_pp"],
                adjusted=row["clip_counters"].get("window_clip_adjusted_segments", 0),
                dropped=row["clip_counters"].get("window_clip_dropped_segments", 0),
                trimmed=row["clip_counters"].get("window_clip_trimmed_ms", 0),
            )
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Baselines are scored after the same local `[0, window_size]` clipping used for final runtime output.",
            "- This is a fairness audit for metric claims; it does not change the baseline source artifacts.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def baseline_segments(
    variant: str,
    key: tuple[str, int, int],
    fast: dict[str, Any],
    slow: dict[str, Any],
    gate_rows: dict[str, dict[str, str]],
    patch_eval_by_id: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    if variant == "fast_base":
        return [dict(seg) for seg in fast.get("pred_segments", [])]
    if variant == "slow_base":
        return [dict(seg) for seg in slow.get("pred_segments", [])]
    segments, _ = materialize_variant(variant, key, fast, slow, gate_rows, patch_eval_by_id)
    return segments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast-summary", type=Path, default=DEFAULT_FAST_SUMMARY)
    parser.add_argument("--slow-summary", type=Path, default=DEFAULT_SLOW_SUMMARY)
    parser.add_argument("--gate-decisions", type=Path, default=DEFAULT_GATE_DECISIONS)
    parser.add_argument("--patches", type=Path, default=DEFAULT_PATCHES)
    parser.add_argument("--metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/metrics.json"))
    parser.add_argument("--window-size", type=int, default=30)
    parser.add_argument("--variants", nargs="*", default=DEFAULT_VARIANTS)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/clipped_baseline_audit"))
    args = parser.parse_args()

    _, fast_by_key = load_summary(args.fast_summary)
    _, slow_by_key = load_summary(args.slow_summary)
    gate_by_window = grouped_gate_rows(load_csv(args.gate_decisions))
    patch_eval_by_id = {patch_id(row): row for row in load_csv(args.patches)}
    keys = selected_keys(fast_by_key, slow_by_key, None, args.window_size, None)
    metrics = read_json(args.metrics)
    final_der = as_float(metrics.get("metrics", {}).get("final_der"), default=float("nan"))

    rows: list[dict[str, Any]] = []
    baseline_summary = []
    for variant in args.variants:
        scores = []
        clip_totals: Counter[str] = Counter()
        for key in keys:
            fast = fast_by_key[key]
            slow = slow_by_key[key]
            gate_rows = gate_by_window.get(key, {})
            segments = baseline_segments(variant, key, fast, slow, gate_rows, patch_eval_by_id)
            clipped, counters = clip_segments_to_window(segments, args.window_size)
            clip_totals.update(counters)
            with suppress_process_output(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                score = score_window(key, f"{variant}_clipped", clipped, fast.get("gt_segments", []), 0.0)
            scores.append(score)
            rows.append(
                {
                    "baseline_id": variant,
                    "window_id": score["window_id"],
                    "recording_id": score["recording_id"],
                    "window_size": score["window_size"],
                    "segment_idx": score["segment_idx"],
                    "der": score.get("der"),
                    "miss_rate": score.get("miss_rate"),
                    "fa_rate": score.get("fa_rate"),
                    "conf_rate": score.get("conf_rate"),
                    "pred_segments": score.get("pred_segments"),
                    **{f"clip_{name}": value for name, value in counters.items()},
                }
            )
        der = aggregate_metric(scores, "der")
        baseline_summary.append(
            {
                "baseline_id": variant,
                "windows": len(scores),
                "der": der,
                "miss_rate": aggregate_metric(scores, "miss_rate"),
                "fa_rate": aggregate_metric(scores, "fa_rate"),
                "conf_rate": aggregate_metric(scores, "conf_rate"),
                "delta_vs_final_pp": (der - final_der) * 100 if der is not None and final_der == final_der else None,
                "beats_final": der < final_der if der is not None and final_der == final_der else None,
                "clip_counters": dict(clip_totals),
            }
        )

    baseline_summary.sort(key=lambda row: (row["der"], row["baseline_id"]))
    best = baseline_summary[0] if baseline_summary else {}
    delta_pp = (best.get("der") - final_der) * 100 if best.get("der") is not None and final_der == final_der else None
    beats_all = bool(baseline_summary) and all(row["der"] > final_der for row in baseline_summary if row.get("der") is not None)
    payload = {
        "runtime_contract": "clipped_baseline_fairness_audit_no_live_calls",
        "status": "pass" if beats_all and delta_pp is not None and delta_pp > 0 else "fail",
        "windows": len(keys),
        "variants": args.variants,
        "final_der": final_der,
        "best_clipped_baseline": best,
        "delta_vs_best_clipped_baseline_pp": delta_pp,
        "beats_all_clipped_baselines": beats_all,
        "baseline_summary": baseline_summary,
        "metric_claim_boundary": "same_window_cached_baselines_scored_after_runtime_window_clipping",
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "clipped_baseline_audit.json"
    md_path = args.output_dir / "clipped_baseline_audit.md"
    csv_path = args.output_dir / "clipped_baseline_scores.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    write_csv(
        csv_path,
        rows,
        [
            "baseline_id",
            "window_id",
            "recording_id",
            "window_size",
            "segment_idx",
            "der",
            "miss_rate",
            "fa_rate",
            "conf_rate",
            "pred_segments",
            "clip_window_clip_adjusted_segments",
            "clip_window_clip_dropped_segments",
            "clip_window_clip_trimmed_ms",
        ],
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    print(
        "status={status} final={final:.2%} best_clipped={best:.2%} delta={delta:.3f}pp beats_all={beats}".format(
            status=payload["status"],
            final=final_der,
            best=best.get("der"),
            delta=delta_pp,
            beats=beats_all,
        )
    )
    raise SystemExit(0 if payload["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
