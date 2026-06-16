#!/usr/bin/env python3
"""Audit runtime evidence for eval/GT leakage.

The report claims that DER, GT support, and oracle labels are evaluation-only.
This script checks current artifacts and prompt exports against that contract,
then separates deployable evidence from development-only probes.
"""

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
import re
from collections import Counter
from pathlib import Path
from typing import Any


FORBIDDEN_KEY_RE = re.compile(r"(^gt_|_gt_|gt$|ground_truth|oracle|eval_only|der|miss|fa_rate|conf_rate|spk_count_gt)", re.I)
EVAL_DERIVED_VALUE_RE = re.compile(r"(high_der|high_fa|high_miss|(?<!cross_model_)speaker_count_mismatch)", re.I)
RUNTIME_ALLOWED_EVAL_WORDS = {"task", "reason", "verdict", "evidence", "role"}


def read_csv_headers(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader)


def read_csv_rows(path: Path, limit: int = 2000) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = []
        for idx, row in enumerate(csv.DictReader(handle)):
            if idx >= limit:
                break
            rows.append(row)
        return rows


def flatten_json(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            items.extend(flatten_json(item, next_prefix))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            items.extend(flatten_json(item, f"{prefix}[{idx}]"))
    else:
        items.append((prefix, value))
    return items


def json_from_user_message(message: dict[str, Any]) -> Any | None:
    if message.get("role") != "user":
        return None
    content = message.get("content", "")
    if not isinstance(content, str):
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def audit_csv(path: Path, artifact: str, expected: str) -> dict[str, object]:
    headers = read_csv_headers(path)
    forbidden_headers = [header for header in headers if FORBIDDEN_KEY_RE.search(header)]
    rows = read_csv_rows(path)
    eval_values: Counter[str] = Counter()
    for row in rows:
        for value in row.values():
            for match in EVAL_DERIVED_VALUE_RE.findall(str(value)):
                eval_values[match.lower()] += 1
    status = "pass"
    if expected == "runtime" and (forbidden_headers or eval_values):
        status = "fail"
    elif expected == "runtime_prompt_context" and eval_values:
        status = "fail"
    elif forbidden_headers or eval_values:
        status = "dev_only"
    return {
        "artifact": artifact,
        "path": str(path),
        "kind": "csv",
        "expected": expected,
        "status": status,
        "forbidden_headers": forbidden_headers,
        "eval_derived_values": dict(eval_values),
        "sampled_rows": len(rows),
    }


def audit_jsonl_prompts(path: Path, artifact: str, expected: str, limit: int = 200) -> dict[str, object]:
    forbidden_keys: Counter[str] = Counter()
    eval_values: Counter[str] = Counter()
    parsed_prompts = 0
    with path.open(encoding="utf-8") as handle:
        for idx, line in enumerate(handle):
            if idx >= limit:
                break
            if not line.strip():
                continue
            row = json.loads(line)
            for message in row.get("messages", []):
                payload = json_from_user_message(message)
                if payload is None:
                    continue
                parsed_prompts += 1
                for key, value in flatten_json(payload):
                    leaf_key = key.rsplit(".", 1)[-1].split("[", 1)[0]
                    if leaf_key not in RUNTIME_ALLOWED_EVAL_WORDS and FORBIDDEN_KEY_RE.search(leaf_key):
                        forbidden_keys[key] += 1
                    if isinstance(value, str):
                        for match in EVAL_DERIVED_VALUE_RE.findall(value):
                            eval_values[match.lower()] += 1
    status = "pass"
    if expected == "runtime" and (forbidden_keys or eval_values):
        status = "fail"
    elif forbidden_keys or eval_values:
        status = "dev_only"
    return {
        "artifact": artifact,
        "path": str(path),
        "kind": "jsonl_prompt",
        "expected": expected,
        "status": status,
        "forbidden_prompt_keys": dict(forbidden_keys.most_common(20)),
        "eval_derived_prompt_values": dict(eval_values),
        "sampled_prompts": parsed_prompts,
    }


def audit_source(path: Path, artifact: str, expected: str, patterns: list[str]) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    hits = {}
    for pattern in patterns:
        matches = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern in line:
                matches.append(f"{lineno}:{line.strip()}")
        if matches:
            hits[pattern] = matches[:10]
    status = "pass"
    if expected == "runtime" and hits:
        status = "fail"
    elif hits:
        status = "dev_only"
    return {
        "artifact": artifact,
        "path": str(path),
        "kind": "source",
        "expected": expected,
        "status": status,
        "source_hits": hits,
    }


def audit_review_timeline(path: Path, artifact: str, expected: str) -> dict[str, object]:
    row = audit_csv(path, artifact, expected)
    rows = read_csv_rows(path)
    blockers = [
        item
        for item in rows
        if str(item.get("blocks_timeline_writeback", "")).strip() not in {"0", "0.0", "false", "False", ""}
    ]
    actions = Counter(item.get("llm_review_action", "") for item in rows)
    memory_blocks = sum(
        1
        for item in rows
        if str(item.get("blocks_memory_update", "")).strip() in {"1", "1.0", "true", "True"}
    )
    if expected == "runtime" and blockers:
        row["status"] = "fail"
    row["timeline_writeback_blockers"] = len(blockers)
    row["memory_update_blocks"] = memory_blocks
    row["llm_review_actions"] = dict(actions)
    return row


def audit_omni_fusion(path: Path, summary_path: Path, artifact: str, expected: str) -> dict[str, object]:
    row = audit_csv(path, artifact, expected)
    rows = read_csv_rows(path)
    allowed_actions = {
        "early_quarantine_candidate",
        "early_review_priority",
        "acoustic_proxy_review",
        "omni_label_only_hint",
        "no_action",
    }
    actions = Counter(item.get("fusion_action", "") for item in rows)
    forbidden_actions = sorted(action for action in actions if action not in allowed_actions)
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    contract = summary.get("runtime_contract", "")
    if expected == "runtime" and (
        forbidden_actions
        or "no_timeline_writeback" not in str(contract)
        or summary.get("clean_review_priority_fp") == "0/4 (0.0%)"
    ):
        row["status"] = "fail"
    row["fusion_actions"] = dict(actions)
    row["forbidden_fusion_actions"] = forbidden_actions
    row["runtime_contract"] = contract
    row["clean_review_priority_fp"] = summary.get("clean_review_priority_fp", "")
    row["high_sentinel_recall"] = summary.get("high_sentinel_recall", "")
    return row


def audit_selector_validation(path: Path, artifact: str, expected: str) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    positive = int(data.get("positive_splits", 0))
    splits = int(data.get("splits", 0))
    delta = float(data.get("weighted_delta_vs_fast", 0.0))
    status = "dev_only"
    if expected == "runtime":
        status = "fail"
    return {
        "artifact": artifact,
        "path": str(path),
        "kind": "json_summary",
        "expected": expected,
        "status": status,
        "positive_splits": f"{positive}/{splits}",
        "weighted_delta_vs_fast": delta,
        "fixed_policy": data.get("fixed_policy", ""),
    }


def verdict(rows: list[dict[str, object]]) -> dict[str, object]:
    counts = Counter(str(row["status"]) for row in rows)
    blocking = [
        row
        for row in rows
        if row["expected"] in {"runtime", "runtime_prompt_context"} and row["status"] == "fail"
    ]
    return {
        "artifact_count": len(rows),
        "status_counts": dict(counts),
        "runtime_blocking_count": len(blocking),
        "runtime_blocking_artifacts": [row["artifact"] for row in blocking],
        "overall_status": "needs_runtime_evidence_fix" if blocking else "pass",
    }


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["artifact", "kind", "expected", "status", "path", "details"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            details = {
                key: value
                for key, value in row.items()
                if key not in {"artifact", "kind", "expected", "status", "path"}
                and value
            }
            writer.writerow(
                {
                    "artifact": row["artifact"],
                    "kind": row["kind"],
                    "expected": row["expected"],
                    "status": row["status"],
                    "path": row["path"],
                    "details": json.dumps(details, ensure_ascii=False, sort_keys=True),
                }
            )


def write_markdown(rows: list[dict[str, object]], summary: dict[str, object], path: Path) -> None:
    lines = [
        "# Runtime Evidence Contract Audit",
        "",
        "| Artifact | Expected | Status | Finding |",
        "|---|---|---|---|",
    ]
    for row in rows:
        finding_parts = []
        if row.get("forbidden_headers"):
            finding_parts.append("headers: " + ", ".join(row["forbidden_headers"][:8]))
        if row.get("eval_derived_values"):
            finding_parts.append("eval-derived values: " + ", ".join(f"{k}={v}" for k, v in row["eval_derived_values"].items()))
        if row.get("forbidden_prompt_keys"):
            finding_parts.append("prompt keys: " + ", ".join(list(row["forbidden_prompt_keys"])[:5]))
        if row.get("eval_derived_prompt_values"):
            finding_parts.append("prompt values: " + ", ".join(f"{k}={v}" for k, v in row["eval_derived_prompt_values"].items()))
        if row.get("source_hits"):
            finding_parts.append("source uses: " + ", ".join(row["source_hits"].keys()))
        finding = "; ".join(finding_parts) if finding_parts else "clean"
        lines.append(f"| {row['artifact']} | {row['expected']} | {row['status']} | {finding} |")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Overall status: `{summary['overall_status']}`.",
            f"- Runtime-blocking artifacts: `{summary['runtime_blocking_count']}`.",
            f"- Status counts: `{json.dumps(summary['status_counts'], ensure_ascii=False, sort_keys=True)}`.",
            "",
            "## Reading",
            "",
            "- `pass` means no GT/eval-derived fields were found in the checked runtime surface.",
            "- `dev_only` means the artifact can be used for analysis, ranking, or safety labels, but not as deployable runtime context.",
            "- `fail` means a surface currently treated as runtime/prompt context contains eval-derived fields or values.",
            "- Current high-risk LLM guard prompts are valid as development risk probes, but must switch from `high_der/high_fa/high_miss` to deployable proxy flags before being claimed as runtime evidence.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/runtime_evidence_audit"))
    args = parser.parse_args()

    checks: list[dict[str, object]] = []
    checks.append(audit_csv(Path("outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv"), "deployable abnormal proxy flags", "runtime"))
    checks.append(audit_csv(Path("outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.csv"), "runtime-safe policy-agent decisions", "runtime"))
    checks.append(audit_csv(Path("outputs/system_timeline/system_timeline.csv"), "four-stage system timeline", "runtime"))
    review_timeline = Path("outputs/timeline_review_audit/llm_review_signal_timeline_audit.csv")
    if review_timeline.exists():
        checks.append(audit_review_timeline(review_timeline, "LLM review-signal timeline audit", "runtime"))
    omni_fusion = Path("outputs/omni_guard/omni_acoustic_fusion.csv")
    omni_fusion_summary = Path("outputs/omni_guard/omni_acoustic_fusion_summary.json")
    if omni_fusion.exists():
        checks.append(audit_omni_fusion(omni_fusion, omni_fusion_summary, "Omni fusion no-writeback contract", "runtime"))
    checks.append(audit_csv(Path("outputs/abnormal_windows/sortformer_diarizen_120.csv"), "eval abnormal flags", "dev_only"))
    selector_holdout = Path("outputs/recover_selector_split_120/recording_holdout_summary.json")
    if selector_holdout.exists():
        checks.append(audit_selector_validation(selector_holdout, "selector recording-holdout validation", "dev_only"))
    checks.append(audit_csv(Path("outputs/writeback_gate_120/gate_decisions.csv"), "legacy 120 writeback gate decisions", "dev_only"))
    checks.append(audit_csv(Path("outputs/policy_agent/sortformer_diarizen_120_decisions.csv"), "deterministic policy-agent decisions", "dev_only"))
    checks.append(audit_csv(Path("outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv"), "120 patch window feature table", "dev_only"))
    checks.append(audit_jsonl_prompts(Path("outputs/llm_policy_agent/mixed18_prompts.jsonl"), "legacy single-patch LLM prompts", "dev_only"))
    checks.append(audit_jsonl_prompts(Path("outputs/llm_window_batch/deepseek_high_risk_prompts.jsonl"), "legacy window-batch LLM prompts", "dev_only"))
    checks.append(audit_jsonl_prompts(Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_prompts.jsonl"), "runtime-safe proxy window-batch prompts", "runtime"))
    split_prompt_path = Path("outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompts.jsonl")
    if split_prompt_path.exists():
        checks.append(audit_jsonl_prompts(split_prompt_path, "runtime-safe split20 replay prompts", "runtime"))
    checks.append(
        audit_source(
            Path("scripts/llm/policy_agent_decisions.py"),
            "deterministic policy-agent source",
            "dev_only",
            ["gt_support", "true_speech_threshold", "true_fa_threshold"],
        )
    )
    checks.append(
        audit_source(
            Path("scripts/search/search_recover_selector_policies.py"),
            "selector policy source",
            "runtime",
            ["gt_support", "spk_count_gt", "fast_der", "slow_der", "oracle"],
        )
    )

    summary = verdict(checks)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "runtime_evidence_audit.csv"
    json_path = args.output_dir / "runtime_evidence_audit.json"
    md_path = args.output_dir / "runtime_evidence_audit.md"
    write_csv(checks, csv_path)
    json_path.write_text(json.dumps({"summary": summary, "checks": checks}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(checks, summary, md_path)
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
