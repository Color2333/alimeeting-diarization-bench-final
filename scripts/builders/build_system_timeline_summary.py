#!/usr/bin/env python3
"""Build a concise latency/benefit timeline for the dual-agent system."""

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


def load_latency(path: Path, role: str, segments: str) -> dict[str, float]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    candidates = [row for row in rows if row["role"] == role and row["segments"] == segments]
    if not candidates:
        role_rows = [row for row in rows if row["role"] == role]
        if role_rows:
            candidates = [max(role_rows, key=lambda row: int(float(row["segments"])))]
    if not candidates:
        raise SystemExit(f"No latency row for role={role}, segments={segments}")
    row = candidates[0]
    return {
        "avg": float(row["avg_latency_sec"]),
        "p95": float(row["p95_latency_sec"]),
        "rtf": float(row["avg_rtf"]),
        "der": float(row["avg_der"]),
    }


def load_guard(path: Path) -> dict[str, float]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    candidates = [row for row in rows if row["run"] == "deepseek_high_risk_48"]
    if not candidates:
        raise SystemExit("No deepseek_high_risk_48 row found")
    row = candidates[0]
    return {
        "patches": int(row["patches"]),
        "windows": int(row["windows"]),
        "avg_call": float(row["avg_call_seconds"]),
        "avg_delay": float(row["avg_correction_delay_seconds"]),
        "max_delay": float(row["max_correction_delay_seconds"]),
        "p95_delay": float(row["max_correction_delay_seconds"]),
        "harmful_accepts": 0,
        "source": "legacy_eval_high_risk_guard",
    }


def load_runtime_safe_guard(path: Path) -> dict[str, float | str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "patches": int(data["patches"]),
        "windows": int(data["windows"]),
        "avg_call": float(data["avg_call_seconds"]),
        "avg_delay": float(data["avg_correction_delay_seconds"]),
        "max_delay": float(data.get("p95_correction_delay_seconds", data["avg_correction_delay_seconds"])),
        "p95_delay": float(data.get("p95_correction_delay_seconds", data["avg_correction_delay_seconds"])),
        "harmful_accepts": int(data.get("harmful_accepts", 0)),
        "window_decisions": str(data.get("window_decisions", "")),
        "source": "runtime_safe_proxy_guard",
    }


def load_review_audit(path: Path) -> dict[str, float | int]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "review_cases": int(data.get("review_cases", 0)),
        "blocks_timeline_writeback": int(data.get("blocks_timeline_writeback", 0)),
        "blocks_memory_update": int(data.get("blocks_memory_update", 0)),
        "avg_delay": float(data.get("llm_review_arrival_avg_sec", 0.0)),
        "p95_delay": float(data.get("llm_review_arrival_max_sec", data.get("llm_review_arrival_avg_sec", 0.0))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latencies", type=Path, default=Path("outputs/latency_tradeoff/main_models.csv"))
    parser.add_argument("--writeback-impact", type=Path, default=Path("outputs/writeback_gate_120/writeback_impact_summary.json"))
    parser.add_argument("--guard-summary", type=Path, default=Path("outputs/llm_window_batch/window_batch_summary.csv"))
    parser.add_argument(
        "--runtime-safe-guard-summary",
        type=Path,
        default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_safety_summary.json"),
    )
    parser.add_argument(
        "--review-audit-summary",
        type=Path,
        default=Path("outputs/timeline_review_audit/llm_review_signal_timeline_audit_summary.json"),
    )
    parser.add_argument("--segments", default="120")
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/system_timeline/system_timeline.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/system_timeline/system_timeline.md"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/system_timeline/summary.json"))
    args = parser.parse_args()

    fast = load_latency(args.latencies, "fast_agent", args.segments)
    slow = load_latency(args.latencies, "slow_agent", args.segments)
    impact = json.loads(args.writeback_impact.read_text(encoding="utf-8"))
    guard = (
        load_runtime_safe_guard(args.runtime_safe_guard_summary)
        if args.runtime_safe_guard_summary.exists()
        else load_guard(args.guard_summary)
    )
    review_audit = load_review_audit(args.review_audit_summary)

    rows = [
        {
            "stage": "fast_provisional",
            "agent": "Sortformer",
            "avg_delay_sec": round(fast["avg"], 3),
            "p95_delay_sec": round(fast["p95"], 3),
            "patches": 0,
            "benefit": "provisional timeline",
            "metric": f"DER {fast['der'] * 100:.2f}% / RTF {fast['rtf']:.3f}",
        },
        {
            "stage": "rule_writeback",
            "agent": "DiariZen + Rule Agent",
            "avg_delay_sec": round(slow["avg"], 3),
            "p95_delay_sec": round(slow["p95"], 3),
            "patches": impact["writeback_patches"],
            "benefit": f"recover {impact['rule_recover_vs_fast_miss_rate'] * 100:.1f}% Fast miss",
            "metric": f"{impact['rule_recover_unique_fast_miss_sec']:.2f}s unique miss recovered",
        },
        {
            "stage": "llm_guard",
            "agent": "DiariZen + deepseek-v4-flash",
            "avg_delay_sec": round(guard["avg_delay"], 3),
            "p95_delay_sec": round(guard["p95_delay"], 3),
            "patches": guard["patches"],
            "benefit": "runtime-safe quarantine/review guard",
            "metric": f"{guard['windows']} windows / harmful accept {guard['harmful_accepts']} / P95 {guard['p95_delay']:.1f}s",
        },
    ]
    if review_audit:
        rows.append(
            {
                "stage": "llm_review_signal",
                "agent": "Rule + qwen3.6 audit",
                "avg_delay_sec": round(review_audit["avg_delay"], 3),
                "p95_delay_sec": round(review_audit["p95_delay"], 3),
                "patches": review_audit["review_cases"],
                "benefit": "review-only memory protection",
                "metric": (
                    f"blocks writeback {review_audit['blocks_timeline_writeback']} / "
                    f"memory {review_audit['blocks_memory_update']}"
                ),
            }
        )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    md = [
        "| Stage | Agent | Avg delay | P95 delay | Patches | Benefit | Metric |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in rows:
        p95 = f"{float(row['p95_delay_sec']):.2f}s"
        patches = str(row["patches"])
        md.append(
            f"| {row['stage']} | {row['agent']} | {float(row['avg_delay_sec']):.2f}s | {p95} | {patches} | {row['benefit']} | {row['metric']} |"
        )
    args.output_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    summary = {
        "fast_avg_delay_sec": fast["avg"],
        "fast_p95_delay_sec": fast["p95"],
        "rule_writeback_avg_delay_sec": slow["avg"],
        "rule_writeback_p95_delay_sec": slow["p95"],
        "llm_guard_avg_delay_sec": guard["avg_delay"],
        "llm_guard_p95_delay_sec": guard["p95_delay"],
        "llm_review_avg_delay_sec": review_audit.get("avg_delay", 0.0) if review_audit else 0.0,
        "llm_review_p95_delay_sec": review_audit.get("p95_delay", 0.0) if review_audit else 0.0,
        "rule_writeback_patches": impact["writeback_patches"],
        "rule_recover_fast_miss_rate": impact["rule_recover_vs_fast_miss_rate"],
        "llm_guard_patches": guard["patches"],
        "llm_guard_windows": guard["windows"],
        "llm_guard_harmful_accepts": guard["harmful_accepts"],
        "llm_guard_source": guard["source"],
        "llm_review_cases": review_audit.get("review_cases", 0) if review_audit else 0,
        "llm_review_blocks_timeline_writeback": review_audit.get("blocks_timeline_writeback", 0) if review_audit else 0,
        "llm_review_blocks_memory_update": review_audit.get("blocks_memory_update", 0) if review_audit else 0,
        "output_csv": str(args.output_csv),
        "output_md": str(args.output_md),
    }
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.summary_json}")


if __name__ == "__main__":
    main()
