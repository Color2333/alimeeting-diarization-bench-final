#!/usr/bin/env python3
"""Build a no-live-call token and quota proxy budget audit."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_token_quota_budget_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_token_quota_budget_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_token_quota_budget_audit.csv")
RESUME_PROMPTS = Path("outputs/research_progress_snapshot/split20_resume_after_top3_export_prompts.jsonl")
FULL_PROMPTS = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompts.jsonl")


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


def prompt_char_len(row: dict[str, Any]) -> int:
    return sum(len(str(message.get("content", ""))) for message in row.get("messages", []))


def prompt_stats(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    chars = [prompt_char_len(row) for row in rows]
    return {
        "prompt_jsonl": str(path),
        "prompt_calls": len(rows),
        "parent_windows": len({str(row.get("parent_window_id") or row.get("window_id", "")) for row in rows}),
        "patch_references": sum(int(row.get("patch_count") or 0) for row in rows),
        "prompt_chars": sum(chars),
        "token_proxy_chars_div4": round(sum(chars) / 4),
        "avg_prompt_chars": round(sum(chars) / len(chars), 1) if chars else 0.0,
        "max_prompt_chars": max(chars, default=0),
    }


def command_by_id(command_audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("command_id")): row for row in command_audit.get("rows", [])}


def attempts_for(command: dict[str, Any]) -> int:
    try:
        return max(1, int(command.get("max_call_attempts") or 1))
    except (TypeError, ValueError):
        return 1


def llm_row(surface_id: str, priority: str, stats: dict[str, Any], command: dict[str, Any]) -> dict[str, Any]:
    max_attempts = attempts_for(command)
    token_proxy = int(stats["token_proxy_chars_div4"])
    return {
        "surface_id": surface_id,
        "priority": priority,
        "surface_type": "llm_prompt_jsonl",
        "prompt_or_call_count": stats["prompt_calls"],
        "parent_windows": stats["parent_windows"],
        "patch_references": stats["patch_references"],
        "prompt_chars": stats["prompt_chars"],
        "token_proxy_chars_div4": token_proxy,
        "max_prompt_chars": stats["max_prompt_chars"],
        "max_call_attempts": max_attempts,
        "max_attempted_requests": int(command.get("planned_live_calls") or stats["prompt_calls"]) * max_attempts,
        "retry_token_proxy_ceiling": token_proxy * max_attempts,
        "clip_model_seconds_proxy": "",
        "retry_clip_model_seconds_ceiling": "",
        "claim_status": "quota_proxy_planning_only_no_live_metric_claim",
    }


def omni_row(omni48: dict[str, Any], command: dict[str, Any]) -> dict[str, Any]:
    summary = omni48.get("summary", {})
    max_attempts = attempts_for(command)
    calls = int(summary.get("call_count") or 0)
    clip_model_seconds = float(summary.get("clip_model_seconds_proxy") or 0.0)
    return {
        "surface_id": "omni48_label_only",
        "priority": "P1",
        "surface_type": "omni_audio_call_manifest",
        "prompt_or_call_count": calls,
        "parent_windows": int(summary.get("window_count") or 0),
        "patch_references": "",
        "prompt_chars": "",
        "token_proxy_chars_div4": "",
        "max_prompt_chars": "",
        "max_call_attempts": max_attempts,
        "max_attempted_requests": calls * max_attempts,
        "retry_token_proxy_ceiling": "",
        "clip_model_seconds_proxy": round(clip_model_seconds, 3),
        "retry_clip_model_seconds_ceiling": round(clip_model_seconds * max_attempts, 3),
        "claim_status": "clip_proxy_planning_only_no_live_metric_claim",
    }


def build_audit(root: Path) -> dict[str, Any]:
    command_audit = read_json(root / "outputs/research_progress_snapshot/live_command_surface_audit.json")
    retry_budget = read_json(root / "outputs/research_progress_snapshot/live_retry_budget_audit.json")
    input_integrity = read_json(root / "outputs/research_progress_snapshot/live_input_integrity_audit.json")
    split20 = read_json(root / "outputs/research_progress_snapshot/split20_full_live_manifest.json")
    resume_export = read_json(root / "outputs/research_progress_snapshot/split20_resume_export_audit.json")
    omni48 = read_json(root / "outputs/research_progress_snapshot/omni48_live_call_manifest.json")
    commands = command_by_id(command_audit)

    resume_stats = prompt_stats(root / RESUME_PROMPTS)
    full_stats = prompt_stats(root / FULL_PROMPTS)
    rows = [
        llm_row("deepseek_resume_after_top3", "P0", resume_stats, commands.get("deepseek_resume_primary", {})),
        llm_row("qwen_full_backup", "P1", full_stats, commands.get("qwen_full_backup_optional", {})),
        omni_row(omni48, commands.get("omni48_label_only_live", {})),
    ]
    llm_rows = [row for row in rows if row["surface_type"] == "llm_prompt_jsonl"]
    p0_rows = [row for row in rows if row["priority"] == "P0"]
    return {
        "runtime_contract": "live_token_quota_budget_audit_no_live_calls",
        "status": "quota_proxy_ready_waiting_credentials_or_quota",
        "token_proxy_policy": "prompt_chars_div4_proxy_not_provider_billing_tokens",
        "source_contracts": {
            "live_command_surface_audit": command_audit.get("runtime_contract", ""),
            "live_retry_budget_audit": retry_budget.get("runtime_contract", ""),
            "live_input_integrity_audit": input_integrity.get("runtime_contract", ""),
            "split20_full_live_manifest": split20.get("runtime_contract", ""),
            "split20_resume_export_audit": resume_export.get("runtime_contract", ""),
            "omni48_live_call_manifest": omni48.get("runtime_contract", ""),
        },
        "summary": {
            "surface_count": len(rows),
            "llm_prompt_surfaces": len(llm_rows),
            "omni_surfaces": sum(1 for row in rows if row["surface_type"] == "omni_audio_call_manifest"),
            "llm_prompt_calls": sum(int(row["prompt_or_call_count"]) for row in llm_rows),
            "llm_prompt_chars": sum(int(row["prompt_chars"]) for row in llm_rows),
            "llm_token_proxy_chars_div4": sum(int(row["token_proxy_chars_div4"]) for row in llm_rows),
            "llm_retry_token_proxy_ceiling": sum(int(row["retry_token_proxy_ceiling"]) for row in llm_rows),
            "p0_token_proxy_chars_div4": sum(int(row["token_proxy_chars_div4"] or 0) for row in p0_rows),
            "p0_retry_token_proxy_ceiling": sum(int(row["retry_token_proxy_ceiling"] or 0) for row in p0_rows),
            "deepseek_resume_token_proxy_chars_div4": rows[0]["token_proxy_chars_div4"],
            "deepseek_resume_retry_token_proxy_ceiling": rows[0]["retry_token_proxy_ceiling"],
            "qwen_full_token_proxy_chars_div4": rows[1]["token_proxy_chars_div4"],
            "qwen_full_retry_token_proxy_ceiling": rows[1]["retry_token_proxy_ceiling"],
            "omni48_clip_model_seconds_proxy": rows[2]["clip_model_seconds_proxy"],
            "omni48_retry_clip_model_seconds_ceiling": rows[2]["retry_clip_model_seconds_ceiling"],
            "max_attempted_requests": retry_budget.get("summary", {}).get("max_attempted_requests", 0),
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(audit: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "surface_id",
        "priority",
        "surface_type",
        "prompt_or_call_count",
        "parent_windows",
        "patch_references",
        "prompt_chars",
        "token_proxy_chars_div4",
        "max_prompt_chars",
        "max_call_attempts",
        "max_attempted_requests",
        "retry_token_proxy_ceiling",
        "clip_model_seconds_proxy",
        "retry_clip_model_seconds_ceiling",
        "claim_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in audit["rows"]:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    lines = [
        "# Live Token Quota Budget Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Token proxy policy: `{audit['token_proxy_policy']}`",
        f"- Surfaces: `{summary['surface_count']}`",
        f"- LLM prompt calls: `{summary['llm_prompt_calls']}`",
        f"- LLM token proxy chars/4: `{summary['llm_token_proxy_chars_div4']}`",
        f"- LLM retry token proxy ceiling: `{summary['llm_retry_token_proxy_ceiling']}`",
        f"- P0 retry token proxy ceiling: `{summary['p0_retry_token_proxy_ceiling']}`",
        f"- Omni48 retry clip-model seconds ceiling: `{summary['omni48_retry_clip_model_seconds_ceiling']}`",
        f"- Max attempted requests: `{summary['max_attempted_requests']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Surface | Priority | Type | Calls | Parents | Prompt chars | Token proxy | Attempts | Retry token/clip ceiling |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in audit["rows"]:
        token_or_clip = row["retry_token_proxy_ceiling"] or row["retry_clip_model_seconds_ceiling"]
        lines.append(
            f"| `{row['surface_id']}` | `{row['priority']}` | `{row['surface_type']}` | "
            f"{row['prompt_or_call_count']} | {row['parent_windows']} | {row['prompt_chars'] or 'n/a'} | "
            f"{row['token_proxy_chars_div4'] or 'n/a'} | {row['max_call_attempts']} | {token_or_clip} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Token proxy is estimated from local prompt text as characters divided by four; it is not provider billing truth.",
            f"- Under the current 2-attempt policy, the two LLM live surfaces have a combined retry token proxy ceiling of {summary['llm_retry_token_proxy_ceiling']}.",
            f"- P0 DeepSeek resume alone has a retry token proxy ceiling of {summary['p0_retry_token_proxy_ceiling']}; Qwen backup remains P1 fallback-only.",
            f"- Omni48 is represented by clip-model seconds, not text tokens; its 2-attempt ceiling is {summary['omni48_retry_clip_model_seconds_ceiling']} clip-model seconds.",
            "- The builder only reads local artifacts; it performs no live/API/model calls and writes no secrets.",
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
