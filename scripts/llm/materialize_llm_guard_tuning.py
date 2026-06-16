#!/usr/bin/env python3
"""Materialize a tuned post-LLM guard policy into JSONL decisions."""

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
from collections import Counter
from pathlib import Path
from typing import Any


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def should_accept_combined_review_keepfast(
    window_decision: str,
    patch: dict[str, Any],
    runtime_decision: dict[str, str],
    review_support: float,
    keepfast_support: float,
) -> bool:
    patch_type = runtime_decision.get("patch_type") or patch.get("patch_type", "")
    support = as_float(runtime_decision.get("support_ratio"))
    if window_decision == "review" and patch_type != "suppress_fast_candidate" and support >= review_support:
        return True
    if patch_type == "keep_fast_supported" and support >= keepfast_support:
        return True
    return False


def patch_decision_counts(patches: list[dict[str, Any]]) -> str:
    counts = Counter(str(patch.get("decision", "unknown")) for patch in patches)
    return " / ".join(f"{key} {counts[key]}" for key in sorted(counts))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w.jsonl"))
    parser.add_argument("--decisions-csv", type=Path, default=Path("outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.csv"))
    parser.add_argument("--policy", choices=["combined_review0.5_keepfast0.5", "combined_review0.8_keepfast0.9"], default="combined_review0.5_keepfast0.5")
    parser.add_argument("--output-jsonl", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned.jsonl"))
    parser.add_argument("--summary-json", type=Path, default=Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_summary.json"))
    args = parser.parse_args()

    review_support, keepfast_support = (0.5, 0.5) if args.policy == "combined_review0.5_keepfast0.5" else (0.8, 0.9)
    runtime_by_patch = {row["patch_id"]: row for row in load_csv(args.decisions_csv)}
    rows = load_jsonl(args.input_jsonl)
    tuned_rows = []
    tuned_patches = 0
    tuned_windows: set[str] = set()
    patch_types: Counter[str] = Counter()
    window_decisions: Counter[str] = Counter()

    for window in rows:
        tuned_window = dict(window)
        window_decision = str(window.get("window_decision", ""))
        new_patches = []
        for patch in window.get("patch_decisions", []):
            runtime_decision = runtime_by_patch.get(patch["patch_id"], {})
            new_patch = dict(patch)
            if new_patch.get("decision") != "accept" and should_accept_combined_review_keepfast(
                window_decision,
                new_patch,
                runtime_decision,
                review_support=review_support,
                keepfast_support=keepfast_support,
            ):
                new_patch["original_decision"] = new_patch.get("original_decision", new_patch.get("decision", ""))
                new_patch["decision"] = "accept"
                new_patch["reason"] = f"tuned_{args.policy}"
                new_patch["next_action"] = runtime_decision.get("next_action") or new_patch.get("next_action", "apply_patch")
                constraints = list(new_patch.get("constraints", []))
                if "post_llm_tuning_zero_harm_candidate" not in constraints:
                    constraints.append("post_llm_tuning_zero_harm_candidate")
                new_patch["constraints"] = constraints
                tuned_patches += 1
                tuned_windows.add(str(window.get("window_id")))
                patch_types[str(runtime_decision.get("patch_type") or new_patch.get("patch_type", ""))] += 1
            new_patches.append(new_patch)
        tuned_window["patch_decisions"] = new_patches
        tuned_window["patch_decision_counts"] = patch_decision_counts(new_patches)
        window_decisions[window_decision] += 1
        tuned_rows.append(tuned_window)

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.output_jsonl.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in tuned_rows),
        encoding="utf-8",
    )
    summary = {
        "policy": args.policy,
        "windows": len(tuned_rows),
        "tuned_windows": len(tuned_windows),
        "tuned_patches": tuned_patches,
        "window_decisions": dict(window_decisions),
        "tuned_patch_types": dict(patch_types),
        "input_jsonl": str(args.input_jsonl),
        "output_jsonl": str(args.output_jsonl),
    }
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
