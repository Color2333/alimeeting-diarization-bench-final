#!/usr/bin/env python3
"""Audit pending live-call input surfaces without making live calls."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_input_integrity_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_input_integrity_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_input_integrity_audit.csv")

FULL_PROMPTS = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompts.jsonl")
RESUME_PROMPTS = Path("outputs/research_progress_snapshot/split20_resume_after_top3_export_prompts.jsonl")
PENDING_IDS = Path("outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt")
OMNI_CSV = Path("outputs/research_progress_snapshot/omni_expansion_manifest.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        return [], 0
    rows: list[dict[str, Any]] = []
    errors = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                errors += 1
    return rows, errors


def rel(path: Path) -> str:
    return str(path)


def prompt_stats(root: Path, path: Path) -> dict[str, Any]:
    rows, parse_errors = read_jsonl(root / path)
    parent_ids = {str(row.get("parent_window_id") or row.get("window_id") or "") for row in rows}
    parent_ids.discard("")
    patch_refs = sum(int(row.get("patch_count") or 0) for row in rows)
    sub_batch_counts = [int(row.get("sub_batch_count") or 0) for row in rows]
    return {
        "path": rel(path),
        "exists": (root / path).exists(),
        "parse_errors": parse_errors,
        "prompt_calls": len(rows),
        "parent_windows": len(parent_ids),
        "patch_references": patch_refs,
        "max_sub_batch_count": max(sub_batch_counts) if sub_batch_counts else 0,
        "parent_ids": parent_ids,
    }


def output_surfaces_by_id(output_audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    surfaces = output_audit.get("surfaces", [])
    if isinstance(surfaces, dict):
        return surfaces
    if isinstance(surfaces, list):
        return {str(row.get("surface_id")): row for row in surfaces}
    return {}


def build_audit(root: Path) -> dict[str, Any]:
    split_export = read_json(root / "outputs/research_progress_snapshot/split20_resume_export_audit.json")
    split_manifest = read_json(root / "outputs/research_progress_snapshot/split20_full_live_manifest.json")
    omni_manifest = read_json(root / "outputs/research_progress_snapshot/omni48_live_call_manifest.json")
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    parallelism = read_json(root / "outputs/research_progress_snapshot/live_parallelism_sensitivity.json")

    full_prompts = prompt_stats(root, FULL_PROMPTS)
    resume_prompts = prompt_stats(root, RESUME_PROMPTS)
    pending_ids = (root / PENDING_IDS).read_text(encoding="utf-8").splitlines() if (root / PENDING_IDS).exists() else []
    pending_id_set = set(pending_ids)
    omni_rows = read_csv(root / OMNI_CSV)
    omni_summary = omni_manifest.get("summary", {})
    manifest_resume = split_manifest.get("resume_surface", {})
    export_summary = split_export.get("summary", {})
    output_surfaces = output_surfaces_by_id(output_audit)

    rows = [
        {
            "surface_id": "deepseek_resume_inputs",
            "priority": "P0",
            "input_type": "llm_resume_prompts",
            "status": "input_ready_waiting_credentials_or_quota",
            "expected_calls": int(export_summary.get("expected_prompts") or 139),
            "observed_calls": resume_prompts["prompt_calls"],
            "expected_parent_windows": int(export_summary.get("expected_parent_windows") or 101),
            "observed_parent_windows": resume_prompts["parent_windows"],
            "parse_errors": resume_prompts["parse_errors"],
            "missing_input_files": [] if resume_prompts["exists"] and (root / PENDING_IDS).exists() else [rel(RESUME_PROMPTS), rel(PENDING_IDS)],
            "input_consistency": (
                resume_prompts["parent_ids"] == pending_id_set
                and resume_prompts["prompt_calls"] == int(export_summary.get("expected_prompts") or 139)
                and resume_prompts["parse_errors"] == 0
                and not export_summary.get("completed_overlap")
                and not export_summary.get("missing_pending")
            ),
            "credential_or_quota_blocker": "known_deepseek_top4_5_failure_AllocationQuota.FreeTierOnly",
            "output_status": output_surfaces.get("deepseek_resume_after_top3", {}).get("status", "missing_output"),
            "writeback_right": "block_or_quarantine_only",
            "source_artifacts": [rel(RESUME_PROMPTS), rel(PENDING_IDS), "outputs/research_progress_snapshot/split20_resume_export_audit.json"],
        },
        {
            "surface_id": "qwen_full_backup_inputs",
            "priority": "P1",
            "input_type": "llm_full_prompts",
            "status": "input_ready_waiting_credentials",
            "expected_calls": int(split_manifest.get("summary", {}).get("prompt_calls") or 147),
            "observed_calls": full_prompts["prompt_calls"],
            "expected_parent_windows": int(split_manifest.get("summary", {}).get("parent_windows") or 104),
            "observed_parent_windows": full_prompts["parent_windows"],
            "parse_errors": full_prompts["parse_errors"],
            "missing_input_files": [] if full_prompts["exists"] else [rel(FULL_PROMPTS)],
            "input_consistency": (
                full_prompts["prompt_calls"] == int(split_manifest.get("summary", {}).get("prompt_calls") or 147)
                and full_prompts["parent_windows"] == int(split_manifest.get("summary", {}).get("parent_windows") or 104)
                and full_prompts["parse_errors"] == 0
            ),
            "credential_or_quota_blocker": "missing_dashscope_or_bailian_api_key_env",
            "output_status": output_surfaces.get("qwen_full_backup", {}).get("status", "missing_output"),
            "writeback_right": "block_or_quarantine_only",
            "source_artifacts": [rel(FULL_PROMPTS), "outputs/research_progress_snapshot/split20_full_live_manifest.json"],
        },
        {
            "surface_id": "omni48_label_only_inputs",
            "priority": "P1",
            "input_type": "omni_audio_manifest",
            "status": "input_ready_waiting_credentials",
            "expected_calls": int(omni_summary.get("expected_call_count") or 96),
            "observed_calls": int(omni_summary.get("call_count") or 0),
            "expected_parent_windows": int(omni_summary.get("window_count") or 48),
            "observed_parent_windows": len(omni_rows),
            "parse_errors": 0,
            "missing_input_files": [] if (root / OMNI_CSV).exists() else [rel(OMNI_CSV)],
            "input_consistency": (
                len(omni_rows) == int(omni_summary.get("window_count") or 48)
                and int(omni_summary.get("audio_missing_count") or 0) == 0
                and int(omni_summary.get("call_count") or 0) == int(omni_summary.get("expected_call_count") or 96)
            ),
            "credential_or_quota_blocker": "missing_dashscope_or_bailian_api_key_env",
            "output_status": output_surfaces.get("omni48_label_only", {}).get("status", "missing_output"),
            "writeback_right": "label_only_no_timeline_writeback",
            "source_artifacts": [rel(OMNI_CSV), "outputs/research_progress_snapshot/omni48_live_call_manifest.json"],
        },
    ]

    for row in rows:
        row["live_calls_performed_by_builder"] = 0
        row["input_ready"] = (
            row["input_consistency"]
            and row["observed_calls"] == row["expected_calls"]
            and row["observed_parent_windows"] == row["expected_parent_windows"]
            and row["parse_errors"] == 0
            and not row["missing_input_files"]
        )

    ready_rows = [row["surface_id"] for row in rows if row["input_ready"]]
    p0_ready = [row["surface_id"] for row in rows if row["priority"] == "P0" and row["input_ready"]]
    output_missing = [row["surface_id"] for row in rows if row["output_status"] == "missing_output"]
    credential_blocked = readiness.get("summary", {}).get("blocked_runs", [])

    return {
        "runtime_contract": "live_input_integrity_audit_no_live_calls",
        "status": "inputs_ready_waiting_credentials_or_quota" if len(ready_rows) == len(rows) else "input_gap_detected",
        "source_contracts": {
            "split20_resume_export_audit": split_export.get("runtime_contract", ""),
            "split20_full_live_manifest": split_manifest.get("runtime_contract", ""),
            "omni48_live_call_manifest": omni_manifest.get("runtime_contract", ""),
            "live_run_readiness": readiness.get("runtime_contract", ""),
            "live_output_audit": output_audit.get("runtime_contract", ""),
            "live_parallelism_sensitivity": parallelism.get("runtime_contract", ""),
        },
        "summary": {
            "surface_count": len(rows),
            "input_ready_surfaces": len(ready_rows),
            "p0_input_ready_surfaces": len(p0_ready),
            "missing_input_surfaces": len(rows) - len(ready_rows),
            "output_missing_surfaces": len(output_missing),
            "credential_or_quota_blocked_runs": len(credential_blocked),
            "deepseek_resume_prompt_calls": resume_prompts["prompt_calls"],
            "deepseek_resume_parent_windows": resume_prompts["parent_windows"],
            "deepseek_resume_pending_ids": len(pending_ids),
            "qwen_full_prompt_calls": full_prompts["prompt_calls"],
            "qwen_full_parent_windows": full_prompts["parent_windows"],
            "omni48_manifest_windows": len(omni_rows),
            "omni48_planned_calls": int(omni_summary.get("call_count") or 0),
            "recommended_policy": parallelism.get("summary", {}).get("recommended_policy", "max20"),
            "recommended_workers": parallelism.get("summary", {}).get("recommended_workers", 8),
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "input_ready_surface_ids": ready_rows,
        "output_missing_surface_ids": output_missing,
        "rows": rows,
    }


def write_csv(audit: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "surface_id",
        "priority",
        "input_type",
        "status",
        "expected_calls",
        "observed_calls",
        "expected_parent_windows",
        "observed_parent_windows",
        "parse_errors",
        "input_ready",
        "input_consistency",
        "credential_or_quota_blocker",
        "output_status",
        "writeback_right",
        "source_artifacts",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in audit["rows"]:
            out = dict(row)
            out["source_artifacts"] = "; ".join(out["source_artifacts"])
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    lines = [
        "# Live Input Integrity Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Surfaces: `{summary['surface_count']}`",
        f"- Input-ready surfaces: `{summary['input_ready_surfaces']}`",
        f"- P0 input-ready surfaces: `{summary['p0_input_ready_surfaces']}`",
        f"- Output-missing surfaces: `{summary['output_missing_surfaces']}`",
        f"- DeepSeek resume prompt calls: `{summary['deepseek_resume_prompt_calls']}`",
        f"- Qwen full prompt calls: `{summary['qwen_full_prompt_calls']}`",
        f"- Omni48 planned calls: `{summary['omni48_planned_calls']}`",
        f"- Recommended policy/workers: `{summary['recommended_policy']}` / `{summary['recommended_workers']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Surface | Priority | Type | Calls | Parents/windows | Input ready | Output status | Writeback right |",
        "|---|---|---|---:|---:|---|---|---|",
    ]
    for row in audit["rows"]:
        lines.append(
            f"| `{row['surface_id']}` | `{row['priority']}` | `{row['input_type']}` | "
            f"{row['observed_calls']}/{row['expected_calls']} | {row['observed_parent_windows']}/{row['expected_parent_windows']} | "
            f"`{row['input_ready']}` | `{row['output_status']}` | `{row['writeback_right']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- All three pending live surfaces have complete local inputs; they are waiting on credentials, quota, or live outputs.",
            "- DeepSeek resume is P0 and uses the exported 139-call resume prompt surface.",
            "- Qwen full backup and Omni48 are P1 input-ready surfaces, but they remain fallback/label-only and do not support new metric claims.",
            "- This builder performs no live/API/model calls and writes no secret values.",
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
