#!/usr/bin/env python3
"""Build an offline split-policy optimization summary for live LLM guard runs."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/split_policy_optimization.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/split_policy_optimization.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/split_policy_optimization.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def policy_role(policy: dict[str, Any], manifest: dict[str, Any]) -> tuple[str, str, bool]:
    max_patches = int(policy.get("max_patches_per_call") or 0)
    if max_patches == int(manifest.get("summary", {}).get("recommended_max_patches_per_call") or 20):
        return (
            "resume_primary",
            "only policy with exported prompts, completed top3 live smoke, and pending resume surface",
            True,
        )
    if max_patches == 15:
        return (
            "latency_stretch_reexport",
            "lower simulated P95 than max20, but it needs a fresh prompt export and cannot directly reuse the max20 top3 smoke as full-surface evidence",
            False,
        )
    if max_patches < 15:
        return (
            "exploratory_low_latency_high_cost",
            "lower simulated P95, but added calls and token multiplier are too high for the next live quota-constrained run",
            False,
        )
    return (
        "not_selected",
        "not on the current evidence-backed resume path",
        False,
    )


def build_optimization(root: Path) -> dict[str, Any]:
    simulation = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation_summary.json")
    manifest = read_json(root / "outputs/research_progress_snapshot/split20_full_live_manifest.json")
    output_audit = read_json(root / "outputs/research_progress_snapshot/live_output_audit.json")
    scoring = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    top3 = read_json(root / "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_comparison.json")
    qwen_top45 = read_json(root / "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json")
    policies = simulation.get("policies", [])
    observed_p95 = float(simulation.get("observed_p95_call_seconds") or 0.0)
    observed_max = float(simulation.get("observed_max_call_seconds") or 0.0)
    manifest_summary = manifest.get("summary", {})

    rows = []
    for policy in policies:
        role, rationale, top3_reusable = policy_role(policy, manifest)
        p95 = float(policy.get("p95_call_seconds") or 0.0)
        max_call = float(policy.get("max_call_seconds") or 0.0)
        token_multiplier = float(policy.get("token_multiplier") or 0.0)
        calls = int(policy.get("calls") or 0)
        rows.append(
            {
                "max_patches_per_call": int(policy.get("max_patches_per_call") or 0),
                "role": role,
                "calls": calls,
                "resume_calls_if_primary": int(manifest_summary.get("deepseek_resume_required_calls_min") or 0)
                if role == "resume_primary"
                else calls,
                "added_calls": int(policy.get("added_calls") or 0),
                "split_windows": int(policy.get("split_windows") or 0),
                "max_parallel_subcalls": int(policy.get("max_parallel_subcalls") or 0),
                "simulated_p95_call_seconds": round(p95, 3),
                "simulated_max_call_seconds": round(max_call, 3),
                "p95_reduction_vs_unsplit_seconds": round(observed_p95 - p95, 3),
                "max_reduction_vs_unsplit_seconds": round(observed_max - max_call, 3),
                "token_multiplier": round(token_multiplier, 3),
                "top3_live_evidence_reusable": top3_reusable,
                "requires_new_prompt_export": not top3_reusable,
                "quota_risk": "lowest" if role == "resume_primary" else ("medium" if int(policy.get("max_patches_per_call") or 0) == 15 else "high"),
                "recommendation": rationale,
            }
        )

    primary = next((row for row in rows if row["role"] == "resume_primary"), rows[0] if rows else {})
    stretch = next((row for row in rows if row["role"] == "latency_stretch_reexport"), {})
    live_blockers = []
    if output_audit.get("summary", {}).get("missing_output_surfaces", 0):
        live_blockers.append("missing_live_output_jsonl")
    if scoring.get("summary", {}).get("ready_to_score_steps", 0) == 0:
        live_blockers.append("scoring_waits_for_live_outputs")
    if manifest_summary.get("deepseek_failure_type"):
        live_blockers.append(str(manifest_summary.get("deepseek_failure_type")))

    return {
        "runtime_contract": "split_policy_optimization_from_existing_artifacts_no_live_calls",
        "status": "ready_primary_resume_blocked_by_live_outputs_or_quota" if live_blockers else "ready_to_execute_primary_resume",
        "source_artifacts": [
            "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation_summary.json",
            "outputs/research_progress_snapshot/split20_full_live_manifest.json",
            "outputs/research_progress_snapshot/live_output_audit.json",
            "outputs/research_progress_snapshot/live_scoring_readiness.json",
            "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_comparison.json",
            "outputs/runtime_safe_llm_window_batch/qwen36_flash_split20_top4_5_parallel_comparison.json",
        ],
        "summary": {
            "policy_count": len(rows),
            "primary_policy": f"max{primary.get('max_patches_per_call')}" if primary else "",
            "primary_calls": primary.get("calls", 0),
            "primary_resume_calls": primary.get("resume_calls_if_primary", 0),
            "primary_simulated_p95_call_seconds": primary.get("simulated_p95_call_seconds", 0.0),
            "primary_token_multiplier": primary.get("token_multiplier", 0.0),
            "stretch_policy": f"max{stretch.get('max_patches_per_call')}" if stretch else "",
            "stretch_calls": stretch.get("calls", 0),
            "stretch_simulated_p95_call_seconds": stretch.get("simulated_p95_call_seconds", 0.0),
            "stretch_token_multiplier": stretch.get("token_multiplier", 0.0),
            "stretch_requires_reexport": stretch.get("requires_new_prompt_export", False),
            "observed_unsplit_p95_call_seconds": observed_p95,
            "observed_unsplit_max_call_seconds": observed_max,
            "top3_live_wall_seconds": top3.get("measured_wall_seconds", ""),
            "top3_harmful_accepts": top3.get("harmful_accepts", ""),
            "qwen_top45_wall_seconds": (qwen_top45.get("runs") or [{}])[0].get("wall_seconds", ""),
            "qwen_top45_verdict": "slower_than_original_max",
            "live_blockers": live_blockers,
            "live_calls_performed_by_builder": 0,
            "no_metric_claim": True,
        },
        "policies": rows,
        "commands": {
            "primary_resume": manifest.get("run_commands", {}).get("deepseek_resume_after_top3", ""),
            "primary_scoring": "python scripts/live/build_live_scoring_readiness.py && python scripts/search/validate_latest_research_artifacts.py",
            "stretch_reexport_max15": (
                "python scripts/llm/llm_window_batch_policy_eval.py --mode export "
                "--decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl "
                "--trigger-policy proxy_flagged_window "
                "--window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv "
                "--patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt "
                "--max-patches-per-call 15 "
                "--output-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split15_replay_prompts.jsonl"
            ),
        },
    }


def write_csv(optimization: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "max_patches_per_call",
        "role",
        "calls",
        "resume_calls_if_primary",
        "added_calls",
        "split_windows",
        "max_parallel_subcalls",
        "simulated_p95_call_seconds",
        "simulated_max_call_seconds",
        "p95_reduction_vs_unsplit_seconds",
        "max_reduction_vs_unsplit_seconds",
        "token_multiplier",
        "top3_live_evidence_reusable",
        "requires_new_prompt_export",
        "quota_risk",
        "recommendation",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in optimization["policies"]:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_markdown(optimization: dict[str, Any], path: Path) -> None:
    summary = optimization["summary"]
    lines = [
        "# Split Policy Optimization",
        "",
        f"- Runtime contract: `{optimization['runtime_contract']}`",
        f"- Status: `{optimization['status']}`",
        f"- Policies: `{summary['policy_count']}`",
        f"- Primary policy: `{summary['primary_policy']}`",
        f"- Primary calls / resume calls: `{summary['primary_calls']}` / `{summary['primary_resume_calls']}`",
        f"- Primary simulated P95 call: `{summary['primary_simulated_p95_call_seconds']}`",
        f"- Primary token multiplier: `{summary['primary_token_multiplier']}`",
        f"- Stretch policy: `{summary['stretch_policy']}`",
        f"- Stretch simulated P95 call: `{summary['stretch_simulated_p95_call_seconds']}`",
        f"- Stretch requires re-export: `{summary['stretch_requires_reexport']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No metric claim: `{summary['no_metric_claim']}`",
        "",
        "| Max patches | Role | Calls | Resume calls | Added calls | Split windows | P95 call | Max call | Token multiplier | Top3 reusable | Quota risk |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in optimization["policies"]:
        lines.append(
            f"| {row['max_patches_per_call']} | `{row['role']}` | {row['calls']} | {row['resume_calls_if_primary']} | "
            f"{row['added_calls']} | {row['split_windows']} | {row['simulated_p95_call_seconds']} | "
            f"{row['simulated_max_call_seconds']} | {row['token_multiplier']} | "
            f"`{row['top3_live_evidence_reusable']}` | `{row['quota_risk']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- `max20` remains the primary live path because it has exported prompts, completed top3 live smoke, and a clean resume surface.",
            "- `max15` is the next latency-stretch candidate: lower simulated P95, but it needs a fresh export and cannot directly reuse the max20 top3 smoke as full-surface evidence.",
            "- Smaller max-patch policies reduce simulated P95 further but raise call count and quota pressure; keep them exploratory until provider capacity is stable.",
            "- This artifact is an offline planning layer and makes no live metric claim.",
            "",
            "## Commands",
            "",
            "```bash",
            optimization["commands"].get("primary_resume", ""),
            "```",
            "",
            "```bash",
            optimization["commands"].get("stretch_reexport_max15", ""),
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    optimization = build_optimization(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(optimization, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(optimization, args.output_md)
    write_csv(optimization, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
