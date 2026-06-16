#!/usr/bin/env python3
"""Build a risk/margin audit for current and pending latency claims."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = Path("outputs/research_progress_snapshot/latency_risk_margin_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/latency_risk_margin_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/latency_risk_margin_audit.csv")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float | None:
    try:
        if value in {"", None}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def risk_from_margin(row: dict[str, Any]) -> tuple[str, str, float | str]:
    slo_class = str(row.get("slo_class", ""))
    p95_margin = as_float(row.get("p95_margin_seconds"))
    p95_threshold = as_float(row.get("p95_threshold_seconds"))
    target_status = str(row.get("target_status", ""))

    if slo_class == "pending_or_blocked":
        return "blocked", "live output or credentials required before claim", ""
    if slo_class == "offline_budget_only":
        return "planning_only", "offline latency estimate cannot support claim", ""
    if slo_class == "fallback_only":
        return "fallback_only", "fallback path is not primary latency support", ""
    if "smoke" in slo_class:
        return "smoke_only", "smoke evidence cannot support full-surface claim", ""
    if target_status != "pass":
        return "fail", "claim-now target failed", ""
    if p95_margin is None or p95_threshold in {None, 0.0}:
        return "claim_current_no_threshold", "claim-current row has no numeric p95 threshold", ""

    ratio = round(p95_margin / float(p95_threshold), 4)
    if p95_margin < 0:
        return "fail", "negative p95 margin", ratio
    if p95_threshold <= 2.0:
        if ratio < 0.05:
            return "tight_margin", "p95 margin below 5% of short-latency threshold", ratio
        if ratio < 0.15:
            return "watch", "p95 margin below 15% of short-latency threshold", ratio
        return "comfortable", "short-latency p95 margin has at least 15% buffer", ratio
    if p95_margin < 2.0 or ratio < 0.05:
        return "tight_margin", "p95 margin below 2s or 5% of threshold", ratio
    if p95_margin < 5.0 or ratio < 0.15:
        return "watch", "p95 margin below 5s or 15% of threshold", ratio
    return "comfortable", "p95 margin has at least 5s and 15% buffer", ratio


def promotion_impact(stage_id: str) -> str:
    mapping = {
        "fast_first_output": "preserve claim-now latency",
        "rule_writeback": "preserve bounded writeback claim",
        "runtime_safe_llm_guard": "preserve but watch before post-live promotion",
        "llm_review_signal": "preserve review/memory-protection timing",
        "omni_realtime_single_smoke": "do not promote to Omni48 claim",
        "split20_simulated_policy": "planning input for DeepSeek resume only",
        "split20_deepseek_top3_live_smoke": "supporting smoke; not full-surface claim",
        "split20_deepseek_full_resume": "blocked until resume output and scoring exist",
        "split20_qwen_backup_top45": "fallback-only execution evidence",
        "omni48_label_only_live": "blocked until 96-call live output exists",
    }
    return mapping.get(stage_id, "review manually before claim promotion")


def watch_action(stage_id: str, risk_level: str) -> str:
    if stage_id == "runtime_safe_llm_guard" and risk_level in {"tight_margin", "watch"}:
        return "prioritize split20 resume or smaller max-patch policy before claiming broader guard latency"
    if risk_level == "tight_margin":
        return "keep claim but mark as margin-sensitive in report/PPT"
    if risk_level == "watch":
        return "monitor in next refresh and compare with live resume output"
    if risk_level == "comfortable":
        return "preserve current claim"
    if risk_level == "blocked":
        return "wait for credentials, live output, and scoring"
    if risk_level == "smoke_only":
        return "keep as smoke/supporting evidence only"
    if risk_level == "planning_only":
        return "use as run planning evidence only"
    if risk_level == "fallback_only":
        return "keep out of primary latency claim"
    return "review before report promotion"


def build_audit(root: Path) -> dict[str, Any]:
    slo = read_json(root / "outputs/research_progress_snapshot/stage_latency_slo_audit.json")
    ledger = read_json(root / "outputs/research_progress_snapshot/runtime_latency_budget_ledger.json")
    promotion = read_json(root / "outputs/research_progress_snapshot/post_live_claim_promotion_gate.json")
    live_readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")

    rows = []
    for row in slo.get("rows", []):
        risk_level, risk_reason, margin_ratio = risk_from_margin(row)
        out = {
            "stage_id": row.get("stage_id", ""),
            "surface": row.get("surface", ""),
            "claim_status": row.get("claim_status", ""),
            "slo_class": row.get("slo_class", ""),
            "target_status": row.get("target_status", ""),
            "avg_seconds": row.get("avg_seconds", ""),
            "p95_seconds": row.get("p95_seconds", ""),
            "wall_seconds": row.get("wall_seconds", ""),
            "avg_margin_seconds": row.get("avg_margin_seconds", ""),
            "p95_margin_seconds": row.get("p95_margin_seconds", ""),
            "p95_margin_ratio": margin_ratio,
            "risk_level": risk_level,
            "risk_reason": risk_reason,
            "promotion_impact": promotion_impact(str(row.get("stage_id", ""))),
            "watch_action": watch_action(str(row.get("stage_id", "")), risk_level),
            "source_artifacts": row.get("source_artifacts", ""),
        }
        rows.append(out)

    claim_rows = [row for row in rows if str(row["slo_class"]).startswith("claim_now")]
    tight_rows = [row["stage_id"] for row in rows if row["risk_level"] == "tight_margin"]
    watch_rows = [row["stage_id"] for row in rows if row["risk_level"] == "watch"]
    blocked_rows = [row["stage_id"] for row in rows if row["risk_level"] == "blocked"]
    non_claimable_rows = [
        row["stage_id"]
        for row in rows
        if row["risk_level"] in {"smoke_only", "planning_only", "fallback_only"}
    ]
    min_claim_margin_ratio = min(
        [float(row["p95_margin_ratio"]) for row in claim_rows if row["p95_margin_ratio"] not in {"", None}],
        default=None,
    )
    guard_row = next((row for row in rows if row["stage_id"] == "runtime_safe_llm_guard"), {})

    return {
        "runtime_contract": "latency_risk_margin_audit_from_slo_no_live_calls",
        "status": "pass" if not any(row["risk_level"] == "fail" for row in claim_rows) else "fail",
        "source_contracts": {
            "slo_audit": slo.get("runtime_contract", ""),
            "latency_ledger": ledger.get("runtime_contract", ""),
            "promotion_gate": promotion.get("runtime_contract", ""),
            "live_readiness": live_readiness.get("runtime_contract", ""),
        },
        "summary": {
            "row_count": len(rows),
            "claim_now_rows": len(claim_rows),
            "tight_margin_rows": len(tight_rows),
            "watch_rows": len(watch_rows),
            "blocked_rows": len(blocked_rows),
            "non_claimable_rows": len(non_claimable_rows),
            "failed_claim_rows": [row["stage_id"] for row in claim_rows if row["risk_level"] == "fail"],
            "tight_margin_stage_ids": tight_rows,
            "watch_stage_ids": watch_rows,
            "blocked_stage_ids": blocked_rows,
            "non_claimable_stage_ids": non_claimable_rows,
            "min_claim_p95_margin_ratio": round(min_claim_margin_ratio, 4) if min_claim_margin_ratio is not None else "",
            "guard_risk_level": guard_row.get("risk_level", ""),
            "guard_p95_margin_seconds": guard_row.get("p95_margin_seconds", ""),
            "guard_p95_margin_ratio": guard_row.get("p95_margin_ratio", ""),
            "post_live_ready_to_promote": promotion.get("summary", {}).get("ready_to_promote_count", 0),
            "live_ready_runs": live_readiness.get("summary", {}).get("ready_count", 0),
            "live_calls_performed_by_builder": 0,
            "no_new_metric_claim": True,
        },
        "rows": rows,
    }


def write_csv(audit: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "stage_id",
        "surface",
        "claim_status",
        "slo_class",
        "target_status",
        "avg_seconds",
        "p95_seconds",
        "wall_seconds",
        "avg_margin_seconds",
        "p95_margin_seconds",
        "p95_margin_ratio",
        "risk_level",
        "risk_reason",
        "promotion_impact",
        "watch_action",
        "source_artifacts",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit["rows"])


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    lines = [
        "# Latency Risk Margin Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Status: `{audit['status']}`",
        f"- Claim-now rows: `{summary['claim_now_rows']}`",
        f"- Tight-margin rows: `{summary['tight_margin_rows']}`",
        f"- Watch rows: `{summary['watch_rows']}`",
        f"- Blocked rows: `{summary['blocked_rows']}`",
        f"- Non-claimable rows: `{summary['non_claimable_rows']}`",
        f"- Guard risk level: `{summary['guard_risk_level']}`",
        f"- Guard P95 margin: `{summary['guard_p95_margin_seconds']}`",
        f"- Guard P95 margin ratio: `{summary['guard_p95_margin_ratio']}`",
        f"- Post-live ready to promote: `{summary['post_live_ready_to_promote']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "## Risk Rows",
        "",
        "| Stage | SLO class | Risk | P95 | P95 margin | Margin ratio | Promotion impact | Watch action |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for row in audit["rows"]:
        lines.append(
            f"| `{row['stage_id']}` | `{row['slo_class']}` | `{row['risk_level']}` | "
            f"{row['p95_seconds'] or 'n/a'} | {row['p95_margin_seconds'] or 'n/a'} | "
            f"{row['p95_margin_ratio'] or 'n/a'} | {row['promotion_impact']} | {row['watch_action']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This audit turns SLO margin into risk labels for report-level latency claims.",
            "- `tight_margin` keeps a current claim valid, but marks it as sensitive to future live-output latency drift.",
            "- Smoke, planning, fallback, and blocked rows stay out of claim-now latency until their promotion gates pass.",
            "- This builder reads existing artifacts only; it performs no live/API/model calls and creates no new metric claim.",
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
