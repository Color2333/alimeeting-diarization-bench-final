#!/usr/bin/env python3
"""Build a no-live-call schema contract for live output and scoring artifacts."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_output_schema_contract.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_output_schema_contract.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_output_schema_contract.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def surfaces_by_id(output_audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    surfaces = output_audit.get("surfaces", [])
    if isinstance(surfaces, dict):
        return surfaces
    return {str(row.get("surface_id")): row for row in surfaces}


def metric_rows_by_id(metric_contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("metric_id")): row for row in metric_contract.get("rows", [])}


def row(
    schema_id: str,
    priority: str,
    artifact_stage: str,
    surface_id: str,
    expected_rows: int,
    required_fields: list[str],
    source_dependency: str,
    current_status: str,
    claim_status: str,
) -> dict[str, Any]:
    return {
        "schema_id": schema_id,
        "priority": priority,
        "artifact_stage": artifact_stage,
        "surface_id": surface_id,
        "expected_rows": expected_rows,
        "required_fields": "; ".join(required_fields),
        "required_field_count": len(required_fields),
        "source_dependency": source_dependency,
        "current_status": current_status,
        "claim_status": claim_status,
    }


def build_contract(root: Path) -> dict[str, Any]:
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    scoring = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    metric = read_json(root / "outputs/research_progress_snapshot/live_metric_extraction_contract.json")
    failure = read_json(root / "outputs/research_progress_snapshot/live_failure_recovery_playbook.json")
    command = read_json(root / "outputs/research_progress_snapshot/live_command_surface_audit.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")

    surfaces = surfaces_by_id(output_audit)
    metrics = metric_rows_by_id(metric)
    deepseek = surfaces.get("deepseek_resume_after_top3", {})
    qwen = surfaces.get("qwen_full_backup", {})
    omni = surfaces.get("omni48_label_only", {})

    llm_success_fields = [
        "window_id",
        "parent_window_id",
        "window_decision",
        "patch_decisions",
        "call_seconds",
        "total_tokens",
        "call_attempts",
        "max_call_attempts",
    ]
    rows = [
        row(
            "deepseek_resume_llm_success_jsonl",
            "P0",
            "live_output_jsonl",
            "deepseek_resume_after_top3",
            as_int(deepseek.get("expected_calls")),
            llm_success_fields,
            "live_output_audit:deepseek_resume_after_top3",
            "blocked_missing_output",
            "required_before_deepseek_safety_and_latency_scoring",
        ),
        row(
            "qwen_full_llm_success_jsonl",
            "P1",
            "live_output_jsonl",
            "qwen_full_backup",
            as_int(qwen.get("expected_calls")),
            llm_success_fields,
            "live_output_audit:qwen_full_backup",
            "blocked_missing_output",
            "fallback_only_required_before_qwen_scoring",
        ),
        row(
            "omni48_success_jsonl",
            "P1",
            "live_output_jsonl",
            "omni48_label_only",
            as_int(omni.get("expected_calls")),
            [
                "call_id",
                "window_id",
                "recording_id",
                "model",
                "bucket",
                "diarization_risk",
                "should_quarantine",
                "should_defer_to_slow_agent",
                "call_seconds",
                "call_attempts",
                "max_call_attempts",
                "schema_ok",
            ],
            "live_output_audit:omni48_label_only",
            "blocked_missing_output",
            "label_only_required_before_omni48_metric_scoring",
        ),
        row(
            "bounded_retry_error_row",
            "P0",
            "live_output_error_row",
            "all_live_surfaces",
            as_int(output_audit.get("summary", {}).get("expected_live_calls")),
            ["error", "call_attempts", "max_call_attempts", "retry_backoff_seconds", "window_id_or_call_id"],
            "live_failure_recovery_playbook:retry_exhausted_errors",
            "future_recovery_path",
            "records_failed_attempts_without_metric_promotion",
        ),
        row(
            "llm_safety_summary",
            "P0",
            "scoring_output_summary",
            "llm_split20_surfaces",
            as_int(scoring.get("summary", {}).get("p0_scoring_steps")),
            [
                "harmful_accepts",
                "conservative_blocks",
                "missing_patch_eval",
                "parent_window_decision_override",
                "avg_call_seconds",
                "p95_call_seconds",
                "p95_correction_delay_seconds",
            ],
            "live_metric_extraction_contract:deepseek_resume_safety_zero_harm",
            "blocked_waiting_live_output",
            "required_before_zero_harm_safety_claim",
        ),
        row(
            "split20_comparison_summary",
            "P0",
            "scoring_output_summary",
            "deepseek_resume_after_top3",
            as_int(metrics.get("deepseek_resume_call_latency", {}).get("expected_input_calls")),
            [
                "parent_windows",
                "split_calls",
                "original_max_call_seconds",
                "split_max_call_seconds",
                "split_parent_avg_max_call_seconds",
                "token_multiplier",
                "harmful_accepts",
                "parent_window_decision_override",
            ],
            "live_metric_extraction_contract:deepseek_resume_call_latency",
            "blocked_waiting_live_output",
            "required_before_full_split20_latency_claim",
        ),
        row(
            "omni48_metric_summary",
            "P1",
            "scoring_output_summary",
            "omni48_label_only",
            as_int(metrics.get("omni48_label_quality", {}).get("expected_input_calls")),
            [
                "model",
                "windows",
                "high_positive_rate",
                "clean_false_positive_rate",
                "quarantines",
                "defers",
                "avg_call_seconds",
                "p95_call_seconds",
                "max_call_seconds",
            ],
            "live_metric_extraction_contract:omni48_label_quality",
            "blocked_waiting_live_output",
            "label_only_no_timeline_writeback",
        ),
        row(
            "promotion_traceability_summary",
            "P0",
            "promotion_output_summary",
            "all_live_surfaces",
            as_int(promotion.get("summary", {}).get("gate_count")),
            ["ready_to_promote_count", "traceability_rows", "fully_covered_rows", "missing_source_rows", "no_new_metric_claim"],
            "post_live_claim_promotion_gate",
            "blocked_waiting_live_output",
            "required_before_report_ppt_claim_promotion",
        ),
    ]

    return {
        "runtime_contract": "live_output_schema_contract_no_live_calls",
        "status": "blocked_waiting_live_outputs",
        "source_contracts": {
            "live_output_audit": output_audit.get("runtime_contract", ""),
            "live_scoring_readiness": scoring.get("runtime_contract", ""),
            "live_metric_extraction_contract": metric.get("runtime_contract", ""),
            "live_failure_recovery_playbook": failure.get("runtime_contract", ""),
            "live_command_surface_audit": command.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
        },
        "summary": {
            "schema_contract_count": len(rows),
            "p0_schema_contracts": sum(1 for item in rows if item["priority"] == "P0"),
            "live_output_schema_contracts": sum(1 for item in rows if item["artifact_stage"] == "live_output_jsonl"),
            "scoring_output_schema_contracts": sum(1 for item in rows if item["artifact_stage"] == "scoring_output_summary"),
            "promotion_schema_contracts": sum(1 for item in rows if item["artifact_stage"] == "promotion_output_summary"),
            "error_row_schema_contracts": sum(1 for item in rows if item["artifact_stage"] == "live_output_error_row"),
            "required_field_count": sum(as_int(item["required_field_count"]) for item in rows),
            "expected_live_output_rows": as_int(output_audit.get("summary", {}).get("expected_live_calls")),
            "missing_output_surfaces": as_int(output_audit.get("summary", {}).get("missing_output_surfaces")),
            "ready_to_score_steps": as_int(scoring.get("summary", {}).get("ready_to_score_steps")),
            "metric_contract_count": as_int(metric.get("summary", {}).get("metric_contract_count")),
            "live_calls_performed_by_builder": 0,
            "no_schema_validation_executed_on_missing_outputs": True,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(contract: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "schema_id",
        "priority",
        "artifact_stage",
        "surface_id",
        "expected_rows",
        "required_field_count",
        "required_fields",
        "source_dependency",
        "current_status",
        "claim_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in contract["rows"]:
            writer.writerow({key: item.get(key, "") for key in fieldnames})


def write_markdown(contract: dict[str, Any], path: Path) -> None:
    summary = contract["summary"]
    lines = [
        "# Live Output Schema Contract",
        "",
        f"- Runtime contract: `{contract['runtime_contract']}`",
        f"- Status: `{contract['status']}`",
        f"- Schema contracts: `{summary['schema_contract_count']}`",
        f"- P0 schema contracts: `{summary['p0_schema_contracts']}`",
        f"- Live output schema contracts: `{summary['live_output_schema_contracts']}`",
        f"- Scoring output schema contracts: `{summary['scoring_output_schema_contracts']}`",
        f"- Required fields: `{summary['required_field_count']}`",
        f"- Expected live output rows: `{summary['expected_live_output_rows']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- Ready to score: `{summary['ready_to_score_steps']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Schema | Stage | Surface | Priority | Expected rows | Required fields | Claim status |",
        "|---|---|---|---|---:|---|---|",
    ]
    for item in contract["rows"]:
        lines.append(
            f"| `{item['schema_id']}` | `{item['artifact_stage']}` | `{item['surface_id']}` | "
            f"`{item['priority']}` | {item['expected_rows']} | {item['required_fields']} | "
            f"`{item['claim_status']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This contract defines the field-level interface between live outputs, scoring scripts, metric extraction, and promotion gates.",
            "- Missing live outputs are not schema-validated yet; the current rows are a preflight schema contract for future validation.",
            "- LLM and Omni live output fields must be present before scoring readiness can move from blocked to ready.",
            "- The builder only reads local artifacts; it performs no live/API/model/scoring calls and writes no secrets.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    contract = build_contract(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(contract, args.output_md)
    write_csv(contract, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
