#!/usr/bin/env python3
"""Build a non-secret readiness manifest for pending live LLM/Omni runs."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DASHSCOPE_ENV_NAMES = ["DASHSCOPE_API_KEY", "BAILIAN_API_KEY", "ALIYUN_BAILIAN_API_KEY"]
BASE_URL_ENV_NAMES = ["DASHSCOPE_BASE_URL"]


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


def env_presence(names: list[str]) -> dict[str, bool]:
    return {name: bool(os.environ.get(name)) for name in names}


def has_any_env(presence: dict[str, bool]) -> bool:
    return any(presence.values())


def split20_call_command(model: str, output_jsonl: str, window_id_file: str | None = None) -> str:
    command = (
        "python scripts/llm_window_batch_policy_eval.py --mode call "
        "--decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl "
        "--trigger-policy proxy_flagged_window "
        "--window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv "
        "--patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt "
        "--max-patches-per-call 20 "
    )
    if window_id_file:
        command += f"--window-id-file {window_id_file} "
    command += (
        f"--model {model} --parallel-workers 8 --skip-existing-output "
        f"--max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl {output_jsonl}"
    )
    return command


def text_len(row: dict[str, Any]) -> int:
    return sum(len(str(message.get("content", ""))) for message in row.get("messages", []))


def build_split_prompt_summary(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    parent_ids = {row.get("parent_window_id", "") for row in rows if row.get("parent_window_id")}
    parent_patch_counts: dict[str, int] = {}
    subcalls_by_parent: dict[str, int] = {}
    patch_refs = 0
    prompt_chars = 0
    for row in rows:
        parent = str(row.get("parent_window_id", ""))
        patch_count = int(row.get("patch_count") or 0)
        patch_refs += patch_count
        prompt_chars += text_len(row)
        if parent:
            parent_patch_counts[parent] = max(parent_patch_counts.get(parent, 0), int(row.get("parent_patch_count") or 0))
            subcalls_by_parent[parent] = max(subcalls_by_parent.get(parent, 0), int(row.get("sub_batch_count") or 0))
    return {
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
        "prompt_calls": len(rows),
        "parent_windows": len(parent_ids),
        "patch_references": patch_refs,
        "unique_parent_patches": sum(parent_patch_counts.values()),
        "max_parallel_subcalls_per_parent": max(subcalls_by_parent.values()) if subcalls_by_parent else 0,
        "estimated_input_tokens_chars_div4": round(prompt_chars / 4),
    }


def build_omni_summary(root: Path) -> dict[str, Any]:
    manifest_path = root / "outputs/research_progress_snapshot/omni_expansion_manifest.json"
    csv_path = root / "outputs/research_progress_snapshot/omni_expansion_manifest.csv"
    call_manifest_path = root / "outputs/research_progress_snapshot/omni48_live_call_manifest.json"
    manifest = read_json(manifest_path)
    call_manifest = read_json(call_manifest_path)
    rows = read_csv(csv_path)
    summary = manifest.get("summary", {})
    call_summary = call_manifest.get("summary", {})
    target_models = summary.get("target_models", [])
    clip_sec_total = sum(float(row.get("clip_sec") or 0.0) for row in rows)
    roles = Counter(row.get("expansion_role", "") for row in rows)
    missing_audio = [f"{row.get('recording_id')}:{row.get('window_size')}:{row.get('segment_idx')}" for row in rows if row.get("audio_exists") != "1"]
    return {
        "manifest_json": str(manifest_path.relative_to(root)),
        "manifest_csv": str(csv_path.relative_to(root)),
        "call_manifest_json": str(call_manifest_path.relative_to(root)),
        "call_manifest_contract": call_manifest.get("runtime_contract", ""),
        "runtime_contract": manifest.get("runtime_contract", ""),
        "selected_windows": len(rows),
        "target_models": target_models,
        "planned_model_calls": int(call_summary.get("call_count") or summary.get("planned_model_calls") or len(rows) * len(target_models)),
        "audio_missing_count": len(missing_audio),
        "audio_missing_windows": missing_audio,
        "clip_audio_seconds": round(clip_sec_total, 3),
        "billable_clip_model_seconds_proxy": round(clip_sec_total * max(len(target_models), 1), 3),
        "role_counts": dict(roles),
        "run_command": summary.get("run_command", ""),
    }


def status_from_blockers(blockers: list[str]) -> str:
    if not blockers:
        return "ready_for_user_approved_live_run"
    lowered = [blocker.lower() for blocker in blockers]
    if any("quota" in blocker or "capacity" in blocker for blocker in lowered):
        return "blocked_by_provider_quota_or_capacity"
    if any("credential" in blocker or "api_key" in blocker for blocker in lowered):
        return "blocked_missing_credentials"
    return "blocked_by_manifest_or_input_gap"


def build_readiness(root: Path) -> dict[str, Any]:
    dashscope_presence = env_presence(DASHSCOPE_ENV_NAMES)
    base_url_presence = env_presence(BASE_URL_ENV_NAMES)
    dashscope_ready = has_any_env(dashscope_presence)
    split_prompts = build_split_prompt_summary(
        root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompts.jsonl"
    )
    split_resume_prompts = build_split_prompt_summary(
        root / "outputs/research_progress_snapshot/split20_resume_after_top3_export_prompts.jsonl"
    )
    split_resume_window_id_file = (
        "outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt"
    )
    omni = build_omni_summary(root)
    deepseek_top3 = read_json(
        root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_comparison.json"
    )
    deepseek_attempt = read_json(
        root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top4_5_parallel_attempt_summary.json"
    )
    qwen_split = read_json(root / "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json")

    omni_blockers = []
    if not dashscope_ready:
        omni_blockers.append("missing_dashscope_or_bailian_api_key_env")
    if omni["selected_windows"] < 48:
        omni_blockers.append("omni_manifest_under_48_windows")
    if omni["audio_missing_count"]:
        omni_blockers.append("omni_manifest_missing_audio")

    deepseek_blockers = []
    if not dashscope_ready:
        deepseek_blockers.append("missing_dashscope_or_bailian_api_key_env")
    if not split_resume_prompts["exists"] or int(split_resume_prompts["prompt_calls"]) < 139:
        deepseek_blockers.append("split20_resume_prompt_manifest_incomplete")
    if deepseek_attempt.get("failure_type"):
        deepseek_blockers.append(f"known_deepseek_top4_5_failure_{deepseek_attempt.get('failure_type')}")

    qwen_blockers = []
    if not dashscope_ready:
        qwen_blockers.append("missing_dashscope_or_bailian_api_key_env")
    if not split_prompts["exists"] or int(split_prompts["prompt_calls"]) < 147:
        qwen_blockers.append("split20_prompt_manifest_incomplete")

    rows = [
        {
            "run_id": "omni48_live",
            "priority": "P1",
            "status": status_from_blockers(omni_blockers),
            "blocked": bool(omni_blockers),
            "blockers": omni_blockers,
            "planned_calls": omni["planned_model_calls"],
            "planned_windows": omni["selected_windows"],
            "target_models": omni["target_models"],
            "estimated_input_scale": f"{omni['billable_clip_model_seconds_proxy']} clip-model seconds proxy",
            "source_artifacts": [omni["manifest_json"], omni["manifest_csv"], omni["call_manifest_json"]],
            "run_command": omni["run_command"],
            "notes": "Manifest is no-writeback and label-only; live run still spends provider quota.",
        },
        {
            "run_id": "split20_deepseek_full",
            "priority": "P0",
            "status": status_from_blockers(deepseek_blockers),
            "blocked": bool(deepseek_blockers),
            "blockers": deepseek_blockers,
            "planned_calls": split_resume_prompts["prompt_calls"],
            "planned_windows": split_resume_prompts["parent_windows"],
            "target_models": ["deepseek-v4-flash"],
            "estimated_input_scale": f"{split_resume_prompts['estimated_input_tokens_chars_div4']} prompt tokens proxy",
            "source_artifacts": [
                split_resume_prompts["path"],
                split_resume_window_id_file,
                "outputs/research_progress_snapshot/split20_resume_export_audit.json",
                "outputs/research_progress_snapshot/split20_full_live_manifest.json",
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top4_5_parallel_attempt_summary.json",
            ],
            "run_command": split20_call_command(
                "deepseek-v4-flash",
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl",
                split_resume_window_id_file,
            ),
            "notes": (
                "Resume surface excludes completed top3 parents; top4/5 failed before generation "
                "with provider quota exhaustion and remain in the pending resume set."
            ),
        },
        {
            "run_id": "split20_qwen_backup",
            "priority": "P1",
            "status": status_from_blockers(qwen_blockers),
            "blocked": bool(qwen_blockers),
            "blockers": qwen_blockers,
            "planned_calls": split_prompts["prompt_calls"],
            "planned_windows": split_prompts["parent_windows"],
            "target_models": ["qwen3.6-flash-2026-04-16"],
            "estimated_input_scale": f"{split_prompts['estimated_input_tokens_chars_div4']} prompt tokens proxy",
            "source_artifacts": [
                split_prompts["path"],
                "outputs/research_progress_snapshot/split20_full_live_manifest.json",
                "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json",
            ],
            "run_command": split20_call_command(
                "qwen3.6-flash-2026-04-16",
                "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl",
            ),
            "notes": "Backup top4/5 evidence had harmful 0 but slower wall time than the original max-call baseline.",
        },
    ]
    blocked = [row["run_id"] for row in rows if row["blocked"]]
    ready = [row["run_id"] for row in rows if not row["blocked"]]
    return {
        "runtime_contract": "live_run_readiness_non_secret_no_live_calls",
        "secret_policy": "env_presence_only_no_secret_values_written",
        "environment": {
            "dashscope_like_api_key_present": dashscope_ready,
            "dashscope_env_present": dashscope_presence,
            "base_url_env_present": base_url_presence,
            "config_defaults_not_counted_as_credentials": True,
        },
        "omni48_manifest": omni,
        "split20_prompt_manifest": split_prompts,
        "split20_resume_prompt_manifest": split_resume_prompts,
        "historical_live_evidence": {
            "deepseek_top3_wall_seconds": deepseek_top3.get("measured_wall_seconds"),
            "deepseek_top3_harmful_accepts": deepseek_top3.get("harmful_accepts"),
            "deepseek_top4_5_failure_type": deepseek_attempt.get("failure_type", ""),
            "qwen_top4_5_wall_seconds": (qwen_split.get("runs") or [{}])[0].get("wall_seconds"),
            "qwen_top4_5_harmful_accepts": qwen_split.get("harmful_accepts"),
        },
        "runs": rows,
        "summary": {
            "run_count": len(rows),
            "ready_count": len(ready),
            "blocked_count": len(blocked),
            "ready_runs": ready,
            "blocked_runs": blocked,
            "p0_blocked_count": sum(1 for row in rows if row["priority"] == "P0" and row["blocked"]),
            "non_secret": True,
            "live_calls_performed": 0,
        },
    }


def write_markdown(readiness: dict[str, Any], path: Path) -> None:
    summary = readiness["summary"]
    env = readiness["environment"]
    lines = [
        "# Live Run Readiness",
        "",
        f"- Runtime contract: `{readiness['runtime_contract']}`",
        f"- Secret policy: `{readiness['secret_policy']}`",
        f"- Ready runs: `{summary['ready_count']}`",
        f"- Blocked runs: `{summary['blocked_count']}`",
        f"- P0 blocked: `{summary['p0_blocked_count']}`",
        f"- Live calls performed: `{summary['live_calls_performed']}`",
        f"- DashScope/Bailian key present in env: `{env['dashscope_like_api_key_present']}`",
        f"- Config defaults counted as credentials: `{not env['config_defaults_not_counted_as_credentials']}`",
        "",
        "## Runs",
        "",
        "| Run | Priority | Status | Calls | Windows | Models | Blockers | Input scale |",
        "|---|---|---|---:|---:|---|---|---|",
    ]
    for row in readiness["runs"]:
        blockers = "<br>".join(row["blockers"]) if row["blockers"] else "none"
        models = "<br>".join(row["target_models"])
        lines.append(
            f"| `{row['run_id']}` | `{row['priority']}` | `{row['status']}` | "
            f"{row['planned_calls']} | {row['planned_windows']} | {models} | {blockers} | {row['estimated_input_scale']} |"
        )
    lines.extend(
        [
            "",
            "## Commands",
            "",
        ]
    )
    for row in readiness["runs"]:
        lines.extend([f"### {row['run_id']}", "", "```bash", row["run_command"], "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=Path("outputs/research_progress_snapshot/live_run_readiness.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/research_progress_snapshot/live_run_readiness.md"))
    args = parser.parse_args()

    readiness = build_readiness(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(readiness, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(readiness, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(json.dumps(readiness["summary"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
