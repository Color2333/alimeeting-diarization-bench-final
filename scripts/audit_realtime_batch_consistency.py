#!/usr/bin/env python3
"""Audit all-cached realtime batch output against corpus-level system output."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def weighted_average(rows: list[dict[str, Any]], value_key: str, weight_key: str) -> float | None:
    total_weight = 0
    total = 0.0
    for row in rows:
        value = row.get(value_key)
        weight = int(row.get(weight_key) or 0)
        if value is None or weight <= 0:
            continue
        total += as_float(value) * weight
        total_weight += weight
    return total / total_weight if total_weight else None


def check(condition: bool, severity: str, code: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "pass" if condition else severity,
        "code": code,
        "message": message,
        "detail": detail or {},
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Realtime Batch Consistency Audit",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Checks: `{payload['pass_count']}` pass, `{payload['warn_count']}` warn, `{payload['fail_count']}` fail",
        f"- Batch weighted final DER: `{payload['summary']['batch_weighted_final_der_pct']}`",
        f"- Corpus final DER: `{payload['summary']['corpus_final_der_pct']}`",
        f"- Absolute DER gap: `{payload['summary']['final_der_abs_gap_pp']:.6f}pp`",
        "",
        "| Status | Code | Message |",
        "|---|---|---|",
    ]
    for row in payload["checks"]:
        lines.append(f"| `{row['status']}` | `{row['code']}` | {row['message']} |")
    lines.extend(
        [
            "",
            "## Per Recording",
            "",
            "| Recording | Status | Windows | Final DER | Timeline |",
            "|---|---|---:|---:|---|",
        ]
    )
    for row in payload["items"]:
        final_der = f"{as_float(row.get('final_der')) * 100:.2f}%" if row.get("final_der") is not None else "n/a"
        lines.append(
            f"| `{row.get('recording_id')}` | `{row.get('status')}` | {row.get('windows_processed')} | "
            f"{final_der} | `{row.get('timeline_integrity_status')}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-summary", type=Path, default=Path("outputs/realtime_batch/all_cached/batch_summary.json"))
    parser.add_argument("--batch-summary-csv", type=Path, default=Path("outputs/realtime_batch/all_cached/batch_summary.csv"))
    parser.add_argument("--system-metrics", type=Path, default=Path("outputs/system_demo/all_cached_recordings/metrics.json"))
    parser.add_argument("--expected-recordings", type=int, default=8)
    parser.add_argument("--expected-windows", type=int, default=120)
    parser.add_argument("--max-final-der-gap-pp", type=float, default=0.0001)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/realtime_batch/audit"))
    args = parser.parse_args()

    batch = read_json(args.batch_summary)
    items = batch.get("items") or read_csv(args.batch_summary_csv)
    system_metrics = read_json(args.system_metrics)
    summary = batch.get("summary", {})
    corpus_final_der = system_metrics.get("metrics", {}).get("final_der")
    batch_weighted_final_der = weighted_average(items, "final_der", "windows_processed")
    reported_batch_final_der = summary.get("final_der")
    final_gap_pp = (
        abs(as_float(batch_weighted_final_der) - as_float(corpus_final_der)) * 100
        if batch_weighted_final_der is not None and corpus_final_der is not None
        else 999.0
    )
    checks = [
        check(bool(batch), "fail", "batch_summary_exists", "all-cached batch summary exists", {"path": str(args.batch_summary)}),
        check(
            batch.get("status") == "pass",
            "fail",
            "batch_status_pass",
            "all-cached batch completed with pass status",
            {"status": batch.get("status")},
        ),
        check(
            summary.get("items") == args.expected_recordings and summary.get("passed_items") == args.expected_recordings,
            "fail",
            "all_recordings_processed",
            "all expected cached recordings are processed and passed",
            {"summary": summary, "expected_recordings": args.expected_recordings},
        ),
        check(
            summary.get("windows_processed") == args.expected_windows,
            "fail",
            "all_windows_processed",
            "all expected cached windows are processed",
            {"windows_processed": summary.get("windows_processed"), "expected_windows": args.expected_windows},
        ),
        check(
            summary.get("timeline_integrity_passed_items") == summary.get("items"),
            "fail",
            "all_item_timeline_integrity_pass",
            "every batch item passed timeline integrity",
            {"summary": summary},
        ),
        check(
            summary.get("deepseek_api_calls") == 0 and summary.get("qwen_api_calls") == 0 and summary.get("omni_api_calls") == 0,
            "fail",
            "batch_zero_live_api_calls",
            "all-cached batch performs zero live API calls",
            {
                "deepseek": summary.get("deepseek_api_calls"),
                "qwen": summary.get("qwen_api_calls"),
                "omni": summary.get("omni_api_calls"),
            },
        ),
        check(
            summary.get("aggregation") == "window_weighted_by_windows_processed",
            "fail",
            "batch_uses_window_weighted_aggregation",
            "batch summary reports corpus DER using window-weighted aggregation rather than item-average aggregation",
            {"aggregation": summary.get("aggregation")},
        ),
        check(
            reported_batch_final_der is not None
            and batch_weighted_final_der is not None
            and abs(as_float(reported_batch_final_der) - batch_weighted_final_der) * 100 <= args.max_final_der_gap_pp,
            "fail",
            "batch_reported_der_is_weighted",
            "reported batch final DER equals recomputed window-weighted final DER",
            {
                "reported_batch_final_der": reported_batch_final_der,
                "recomputed_batch_weighted_final_der": batch_weighted_final_der,
            },
        ),
        check(
            final_gap_pp <= args.max_final_der_gap_pp,
            "fail",
            "batch_der_matches_corpus_demo",
            "weighted batch final DER matches corpus-level all-cached demo DER",
            {
                "batch_weighted_final_der": batch_weighted_final_der,
                "corpus_final_der": corpus_final_der,
                "final_der_abs_gap_pp": final_gap_pp,
                "max_final_der_gap_pp": args.max_final_der_gap_pp,
            },
        ),
    ]
    fail_count = sum(1 for row in checks if row["status"] == "fail")
    warn_count = sum(1 for row in checks if row["status"] == "warn")
    pass_count = sum(1 for row in checks if row["status"] == "pass")
    payload = {
        "runtime_contract": "offline_realtime_batch_consistency_no_live_calls",
        "status": "fail" if fail_count else ("warn" if warn_count else "pass"),
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "checks": checks,
        "summary": {
            "batch_summary": str(args.batch_summary),
            "system_metrics": str(args.system_metrics),
            "batch_weighted_final_der": batch_weighted_final_der,
            "reported_batch_final_der": reported_batch_final_der,
            "batch_final_der_item_avg": summary.get("final_der_item_avg"),
            "batch_weighted_final_der_pct": f"{batch_weighted_final_der * 100:.4f}%" if batch_weighted_final_der is not None else "n/a",
            "corpus_final_der": corpus_final_der,
            "corpus_final_der_pct": f"{as_float(corpus_final_der) * 100:.4f}%" if corpus_final_der is not None else "n/a",
            "final_der_abs_gap_pp": final_gap_pp,
        },
        "items": items,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "realtime_batch_consistency.json"
    md_path = args.output_dir / "realtime_batch_consistency.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "status={status} pass={passed} warn={warn} fail={fail} gap={gap:.6f}pp".format(
            status=payload["status"],
            passed=pass_count,
            warn=warn_count,
            fail=fail_count,
            gap=final_gap_pp,
        )
    )
    raise SystemExit(1 if fail_count else 0)


if __name__ == "__main__":
    main()
