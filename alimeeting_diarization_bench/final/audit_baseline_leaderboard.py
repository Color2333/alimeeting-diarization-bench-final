#!/usr/bin/env python3
"""Build an apples-to-apples leaderboard over discovered baseline artifacts.

The system metric already compares against the runtime same-window baselines.
This audit widens the claim boundary by scanning historical summary artifacts
and separating full current-window coverage from partial/smoke runs.
"""

from __future__ import annotations

# Keep final modules import-compatible when executed with python -m.
import sys as _sys
from pathlib import Path as _Path
_SCRIPT_ROOT = _Path(__file__).resolve().parent
_REPO_ROOT = _Path(__file__).resolve().parents[2]
for _candidate in [_REPO_ROOT, _SCRIPT_ROOT, *_SCRIPT_ROOT.iterdir()]:
    if _candidate.is_dir():
        _value = str(_candidate)
        if _value not in _sys.path:
            _sys.path.insert(0, _value)

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def window_id_from_result(row: dict[str, Any]) -> str | None:
    recording_id = row.get("recording_id")
    window_size = row.get("window_size")
    segment_idx = row.get("segment_idx")
    if recording_id is not None and window_size is not None and segment_idx is not None:
        return f"{recording_id}:{int(window_size)}:{int(segment_idx)}"

    key = str(row.get("key", ""))
    parts = key.split("|")
    if len(parts) >= 3 and parts[1].startswith("ws") and parts[2].startswith("seg"):
        try:
            return f"{parts[0]}:{int(parts[1][2:])}:{int(parts[2][3:])}"
        except ValueError:
            return None
    return None


def model_label(path: Path, payload: dict[str, Any]) -> str:
    model = payload.get("model_name") or path.parent.name
    mode = payload.get("speaker_count_mode")
    root = path.parent.parent.name if path.parent.parent.name != "outputs" else path.parent.name
    bits = [root, str(model)]
    if mode not in (None, ""):
        bits.append(f"spk_{mode}")
    return "/".join(bits)


def summarize_results(path: Path, payload: dict[str, Any], selected_windows: set[str]) -> dict[str, Any] | None:
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return None

    overlap: list[dict[str, Any]] = []
    seen_windows: set[str] = set()
    for row in results:
        if not isinstance(row, dict):
            continue
        if row.get("success") is False:
            continue
        wid = window_id_from_result(row)
        der = as_float(row.get("der"))
        if wid is None or der is None:
            continue
        if wid in selected_windows and wid not in seen_windows:
            overlap.append(row)
            seen_windows.add(wid)

    if not overlap:
        return None

    der_values = [float(row["der"]) for row in overlap]
    miss_values = [as_float(row.get("miss_rate")) for row in overlap]
    fa_values = [as_float(row.get("fa_rate")) for row in overlap]
    conf_values = [as_float(row.get("conf_rate")) for row in overlap]
    lat_values = [as_float(row.get("latency")) for row in overlap]
    coverage = len(seen_windows) / len(selected_windows) if selected_windows else 0.0
    return {
        "candidate_id": model_label(path, payload),
        "source_type": "historical_summary_results",
        "path": str(path),
        "coverage_windows": len(seen_windows),
        "expected_windows": len(selected_windows),
        "coverage_ratio": coverage,
        "comparable_scope": "full_current_window_pool" if seen_windows == selected_windows else "partial_overlap_only",
        "der": sum(der_values) / len(der_values),
        "miss_rate": avg_present(miss_values),
        "fa_rate": avg_present(fa_values),
        "conf_rate": avg_present(conf_values),
        "avg_latency": avg_present(lat_values),
        "reported_avg_der": payload.get("avg_der"),
        "reported_total_segments": payload.get("total_segments"),
        "reported_successful": payload.get("successful"),
        "missing_windows": sorted(selected_windows - seen_windows)[:20],
    }


def avg_present(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def runtime_baseline_rows(baseline_path: Path, expected_windows: int) -> list[dict[str, Any]]:
    if not baseline_path.exists():
        return []
    payload = read_json(baseline_path)
    if not isinstance(payload, list):
        return []
    rows = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        der = as_float(row.get("der"))
        if der is None:
            continue
        rows.append(
            {
                "candidate_id": f"runtime_same_window/{row.get('baseline_id')}",
                "source_type": "runtime_baseline_comparison",
                "path": str(baseline_path),
                "coverage_windows": row.get("windows", expected_windows),
                "expected_windows": expected_windows,
                "coverage_ratio": 1.0 if row.get("windows", expected_windows) == expected_windows else None,
                "comparable_scope": "full_current_window_pool",
                "der": der,
                "miss_rate": row.get("miss_rate"),
                "fa_rate": row.get("fa_rate"),
                "conf_rate": row.get("conf_rate"),
                "avg_latency": None,
                "reported_avg_der": der,
                "reported_total_segments": row.get("windows", expected_windows),
                "reported_successful": row.get("windows", expected_windows),
                "missing_windows": [],
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], final_der: float) -> None:
    fields = [
        "rank",
        "candidate_id",
        "source_type",
        "comparable_scope",
        "coverage_windows",
        "expected_windows",
        "der",
        "delta_vs_final_pp",
        "beats_final",
        "avg_latency",
        "path",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(rows, 1):
            der = float(row["der"])
            writer.writerow(
                {
                    "rank": i,
                    "candidate_id": row["candidate_id"],
                    "source_type": row["source_type"],
                    "comparable_scope": row["comparable_scope"],
                    "coverage_windows": row["coverage_windows"],
                    "expected_windows": row["expected_windows"],
                    "der": f"{der:.8f}",
                    "delta_vs_final_pp": f"{(der - final_der) * 100:.6f}",
                    "beats_final": der < final_der,
                    "avg_latency": "" if row.get("avg_latency") is None else f"{float(row['avg_latency']):.4f}",
                    "path": row["path"],
                }
            )


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Baseline Leaderboard Audit",
        "",
        f"- Status: `{payload['status']}`",
        f"- Final DER: `{summary['final_der_pct']}`",
        f"- Full-coverage baselines: `{summary['full_coverage_baselines']}`",
        f"- Beats all full-coverage baselines: `{summary['beats_all_full_coverage_baselines']}`",
        f"- Best full baseline: `{summary.get('best_full_coverage_baseline')}` / `{summary.get('best_full_coverage_der_pct')}`",
        f"- Partial/non-comparable candidates: `{summary['partial_or_noncomparable_candidates']}`",
        "",
        "## Full Current-Window Pool",
        "",
        "| Rank | Candidate | DER | Delta vs Final | Source |",
        "|---:|---|---:|---:|---|",
    ]
    for i, row in enumerate(payload["full_coverage_leaderboard"][:20], 1):
        lines.append(
            "| {rank} | `{candidate}` | {der:.4%} | {delta:.4f}pp | `{source}` |".format(
                rank=i,
                candidate=row["candidate_id"],
                der=float(row["der"]),
                delta=(float(row["der"]) - float(summary["final_der"])) * 100,
                source=row["source_type"],
            )
        )
    lines.extend(
        [
            "",
            "## Partial / Not Final-Comparable",
            "",
            "| Candidate | Coverage | DER on overlap | Note |",
            "|---|---:|---:|---|",
        ]
    )
    for row in payload["partial_or_noncomparable"][:30]:
        lines.append(
            "| `{candidate}` | {coverage}/{expected} | {der:.4%} | `{scope}` |".format(
                candidate=row["candidate_id"],
                coverage=row["coverage_windows"],
                expected=row["expected_windows"],
                der=float(row["der"]),
                scope=row["comparable_scope"],
            )
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Only `full_current_window_pool` rows can support the current all-cached metric claim.",
            "- Partial runs are useful signals, but they cannot prove the final system beats all baselines over the full 120-window development pool.",
            "- This audit uses existing artifacts only and performs no model inference or live API calls.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/metrics.json"))
    parser.add_argument(
        "--runtime-baseline-comparison",
        type=Path,
        default=Path("outputs/system_demo/all_cached_recordings/baseline_comparison.json"),
    )
    parser.add_argument("--scan-root", type=Path, default=Path("outputs"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/baseline_leaderboard_audit"))
    args = parser.parse_args()

    metrics = read_json(args.metrics)
    selected_windows = set(metrics.get("selected_window_ids") or [])
    final_der = as_float(metrics.get("metrics", {}).get("final_der"))
    if not selected_windows or final_der is None:
        raise SystemExit("metrics must contain selected_window_ids and metrics.final_der")

    candidates = runtime_baseline_rows(args.runtime_baseline_comparison, len(selected_windows))
    for path in sorted(args.scan_root.rglob("summary.json")):
        try:
            payload = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        row = summarize_results(path, payload, selected_windows)
        if row is not None:
            candidates.append(row)

    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["candidate_id"], row["path"])
        current = dedup.get(key)
        if current is None or int(row["coverage_windows"]) > int(current["coverage_windows"]):
            dedup[key] = row
    candidates = list(dedup.values())

    full = sorted(
        [row for row in candidates if row["comparable_scope"] == "full_current_window_pool"],
        key=lambda row: float(row["der"]),
    )
    partial = sorted(
        [row for row in candidates if row["comparable_scope"] != "full_current_window_pool"],
        key=lambda row: (-int(row["coverage_windows"]), float(row["der"])),
    )
    stronger = [row for row in full if float(row["der"]) < final_der]
    best = full[0] if full else None
    payload = {
        "runtime_contract": "baseline_leaderboard_audit_no_live_calls",
        "status": "pass" if full and not stronger else ("fail" if stronger else "warn_no_full_coverage_baselines"),
        "summary": {
            "final_der": final_der,
            "final_der_pct": f"{final_der * 100:.4f}%",
            "selected_windows": len(selected_windows),
            "discovered_candidates": len(candidates),
            "full_coverage_baselines": len(full),
            "partial_or_noncomparable_candidates": len(partial),
            "beats_all_full_coverage_baselines": bool(full and not stronger),
            "best_full_coverage_baseline": best.get("candidate_id") if best else None,
            "best_full_coverage_der": best.get("der") if best else None,
            "best_full_coverage_der_pct": f"{float(best['der']) * 100:.4f}%" if best else None,
            "delta_vs_best_full_coverage_pp": (float(best["der"]) - final_der) * 100 if best else None,
            "stronger_full_coverage_baselines": [row["candidate_id"] for row in stronger],
            "metric_claim_boundary": "full_current_window_pool_only",
        },
        "full_coverage_leaderboard": full,
        "partial_or_noncomparable": partial,
        "inputs": {
            "metrics": str(args.metrics),
            "runtime_baseline_comparison": str(args.runtime_baseline_comparison),
            "scan_root": str(args.scan_root),
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "baseline_leaderboard_audit.json"
    csv_path = args.output_dir / "baseline_leaderboard_audit.csv"
    md_path = args.output_dir / "baseline_leaderboard_audit.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(csv_path, full + partial, final_der)
    write_markdown(md_path, payload)
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    print(
        "status={status} full={full} partial={partial} best={best} delta_pp={delta}".format(
            status=payload["status"],
            full=payload["summary"]["full_coverage_baselines"],
            partial=payload["summary"]["partial_or_noncomparable_candidates"],
            best=payload["summary"]["best_full_coverage_baseline"],
            delta=payload["summary"]["delta_vs_best_full_coverage_pp"],
        )
    )
    raise SystemExit(1 if payload["status"] == "fail" else 0)


if __name__ == "__main__":
    main()
