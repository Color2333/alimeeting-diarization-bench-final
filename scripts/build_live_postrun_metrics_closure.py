#!/usr/bin/env python3
"""Summarize live-run metric closure status without making live calls."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_postrun_metrics_closure.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_postrun_metrics_closure.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_postrun_metrics_closure.csv")
DEEPSEEK_RESUME_JSONL = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl")
QWEN_FULL_JSONL = Path("outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl")
OMNI48_JSONL = Path("outputs/omni_guard/omni_expansion_48_live.jsonl")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def first_jsonl(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    return rows[0] if rows else {}


def successful_llm_calls(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if not row.get("error") and row.get("window_decision") not in {"", "error", None})


def successful_omni_calls(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if not row.get("error") and row.get("schema_ok") is not False)


def parent_count(rows: list[dict[str, Any]]) -> int:
    parents = {str(row.get("parent_window_id") or row.get("window_id") or "") for row in rows}
    return len({parent for parent in parents if parent})


def pct(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def build_closure(root: Path) -> dict[str, Any]:
    split20 = read_json(root / "outputs/research_progress_snapshot/split20_full_live_manifest.json")
    split_summary = split20.get("summary", {})
    export = read_json(root / "outputs/research_progress_snapshot/split20_resume_export_audit.json")
    export_summary = export.get("summary", {})
    plan = read_json(root / "outputs/research_progress_snapshot/live_agent_execution_plan.json")
    omni_calls = read_json(root / "outputs/research_progress_snapshot/omni48_live_call_manifest.json")
    top3 = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_comparison.json")
    deepseek_attempt = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top4_5_parallel_attempt_summary.json")
    qwen_top45 = read_json(root / "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json")
    omni_realtime = first_jsonl(root / "outputs/omni_guard/qwen35_omni_flash_realtime_guard_8s.jsonl")

    deepseek_resume_rows = read_jsonl(root / DEEPSEEK_RESUME_JSONL)
    qwen_full_rows = read_jsonl(root / QWEN_FULL_JSONL)
    omni48_rows = read_jsonl(root / OMNI48_JSONL)

    split_expected_calls = int(split_summary.get("prompt_calls") or 147)
    split_expected_parents = int(split_summary.get("parent_windows") or 104)
    deepseek_top3_calls = int(top3.get("split_calls") or split_summary.get("deepseek_completed_calls") or 0)
    deepseek_top3_parents = int(top3.get("parent_windows") or split_summary.get("deepseek_completed_parent_windows") or 0)
    deepseek_failed_calls = int(deepseek_attempt.get("failed_calls") or split_summary.get("deepseek_quota_failed_calls") or 0)
    deepseek_failed_parents = len(deepseek_attempt.get("parent_windows") or [])
    deepseek_resume_expected_calls = int(export_summary.get("expected_prompts") or split_summary.get("deepseek_resume_required_calls_min") or 0)
    deepseek_resume_expected_parents = int(export_summary.get("expected_parent_windows") or split_summary.get("deepseek_resume_parent_windows") or 0)
    deepseek_resume_success = successful_llm_calls(deepseek_resume_rows)
    deepseek_resume_parents = parent_count(deepseek_resume_rows)
    deepseek_success_calls = deepseek_top3_calls + deepseek_resume_success
    deepseek_observed_calls = deepseek_top3_calls + deepseek_failed_calls + len(deepseek_resume_rows)

    qwen_top45_calls = int(qwen_top45.get("split_calls") or split_summary.get("qwen_backup_calls") or 0)
    qwen_top45_success = int((qwen_top45.get("runs") or [{}])[0].get("successful_calls") or qwen_top45_calls)
    qwen_full_success = successful_llm_calls(qwen_full_rows)
    qwen_full_parents = parent_count(qwen_full_rows)
    omni_expected_calls = int(omni_calls.get("summary", {}).get("call_count") or 96)
    omni_expected_windows = int(omni_calls.get("summary", {}).get("window_count") or 48)
    omni_success = successful_omni_calls(omni48_rows)
    omni_errors = sum(1 for row in omni48_rows if row.get("error"))

    split_latency_claim_status = "pending_deepseek_resume_live_outputs"
    if deepseek_success_calls == split_expected_calls and int(top3.get("harmful_accepts", 0)) == 0:
        split_latency_claim_status = "ready_to_score_full_surface_latency"
    elif deepseek_failed_calls:
        split_latency_claim_status = "blocked_by_quota_or_missing_resume"
    omni_latency_status = "pending_omni48_live_outputs"
    if omni_success == omni_expected_calls:
        omni_latency_status = "ready_to_score_first_text_and_total_latency"

    surfaces = [
        {
            "surface_id": "deepseek_top3_parallel_smoke",
            "kind": "llm_split20",
            "expected_calls": deepseek_top3_calls,
            "observed_calls": deepseek_top3_calls,
            "successful_calls": deepseek_top3_calls,
            "failed_calls": 0,
            "parent_windows": deepseek_top3_parents,
            "status": "completed_limited_smoke",
            "latency_evidence": f"wall {top3.get('measured_wall_seconds')}s vs original max {top3.get('original_max_call_seconds')}s",
            "claim_status": "supporting_smoke_only",
        },
        {
            "surface_id": "deepseek_top4_5_quota_attempt",
            "kind": "llm_split20",
            "expected_calls": int(deepseek_attempt.get("calls") or deepseek_failed_calls),
            "observed_calls": int(deepseek_attempt.get("calls") or deepseek_failed_calls),
            "successful_calls": int(deepseek_attempt.get("successful_calls") or 0),
            "failed_calls": deepseek_failed_calls,
            "parent_windows": deepseek_failed_parents,
            "status": f"failed_{deepseek_attempt.get('failure_type', 'unknown')}",
            "latency_evidence": "no generation before quota failure",
            "claim_status": "blocking_full_surface_claim",
        },
        {
            "surface_id": "deepseek_resume_after_top3",
            "kind": "llm_split20",
            "expected_calls": deepseek_resume_expected_calls,
            "observed_calls": len(deepseek_resume_rows),
            "successful_calls": deepseek_resume_success,
            "failed_calls": max(len(deepseek_resume_rows) - deepseek_resume_success, 0),
            "parent_windows": deepseek_resume_parents,
            "status": "pending_live_output" if not deepseek_resume_rows else "partial_or_complete_live_output",
            "latency_evidence": "resume wall not measured yet" if not deepseek_resume_rows else "resume output present; summarize run wall next",
            "claim_status": split_latency_claim_status,
        },
        {
            "surface_id": "qwen_top4_5_backup",
            "kind": "llm_split20_backup",
            "expected_calls": qwen_top45_calls,
            "observed_calls": qwen_top45_calls,
            "successful_calls": qwen_top45_success,
            "failed_calls": max(qwen_top45_calls - qwen_top45_success, 0),
            "parent_windows": int(qwen_top45.get("parent_windows") or 0),
            "status": "completed_backup_not_latency_supporting",
            "latency_evidence": f"wall {(qwen_top45.get('runs') or [{}])[0].get('wall_seconds')}s; verdict slower_than_original_max",
            "claim_status": "execution_fallback_only",
        },
        {
            "surface_id": "qwen_full_backup",
            "kind": "llm_split20_backup",
            "expected_calls": split_expected_calls,
            "observed_calls": len(qwen_full_rows),
            "successful_calls": qwen_full_success,
            "failed_calls": max(len(qwen_full_rows) - qwen_full_success, 0),
            "parent_windows": qwen_full_parents,
            "status": "pending_live_output" if not qwen_full_rows else "partial_or_complete_live_output",
            "latency_evidence": "full backup wall not measured yet" if not qwen_full_rows else "full backup output present; summarize run wall next",
            "claim_status": "fallback_only_not_primary_latency_claim",
        },
        {
            "surface_id": "omni48_label_only",
            "kind": "omni_label_only",
            "expected_calls": omni_expected_calls,
            "observed_calls": len(omni48_rows),
            "successful_calls": omni_success,
            "failed_calls": omni_errors,
            "parent_windows": omni_expected_windows if omni48_rows else 0,
            "status": "pending_live_output" if not omni48_rows else "partial_or_complete_live_output",
            "latency_evidence": "first text/total latency not measured for Omni48 yet",
            "claim_status": omni_latency_status,
        },
        {
            "surface_id": "omni_realtime_single_smoke",
            "kind": "omni_realtime_smoke",
            "expected_calls": 1 if omni_realtime else 0,
            "observed_calls": 1 if omni_realtime else 0,
            "successful_calls": 1 if omni_realtime and not omni_realtime.get("errors") else 0,
            "failed_calls": 1 if omni_realtime and omni_realtime.get("errors") else 0,
            "parent_windows": 1 if omni_realtime else 0,
            "status": "completed_single_latency_smoke" if omni_realtime else "missing_smoke",
            "latency_evidence": (
                f"first_text {omni_realtime.get('first_text_seconds')}s; total {omni_realtime.get('call_seconds')}s"
                if omni_realtime
                else "n/a"
            ),
            "claim_status": "smoke_only_not_omni48_claim",
        },
    ]

    missing_live_outputs = [
        str(path)
        for path, expected in [
            (DEEPSEEK_RESUME_JSONL, deepseek_resume_expected_calls),
            (QWEN_FULL_JSONL, split_expected_calls),
            (OMNI48_JSONL, omni_expected_calls),
        ]
        if expected and not (root / path).exists()
    ]
    return {
        "runtime_contract": "live_postrun_metrics_closure_no_live_calls",
        "source_plan_contract": plan.get("runtime_contract", ""),
        "status": "pending_live_outputs" if missing_live_outputs else "live_outputs_present_needs_scoring",
        "summary": {
            "split20_expected_calls": split_expected_calls,
            "split20_expected_parent_windows": split_expected_parents,
            "deepseek_success_calls": deepseek_success_calls,
            "deepseek_observed_calls_including_failed": deepseek_observed_calls,
            "deepseek_completion_rate": pct(deepseek_success_calls, split_expected_calls),
            "deepseek_resume_expected_calls": deepseek_resume_expected_calls,
            "deepseek_resume_successful_calls": deepseek_resume_success,
            "deepseek_quota_failed_calls": deepseek_failed_calls,
            "qwen_backup_observed_calls": qwen_top45_calls + len(qwen_full_rows),
            "omni48_expected_calls": omni_expected_calls,
            "omni48_successful_calls": omni_success,
            "omni48_completion_rate": pct(omni_success, omni_expected_calls),
            "omni_realtime_first_text_seconds": omni_realtime.get("first_text_seconds", ""),
            "omni_realtime_total_seconds": omni_realtime.get("call_seconds", ""),
            "split20_latency_claim_status": split_latency_claim_status,
            "omni48_latency_claim_status": omni_latency_status,
            "missing_live_outputs": missing_live_outputs,
            "live_calls_performed_by_builder": 0,
        },
        "surfaces": surfaces,
    }


def write_csv(closure: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "surface_id",
        "kind",
        "expected_calls",
        "observed_calls",
        "successful_calls",
        "failed_calls",
        "parent_windows",
        "status",
        "latency_evidence",
        "claim_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(closure["surfaces"])


def write_markdown(closure: dict[str, Any], path: Path) -> None:
    summary = closure["summary"]
    lines = [
        "# Live Postrun Metrics Closure",
        "",
        f"- Runtime contract: `{closure['runtime_contract']}`",
        f"- Status: `{closure['status']}`",
        f"- Split20 expected calls: `{summary['split20_expected_calls']}`",
        f"- DeepSeek success calls: `{summary['deepseek_success_calls']}`",
        f"- DeepSeek resume expected calls: `{summary['deepseek_resume_expected_calls']}`",
        f"- DeepSeek quota-failed calls: `{summary['deepseek_quota_failed_calls']}`",
        f"- Split20 latency claim status: `{summary['split20_latency_claim_status']}`",
        f"- Omni48 expected calls: `{summary['omni48_expected_calls']}`",
        f"- Omni48 successful calls: `{summary['omni48_successful_calls']}`",
        f"- Omni48 latency claim status: `{summary['omni48_latency_claim_status']}`",
        f"- Omni realtime single-smoke latency: `{summary['omni_realtime_first_text_seconds']}` first text / `{summary['omni_realtime_total_seconds']}` total",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        "",
        "## Surfaces",
        "",
        "| Surface | Kind | Expected | Observed | Success | Failed | Status | Claim status |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in closure["surfaces"]:
        lines.append(
            f"| `{row['surface_id']}` | `{row['kind']}` | {row['expected_calls']} | {row['observed_calls']} | "
            f"{row['successful_calls']} | {row['failed_calls']} | `{row['status']}` | `{row['claim_status']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This artifact is a postrun closure checker; it performs no live LLM/Omni calls.",
            "- Current DeepSeek evidence is limited to the top3 live smoke plus a quota-failed top4/top5 attempt.",
            "- Full split20 latency remains unclaimed until the resume output exists and covers the remaining 139 calls.",
            "- Omni48 first-text and total latency remain unclaimed until the 96-call label-only expansion output exists.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    closure = build_closure(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(closure, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(closure, args.output_md)
    write_csv(closure, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
