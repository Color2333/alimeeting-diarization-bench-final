#!/usr/bin/env python3
"""Build post-live scoring readiness commands without running live calls or scoring."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_scoring_readiness.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_scoring_readiness.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_scoring_readiness.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def shlex_join(parts: list[str]) -> str:
    return " ".join(parts)


def surface_by_id(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("surface_id")): row for row in audit.get("surfaces", [])}


def build_readiness(root: Path) -> dict[str, Any]:
    audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    closure = read_json(root / "outputs/research_progress_snapshot/live_postrun_metrics_closure.json")
    agent_plan = read_json(root / "outputs/research_progress_snapshot/live_agent_execution_plan.json")
    split_manifest = read_json(root / "outputs/research_progress_snapshot/split20_full_live_manifest.json")
    surfaces = surface_by_id(audit)

    deepseek_resume = surfaces.get("deepseek_resume_after_top3", {})
    qwen_full = surfaces.get("qwen_full_backup", {})
    omni48 = surfaces.get("omni48_label_only", {})
    top3 = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_comparison.json")
    qwen_top45 = read_json(root / "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json")

    deepseek_resume_jsonl = "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl"
    deepseek_resume_csv = "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.csv"
    deepseek_resume_summary = "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_summary.json"
    deepseek_resume_safety = "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety_summary.json"
    deepseek_full_comparison = "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.json"

    qwen_full_jsonl = "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl"
    qwen_full_csv = "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.csv"
    qwen_full_summary = "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_summary.json"
    qwen_full_safety = "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety_summary.json"
    qwen_full_comparison = "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_comparison.json"

    omni48_jsonl = "outputs/omni_guard/omni_expansion_48_live.jsonl"
    omni48_csv = "outputs/omni_guard/omni_expansion_48_live.csv"
    omni48_summary_csv = "outputs/omni_guard/omni_expansion_48_live_summary.csv"
    omni48_summary_md = "outputs/omni_guard/omni_expansion_48_live_summary.md"

    rows = [
        {
            "scoring_id": "deepseek_resume_safety",
            "surface_id": "deepseek_resume_after_top3",
            "kind": "llm_safety",
            "priority": "P0",
            "expected_input_calls": deepseek_resume.get("expected_calls", 139),
            "coverage_gate": deepseek_resume.get("claim_gate", "blocked_missing_output"),
            "status": "ready_to_score" if deepseek_resume.get("claim_gate") == "ready_for_llm_safety_latency_scoring" else "blocked_waiting_live_output",
            "input_artifacts": [deepseek_resume_jsonl],
            "output_artifacts": [
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.csv",
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.md",
                deepseek_resume_safety,
            ],
            "scoring_command": shlex_join(
                [
                    "python",
                    "scripts/analyze_runtime_safe_llm_guard.py",
                    "--batch-jsonl",
                    deepseek_resume_jsonl,
                    "--output-csv",
                    "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.csv",
                    "--output-md",
                    "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.md",
                    "--summary-json",
                    deepseek_resume_safety,
                ]
            ),
            "success_gate": "harmful_accepts == 0; missing_patch_eval == 0; parent_window_decision_override true",
            "claim_effect": "enables full DeepSeek split20 safety half after resume output exists",
        },
        {
            "scoring_id": "deepseek_full_split20_comparison",
            "surface_id": "deepseek_resume_after_top3",
            "kind": "llm_latency_comparison",
            "priority": "P0",
            "expected_input_calls": int(top3.get("split_calls") or 8) + int(deepseek_resume.get("expected_calls", 139)),
            "coverage_gate": deepseek_resume.get("claim_gate", "blocked_missing_output"),
            "status": "ready_after_resume_safety" if deepseek_resume.get("claim_gate") == "ready_for_llm_safety_latency_scoring" else "blocked_waiting_live_output",
            "input_artifacts": [
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel.csv",
                deepseek_resume_csv,
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_summary.json",
                deepseek_resume_summary,
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_safety_summary.json",
                deepseek_resume_safety,
            ],
            "output_artifacts": [
                deepseek_full_comparison,
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.md",
            ],
            "scoring_command": shlex_join(
                [
                    "python",
                    "scripts/summarize_split_llm_runs.py",
                    "--split-csv",
                    "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel.csv",
                    "--split-csv",
                    deepseek_resume_csv,
                    "--run-summary",
                    "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_summary.json",
                    "--run-summary",
                    deepseek_resume_summary,
                    "--safety-summary",
                    "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_safety_summary.json",
                    "--safety-summary",
                    deepseek_resume_safety,
                    "--output-json",
                    deepseek_full_comparison,
                    "--output-md",
                    "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.md",
                ]
            ),
            "success_gate": "parent_windows == 104; split_calls == 147; harmful_accepts == 0; report measured wall and token multiplier",
            "claim_effect": "turns split20 from top3 smoke into full-surface latency evidence if successful",
        },
        {
            "scoring_id": "qwen_full_backup_safety",
            "surface_id": "qwen_full_backup",
            "kind": "llm_backup_safety",
            "priority": "P1",
            "expected_input_calls": qwen_full.get("expected_calls", 147),
            "coverage_gate": qwen_full.get("claim_gate", "blocked_missing_output"),
            "status": "ready_to_score" if qwen_full.get("claim_gate") == "ready_for_llm_safety_latency_scoring" else "blocked_waiting_live_output",
            "input_artifacts": [qwen_full_jsonl],
            "output_artifacts": [
                "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety.csv",
                "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety.md",
                qwen_full_safety,
            ],
            "scoring_command": shlex_join(
                [
                    "python",
                    "scripts/analyze_runtime_safe_llm_guard.py",
                    "--batch-jsonl",
                    qwen_full_jsonl,
                    "--output-csv",
                    "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety.csv",
                    "--output-md",
                    "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety.md",
                    "--summary-json",
                    qwen_full_safety,
                ]
            ),
            "success_gate": "harmful_accepts == 0; fallback only unless latency beats primary or provider changes",
            "claim_effect": "keeps Qwen as execution fallback, not primary latency claim by default",
        },
        {
            "scoring_id": "qwen_full_backup_comparison",
            "surface_id": "qwen_full_backup",
            "kind": "llm_backup_latency_comparison",
            "priority": "P1",
            "expected_input_calls": qwen_full.get("expected_calls", 147),
            "coverage_gate": qwen_full.get("claim_gate", "blocked_missing_output"),
            "status": "ready_after_qwen_safety" if qwen_full.get("claim_gate") == "ready_for_llm_safety_latency_scoring" else "blocked_waiting_live_output",
            "input_artifacts": [qwen_full_csv, qwen_full_summary, qwen_full_safety],
            "output_artifacts": [
                qwen_full_comparison,
                "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_comparison.md",
            ],
            "scoring_command": shlex_join(
                [
                    "python",
                    "scripts/summarize_split_llm_runs.py",
                    "--split-csv",
                    qwen_full_csv,
                    "--run-summary",
                    qwen_full_summary,
                    "--safety-summary",
                    qwen_full_safety,
                    "--output-json",
                    qwen_full_comparison,
                    "--output-md",
                    "outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_comparison.md",
                ]
            ),
            "success_gate": "parent_windows == 104; split_calls == 147; harmful_accepts == 0; compare against DeepSeek primary evidence",
            "claim_effect": "documents full-surface backup behavior and latency if fallback run is executed",
        },
        {
            "scoring_id": "omni48_label_summary",
            "surface_id": "omni48_label_only",
            "kind": "omni_label_scoring",
            "priority": "P1",
            "expected_input_calls": omni48.get("expected_calls", 96),
            "coverage_gate": omni48.get("claim_gate", "blocked_missing_output"),
            "status": "ready_to_score" if omni48.get("claim_gate") == "ready_for_omni_metric_scoring" else "blocked_waiting_live_output",
            "input_artifacts": [omni48_jsonl, omni48_csv],
            "output_artifacts": [omni48_summary_csv, omni48_summary_md],
            "scoring_command": shlex_join(
                [
                    "python",
                    "scripts/summarize_omni_window_batch.py",
                    omni48_csv,
                    "--output-csv",
                    omni48_summary_csv,
                    "--output-md",
                    omni48_summary_md,
                ]
            ),
            "success_gate": "96 calls complete; report high positive, clean false positive, avg/P95/max call latency; label-only no timeline writeback",
            "claim_effect": "enables Omni48 label-only recall/precision/latency scoring after live output exists",
        },
    ]

    blocked = [row for row in rows if str(row["status"]).startswith("blocked")]
    ready = [row for row in rows if str(row["status"]).startswith("ready")]
    status = "blocked_waiting_live_outputs" if blocked else "ready_to_score_live_outputs"
    return {
        "runtime_contract": "live_scoring_readiness_no_live_calls",
        "status": status,
        "source_contracts": {
            "live_output_audit": audit.get("runtime_contract", ""),
            "live_postrun_metrics_closure": closure.get("runtime_contract", ""),
            "live_agent_execution_plan": agent_plan.get("runtime_contract", ""),
            "split20_full_live_manifest": split_manifest.get("runtime_contract", ""),
        },
        "summary": {
            "scoring_step_count": len(rows),
            "ready_to_score_steps": len(ready),
            "blocked_steps": len(blocked),
            "p0_scoring_steps": sum(1 for row in rows if row["priority"] == "P0"),
            "unique_live_output_calls": int(audit.get("summary", {}).get("expected_live_calls") or 382),
            "expected_input_calls": sum(int(row["expected_input_calls"] or 0) for row in rows),
            "deepseek_resume_expected_calls": int(deepseek_resume.get("expected_calls") or 139),
            "qwen_full_expected_calls": int(qwen_full.get("expected_calls") or 147),
            "omni48_expected_calls": int(omni48.get("expected_calls") or 96),
            "deepseek_top3_completed_calls": int(top3.get("split_calls") or 8),
            "qwen_top45_backup_calls": int(qwen_top45.get("split_calls") or 4),
            "live_calls_performed_by_builder": 0,
            "no_scoring_commands_executed": True,
        },
        "scoring_steps": rows,
    }


def write_csv(readiness: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "scoring_id",
        "surface_id",
        "kind",
        "priority",
        "expected_input_calls",
        "coverage_gate",
        "status",
        "success_gate",
        "claim_effect",
        "scoring_command",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in readiness["scoring_steps"]:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_markdown(readiness: dict[str, Any], path: Path) -> None:
    summary = readiness["summary"]
    lines = [
        "# Live Scoring Readiness",
        "",
        f"- Runtime contract: `{readiness['runtime_contract']}`",
        f"- Status: `{readiness['status']}`",
        f"- Scoring steps: `{summary['scoring_step_count']}`",
        f"- Ready to score: `{summary['ready_to_score_steps']}`",
        f"- Blocked steps: `{summary['blocked_steps']}`",
        f"- P0 scoring steps: `{summary['p0_scoring_steps']}`",
        f"- Unique live output calls: `{summary['unique_live_output_calls']}`",
        f"- Expected input calls across scoring commands: `{summary['expected_input_calls']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- Scoring commands executed: `{not summary['no_scoring_commands_executed']}`",
        "",
        "| Scoring step | Surface | Priority | Expected calls | Coverage gate | Status | Claim effect |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for row in readiness["scoring_steps"]:
        effect = str(row["claim_effect"]).replace("|", "/")
        lines.append(
            f"| `{row['scoring_id']}` | `{row['surface_id']}` | `{row['priority']}` | "
            f"{row['expected_input_calls']} | `{row['coverage_gate']}` | `{row['status']}` | {effect} |"
        )
    lines.extend(["", "## Commands", ""])
    for row in readiness["scoring_steps"]:
        lines.extend(
            [
                f"### {row['scoring_id']}",
                "",
                "```bash",
                str(row["scoring_command"]),
                "```",
                "",
                f"- Success gate: {row['success_gate']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Reading",
            "",
            "- This artifact plans post-live scoring only; it does not execute scoring commands or model calls.",
            "- Output coverage must pass `live_output_audit` before a scoring command can support a claim.",
            "- DeepSeek resume has P0 priority because it is the shortest path from split20 smoke to full-surface latency/safety evidence.",
            "- Qwen remains a backup/fallback path unless full-surface latency evidence beats the primary route.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    readiness = build_readiness(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(readiness, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(readiness, args.output_md)
    write_csv(readiness, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
