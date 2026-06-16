#!/usr/bin/env python3
"""Audit pending or completed live LLM/Omni output files without live calls."""

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
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_output_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_output_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_output_audit.csv")

FULL_PROMPTS = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompts.jsonl")
RESUME_PROMPTS = Path("outputs/research_progress_snapshot/split20_resume_after_top3_export_prompts.jsonl")
DEEPSEEK_RESUME_JSONL = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl")
QWEN_FULL_JSONL = Path("outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl")
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
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                parse_errors += 1
                row = {"window_id": f"parse_error:{line_no}", "error": f"json_decode_error:{exc.msg}"}
            rows.append(row)
    return rows, parse_errors


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))
    return round(ordered[index], 3)


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def call_seconds(rows: list[dict[str, Any]]) -> list[float]:
    values = []
    for row in rows:
        try:
            if row.get("call_seconds") not in {"", None}:
                values.append(float(row.get("call_seconds")))
        except (TypeError, ValueError):
            continue
    return values


def prompt_surface(path: Path) -> dict[str, Any]:
    rows, parse_errors = read_jsonl(path)
    call_ids = [str(row.get("window_id", "")) for row in rows if row.get("window_id")]
    parent_ids = [str(row.get("parent_window_id") or row.get("window_id") or "") for row in rows]
    return {
        "path": str(path),
        "exists": path.exists(),
        "parse_errors": parse_errors,
        "expected_calls": len(call_ids),
        "expected_parent_windows": len({parent_id for parent_id in parent_ids if parent_id}),
        "call_ids": set(call_ids),
        "parent_ids": {parent_id for parent_id in parent_ids if parent_id},
    }


def row_call_id(row: dict[str, Any], kind: str) -> str:
    if row.get("call_id"):
        return str(row["call_id"])
    if row.get("window_id") and kind.startswith("llm"):
        return str(row["window_id"])
    if kind.startswith("omni"):
        window_id = row.get("window_id") or f"{row.get('recording_id')}:{row.get('window_size')}:{row.get('segment_idx')}"
        return f"{window_id}:{row.get('model')}"
    return str(row.get("window_id", ""))


def parent_id(row: dict[str, Any], kind: str) -> str:
    if row.get("parent_window_id"):
        return str(row["parent_window_id"])
    if row.get("window_id"):
        return str(row["window_id"]).split(":part", 1)[0]
    if kind.startswith("omni"):
        return f"{row.get('recording_id')}:{row.get('window_size')}:{row.get('segment_idx')}"
    return ""


def llm_success(row: dict[str, Any]) -> bool:
    return not row.get("error") and row.get("window_decision") not in {"", "error", None}


def omni_success(row: dict[str, Any]) -> bool:
    return not row.get("error") and row.get("schema_ok") is not False


def audit_surface(
    *,
    surface_id: str,
    kind: str,
    expected_calls: int,
    expected_parent_windows: int,
    expected_call_ids: set[str],
    expected_parent_ids: set[str],
    output_jsonl: Path,
    summary_json: Path | None,
) -> dict[str, Any]:
    rows, parse_errors = read_jsonl(output_jsonl)
    ids = [row_call_id(row, kind) for row in rows]
    parents = [parent_id(row, kind) for row in rows]
    duplicate_call_ids = sorted(call_id for call_id, count in Counter(ids).items() if call_id and count > 1)
    observed_call_ids = {call_id for call_id in ids if call_id}
    observed_parent_ids = {pid for pid in parents if pid}
    if expected_call_ids:
        missing_call_ids = sorted(expected_call_ids - observed_call_ids)
        extra_call_ids = sorted(observed_call_ids - expected_call_ids)
    else:
        missing_call_ids = []
        extra_call_ids = []
    if expected_parent_ids:
        missing_parent_ids = sorted(expected_parent_ids - observed_parent_ids)
        extra_parent_ids = sorted(observed_parent_ids - expected_parent_ids)
    else:
        missing_parent_ids = []
        extra_parent_ids = []

    success_fn = omni_success if kind.startswith("omni") else llm_success
    successful_rows = [row for row in rows if success_fn(row)]
    failed_rows = [row for row in rows if not success_fn(row)]
    error_types = Counter(str(row.get("error", "")).split("(", 1)[0] or "missing_success_signal" for row in failed_rows)
    latencies = call_seconds(successful_rows)
    summary = read_json(summary_json) if summary_json else {}
    summary_mismatches = []
    if summary:
        if int(summary.get("calls", len(rows))) != len(rows):
            summary_mismatches.append("calls")
        if int(summary.get("successful_calls", len(successful_rows))) != len(successful_rows):
            summary_mismatches.append("successful_calls")
        if int(summary.get("error_count", len(failed_rows))) != len(failed_rows):
            summary_mismatches.append("error_count")

    output_exists = output_jsonl.exists()
    complete = (
        output_exists
        and len(rows) == expected_calls
        and len(successful_rows) == expected_calls
        and not parse_errors
        and not duplicate_call_ids
        and not missing_call_ids
        and not extra_call_ids
    )
    partial = output_exists and not complete
    if not output_exists:
        status = "missing_output"
        claim_gate = "blocked_missing_output"
    elif partial:
        status = "partial_or_invalid_output"
        claim_gate = "blocked_partial_or_invalid_output"
    elif kind.startswith("omni"):
        status = "complete_output_needs_metric_scoring"
        claim_gate = "ready_for_omni_metric_scoring"
    else:
        status = "complete_output_needs_safety_scoring"
        claim_gate = "ready_for_llm_safety_latency_scoring"

    return {
        "surface_id": surface_id,
        "kind": kind,
        "expected_calls": expected_calls,
        "expected_parent_windows": expected_parent_windows,
        "output_jsonl": str(output_jsonl),
        "summary_json": str(summary_json) if summary_json else "",
        "output_exists": output_exists,
        "summary_exists": bool(summary_json and summary_json.exists()),
        "observed_calls": len(rows),
        "successful_calls": len(successful_rows),
        "failed_calls": len(failed_rows),
        "parse_errors": parse_errors,
        "observed_parent_windows": len(observed_parent_ids),
        "missing_calls": max(expected_calls - len(successful_rows), 0),
        "missing_parent_windows": max(expected_parent_windows - len(observed_parent_ids), 0),
        "duplicate_call_ids": len(duplicate_call_ids),
        "extra_call_ids": len(extra_call_ids),
        "extra_parent_windows": len(extra_parent_ids),
        "error_types": dict(error_types),
        "avg_call_seconds": mean(latencies),
        "p95_call_seconds": p95(latencies),
        "max_call_seconds": round(max(latencies), 3) if latencies else 0.0,
        "summary_wall_seconds": summary.get("wall_seconds", ""),
        "summary_parallel_workers": summary.get("parallel_workers", ""),
        "summary_mismatches": summary_mismatches,
        "status": status,
        "claim_gate": claim_gate,
        "sample_missing_call_ids": missing_call_ids[:5],
        "sample_extra_call_ids": extra_call_ids[:5],
    }


def build_audit(root: Path) -> dict[str, Any]:
    split_manifest = read_json(root / "outputs/research_progress_snapshot/split20_full_live_manifest.json")
    omni_manifest = read_json(root / "outputs/research_progress_snapshot/omni48_live_call_manifest.json")
    resume_surface = prompt_surface(root / RESUME_PROMPTS)
    full_surface = prompt_surface(root / FULL_PROMPTS)
    omni_calls = omni_manifest.get("calls", [])
    omni_expected_call_ids = {str(row.get("call_id")) for row in omni_calls if row.get("call_id")}
    omni_expected_parent_ids = {str(row.get("window_id")) for row in omni_calls if row.get("window_id")}

    split_summary = split_manifest.get("summary", {})
    omni_summary = omni_manifest.get("summary", {})
    surfaces = [
        audit_surface(
            surface_id="deepseek_resume_after_top3",
            kind="llm_split20_primary",
            expected_calls=int(resume_surface["expected_calls"] or split_summary.get("deepseek_resume_required_calls_min") or 0),
            expected_parent_windows=int(resume_surface["expected_parent_windows"] or split_summary.get("deepseek_resume_parent_windows") or 0),
            expected_call_ids=set(resume_surface["call_ids"]),
            expected_parent_ids=set(resume_surface["parent_ids"]),
            output_jsonl=root / DEEPSEEK_RESUME_JSONL,
            summary_json=(root / DEEPSEEK_RESUME_JSONL).with_name(DEEPSEEK_RESUME_JSONL.stem + "_summary.json"),
        ),
        audit_surface(
            surface_id="qwen_full_backup",
            kind="llm_split20_backup",
            expected_calls=int(full_surface["expected_calls"] or split_summary.get("prompt_calls") or 0),
            expected_parent_windows=int(full_surface["expected_parent_windows"] or split_summary.get("parent_windows") or 0),
            expected_call_ids=set(full_surface["call_ids"]),
            expected_parent_ids=set(full_surface["parent_ids"]),
            output_jsonl=root / QWEN_FULL_JSONL,
            summary_json=(root / QWEN_FULL_JSONL).with_name(QWEN_FULL_JSONL.stem + "_summary.json"),
        ),
        audit_surface(
            surface_id="omni48_label_only",
            kind="omni_label_only",
            expected_calls=int(omni_summary.get("call_count") or len(omni_expected_call_ids)),
            expected_parent_windows=int(omni_summary.get("window_count") or len(omni_expected_parent_ids)),
            expected_call_ids=omni_expected_call_ids,
            expected_parent_ids=omni_expected_parent_ids,
            output_jsonl=root / OMNI48_JSONL,
            summary_json=None,
        ),
    ]
    missing_outputs = [row["surface_id"] for row in surfaces if row["status"] == "missing_output"]
    partial_outputs = [row["surface_id"] for row in surfaces if row["status"] == "partial_or_invalid_output"]
    claim_ready = [row["surface_id"] for row in surfaces if str(row["claim_gate"]).startswith("ready")]
    status = "pending_live_outputs"
    if partial_outputs:
        status = "partial_or_invalid_live_outputs"
    elif not missing_outputs and claim_ready:
        status = "live_outputs_ready_for_scoring"

    return {
        "runtime_contract": "live_output_audit_no_live_calls",
        "status": status,
        "source_artifacts": [
            str(FULL_PROMPTS),
            str(RESUME_PROMPTS),
            "outputs/research_progress_snapshot/split20_full_live_manifest.json",
            "outputs/research_progress_snapshot/omni48_live_call_manifest.json",
        ],
        "summary": {
            "surface_count": len(surfaces),
            "missing_output_surfaces": len(missing_outputs),
            "partial_or_invalid_surfaces": len(partial_outputs),
            "claim_ready_surfaces": len(claim_ready),
            "expected_live_calls": sum(int(row["expected_calls"]) for row in surfaces),
            "observed_live_output_rows": sum(int(row["observed_calls"]) for row in surfaces),
            "successful_live_output_rows": sum(int(row["successful_calls"]) for row in surfaces),
            "live_calls_performed_by_auditor": 0,
            "missing_outputs": missing_outputs,
            "partial_outputs": partial_outputs,
            "claim_ready": claim_ready,
        },
        "surfaces": surfaces,
    }


def write_csv(audit: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "surface_id",
        "kind",
        "expected_calls",
        "expected_parent_windows",
        "output_exists",
        "summary_exists",
        "observed_calls",
        "successful_calls",
        "failed_calls",
        "missing_calls",
        "observed_parent_windows",
        "missing_parent_windows",
        "duplicate_call_ids",
        "extra_call_ids",
        "avg_call_seconds",
        "p95_call_seconds",
        "max_call_seconds",
        "status",
        "claim_gate",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in audit["surfaces"]:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    lines = [
        "# Live Output Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Surfaces: `{summary['surface_count']}`",
        f"- Expected live calls: `{summary['expected_live_calls']}`",
        f"- Observed live output rows: `{summary['observed_live_output_rows']}`",
        f"- Successful live output rows: `{summary['successful_live_output_rows']}`",
        f"- Missing output surfaces: `{summary['missing_output_surfaces']}`",
        f"- Partial/invalid surfaces: `{summary['partial_or_invalid_surfaces']}`",
        f"- Claim-ready surfaces: `{summary['claim_ready_surfaces']}`",
        f"- Live calls performed by auditor: `{summary['live_calls_performed_by_auditor']}`",
        "",
        "| Surface | Kind | Expected | Observed | Success | Missing | P95 call | Status | Claim gate |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in audit["surfaces"]:
        lines.append(
            f"| `{row['surface_id']}` | `{row['kind']}` | {row['expected_calls']} | "
            f"{row['observed_calls']} | {row['successful_calls']} | {row['missing_calls']} | "
            f"{row['p95_call_seconds']} | `{row['status']}` | `{row['claim_gate']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This audit reads live-output files only; it performs no LLM or Omni calls.",
            "- A surface is claim-ready only after the expected calls are present, successful, non-duplicated, and parse cleanly.",
            "- LLM surfaces still need downstream safety scoring before being promoted from output coverage to full latency/safety evidence.",
            "- Omni48 still needs metric scoring after its label-only output is complete.",
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
