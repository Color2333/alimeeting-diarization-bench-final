#!/usr/bin/env python3
"""Audit stage latency SLO status from the runtime latency budget ledger."""

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
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/stage_latency_slo_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/stage_latency_slo_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/stage_latency_slo_audit.csv")

P95_THRESHOLDS = {
    "fast_first_output": 1.0,
    "rule_writeback": 35.0,
    "runtime_safe_llm_guard": 65.0,
}
AVG_THRESHOLDS = {
    "fast_first_output": 1.0,
    "rule_writeback": 30.0,
    "runtime_safe_llm_guard": 50.0,
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float | None:
    try:
        if value in {"", None}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_row(row: dict[str, Any]) -> dict[str, Any]:
    stage_id = row.get("stage_id", "")
    claim_status = str(row.get("claim_status", ""))
    target_status = str(row.get("target_status", ""))
    avg = as_float(row.get("avg_seconds"))
    p95 = as_float(row.get("p95_seconds"))
    wall = as_float(row.get("wall_seconds"))
    avg_threshold = AVG_THRESHOLDS.get(stage_id)
    p95_threshold = P95_THRESHOLDS.get(stage_id)

    if claim_status.startswith("claim_now"):
        slo_class = "claim_now_slo_pass" if target_status == "pass" else "claim_now_slo_fail"
    elif "smoke" in claim_status:
        slo_class = "smoke_slo_pass" if target_status == "pass" else "smoke_only_or_incomplete"
    elif claim_status == "offline_budget_only":
        slo_class = "offline_budget_only"
    elif "pending" in claim_status or "blocked" in claim_status:
        slo_class = "pending_or_blocked"
    elif "fallback" in claim_status:
        slo_class = "fallback_only"
    else:
        slo_class = "not_claimable"

    if p95 is not None and p95_threshold is not None:
        p95_margin = round(p95_threshold - p95, 3)
    else:
        p95_margin = ""
    if avg is not None and avg_threshold is not None:
        avg_margin = round(avg_threshold - avg, 3)
    else:
        avg_margin = ""

    return {
        "stage_id": stage_id,
        "surface": row.get("surface", ""),
        "claim_status": claim_status,
        "target": row.get("target", ""),
        "target_status": target_status,
        "slo_class": slo_class,
        "avg_seconds": avg if avg is not None else "",
        "p95_seconds": p95 if p95 is not None else "",
        "wall_seconds": wall if wall is not None else "",
        "avg_threshold_seconds": avg_threshold if avg_threshold is not None else "",
        "p95_threshold_seconds": p95_threshold if p95_threshold is not None else "",
        "avg_margin_seconds": avg_margin,
        "p95_margin_seconds": p95_margin,
        "writeback_right": row.get("writeback_right", ""),
        "source_artifacts": row.get("source_artifacts", ""),
    }


def build_audit(root: Path) -> dict[str, Any]:
    ledger = read_json(root / "outputs/research_progress_snapshot/runtime_latency_budget_ledger.json")
    rows = [classify_row(row) for row in ledger.get("rows", [])]
    claim_rows = [row for row in rows if str(row["slo_class"]).startswith("claim_now")]
    failed_claim_rows = [row["stage_id"] for row in claim_rows if row["slo_class"] != "claim_now_slo_pass"]
    smoke_rows = [row for row in rows if str(row["slo_class"]).startswith("smoke")]
    pending_rows = [row for row in rows if row["slo_class"] == "pending_or_blocked"]
    min_p95_margin = min(
        [float(row["p95_margin_seconds"]) for row in claim_rows if row["p95_margin_seconds"] not in {"", None}],
        default=None,
    )
    guard_row = next((row for row in rows if row["stage_id"] == "runtime_safe_llm_guard"), {})
    return {
        "runtime_contract": "stage_latency_slo_audit_from_latency_ledger_no_live_calls",
        "status": "pass" if not failed_claim_rows else "fail",
        "source_ledger_contract": ledger.get("runtime_contract", ""),
        "summary": {
            "row_count": len(rows),
            "claim_now_slo_rows": len(claim_rows),
            "claim_now_slo_pass": sum(1 for row in claim_rows if row["slo_class"] == "claim_now_slo_pass"),
            "claim_now_slo_fail": len(failed_claim_rows),
            "smoke_rows": len(smoke_rows),
            "pending_or_blocked_rows": len(pending_rows),
            "offline_budget_rows": sum(1 for row in rows if row["slo_class"] == "offline_budget_only"),
            "fallback_rows": sum(1 for row in rows if row["slo_class"] == "fallback_only"),
            "failed_claim_rows": failed_claim_rows,
            "min_claim_p95_margin_seconds": min_p95_margin if min_p95_margin is not None else "",
            "guard_p95_margin_seconds": guard_row.get("p95_margin_seconds", ""),
            "live_calls_performed_by_builder": 0,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(audit: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "stage_id",
        "surface",
        "claim_status",
        "target",
        "target_status",
        "slo_class",
        "avg_seconds",
        "p95_seconds",
        "wall_seconds",
        "avg_threshold_seconds",
        "p95_threshold_seconds",
        "avg_margin_seconds",
        "p95_margin_seconds",
        "writeback_right",
        "source_artifacts",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit["rows"])


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    lines = [
        "# Stage Latency SLO Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Claim-now SLO pass: `{summary['claim_now_slo_pass']}/{summary['claim_now_slo_rows']}`",
        f"- Smoke rows: `{summary['smoke_rows']}`",
        f"- Pending/blocked rows: `{summary['pending_or_blocked_rows']}`",
        f"- Min claim P95 margin: `{summary['min_claim_p95_margin_seconds']}`",
        f"- Guard P95 margin: `{summary['guard_p95_margin_seconds']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Stage | Claim status | SLO class | Avg | P95 | Wall | Target | P95 margin |",
        "|---|---|---|---:|---:|---:|---|---:|",
    ]
    for row in audit["rows"]:
        lines.append(
            f"| `{row['stage_id']}` | `{row['claim_status']}` | `{row['slo_class']}` | "
            f"{row['avg_seconds'] or 'n/a'} | {row['p95_seconds'] or 'n/a'} | {row['wall_seconds'] or 'n/a'} | "
            f"`{row['target']}` | {row['p95_margin_seconds'] or 'n/a'} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This audit derives SLO status from the latency ledger; it performs no model calls and creates no new metric claim.",
            "- Claim-now rows must pass their explicit SLO targets before they can be used as report-level latency claims.",
            "- Smoke rows can support readiness or routing evidence, but not full-surface claims.",
            "- Pending/blocked rows remain excluded from claim-now latency until live outputs and scoring artifacts exist.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    audit = build_audit(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(audit, args.output_md)
    write_csv(audit, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
