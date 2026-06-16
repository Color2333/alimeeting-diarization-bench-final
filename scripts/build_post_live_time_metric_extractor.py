#!/usr/bin/env python3
"""Extract post-live time metrics from live output files without live calls."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_time_metric_extractor.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_time_metric_extractor.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_time_metric_extractor.csv")

DEEPSEEK_RESUME_JSONL = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl")
DEEPSEEK_RESUME_SUMMARY = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_summary.json")
QWEN_FULL_JSONL = Path("outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl")
QWEN_FULL_SUMMARY = Path("outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_summary.json")
OMNI48_JSONL = Path("outputs/omni_guard/omni_expansion_48_live.jsonl")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        return [], 0
    rows: list[dict[str, Any]] = []
    parse_errors = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                parse_errors += 1
    return rows, parse_errors


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any) -> float | None:
    try:
        if value in {"", None}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return round(ordered[idx], 3)


def avg(values: list[float]) -> float:
    return round(mean(values), 3) if values else 0.0


def success_rows(rows: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    if kind == "omni":
        return [row for row in rows if not row.get("error") and row.get("schema_ok") is not False]
    return [row for row in rows if not row.get("error") and row.get("window_decision") not in {"", None, "error"}]


def values(rows: list[dict[str, Any]], field: str) -> list[float]:
    output: list[float] = []
    for row in rows:
        value = as_float(row.get(field))
        if value is not None:
            output.append(value)
    return output


def row_for_surface(
    *,
    time_metric_id: str,
    priority: str,
    surface_id: str,
    kind: str,
    output_path: Path,
    summary_path: Path | None,
    expected_rows: int,
    promotion_gate: str,
    claim_boundary: str,
) -> dict[str, Any]:
    full_output_path = ROOT / output_path
    rows, parse_errors = read_jsonl(full_output_path)
    successful = success_rows(rows, kind)
    call_seconds = values(successful, "call_seconds")
    first_text_seconds = values(successful, "first_text_seconds")
    call_attempts = [as_int(row.get("call_attempts"), 1) for row in successful]
    retry_rows = sum(1 for item in call_attempts if item > 1)
    summary = read_json(ROOT / summary_path) if summary_path else {}
    missing_rows = max(expected_rows - len(successful), 0)
    if not full_output_path.exists():
        status = "blocked_missing_output"
    elif parse_errors:
        status = "blocked_parse_errors"
    elif len(successful) < expected_rows:
        status = "blocked_partial_output"
    else:
        status = "ready_for_time_metric_review"
    return {
        "time_metric_id": time_metric_id,
        "priority": priority,
        "surface_id": surface_id,
        "kind": kind,
        "status": status,
        "output_jsonl": str(output_path),
        "summary_json": str(summary_path) if summary_path else "",
        "output_exists": full_output_path.exists(),
        "summary_exists": bool(summary_path and (ROOT / summary_path).exists()),
        "expected_rows": expected_rows,
        "observed_rows": len(rows),
        "successful_rows": len(successful),
        "missing_rows": missing_rows,
        "parse_errors": parse_errors,
        "avg_call_seconds": avg(call_seconds),
        "p50_call_seconds": quantile(call_seconds, 0.50),
        "p95_call_seconds": quantile(call_seconds, 0.95),
        "max_call_seconds": round(max(call_seconds), 3) if call_seconds else 0.0,
        "avg_first_text_seconds": avg(first_text_seconds),
        "p95_first_text_seconds": quantile(first_text_seconds, 0.95),
        "retry_rows": retry_rows,
        "wall_seconds": summary.get("wall_seconds", ""),
        "promotion_gate": promotion_gate,
        "claim_boundary": claim_boundary,
    }


def build_extractor(root: Path) -> dict[str, Any]:
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    stats_plan = read_json(root / "outputs/research_progress_snapshot/post_live_time_metric_statistics_plan.json")
    schema = read_json(root / "outputs/research_progress_snapshot/live_output_schema_contract.json")
    bundle = read_json(root / "outputs/research_progress_snapshot/live_execution_bundle.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")

    output_summary = output_audit.get("summary", {})
    stats_summary = stats_plan.get("summary", {})
    schema_summary = schema.get("summary", {})
    bundle_summary = bundle.get("summary", {})
    promotion_summary = promotion.get("summary", {})
    trace_summary = traceability.get("summary", {})

    rows = [
        row_for_surface(
            time_metric_id="deepseek_resume_time_metric_extract",
            priority="P0",
            surface_id="deepseek_resume_after_top3",
            kind="llm",
            output_path=DEEPSEEK_RESUME_JSONL,
            summary_path=DEEPSEEK_RESUME_SUMMARY,
            expected_rows=as_int(stats_summary.get("p0_planned_live_calls")),
            promotion_gate="deepseek_split20_resume_latency",
            claim_boundary="not_claimable_until_resume_output_audit_scoring_and_traceability",
        ),
        row_for_surface(
            time_metric_id="qwen_backup_time_metric_extract",
            priority="P1",
            surface_id="qwen_full_backup",
            kind="llm",
            output_path=QWEN_FULL_JSONL,
            summary_path=QWEN_FULL_SUMMARY,
            expected_rows=147,
            promotion_gate="qwen_full_backup_claim",
            claim_boundary="fallback_only_not_primary_latency_claim",
        ),
        row_for_surface(
            time_metric_id="omni48_label_time_metric_extract",
            priority="P1",
            surface_id="omni48_label_only",
            kind="omni",
            output_path=OMNI48_JSONL,
            summary_path=None,
            expected_rows=96,
            promotion_gate="omni48_label_metrics",
            claim_boundary="label_only_latency_not_guard_or_timeline_claim",
        ),
    ]
    missing = [row for row in rows if row["status"] == "blocked_missing_output"]
    ready = [row for row in rows if row["status"] == "ready_for_time_metric_review"]
    blocked = [row for row in rows if str(row["status"]).startswith("blocked")]
    return {
        "runtime_contract": "post_live_time_metric_extractor_no_live_calls",
        "status": "blocked_waiting_live_outputs" if blocked else "ready_for_time_metric_review",
        "source_contracts": {
            "live_output_audit": output_audit.get("runtime_contract", ""),
            "post_live_time_metric_statistics_plan": stats_plan.get("runtime_contract", ""),
            "live_output_schema_contract": schema.get("runtime_contract", ""),
            "live_execution_bundle": bundle.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "summary": {
            "extractor_rows": len(rows),
            "p0_extractor_rows": sum(1 for row in rows if row["priority"] == "P0"),
            "p1_extractor_rows": sum(1 for row in rows if row["priority"] == "P1"),
            "missing_output_rows": len(missing),
            "blocked_extractor_rows": len(blocked),
            "ready_time_metric_rows": len(ready),
            "computed_time_metric_rows": sum(1 for row in rows if row["successful_rows"] > 0),
            "expected_rows_total": sum(as_int(row["expected_rows"]) for row in rows),
            "observed_rows_total": sum(as_int(row["observed_rows"]) for row in rows),
            "successful_rows_total": sum(as_int(row["successful_rows"]) for row in rows),
            "parse_error_rows": sum(as_int(row["parse_errors"]) for row in rows),
            "retry_rows_total": sum(as_int(row["retry_rows"]) for row in rows),
            "expected_live_calls": as_int(output_summary.get("expected_live_calls")),
            "missing_output_surfaces": as_int(output_summary.get("missing_output_surfaces")),
            "time_stat_rows": as_int(stats_summary.get("time_stat_rows")),
            "schema_contract_count": as_int(schema_summary.get("schema_contract_count")),
            "planned_live_calls": as_int(bundle_summary.get("planned_live_calls")),
            "p0_planned_live_calls": as_int(bundle_summary.get("p0_planned_live_calls")),
            "ready_to_promote_count": as_int(promotion_summary.get("ready_to_promote_count")),
            "traceability_rows": as_int(trace_summary.get("traceability_rows")),
            "live_calls_performed_by_builder": 0,
            "no_scoring_commands_executed": True,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(extractor: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "time_metric_id",
        "priority",
        "surface_id",
        "kind",
        "status",
        "output_jsonl",
        "expected_rows",
        "observed_rows",
        "successful_rows",
        "missing_rows",
        "parse_errors",
        "avg_call_seconds",
        "p50_call_seconds",
        "p95_call_seconds",
        "max_call_seconds",
        "avg_first_text_seconds",
        "p95_first_text_seconds",
        "retry_rows",
        "wall_seconds",
        "promotion_gate",
        "claim_boundary",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in extractor["rows"]:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_markdown(extractor: dict[str, Any], path: Path) -> None:
    summary = extractor["summary"]
    lines = [
        "# Post-Live Time Metric Extractor",
        "",
        f"- Runtime contract: `{extractor['runtime_contract']}`",
        f"- Status: `{extractor['status']}`",
        f"- Extractor rows: `{summary['extractor_rows']}`",
        f"- P0 / P1 rows: `{summary['p0_extractor_rows']}` / `{summary['p1_extractor_rows']}`",
        f"- Missing output rows: `{summary['missing_output_rows']}`",
        f"- Blocked extractor rows: `{summary['blocked_extractor_rows']}`",
        f"- Ready time metric rows: `{summary['ready_time_metric_rows']}`",
        f"- Computed time metric rows: `{summary['computed_time_metric_rows']}`",
        f"- Expected rows total: `{summary['expected_rows_total']}`",
        f"- Observed rows total: `{summary['observed_rows_total']}`",
        f"- Successful rows total: `{summary['successful_rows_total']}`",
        f"- Parse error rows: `{summary['parse_error_rows']}`",
        f"- Retry rows total: `{summary['retry_rows_total']}`",
        f"- Expected live calls: `{summary['expected_live_calls']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- Time statistic rows: `{summary['time_stat_rows']}`",
        f"- Planned live calls: `{summary['planned_live_calls']}`",
        f"- P0 planned live calls: `{summary['p0_planned_live_calls']}`",
        f"- Ready to promote: `{summary['ready_to_promote_count']}`",
        f"- Traceability rows: `{summary['traceability_rows']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No scoring commands executed: `{summary['no_scoring_commands_executed']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Metric | Priority | Surface | Status | Expected | Observed | Avg | P50 | P95 | Max | Boundary |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in extractor["rows"]:
        lines.append(
            f"| `{row['time_metric_id']}` | `{row['priority']}` | `{row['surface_id']}` | "
            f"`{row['status']}` | {row['expected_rows']} | {row['observed_rows']} | "
            f"{row['avg_call_seconds']} | {row['p50_call_seconds']} | {row['p95_call_seconds']} | "
            f"{row['max_call_seconds']} | `{row['claim_boundary']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This extractor reads pending live output JSONL files only; it performs no live/API/model/scoring calls.",
            "- It computes time metrics only when the expected live rows exist and parse cleanly.",
            "- DeepSeek remains unclaimable until output audit, safety scoring, comparison, promotion, and traceability pass.",
            "- Qwen remains fallback-only and Omni48 remains label-only, so this extractor does not create a primary timeline latency claim.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    extractor = build_extractor(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(extractor, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(extractor, args.output_md)
    write_csv(extractor, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
