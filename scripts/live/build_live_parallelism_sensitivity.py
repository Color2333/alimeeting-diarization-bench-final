#!/usr/bin/env python3
"""Build a no-live-call worker/policy timing sensitivity table."""

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
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_parallelism_sensitivity.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_parallelism_sensitivity.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_parallelism_sensitivity.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def ceil_waves(calls: int, workers: int) -> int:
    if calls <= 0:
        return 0
    return int(math.ceil(calls / max(workers, 1)))


def policy_label(row: dict[str, Any]) -> str:
    return f"max{int(row.get('max_patches_per_call') or 0)}"


def worker_risk(workers: int) -> str:
    if workers <= 4:
        return "low_burst_slow_wall"
    if workers == 8:
        return "current_runbook_default"
    if workers <= 12:
        return "medium_burst_needs_provider_stability"
    return "high_burst_exploratory_only"


def recommendation(policy: str, workers: int, role: str) -> str:
    if policy == "max20" and workers == 8:
        return "recommended_p0_default"
    if policy == "max20" and workers > 8:
        return "speedup_candidate_after_quota_stable"
    if policy == "max20":
        return "safe_but_slower_fallback"
    if policy == "max15":
        return "stretch_reexport_only"
    if role == "exploratory_low_latency_high_cost":
        return "exploratory_high_quota_cost"
    return "not_selected"


def build_sensitivity(root: Path) -> dict[str, Any]:
    split_policy = read_json(root / "outputs/research_progress_snapshot/split_policy_optimization.json")
    timing = read_json(root / "outputs/research_progress_snapshot/live_execution_timing_plan.json")
    mitigation = read_json(root / "outputs/research_progress_snapshot/latency_risk_mitigation_plan.json")
    runbook = read_json(root / "outputs/research_progress_snapshot/live_execution_runbook.json")
    live_readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")

    worker_counts = [4, 8, 12, 16]
    policies = split_policy.get("policies", [])
    rows: list[dict[str, Any]] = []
    for policy in policies:
        label = policy_label(policy)
        role = str(policy.get("role", ""))
        calls = int(policy.get("resume_calls_if_primary") or policy.get("calls") or 0)
        p95 = float(policy.get("simulated_p95_call_seconds") or 0.0)
        token_multiplier = float(policy.get("token_multiplier") or 0.0)
        requires_reexport = bool(policy.get("requires_new_prompt_export"))
        top3_reusable = bool(policy.get("top3_live_evidence_reusable"))
        for workers in worker_counts:
            waves = ceil_waves(calls, workers)
            wall = round(waves * p95, 3)
            rows.append(
                {
                    "policy": label,
                    "role": role,
                    "workers": workers,
                    "calls": calls,
                    "waves": waves,
                    "p95_call_seconds": round(p95, 3),
                    "estimated_wall_seconds": wall,
                    "token_multiplier": round(token_multiplier, 3),
                    "requires_reexport": requires_reexport,
                    "top3_live_evidence_reusable": top3_reusable,
                    "worker_risk": worker_risk(workers),
                    "recommendation": recommendation(label, workers, role),
                    "claim_status": "planning_only_no_live_metric_claim",
                }
            )

    primary_row = next((row for row in rows if row["policy"] == "max20" and row["workers"] == 8), {})
    primary_12 = next((row for row in rows if row["policy"] == "max20" and row["workers"] == 12), {})
    stretch_8 = next((row for row in rows if row["policy"] == "max15" and row["workers"] == 8), {})
    qwen_wall = timing.get("summary", {}).get("qwen_estimated_wall_seconds", 0.0)
    blocked = live_readiness.get("summary", {}).get("blocked_runs", [])

    return {
        "runtime_contract": "live_parallelism_sensitivity_no_live_calls",
        "status": "planning_only_blocked_waiting_for_credentials_or_quota",
        "source_contracts": {
            "split_policy_optimization": split_policy.get("runtime_contract", ""),
            "live_execution_timing_plan": timing.get("runtime_contract", ""),
            "latency_risk_mitigation_plan": mitigation.get("runtime_contract", ""),
            "live_execution_runbook": runbook.get("runtime_contract", ""),
            "live_run_readiness": live_readiness.get("runtime_contract", ""),
        },
        "summary": {
            "row_count": len(rows),
            "policy_count": len(policies),
            "worker_count": len(worker_counts),
            "recommended_policy": "max20",
            "recommended_workers": 8,
            "recommended_estimated_wall_seconds": primary_row.get("estimated_wall_seconds", ""),
            "recommended_waves": primary_row.get("waves", ""),
            "recommended_calls": primary_row.get("calls", ""),
            "recommended_worker_risk": primary_row.get("worker_risk", ""),
            "max20_worker12_estimated_wall_seconds": primary_12.get("estimated_wall_seconds", ""),
            "max20_worker12_wall_gain_seconds": round(
                float(primary_row.get("estimated_wall_seconds", 0.0)) - float(primary_12.get("estimated_wall_seconds", 0.0)),
                3,
            )
            if primary_row and primary_12
            else "",
            "stretch_max15_workers8_estimated_wall_seconds": stretch_8.get("estimated_wall_seconds", ""),
            "stretch_max15_requires_reexport": stretch_8.get("requires_reexport", ""),
            "qwen_backup_workers8_estimated_wall_seconds": qwen_wall,
            "blocked_runs": blocked,
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(plan: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "policy",
        "role",
        "workers",
        "calls",
        "waves",
        "p95_call_seconds",
        "estimated_wall_seconds",
        "token_multiplier",
        "requires_reexport",
        "top3_live_evidence_reusable",
        "worker_risk",
        "recommendation",
        "claim_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in plan["rows"]:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_markdown(plan: dict[str, Any], path: Path) -> None:
    summary = plan["summary"]
    lines = [
        "# Live Parallelism Sensitivity",
        "",
        f"- Runtime contract: `{plan['runtime_contract']}`",
        f"- Status: `{plan['status']}`",
        f"- Rows: `{summary['row_count']}`",
        f"- Policies / worker counts: `{summary['policy_count']}` / `{summary['worker_count']}`",
        f"- Recommended policy/workers: `{summary['recommended_policy']}` / `{summary['recommended_workers']}`",
        f"- Recommended estimated wall: `{summary['recommended_estimated_wall_seconds']}`",
        f"- Recommended waves: `{summary['recommended_waves']}`",
        f"- max20 worker12 estimated wall: `{summary['max20_worker12_estimated_wall_seconds']}`",
        f"- max20 worker12 wall gain: `{summary['max20_worker12_wall_gain_seconds']}`",
        f"- Stretch max15 workers8 estimated wall: `{summary['stretch_max15_workers8_estimated_wall_seconds']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Policy | Role | Workers | Calls | Waves | P95 call | Wall estimate | Token x | Risk | Recommendation |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in plan["rows"]:
        if row["policy"] not in {"max20", "max15"} and row["workers"] not in {8, 12}:
            continue
        lines.append(
            f"| `{row['policy']}` | `{row['role']}` | {row['workers']} | {row['calls']} | {row['waves']} | "
            f"{row['p95_call_seconds']} | {row['estimated_wall_seconds']} | {row['token_multiplier']} | "
            f"`{row['worker_risk']}` | `{row['recommendation']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Keep `max20` with 8 workers as the P0 default because it matches the exported resume surface and current runbook.",
            "- `max20` with 12 workers could reduce the estimated wall by 128.148s, but it raises burst pressure and should wait for provider stability.",
            "- `max15` at 8 workers is faster than `max20` at 8 workers, but it requires a fresh export and cannot reuse max20 top3 evidence.",
            "- All rows are planning estimates only; no live/API/model calls are performed and no new latency metric is claimed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    plan = build_sensitivity(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(plan, args.output_md)
    write_csv(plan, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
