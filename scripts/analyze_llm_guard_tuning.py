#!/usr/bin/env python3
"""Analyze deployable post-LLM guard relaxations on the 104-window proxy set.

The runtime LLM guard is intentionally conservative. This script evaluates
candidate execution-layer relaxations using only deployable fields as policy
inputs, then joins GT support after the fact to measure harmful accepts.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Callable


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def join_rows(safety_path: Path, decisions_path: Path) -> list[dict[str, object]]:
    safety_rows = load_csv(safety_path)
    decision_rows = {row["patch_id"]: row for row in load_csv(decisions_path)}
    rows: list[dict[str, object]] = []
    for row in safety_rows:
        decision = decision_rows.get(row["patch_id"], {})
        rows.append(
            {
                **row,
                "support_ratio": as_float(decision.get("support_ratio")),
                "duration": as_float(decision.get("duration")),
                "rule_decision": decision.get("decision", ""),
                "rule_reason": decision.get("reason", ""),
                "constraints": decision.get("constraints", ""),
                "next_action": decision.get("next_action", ""),
            }
        )
    return rows


def counter_text(counter: Counter[str]) -> str:
    return " / ".join(f"{key} {counter[key]}" for key in sorted(counter)) or "none"


def policy_specs() -> list[tuple[str, str, Callable[[dict[str, object]], bool]]]:
    return [
        (
            "review_support_ge_0.5_non_suppress",
            "review windows; non-suppress patches; cross-model support >= 0.5",
            lambda row: row["window_decision"] == "review"
            and row["patch_type"] != "suppress_fast_candidate"
            and float(row["support_ratio"]) >= 0.5,
        ),
        (
            "review_support_ge_0.8_non_suppress",
            "review windows; non-suppress patches; cross-model support >= 0.8",
            lambda row: row["window_decision"] == "review"
            and row["patch_type"] != "suppress_fast_candidate"
            and float(row["support_ratio"]) >= 0.8,
        ),
        (
            "keep_fast_supported_ge_0.5_passthrough",
            "keep_fast_supported passthrough; cross-model support >= 0.5",
            lambda row: row["patch_type"] == "keep_fast_supported" and float(row["support_ratio"]) >= 0.5,
        ),
        (
            "keep_fast_supported_ge_0.9_passthrough",
            "keep_fast_supported passthrough; cross-model support >= 0.9",
            lambda row: row["patch_type"] == "keep_fast_supported" and float(row["support_ratio"]) >= 0.9,
        ),
        (
            "combined_review0.5_keepfast0.5",
            "review non-suppress support >= 0.5, plus keep_fast_supported passthrough support >= 0.5",
            lambda row: (
                row["window_decision"] == "review"
                and row["patch_type"] != "suppress_fast_candidate"
                and float(row["support_ratio"]) >= 0.5
            )
            or (row["patch_type"] == "keep_fast_supported" and float(row["support_ratio"]) >= 0.5),
        ),
        (
            "combined_review0.8_keepfast0.9",
            "review non-suppress support >= 0.8, plus keep_fast_supported passthrough support >= 0.9",
            lambda row: (
                row["window_decision"] == "review"
                and row["patch_type"] != "suppress_fast_candidate"
                and float(row["support_ratio"]) >= 0.8
            )
            or (row["patch_type"] == "keep_fast_supported" and float(row["support_ratio"]) >= 0.9),
        ),
        (
            "negative_quarantine_support_ge_0.95",
            "negative control: quarantine non-suppress patches with support >= 0.95",
            lambda row: row["window_decision"] == "quarantine"
            and row["patch_type"] != "suppress_fast_candidate"
            and float(row["support_ratio"]) >= 0.95,
        ),
    ]


def evaluate_policy(rows: list[dict[str, object]], name: str, predicate_text: str, predicate: Callable[[dict[str, object]], bool]) -> dict[str, object]:
    candidates = [row for row in rows if row["safety_class"] != "safe_accept" and predicate(row)]
    safety = Counter(str(row["safety_class"]) for row in candidates)
    patch_types = Counter(str(row["patch_type"]) for row in candidates)
    windows = Counter(str(row["window_decision"]) for row in candidates)
    current = Counter(str(row["safety_class"]) for row in rows)
    recovered = safety["conservative_block"]
    harmful = safety["safe_block"]
    return {
        "policy": name,
        "predicate": predicate_text,
        "candidate_accepts": len(candidates),
        "conservative_recovered": recovered,
        "harmful_accepts": harmful,
        "safe_accepts_after": current["safe_accept"] + recovered,
        "conservative_blocks_after": current["conservative_block"] - recovered,
        "safe_blocks_after": current["safe_block"] - harmful,
        "patch_type_mix": counter_text(patch_types),
        "window_mix": counter_text(windows),
        "verdict": "candidate_zero_harm_sample" if harmful == 0 and recovered > 0 else "negative_control_or_reject",
    }


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(summary: dict[str, object], rows: list[dict[str, object]], path: Path) -> None:
    lines = [
        "# LLM Guard Tuning Analysis",
        "",
        "## Current 104w Guard",
        "",
        f"- Windows: {summary['windows']}",
        f"- Patches: {summary['patches']}",
        f"- Current safety: {summary['current_safety']}",
        f"- Current window decisions: {summary['window_decisions']}",
        "",
        "## Candidate Policies",
        "",
        "| Policy | Candidate accepts | Conservative recovered | Harmful accepts | Safe accepts after | Conservative after | Verdict | Predicate |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {policy} | {candidate_accepts} | {conservative_recovered} | {harmful_accepts} | "
            "{safe_accepts_after} | {conservative_blocks_after} | {verdict} | {predicate} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Policies use deployable fields only: LLM window decision, patch type, and cross-model support.",
            "- GT support is used only after the policy simulation to label safe vs harmful accepts.",
            "- The negative control shows why high support alone is not enough inside quarantine windows.",
            "- `keep_fast_supported` passthrough should be treated as preserving an already visible fast segment, not writing a new slow timestamp.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--safety-csv", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_safety.csv"))
    parser.add_argument("--decisions-csv", type=Path, default=Path("outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.csv"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/llm_guard_tuning_104w.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/llm_guard_tuning_104w.md"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/llm_guard_tuning_104w_summary.json"))
    args = parser.parse_args()

    rows = join_rows(args.safety_csv, args.decisions_csv)
    results = [evaluate_policy(rows, name, text, predicate) for name, text, predicate in policy_specs()]
    current_safety = Counter(str(row["safety_class"]) for row in rows)
    window_decisions = Counter(str(row["window_decision"]) for row in rows)
    best_zero_harm = max(
        (row for row in results if row["harmful_accepts"] == 0),
        key=lambda row: int(row["conservative_recovered"]),
    )
    summary = {
        "windows": len({row["window_id"] for row in rows}),
        "patches": len(rows),
        "current_safety": counter_text(current_safety),
        "window_decisions": counter_text(window_decisions),
        "best_zero_harm_policy": best_zero_harm["policy"],
        "best_zero_harm_conservative_recovered": best_zero_harm["conservative_recovered"],
        "best_zero_harm_safe_accepts_after": best_zero_harm["safe_accepts_after"],
        "best_zero_harm_conservative_blocks_after": best_zero_harm["conservative_blocks_after"],
        "best_zero_harm_harmful_accepts": best_zero_harm["harmful_accepts"],
    }

    write_csv(results, args.output_csv)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, results, args.output_md)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.summary_json}")


if __name__ == "__main__":
    main()
