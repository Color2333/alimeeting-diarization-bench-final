#!/usr/bin/env python3
"""Dry-export and audit the split15 stretch prompt surface."""

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
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXPORT_JSONL = Path("outputs/research_progress_snapshot/split15_stretch_reexport_prompts.jsonl")
OUTPUT_JSON = Path("outputs/research_progress_snapshot/split15_stretch_reexport_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/split15_stretch_reexport_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/split15_stretch_reexport_audit.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def export_command(output_jsonl: Path) -> list[str]:
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
        "--max-patches-per-call",
        "15",
        "--model",
        "deepseek-v4-flash",
        "--output-jsonl",
        str(output_jsonl),
    ]


def prompt_char_len(row: dict[str, Any]) -> int:
    return sum(len(str(message.get("content", ""))) for message in row.get("messages", []))


def build_audit(root: Path, export_jsonl: Path) -> dict[str, Any]:
    split_policy = read_json(root / "outputs/research_progress_snapshot/split_policy_optimization.json")
    split_manifest = read_json(root / "outputs/research_progress_snapshot/split20_full_live_manifest.json")
    simulation = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation_summary.json")
    cmd = export_command(export_jsonl)
    proc = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)

    prompt_rows = read_jsonl(root / export_jsonl)
    parent_ids = sorted({str(row.get("parent_window_id") or row.get("window_id", "")) for row in prompt_rows})
    manifest_parent_ids = sorted(str(row.get("parent_window_id", "")) for row in split_manifest.get("parents", []))
    split15_policy = next(
        (
            row
            for row in split_policy.get("policies", [])
            if int(row.get("max_patches_per_call") or 0) == 15
        ),
        {},
    )
    sim15_policy = next(
        (
            row
            for row in simulation.get("policies", [])
            if int(row.get("max_patches_per_call") or 0) == 15
        ),
        {},
    )
    expected_prompts = int(split_policy.get("summary", {}).get("stretch_calls") or sim15_policy.get("calls") or 0)
    expected_parents = int(split_manifest.get("summary", {}).get("parent_windows") or 0)
    expected_split_windows = int(sim15_policy.get("split_windows") or split15_policy.get("split_windows") or 0)
    sub_batch_distribution = Counter(str(row.get("sub_batch_count", 1)) for row in prompt_rows)
    parent_call_counts = Counter(str(row.get("parent_window_id") or row.get("window_id", "")) for row in prompt_rows)
    split_parent_windows = sum(1 for count in parent_call_counts.values() if count > 1)
    max_subcalls_per_parent = max(parent_call_counts.values(), default=0)
    missing_parent_ids = sorted(set(manifest_parent_ids) - set(parent_ids))
    extra_parent_ids = sorted(set(parent_ids) - set(manifest_parent_ids))

    failures = []
    if len(prompt_rows) != expected_prompts:
        failures.append("stretch_prompt_count_mismatch")
    if len(parent_ids) != expected_parents:
        failures.append("stretch_parent_count_mismatch")
    if split_parent_windows != expected_split_windows:
        failures.append("stretch_split_window_count_mismatch")
    if missing_parent_ids:
        failures.append("stretch_missing_parent")
    if extra_parent_ids:
        failures.append("stretch_extra_parent")

    parent_rows = [
        {
            "parent_window_id": parent_id,
            "prompt_calls": parent_call_counts[parent_id],
            "recording_id": parent_id.split(":")[0],
            "segment_idx": parent_id.split(":")[-1],
        }
        for parent_id in parent_ids
    ]
    return {
        "runtime_contract": "split15_stretch_reexport_audit_no_live_calls",
        "status": "pass" if not failures else "fail",
        "export_prompt_jsonl": str(export_jsonl),
        "export_command": " ".join(cmd),
        "source_contracts": {
            "split_policy_optimization": split_policy.get("runtime_contract", ""),
            "split20_full_live_manifest": split_manifest.get("runtime_contract", ""),
        },
        "summary": {
            "export_prompts": len(prompt_rows),
            "expected_prompts": expected_prompts,
            "export_parent_windows": len(parent_ids),
            "expected_parent_windows": expected_parents,
            "split_parent_windows": split_parent_windows,
            "expected_split_parent_windows": expected_split_windows,
            "max_subcalls_per_parent": max_subcalls_per_parent,
            "prompt_patch_references": sum(int(row.get("patch_count") or 0) for row in prompt_rows),
            "estimated_prompt_tokens_chars_div4": round(sum(prompt_char_len(row) for row in prompt_rows) / 4),
            "simulated_p95_call_seconds": split15_policy.get("simulated_p95_call_seconds", sim15_policy.get("p95_call_seconds", 0.0)),
            "simulated_max_call_seconds": split15_policy.get("simulated_max_call_seconds", sim15_policy.get("max_call_seconds", 0.0)),
            "token_multiplier": split15_policy.get("token_multiplier", sim15_policy.get("token_multiplier", 0.0)),
            "requires_new_prompt_export": True,
            "top3_live_evidence_reusable": False,
            "missing_parent_count": len(missing_parent_ids),
            "extra_parent_count": len(extra_parent_ids),
            "sub_batch_count_distribution": dict(sub_batch_distribution),
            "live_calls_performed": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "missing_parent_ids": missing_parent_ids[:20],
        "extra_parent_ids": extra_parent_ids[:20],
        "failures": failures,
        "parents": parent_rows,
    }


def write_csv(audit: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["parent_window_id", "recording_id", "segment_idx", "prompt_calls"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in audit["parents"]:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    lines = [
        "# Split15 Stretch Re-export Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Export prompts: `{summary['export_prompts']}` / expected `{summary['expected_prompts']}`",
        f"- Export parents: `{summary['export_parent_windows']}` / expected `{summary['expected_parent_windows']}`",
        f"- Split parent windows: `{summary['split_parent_windows']}` / expected `{summary['expected_split_parent_windows']}`",
        f"- Max subcalls per parent: `{summary['max_subcalls_per_parent']}`",
        f"- Simulated P95 call: `{summary['simulated_p95_call_seconds']}`",
        f"- Token multiplier: `{summary['token_multiplier']}`",
        f"- Top3 live evidence reusable: `{summary['top3_live_evidence_reusable']}`",
        f"- Requires new prompt export: `{summary['requires_new_prompt_export']}`",
        f"- Live calls performed: `{summary['live_calls_performed']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
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
        "- The max15 surface is a stretch latency candidate, not the default P0 live path.",
        "- It cannot reuse max20 top3 live evidence as full-surface evidence; a fresh live output and scoring pass are required before any claim promotion.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-jsonl", type=Path, default=EXPORT_JSONL)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    audit = build_audit(ROOT, args.export_jsonl)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(audit, args.output_md)
    write_csv(audit, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.export_jsonl}")
    print(json.dumps({"status": audit["status"], "summary": audit["summary"], "failures": audit["failures"]}, ensure_ascii=False, sort_keys=True))
    if audit["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
