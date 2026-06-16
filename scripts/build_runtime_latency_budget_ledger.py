#!/usr/bin/env python3
"""Build a latency budget ledger across runtime and pending live-agent paths."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/runtime_latency_budget_ledger.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/runtime_latency_budget_ledger.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/runtime_latency_budget_ledger.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl_first(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                return json.loads(line)
    return {}


def seconds(value: Any) -> float | None:
    try:
        if value in {"", None}:
            return None
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def pass_if(value: float | None, threshold: float | None, op: str = "le") -> str:
    if value is None or threshold is None:
        return "not_applicable"
    if op == "lt":
        return "pass" if value < threshold else "fail"
    return "pass" if value <= threshold else "fail"


def build_ledger(root: Path) -> dict[str, Any]:
    timeline = read_json(root / "outputs/system_timeline/summary.json")
    llm_latency = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_latency_summary.json")
    split_sim = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation_summary.json")
    split_top3 = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_comparison.json")
    qwen_top45 = read_json(root / "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json")
    live_agent = read_json(root / "outputs/research_progress_snapshot/live_agent_execution_plan.json")
    postrun = read_json(root / "outputs/research_progress_snapshot/live_postrun_metrics_closure.json")
    omni_realtime = read_jsonl_first(root / "outputs/omni_guard/qwen35_omni_flash_realtime_guard_8s.jsonl")

    split_policy = split_sim.get("recommended_policy", {})
    live_steps = {step.get("step_id"): step for step in live_agent.get("steps", [])}
    postrun_summary = postrun.get("summary", {})
    qwen_run = (qwen_top45.get("runs") or [{}])[0]

    rows = [
        {
            "stage_id": "fast_first_output",
            "surface": "runtime_120_windows",
            "metric": "first_visible_update_avg_p95",
            "avg_seconds": seconds(timeline.get("fast_avg_delay_sec")),
            "p95_seconds": seconds(timeline.get("fast_p95_delay_sec")),
            "wall_seconds": "",
            "target": "avg<=1s_and_p95<=1s",
            "target_status": (
                "pass"
                if pass_if(seconds(timeline.get("fast_avg_delay_sec")), 1.0) == "pass"
                and pass_if(seconds(timeline.get("fast_p95_delay_sec")), 1.0) == "pass"
                else "fail"
            ),
            "claim_status": "claim_now_runtime",
            "writeback_right": "fast_provisional",
            "source_artifacts": "outputs/system_timeline/summary.json",
        },
        {
            "stage_id": "rule_writeback",
            "surface": "runtime_120_windows",
            "metric": "bounded_writeback_arrival_avg_p95",
            "avg_seconds": seconds(timeline.get("rule_writeback_avg_delay_sec")),
            "p95_seconds": seconds(timeline.get("rule_writeback_p95_delay_sec")),
            "wall_seconds": "",
            "target": "avg<=30s_and_p95<=35s",
            "target_status": (
                "pass"
                if pass_if(seconds(timeline.get("rule_writeback_avg_delay_sec")), 30.0) == "pass"
                and pass_if(seconds(timeline.get("rule_writeback_p95_delay_sec")), 35.0) == "pass"
                else "fail"
            ),
            "claim_status": "claim_now_runtime",
            "writeback_right": "bounded_timeline_writeback",
            "source_artifacts": "outputs/system_timeline/summary.json",
        },
        {
            "stage_id": "runtime_safe_llm_guard",
            "surface": "104_proxy_flagged_windows",
            "metric": "guard_arrival_avg_p95_zero_harm",
            "avg_seconds": seconds(timeline.get("llm_guard_avg_delay_sec")),
            "p95_seconds": seconds(timeline.get("llm_guard_p95_delay_sec")),
            "wall_seconds": "",
            "target": "avg<=50s_and_p95<=65s",
            "target_status": (
                "pass"
                if pass_if(seconds(timeline.get("llm_guard_avg_delay_sec")), 50.0) == "pass"
                and pass_if(seconds(timeline.get("llm_guard_p95_delay_sec")), 65.0) == "pass"
                else "fail"
            ),
            "claim_status": "claim_now_runtime_zero_harm",
            "writeback_right": "block_or_quarantine_only",
            "source_artifacts": "outputs/system_timeline/summary.json; outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_latency_summary.json",
        },
        {
            "stage_id": "llm_review_signal",
            "surface": "4_review_cases",
            "metric": "review_signal_arrival_avg_p95",
            "avg_seconds": seconds(timeline.get("llm_review_avg_delay_sec")),
            "p95_seconds": seconds(timeline.get("llm_review_p95_delay_sec")),
            "wall_seconds": "",
            "target": "review_only_no_timeline_override",
            "target_status": "pass",
            "claim_status": "claim_now_memory_protection",
            "writeback_right": "memory_protection_only",
            "source_artifacts": "outputs/system_timeline/summary.json; outputs/timeline_review_audit/llm_review_signal_timeline_audit_summary.json",
        },
        {
            "stage_id": "omni_realtime_single_smoke",
            "surface": "single_8s_audio_clip",
            "metric": "first_text_and_total_latency",
            "avg_seconds": seconds(omni_realtime.get("first_text_seconds")),
            "p95_seconds": "",
            "wall_seconds": seconds(omni_realtime.get("call_seconds")),
            "target": "first_text<1s_total<2s",
            "target_status": (
                "pass"
                if pass_if(seconds(omni_realtime.get("first_text_seconds")), 1.0, op="lt") == "pass"
                and pass_if(seconds(omni_realtime.get("call_seconds")), 2.0, op="lt") == "pass"
                else "pending_or_fail"
            ),
            "claim_status": "smoke_only_not_omni48_claim",
            "writeback_right": "label_only_no_timeline_writeback",
            "source_artifacts": "outputs/omni_guard/qwen35_omni_flash_realtime_guard_8s.jsonl",
        },
        {
            "stage_id": "split20_simulated_policy",
            "surface": "104_proxy_flagged_windows_offline_model",
            "metric": "simulated_p95_call_and_correction_delay",
            "avg_seconds": seconds(split_policy.get("avg_correction_delay_seconds")),
            "p95_seconds": seconds(split_policy.get("p95_correction_delay_seconds")),
            "wall_seconds": "",
            "target": "planning_only_no_live_claim",
            "target_status": "planning_only",
            "claim_status": "offline_budget_only",
            "writeback_right": "none",
            "source_artifacts": "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation_summary.json",
        },
        {
            "stage_id": "split20_deepseek_top3_live_smoke",
            "surface": "3_slowest_parent_windows_8_calls",
            "metric": "measured_parallel_wall",
            "avg_seconds": "",
            "p95_seconds": "",
            "wall_seconds": seconds(split_top3.get("measured_wall_seconds")),
            "target": "wall<original_max_on_top3",
            "target_status": (
                "pass"
                if seconds(split_top3.get("measured_wall_seconds")) is not None
                and seconds(split_top3.get("original_max_call_seconds")) is not None
                and float(split_top3["measured_wall_seconds"]) < float(split_top3["original_max_call_seconds"])
                and int(split_top3.get("harmful_accepts", -1)) == 0
                else "fail_or_pending"
            ),
            "claim_status": "supporting_smoke_only",
            "writeback_right": "block_or_quarantine_only",
            "source_artifacts": "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_comparison.json",
        },
        {
            "stage_id": "split20_deepseek_full_resume",
            "surface": "101_pending_parent_windows_139_calls",
            "metric": "planned_resume_wall_budget",
            "avg_seconds": "",
            "p95_seconds": "",
            "wall_seconds": seconds(live_steps.get("split20_deepseek_resume_after_top3", {}).get("estimated_wall_seconds")),
            "target": "needs_live_resume_output_before_claim",
            "target_status": "blocked_external",
            "claim_status": postrun_summary.get("split20_latency_claim_status", "pending_live_outputs"),
            "writeback_right": "block_or_quarantine_only",
            "source_artifacts": "outputs/research_progress_snapshot/live_agent_execution_plan.json; outputs/research_progress_snapshot/live_postrun_metrics_closure.json",
        },
        {
            "stage_id": "split20_qwen_backup_top45",
            "surface": "2_parent_windows_4_calls",
            "metric": "backup_measured_wall",
            "avg_seconds": "",
            "p95_seconds": "",
            "wall_seconds": seconds(qwen_run.get("wall_seconds")),
            "target": "backup_only_not_latency_supporting",
            "target_status": "backup_completed_slow",
            "claim_status": "execution_fallback_only",
            "writeback_right": "block_or_quarantine_only",
            "source_artifacts": "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json",
        },
        {
            "stage_id": "omni48_label_only_live",
            "surface": "48_windows_96_calls",
            "metric": "first_text_total_latency_pending",
            "avg_seconds": "",
            "p95_seconds": "",
            "wall_seconds": "",
            "target": "needs_96_call_live_output",
            "target_status": "blocked_missing_credentials",
            "claim_status": postrun_summary.get("omni48_latency_claim_status", "pending_omni48_live_outputs"),
            "writeback_right": "label_only_no_timeline_writeback",
            "source_artifacts": "outputs/research_progress_snapshot/omni48_live_call_manifest.json; outputs/research_progress_snapshot/live_postrun_metrics_closure.json",
        },
    ]
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["claim_status"]] = status_counts.get(row["claim_status"], 0) + 1
    failed_claim_rows = [
        row["stage_id"]
        for row in rows
        if row["claim_status"].startswith("claim_now") and row["target_status"] != "pass"
    ]
    return {
        "runtime_contract": "runtime_latency_budget_ledger_from_existing_artifacts",
        "status": "pass" if not failed_claim_rows else "fail",
        "summary": {
            "row_count": len(rows),
            "claim_now_rows": sum(1 for row in rows if row["claim_status"].startswith("claim_now")),
            "smoke_only_rows": sum(1 for row in rows if "smoke" in row["claim_status"]),
            "pending_or_blocked_rows": sum(1 for row in rows if "pending" in row["claim_status"] or "blocked" in row["claim_status"]),
            "offline_budget_rows": sum(1 for row in rows if row["claim_status"] == "offline_budget_only"),
            "failed_claim_rows": failed_claim_rows,
            "status_counts": status_counts,
            "live_calls_performed_by_builder": 0,
        },
        "rows": rows,
    }


def write_csv(ledger: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "stage_id",
        "surface",
        "metric",
        "avg_seconds",
        "p95_seconds",
        "wall_seconds",
        "target",
        "target_status",
        "claim_status",
        "writeback_right",
        "source_artifacts",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ledger["rows"])


def fmt(value: object) -> str:
    if value in {"", None}:
        return "n/a"
    return f"{float(value):.3f}s"


def write_markdown(ledger: dict[str, Any], path: Path) -> None:
    summary = ledger["summary"]
    lines = [
        "# Runtime Latency Budget Ledger",
        "",
        f"- Runtime contract: `{ledger['runtime_contract']}`",
        f"- Status: `{ledger['status']}`",
        f"- Rows: `{summary['row_count']}`",
        f"- Claim-now rows: `{summary['claim_now_rows']}`",
        f"- Smoke-only rows: `{summary['smoke_only_rows']}`",
        f"- Pending/blocked rows: `{summary['pending_or_blocked_rows']}`",
        f"- Offline budget rows: `{summary['offline_budget_rows']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        "",
        "## Ledger",
        "",
        "| Stage | Surface | Avg | P95 | Wall | Target status | Claim status | Writeback |",
        "|---|---|---:|---:|---:|---|---|---|",
    ]
    for row in ledger["rows"]:
        lines.append(
            f"| `{row['stage_id']}` | {row['surface']} | {fmt(row['avg_seconds'])} | {fmt(row['p95_seconds'])} | "
            f"{fmt(row['wall_seconds'])} | `{row['target_status']}` | `{row['claim_status']}` | `{row['writeback_right']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Claim-now rows are runtime evidence already covered by validation; smoke rows cannot support full-surface claims.",
            "- Offline split20 budget rows estimate latency only; they do not replace live wall-clock evidence.",
            "- Pending live rows remain blocked by credentials, provider quota, or missing live outputs.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    ledger = build_ledger(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(ledger, args.output_md)
    write_csv(ledger, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
