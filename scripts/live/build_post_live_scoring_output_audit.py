#!/usr/bin/env python3
"""Audit expected post-live scoring outputs without running scoring commands."""

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
OUTPUT_JSON = Path("outputs/research_progress_snapshot/post_live_scoring_output_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/post_live_scoring_output_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/post_live_scoring_output_audit.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def artifact_path(path: str) -> Path:
    return ROOT / path


def blocked_state(state: str) -> bool:
    return "blocked" in state or "waiting" in state


def build_audit(root: Path) -> dict[str, Any]:
    scoring_plan = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_execution_plan.json")
    scoring_launcher = read_json(root / "outputs/research_progress_snapshot/post_live_scoring_launcher.json")
    scoring_readiness = read_json(root / "outputs/research_progress_snapshot/live_scoring_readiness.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    traceability = read_json(root / "outputs/research_progress_snapshot/report_ppt_traceability.json")

    launcher_summary = scoring_launcher.get("summary", {})
    readiness_summary = scoring_readiness.get("summary", {})
    promotion_summary = promotion.get("summary", {})
    traceability_summary = traceability.get("summary", {})

    rows: list[dict[str, Any]] = []
    artifact_rows: list[dict[str, Any]] = []
    for source_row in scoring_plan.get("rows", []):
        artifacts = [str(path) for path in source_row.get("output_artifacts", [])]
        existing = [path for path in artifacts if artifact_path(path).exists()]
        missing = [path for path in artifacts if not artifact_path(path).exists()]
        current_state = str(source_row.get("current_state", ""))
        current_state_blocked = blocked_state(current_state)
        all_outputs_exist = bool(artifacts) and not missing
        ready_for_promotion_gate = all_outputs_exist and not current_state_blocked
        row = {
            "scoring_execution_id": str(source_row.get("scoring_execution_id", "")),
            "step_order": as_int(source_row.get("step_order")),
            "priority": str(source_row.get("priority", "")),
            "surface_id": str(source_row.get("surface_id", "")),
            "execution_phase": str(source_row.get("execution_phase", "")),
            "current_state": current_state,
            "current_state_blocked": current_state_blocked,
            "promotion_gate": str(source_row.get("promotion_gate", "")),
            "claim_boundary": str(source_row.get("claim_boundary", "")),
            "output_artifact_count": len(artifacts),
            "existing_output_artifacts": existing,
            "missing_output_artifacts": missing,
            "existing_output_artifact_count": len(existing),
            "missing_output_artifact_count": len(missing),
            "all_output_artifacts_exist": all_outputs_exist,
            "ready_for_promotion_gate": ready_for_promotion_gate,
        }
        rows.append(row)
        for artifact in artifacts:
            artifact_rows.append(
                {
                    "scoring_execution_id": row["scoring_execution_id"],
                    "artifact": artifact,
                    "exists": artifact_path(artifact).exists(),
                    "promotion_gate": row["promotion_gate"],
                    "claim_boundary": row["claim_boundary"],
                }
            )

    all_outputs_exist_rows = [row for row in rows if row["all_output_artifacts_exist"]]
    ready_rows = [row for row in rows if row["ready_for_promotion_gate"]]
    blocked_rows = [row for row in rows if row["current_state_blocked"]]
    missing_rows = [row for row in rows if row["missing_output_artifacts"]]
    total_artifacts = sum(row["output_artifact_count"] for row in rows)
    existing_artifacts = sum(row["existing_output_artifact_count"] for row in rows)
    missing_artifacts = sum(row["missing_output_artifact_count"] for row in rows)

    return {
        "runtime_contract": "post_live_scoring_output_audit_no_scoring_calls",
        "status": "blocked_waiting_scoring_outputs" if not ready_rows else "ready_for_promotion_review",
        "source_contracts": {
            "post_live_scoring_execution_plan": scoring_plan.get("runtime_contract", ""),
            "post_live_scoring_launcher": scoring_launcher.get("runtime_contract", ""),
            "live_scoring_readiness": scoring_readiness.get("runtime_contract", ""),
            "post_live_claim_promotion_gate": promotion.get("runtime_contract", ""),
            "report_ppt_traceability": traceability.get("runtime_contract", ""),
        },
        "summary": {
            "scoring_output_rows": len(rows),
            "p0_output_rows": sum(1 for row in rows if row["priority"] == "P0"),
            "p1_output_rows": sum(1 for row in rows if row["priority"] == "P1"),
            "total_output_artifacts": total_artifacts,
            "existing_output_artifacts": existing_artifacts,
            "missing_output_artifacts": missing_artifacts,
            "all_output_artifacts_exist_rows": len(all_outputs_exist_rows),
            "missing_output_rows": len(missing_rows),
            "blocked_current_state_rows": len(blocked_rows),
            "promotion_ready_rows": len(ready_rows),
            "ready_to_score_steps": as_int(readiness_summary.get("ready_to_score_steps")),
            "ready_to_promote_count": as_int(promotion_summary.get("ready_to_promote_count")),
            "scoring_launcher_executed_rows": as_int(launcher_summary.get("executed_scoring_rows")),
            "scoring_execute_record_exists": bool(launcher_summary.get("scoring_execute_record_exists", False)),
            "traceability_rows": as_int(traceability_summary.get("traceability_rows")),
            "live_calls_performed_by_builder": 0,
            "no_live_calls_performed": True,
            "no_scoring_commands_executed": True,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
        "rows": rows,
        "artifact_rows": artifact_rows,
    }


def write_csv(audit: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "scoring_execution_id",
        "step_order",
        "priority",
        "surface_id",
        "execution_phase",
        "current_state",
        "current_state_blocked",
        "promotion_gate",
        "claim_boundary",
        "output_artifact_count",
        "existing_output_artifact_count",
        "missing_output_artifact_count",
        "all_output_artifacts_exist",
        "ready_for_promotion_gate",
        "missing_output_artifacts",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in audit["rows"]:
            out = dict(row)
            out["missing_output_artifacts"] = "; ".join(out["missing_output_artifacts"])
            writer.writerow({field: out.get(field, "") for field in fieldnames})


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    lines = [
        "# Post-Live Scoring Output Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Scoring output rows: `{summary['scoring_output_rows']}`",
        f"- P0 / P1 output rows: `{summary['p0_output_rows']}` / `{summary['p1_output_rows']}`",
        f"- Total output artifacts: `{summary['total_output_artifacts']}`",
        f"- Existing output artifacts: `{summary['existing_output_artifacts']}`",
        f"- Missing output artifacts: `{summary['missing_output_artifacts']}`",
        f"- All-output-exist rows: `{summary['all_output_artifacts_exist_rows']}`",
        f"- Missing output rows: `{summary['missing_output_rows']}`",
        f"- Blocked current-state rows: `{summary['blocked_current_state_rows']}`",
        f"- Promotion-ready rows: `{summary['promotion_ready_rows']}`",
        f"- Ready to score steps: `{summary['ready_to_score_steps']}`",
        f"- Ready to promote count: `{summary['ready_to_promote_count']}`",
        f"- Scoring launcher executed rows: `{summary['scoring_launcher_executed_rows']}`",
        f"- Scoring execute record exists: `{summary['scoring_execute_record_exists']}`",
        f"- Traceability rows: `{summary['traceability_rows']}`",
        f"- No live calls performed: `{summary['no_live_calls_performed']}`",
        f"- No scoring commands executed: `{summary['no_scoring_commands_executed']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Step | Priority | Surface | State | Existing | Missing | Promotion-ready | Gate |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for row in audit["rows"]:
        lines.append(
            f"| `{row['scoring_execution_id']}` | `{row['priority']}` | `{row['surface_id']}` | "
            f"`{row['current_state']}` | `{row['existing_output_artifact_count']}` | "
            f"`{row['missing_output_artifact_count']}` | `{row['ready_for_promotion_gate']}` | "
            f"`{row['promotion_gate']}` |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This audit checks expected scoring output artifacts from the execution plan on disk.",
            "- File existence alone is not enough for promotion; a row must also be unblocked by the scoring plan and promotion gates.",
            "- The builder performs no live/API/model/scoring calls and writes no secret values.",
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
    args.output_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(audit, args.output_md)
    write_csv(audit, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")
    print(json.dumps({"status": audit["status"], "summary": audit["summary"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
