#!/usr/bin/env python3
"""Dry-export and audit the split20 resume-after-top3 prompt surface."""

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
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path("outputs/research_progress_snapshot/split20_full_live_manifest.json")
EXPORT_JSONL = Path("outputs/research_progress_snapshot/split20_resume_after_top3_export_prompts.jsonl")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def export_command(output_jsonl: Path, pending_file: str) -> list[str]:
    return [
        sys.executable,
        "scripts/llm/llm_window_batch_policy_eval.py",
        "--mode",
        "export",
        "--decisions",
        "outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl",
        "--trigger-policy",
        "proxy_flagged_window",
        "--window-evidence",
        "outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv",
        "--patch-id-file",
        "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt",
        "--window-id-file",
        pending_file,
        "--max-patches-per-call",
        "20",
        "--model",
        "deepseek-v4-flash",
        "--output-jsonl",
        str(output_jsonl),
    ]


def build_audit(root: Path, export_jsonl: Path) -> dict[str, Any]:
    manifest = read_json(root / MANIFEST)
    resume = manifest.get("resume_surface", {})
    pending_file = str(resume.get("pending_window_id_file", ""))
    completed_file = str(resume.get("completed_window_id_file", ""))
    failed_file = str(resume.get("failed_window_id_file", ""))
    cmd = export_command(export_jsonl, pending_file)
    started = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)
    if started.returncode != 0:
        raise RuntimeError(started.stderr or started.stdout)

    prompt_rows = read_jsonl(root / export_jsonl)
    pending_ids = read_lines(root / pending_file)
    completed_ids = read_lines(root / completed_file)
    failed_ids = read_lines(root / failed_file)
    parent_ids = sorted({str(row.get("parent_window_id") or row.get("window_id", "")) for row in prompt_rows})
    sub_batch_distribution = Counter(str(row.get("sub_batch_count", 1)) for row in prompt_rows)
    completed_overlap = sorted(set(parent_ids) & set(completed_ids))
    missing_pending = sorted(set(pending_ids) - set(parent_ids))
    extra_parent_ids = sorted(set(parent_ids) - set(pending_ids))
    failed_missing = sorted(set(failed_ids) - set(parent_ids))
    prompt_patch_refs = sum(int(row.get("patch_count") or 0) for row in prompt_rows)
    expected_calls = int(manifest.get("summary", {}).get("deepseek_resume_required_calls_min", 0))
    expected_parents = int(manifest.get("summary", {}).get("deepseek_resume_parent_windows", 0))
    failures = []
    if len(prompt_rows) != expected_calls:
        failures.append("export_prompt_count_mismatch")
    if len(parent_ids) != expected_parents:
        failures.append("export_parent_count_mismatch")
    if completed_overlap:
        failures.append("export_includes_completed_top3")
    if missing_pending:
        failures.append("export_missing_pending_parent")
    if extra_parent_ids:
        failures.append("export_has_extra_parent")
    if failed_missing:
        failures.append("export_missing_quota_failed_parent")
    return {
        "runtime_contract": "split20_resume_export_audit_no_live_calls",
        "status": "pass" if not failures else "fail",
        "export_prompt_jsonl": str(export_jsonl),
        "export_command": " ".join(cmd),
        "summary": {
            "export_prompts": len(prompt_rows),
            "export_parent_windows": len(parent_ids),
            "prompt_patch_references": prompt_patch_refs,
            "expected_prompts": expected_calls,
            "expected_parent_windows": expected_parents,
            "pending_window_id_file": pending_file,
            "pending_ids": len(pending_ids),
            "completed_ids": len(completed_ids),
            "failed_ids": len(failed_ids),
            "completed_overlap": completed_overlap,
            "missing_pending": missing_pending[:20],
            "extra_parent_ids": extra_parent_ids[:20],
            "failed_missing": failed_missing,
            "sub_batch_count_distribution": dict(sub_batch_distribution),
            "live_calls_performed": 0,
        },
        "failures": failures,
    }


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    lines = [
        "# Split20 Resume Export Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Export prompts: `{summary['export_prompts']}` / expected `{summary['expected_prompts']}`",
        f"- Export parents: `{summary['export_parent_windows']}` / expected `{summary['expected_parent_windows']}`",
        f"- Pending ids: `{summary['pending_ids']}`",
        f"- Completed overlap: `{len(summary['completed_overlap'])}`",
        f"- Failed quota parents retained: `{summary['failed_ids'] - len(summary['failed_missing'])}/{summary['failed_ids']}`",
        f"- Live calls performed: `{summary['live_calls_performed']}`",
        f"- Export prompt JSONL: `{audit['export_prompt_jsonl']}`",
        "",
        "## Command",
        "",
        "```bash",
        audit["export_command"],
        "```",
        "",
        "## Reading",
        "",
        "- This audit runs the existing batch runner in export mode only; it does not call any model.",
        "- It proves the resume window-id file selects the intended remaining parent windows after excluding completed top3.",
        "- The two quota-failed top4/top5 windows remain in the pending surface, because they still need valid DeepSeek generation.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-jsonl", type=Path, default=EXPORT_JSONL)
    parser.add_argument("--output-json", type=Path, default=Path("outputs/research_progress_snapshot/split20_resume_export_audit.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/research_progress_snapshot/split20_resume_export_audit.md"))
    args = parser.parse_args()

    audit = build_audit(ROOT, args.export_jsonl)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(audit, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.export_jsonl}")
    print(json.dumps({"status": audit["status"], "summary": audit["summary"], "failures": audit["failures"]}, ensure_ascii=False, sort_keys=True))
    if audit["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
