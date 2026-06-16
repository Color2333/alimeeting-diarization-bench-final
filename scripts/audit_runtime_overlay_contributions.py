#!/usr/bin/env python3
"""Audit marginal contribution and risk of runtime overlay sources."""

from __future__ import annotations

import argparse
import csv
import json
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def average(values: list[float]) -> float | None:
    values = [value for value in values if value == value]
    return sum(values) / len(values) if values else None


def load_baseline_scores(path: Path) -> dict[str, dict[str, float]]:
    scores: dict[str, dict[str, float]] = defaultdict(dict)
    for row in read_csv(path):
        scores[str(row["window_id"])][str(row["baseline_id"])] = as_float(row.get("der"), default=float("nan"))
    return scores


def check(condition: bool, severity: str, code: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "pass" if condition else severity,
        "code": code,
        "message": message,
        "detail": detail or {},
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Runtime Overlay Contribution Audit",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Overlay windows: `{payload['summary']['overlay_windows']}`",
        f"- Contribution vs clipped Slow: `{payload['summary']['overlay_contribution_vs_slow_pp']:.4f}pp`",
        f"- Final margin vs clipped Slow: `{payload['summary']['final_margin_vs_clipped_slow_pp']:.4f}pp`",
        f"- Negative overlay windows: `{payload['summary']['negative_overlay_windows_vs_slow']}`",
        "",
        "## By Source",
        "",
        "| Source | Windows | Contribution | Avg Delta | Negative Windows | Recordings |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in payload["source_summary"]:
        lines.append(
            "| `{source}` | {windows} | {contrib:.4f}pp | {avg:.3f}pp | {neg} | `{recs}` |".format(
                source=row["final_source"],
                windows=row["windows"],
                contrib=row["global_contribution_vs_slow_pp"],
                avg=row["avg_delta_vs_slow_pp"],
                neg=row["negative_windows_vs_slow"],
                recs=",".join(row["recording_ids"]),
            )
        )
    lines.extend(
        [
            "",
            "## Overlay Windows",
            "",
            "| Window | Source | Recording | Final DER | Slow DER | Delta vs Slow | Fast DER |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in payload["overlay_windows"]:
        lines.append(
            "| `{window_id}` | `{source}` | `{recording_id}` | {final:.2%} | {slow:.2%} | {delta:.3f}pp | {fast:.2%} |".format(
                window_id=row["window_id"],
                source=row["final_source"],
                recording_id=row["recording_id"],
                final=row["final_der"],
                slow=row["slow_der"],
                delta=row["delta_vs_slow_pp"],
                fast=row["fast_der"],
            )
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Contributions are measured against the clipped Slow baseline on the same windows.",
            "- A pass means every active overlay source has non-negative aggregate contribution and no window-level regression versus clipped Slow.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/window_metrics.csv"))
    parser.add_argument("--clipped-baseline-scores", type=Path, default=Path("outputs/clipped_baseline_audit/clipped_baseline_scores.csv"))
    parser.add_argument("--clipped-baseline-audit", type=Path, default=Path("outputs/clipped_baseline_audit/clipped_baseline_audit.json"))
    parser.add_argument("--baseline-id", default="slow_base")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/runtime_overlay_contributions"))
    args = parser.parse_args()

    window_rows = read_csv(args.window_metrics)
    baseline_scores = load_baseline_scores(args.clipped_baseline_scores)
    clipped_audit = read_json(args.clipped_baseline_audit)
    total_windows = len(window_rows)
    detail_rows = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in window_rows:
        window_id = str(row["window_id"])
        final_der = as_float(row.get("final_der"), default=float("nan"))
        slow_der = baseline_scores.get(window_id, {}).get(args.baseline_id, float("nan"))
        fast_der = baseline_scores.get(window_id, {}).get("fast_base", float("nan"))
        source = str(row.get("final_source", ""))
        delta = slow_der - final_der
        detail = {
            "window_id": window_id,
            "recording_id": row.get("recording_id"),
            "window_size": row.get("window_size"),
            "segment_idx": row.get("segment_idx"),
            "final_source": source,
            "final_der": final_der,
            "slow_der": slow_der,
            "fast_der": fast_der,
            "delta_vs_slow": delta,
            "delta_vs_slow_pp": delta * 100,
            "is_overlay": source != "slow",
            "negative_vs_slow": delta < -1e-12,
        }
        detail_rows.append(detail)
        grouped[source].append(detail)

    source_summary = []
    for source, rows in sorted(grouped.items()):
        delta_sum = sum(as_float(row["delta_vs_slow"]) for row in rows)
        source_summary.append(
            {
                "final_source": source,
                "windows": len(rows),
                "recording_ids": sorted({str(row["recording_id"]) for row in rows}),
                "avg_final_der": average([as_float(row["final_der"], default=float("nan")) for row in rows]),
                "avg_slow_der": average([as_float(row["slow_der"], default=float("nan")) for row in rows]),
                "avg_delta_vs_slow_pp": (delta_sum / len(rows)) * 100 if rows else 0.0,
                "total_delta_vs_slow_pp": delta_sum * 100,
                "global_contribution_vs_slow_pp": (delta_sum / total_windows) * 100 if total_windows else 0.0,
                "negative_windows_vs_slow": sum(1 for row in rows if row["negative_vs_slow"]),
            }
        )
    overlay_rows = [row for row in detail_rows if row["is_overlay"]]
    overlay_contribution_pp = sum(as_float(row["delta_vs_slow"]) for row in overlay_rows) / total_windows * 100 if total_windows else 0.0
    final_margin_pp = as_float(clipped_audit.get("delta_vs_best_clipped_baseline_pp"), default=float("nan"))
    margin_gap_pp = abs(overlay_contribution_pp - final_margin_pp) if final_margin_pp == final_margin_pp else 999.0
    active_overlay_sources = [row for row in source_summary if row["final_source"] != "slow"]
    checks = [
        check(bool(window_rows), "fail", "window_metrics_exist", "window metrics are readable", {"path": str(args.window_metrics)}),
        check(bool(baseline_scores), "fail", "clipped_scores_exist", "clipped baseline scores are readable", {"path": str(args.clipped_baseline_scores)}),
        check(
            all(row["total_delta_vs_slow_pp"] >= -1e-9 for row in active_overlay_sources),
            "fail",
            "overlay_sources_non_negative",
            "every active overlay source has non-negative aggregate contribution versus clipped Slow",
            {"source_summary": active_overlay_sources},
        ),
        check(
            sum(row["negative_windows_vs_slow"] for row in active_overlay_sources) == 0,
            "fail",
            "no_negative_overlay_windows",
            "no active overlay window regresses versus clipped Slow",
            {"source_summary": active_overlay_sources},
        ),
        check(
            margin_gap_pp <= 1e-6,
            "fail",
            "overlay_contribution_matches_margin",
            "sum of overlay contributions explains the final margin over clipped Slow",
            {"overlay_contribution_pp": overlay_contribution_pp, "final_margin_pp": final_margin_pp, "gap_pp": margin_gap_pp},
        ),
    ]
    fail_count = sum(1 for row in checks if row["status"] == "fail")
    warn_count = sum(1 for row in checks if row["status"] == "warn")
    pass_count = sum(1 for row in checks if row["status"] == "pass")
    payload = {
        "runtime_contract": "runtime_overlay_contribution_audit_no_live_calls_clipped_baseline_reference",
        "status": "fail" if fail_count else ("warn" if warn_count else "pass"),
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "checks": checks,
        "summary": {
            "windows": total_windows,
            "overlay_windows": len(overlay_rows),
            "overlay_sources": len(active_overlay_sources),
            "overlay_contribution_vs_slow_pp": overlay_contribution_pp,
            "final_margin_vs_clipped_slow_pp": final_margin_pp,
            "overlay_margin_gap_pp": margin_gap_pp,
            "negative_overlay_windows_vs_slow": sum(1 for row in overlay_rows if row["negative_vs_slow"]),
        },
        "source_summary": source_summary,
        "overlay_windows": overlay_rows,
        "metric_claim_boundary": "same_window_clipped_slow_comparison_not_true_heldout",
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "runtime_overlay_contributions.json"
    md_path = args.output_dir / "runtime_overlay_contributions.md"
    detail_csv = args.output_dir / "runtime_overlay_contribution_windows.csv"
    source_csv = args.output_dir / "runtime_overlay_contribution_sources.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    write_csv(detail_csv, detail_rows)
    write_csv(source_csv, source_summary)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {detail_csv}")
    print(f"Wrote {source_csv}")
    print(
        "status={status} overlays={overlays} contribution={contrib:.4f}pp margin={margin:.4f}pp negative={negative}".format(
            status=payload["status"],
            overlays=len(overlay_rows),
            contrib=overlay_contribution_pp,
            margin=final_margin_pp,
            negative=payload["summary"]["negative_overlay_windows_vs_slow"],
        )
    )
    raise SystemExit(1 if fail_count else 0)


if __name__ == "__main__":
    main()
