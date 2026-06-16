#!/usr/bin/env python3
"""Build the full-surface split20 live-run manifest without live calls."""

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
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROMPTS = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompts.jsonl")
LATENCY_CSV = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_latency.csv")
SIM_CSV = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation.csv")
SIM_SUMMARY = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation_summary.json")
TOP3 = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_comparison.json")
TOP45_ATTEMPT = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top4_5_parallel_attempt_summary.json")
QWEN_TOP45 = Path("outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json")
PENDING_WINDOW_IDS = Path("outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt")
COMPLETED_WINDOW_IDS = Path("outputs/research_progress_snapshot/split20_deepseek_completed_top3_window_ids.txt")
FAILED_WINDOW_IDS = Path("outputs/research_progress_snapshot/split20_deepseek_quota_failed_window_ids.txt")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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


def rel(path: Path) -> str:
    return str(path)


def prompt_char_len(row: dict[str, Any]) -> int:
    return sum(len(str(message.get("content", ""))) for message in row.get("messages", []))


def executable_deepseek_command(output_jsonl: str, window_id_file: str | None = None) -> str:
    command = (
        "python scripts/llm/llm_window_batch_policy_eval.py "
        "--mode call "
        "--decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl "
        "--trigger-policy proxy_flagged_window "
        "--window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv "
        "--patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt "
    )
    if window_id_file:
        command += f"--window-id-file {window_id_file} "
    command += (
        "--max-patches-per-call 20 "
        "--model deepseek-v4-flash "
        "--parallel-workers 8 "
        "--skip-existing-output "
        "--max-call-attempts 2 "
        "--retry-backoff-seconds 2.0 "
        f"--output-jsonl {output_jsonl}"
    )
    return command


def build_manifest(root: Path) -> dict[str, Any]:
    prompt_rows = read_jsonl(root / PROMPTS)
    latency_rows = {row["window_id"]: row for row in read_csv(root / LATENCY_CSV)}
    sim_rows = {row["window_id"]: row for row in read_csv(root / SIM_CSV) if row.get("max_patches_per_call") == "20"}
    sim_summary = read_json(root / SIM_SUMMARY)
    top3 = read_json(root / TOP3)
    top45_attempt = read_json(root / TOP45_ATTEMPT)
    qwen_top45 = read_json(root / QWEN_TOP45)

    prompt_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in prompt_rows:
        prompt_by_parent[str(row.get("parent_window_id") or row.get("window_id"))].append(row)

    deepseek_completed = {row.get("parent_window_id") for row in top3.get("parents", [])}
    deepseek_failed = set(top45_attempt.get("parent_windows", []))
    qwen_completed = {row.get("parent_window_id") for row in qwen_top45.get("parents", [])}
    top3_by_parent = {row.get("parent_window_id"): row for row in top3.get("parents", [])}
    qwen_by_parent = {row.get("parent_window_id"): row for row in qwen_top45.get("parents", [])}

    parent_rows = []
    for parent_id, calls in sorted(
        prompt_by_parent.items(),
        key=lambda item: -float(latency_rows.get(item[0], {}).get("call_seconds") or 0.0),
    ):
        latency = latency_rows.get(parent_id, {})
        sim = sim_rows.get(parent_id, {})
        deepseek_status = "pending_live"
        if parent_id in deepseek_completed:
            deepseek_status = "completed_top3_parallel"
        elif parent_id in deepseek_failed:
            deepseek_status = f"failed_{top45_attempt.get('failure_type', 'unknown')}"
        qwen_status = "not_run"
        if parent_id in qwen_completed:
            qwen_status = "completed_backup"
        parent_rows.append(
            {
                "parent_window_id": parent_id,
                "recording_id": parent_id.split(":")[0],
                "segment_idx": parent_id.split(":")[-1],
                "patch_count": int(latency.get("patch_count") or sum(int(row.get("patch_count") or 0) for row in calls)),
                "subcalls": len(calls),
                "prompt_chars": sum(prompt_char_len(row) for row in calls),
                "estimated_prompt_tokens_chars_div4": round(sum(prompt_char_len(row) for row in calls) / 4),
                "original_call_seconds": float(latency.get("call_seconds") or 0.0),
                "simulated_parallel_call_seconds": float(sim.get("simulated_parallel_call_seconds") or 0.0),
                "observed_total_tokens": int(float(latency.get("total_tokens") or 0)),
                "simulated_total_tokens": float(sim.get("simulated_total_tokens") or 0.0),
                "window_decision": latency.get("window_decision", ""),
                "deepseek_status": deepseek_status,
                "deepseek_live_split_max_seconds": float(top3_by_parent.get(parent_id, {}).get("split_max_call_seconds") or 0.0),
                "deepseek_live_token_multiplier": float(top3_by_parent.get(parent_id, {}).get("token_multiplier") or 0.0),
                "qwen_status": qwen_status,
                "qwen_live_split_max_seconds": float(qwen_by_parent.get(parent_id, {}).get("split_max_call_seconds") or 0.0),
                "qwen_live_token_multiplier": float(qwen_by_parent.get(parent_id, {}).get("token_multiplier") or 0.0),
            }
        )

    total_calls = len(prompt_rows)
    completed_deepseek_calls = int(top3.get("split_calls", 0))
    failed_deepseek_calls = int(top45_attempt.get("failed_calls", 0))
    qwen_calls = int(qwen_top45.get("split_calls", 0))
    recommended = sim_summary.get("recommended_policy", {})
    completed_window_ids = [row["parent_window_id"] for row in parent_rows if row["deepseek_status"] == "completed_top3_parallel"]
    failed_window_ids = [row["parent_window_id"] for row in parent_rows if row["deepseek_status"].startswith("failed_")]
    pending_window_ids = [row["parent_window_id"] for row in parent_rows if row["deepseek_status"] != "completed_top3_parallel"]
    pending_calls = sum(int(row["subcalls"]) for row in parent_rows if row["parent_window_id"] in set(pending_window_ids))
    summary = {
        "parent_windows": len(prompt_by_parent),
        "prompt_calls": total_calls,
        "patch_references": sum(int(row.get("patch_count") or 0) for row in prompt_rows),
        "split_parent_windows": sum(1 for rows in prompt_by_parent.values() if len(rows) > 1),
        "max_subcalls_per_parent": max((len(rows) for rows in prompt_by_parent.values()), default=0),
        "estimated_prompt_tokens_chars_div4": round(sum(prompt_char_len(row) for row in prompt_rows) / 4),
        "recommended_max_patches_per_call": recommended.get("max_patches_per_call", 20),
        "simulated_p95_call_seconds": recommended.get("p95_call_seconds"),
        "simulated_p95_correction_delay_seconds": recommended.get("p95_correction_delay_seconds"),
        "simulated_token_multiplier": recommended.get("token_multiplier"),
        "deepseek_completed_parent_windows": len(deepseek_completed),
        "deepseek_completed_calls": completed_deepseek_calls,
        "deepseek_top3_wall_seconds": top3.get("measured_wall_seconds"),
        "deepseek_top3_harmful_accepts": top3.get("harmful_accepts"),
        "deepseek_quota_failed_parent_windows": len(deepseek_failed),
        "deepseek_quota_failed_calls": failed_deepseek_calls,
        "deepseek_failure_type": top45_attempt.get("failure_type", ""),
        "deepseek_resume_parent_windows": len(pending_window_ids),
        "deepseek_resume_required_calls_min": pending_calls,
        "deepseek_full_surface_status": "blocked_by_provider_quota_or_capacity",
        "qwen_backup_parent_windows": len(qwen_completed),
        "qwen_backup_calls": qwen_calls,
        "qwen_backup_wall_seconds": (qwen_top45.get("runs") or [{}])[0].get("wall_seconds"),
        "qwen_backup_harmful_accepts": qwen_top45.get("harmful_accepts"),
        "qwen_backup_latency_verdict": "slower_than_original_max",
        "live_calls_performed_by_builder": 0,
    }
    return {
        "runtime_contract": "split20_full_live_manifest_no_live_calls",
        "summary": summary,
        "source_artifacts": [
            rel(PROMPTS),
            rel(LATENCY_CSV),
            rel(SIM_SUMMARY),
            rel(TOP3),
            rel(TOP45_ATTEMPT),
            rel(QWEN_TOP45),
        ],
        "resume_surface": {
            "pending_window_id_file": rel(PENDING_WINDOW_IDS),
            "pending_parent_windows": len(pending_window_ids),
            "pending_calls": pending_calls,
            "completed_window_id_file": rel(COMPLETED_WINDOW_IDS),
            "completed_parent_windows": len(completed_window_ids),
            "failed_window_id_file": rel(FAILED_WINDOW_IDS),
            "failed_parent_windows": len(failed_window_ids),
            "pending_window_ids": pending_window_ids,
            "completed_window_ids": completed_window_ids,
            "failed_window_ids": failed_window_ids,
        },
        "run_commands": {
            "deepseek_full_parallel": executable_deepseek_command(
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_live.jsonl"
            ),
            "deepseek_resume_after_top3": executable_deepseek_command(
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl",
                window_id_file=rel(PENDING_WINDOW_IDS),
            ),
            "qwen_backup_full_parallel": executable_deepseek_command(
                "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl"
            ).replace("deepseek-v4-flash", "qwen3.6-flash-2026-04-16"),
        },
        "parents": parent_rows,
    }


def write_csv_rows(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_id_file(ids: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(ids) + ("\n" if ids else ""), encoding="utf-8")


def write_markdown(manifest: dict[str, Any], path: Path) -> None:
    summary = manifest["summary"]
    resume = manifest["resume_surface"]
    lines = [
        "# Split20 Full Live Manifest",
        "",
        f"- Runtime contract: `{manifest['runtime_contract']}`",
        f"- Parent windows: `{summary['parent_windows']}`",
        f"- Prompt calls: `{summary['prompt_calls']}`",
        f"- Patch references: `{summary['patch_references']}`",
        f"- Split parent windows: `{summary['split_parent_windows']}`",
        f"- Max subcalls per parent: `{summary['max_subcalls_per_parent']}`",
        f"- Estimated prompt tokens proxy: `{summary['estimated_prompt_tokens_chars_div4']}`",
        f"- Simulated P95 call: `{summary['simulated_p95_call_seconds']}s`",
        f"- Simulated P95 correction delay: `{summary['simulated_p95_correction_delay_seconds']}s`",
        f"- DeepSeek completed: `{summary['deepseek_completed_parent_windows']}` parents / `{summary['deepseek_completed_calls']}` calls",
        f"- DeepSeek top3 wall: `{summary['deepseek_top3_wall_seconds']}s`; harmful accepts `{summary['deepseek_top3_harmful_accepts']}`",
        f"- DeepSeek quota failed: `{summary['deepseek_quota_failed_parent_windows']}` parents / `{summary['deepseek_quota_failed_calls']}` calls; `{summary['deepseek_failure_type']}`",
        f"- DeepSeek resume surface: `{summary['deepseek_resume_parent_windows']}` parents / `{summary['deepseek_resume_required_calls_min']}` calls",
        f"- Qwen backup: `{summary['qwen_backup_parent_windows']}` parents / `{summary['qwen_backup_calls']}` calls; wall `{summary['qwen_backup_wall_seconds']}s`; harmful `{summary['qwen_backup_harmful_accepts']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        "",
        "## Resume Surface",
        "",
        f"- Pending window-id file: `{resume['pending_window_id_file']}`",
        f"- Pending parent windows: `{resume['pending_parent_windows']}`",
        f"- Pending calls: `{resume['pending_calls']}`",
        f"- Completed top3 window-id file: `{resume['completed_window_id_file']}`",
        f"- Failed quota window-id file: `{resume['failed_window_id_file']}`",
        "",
        "## Commands",
        "",
    ]
    for name, command in manifest["run_commands"].items():
        lines.extend([f"### {name}", "", "```bash", command, "```", ""])
    lines.extend(
        [
            "## Slowest Parent Windows",
            "",
            "| Parent | Patches | Subcalls | Original call | Sim split | DeepSeek status | Qwen status |",
            "|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in manifest["parents"][:12]:
        lines.append(
            "| {parent_window_id} | {patch_count} | {subcalls} | {original_call_seconds:.2f}s | "
            "{simulated_parallel_call_seconds:.2f}s | `{deepseek_status}` | `{qwen_status}` |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This manifest is the execution surface for the P0 full split20 live validation; it does not call any model.",
            "- The current positive latency evidence is limited to the DeepSeek top3 parallel smoke.",
            "- Qwen backup proves the top4/top5 execution path can run with harmful accept 0, but it is slower and cannot support the latency claim.",
            "- Full-surface latency remains unclaimed until the DeepSeek quota/capacity blocker is removed and all 104 parent windows complete.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=Path("outputs/research_progress_snapshot/split20_full_live_manifest.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/research_progress_snapshot/split20_full_live_manifest.md"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/research_progress_snapshot/split20_full_live_manifest.csv"))
    args = parser.parse_args()

    manifest = build_manifest(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(manifest, args.output_md)
    write_csv_rows(manifest["parents"], args.output_csv)
    write_id_file(manifest["resume_surface"]["pending_window_ids"], ROOT / PENDING_WINDOW_IDS)
    write_id_file(manifest["resume_surface"]["completed_window_ids"], ROOT / COMPLETED_WINDOW_IDS)
    write_id_file(manifest["resume_surface"]["failed_window_ids"], ROOT / FAILED_WINDOW_IDS)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {PENDING_WINDOW_IDS}")
    print(f"Wrote {COMPLETED_WINDOW_IDS}")
    print(f"Wrote {FAILED_WINDOW_IDS}")
    print(json.dumps(manifest["summary"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
