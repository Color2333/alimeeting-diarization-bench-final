#!/usr/bin/env python3
"""Run an LLM Policy Agent over rule-agent patch decisions.

The LLM is only allowed to arbitrate within the structured decision space:
accept / reject / defer / quarantine. It cannot invent timestamps or rewrite
diarization output directly.
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
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alimeeting_diarization_bench.config import APIKeys


SYSTEM_PROMPT = """You are a policy agent for a speaker diarization system.
You do NOT perform diarization. You only arbitrate structured correction patches.

Allowed decisions:
- accept: apply the patch
- reject: do not apply the patch
- defer: wait for more context, memory cleanup, or semantic evidence
- quarantine: isolate the whole window/patch because it may contaminate the timeline

Hard rules:
- Never invent or alter timestamps.
- Never accept suppress_fa unless evidence is strong.
- Short segments should not update speaker memory.
- If memory is low confidence, defer relabel decisions.
- If a window has high DER/high FA abnormal flags, prefer quarantine or defer.
- recover_miss can be accepted when cross-model/semantic evidence is strong.

Return only valid JSON:
{
  "decision": "accept|reject|defer|quarantine",
  "reason": "short_snake_case",
  "confidence": 0.0,
  "constraints": ["..."],
  "next_action": "short_action"
}
"""


ALLOWED_MODELS = [
    "qwen3.7-plus",
    "deepseek-v4-flash",
    "qwen3.6-flash-2026-04-16",
    "qwen3.6-35b-a3b",
    "glm-5.1",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def risk_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if row.get("decision") in {"quarantine", "defer"} else 1,
        float(row.get("confidence") or 0.0),
        -float(row.get("duration") or 0.0),
    )


def pick_risk_first(rows: list[dict[str, Any]], max_items: int | None, include_accept: bool) -> list[dict[str, Any]]:
    if include_accept:
        candidates = rows
    else:
        candidates = [
            row
            for row in rows
            if row.get("decision") != "accept"
            or float(row.get("confidence") or 0.0) < 0.65
        ]
    candidates.sort(key=risk_sort_key)
    return candidates[:max_items] if max_items is not None else candidates


def pick_mixed(rows: list[dict[str, Any]], max_items: int | None, include_accept: bool) -> list[dict[str, Any]]:
    candidates = rows if include_accept else [row for row in rows if row.get("decision") != "accept"]
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in candidates:
        buckets.setdefault((str(row.get("decision")), str(row.get("patch_type"))), []).append(row)
    for bucket_rows in buckets.values():
        bucket_rows.sort(key=risk_sort_key)

    bucket_order = [
        ("quarantine", "recover_slow_segment"),
        ("defer", "boundary_fix_or_relabel"),
        ("defer", "recover_slow_segment"),
        ("defer", "suppress_fast_candidate"),
        ("accept", "suppress_fast_candidate"),
        ("accept", "recover_slow_segment"),
        ("accept", "boundary_fix_or_relabel"),
        ("accept", "keep_fast_supported"),
        ("accept", "align_slow_segment"),
    ]
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    limit = max_items if max_items is not None else len(candidates)
    while len(selected) < limit:
        made_progress = False
        for key in bucket_order:
            bucket = buckets.get(key, [])
            while bucket and bucket[0]["patch_id"] in seen:
                bucket.pop(0)
            if bucket and len(selected) < limit:
                row = bucket.pop(0)
                selected.append(row)
                seen.add(row["patch_id"])
                made_progress = True
        if not made_progress:
            break
    return selected


def pick_items(
    rows: list[dict[str, Any]],
    max_items: int | None,
    include_accept: bool,
    selection: str,
) -> list[dict[str, Any]]:
    if selection == "mixed":
        return pick_mixed(rows, max_items=max_items, include_accept=include_accept)
    return pick_risk_first(rows, max_items=max_items, include_accept=include_accept)


def prompt_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "patch_id": row["patch_id"],
        "patch": {
            "source": row["source"],
            "patch_type": row["patch_type"],
            "start": row["start"],
            "end": row["end"],
            "duration": row["duration"],
            "speaker": row["speaker"],
            "matched_source": row.get("matched_source"),
            "matched_speaker": row.get("matched_speaker"),
            "support_ratio": row.get("support_ratio"),
            "abnormal_flags": row.get("abnormal_flags", []),
        },
        "rule_agent_decision": {
            "decision": row["decision"],
            "reason": row["reason"],
            "constraints": row.get("constraints", []),
            "next_action": row.get("next_action"),
            "confidence": row.get("confidence"),
        },
        "task": (
            "Audit the rule-agent decision. Return one JSON object using only "
            "the allowed decision space. Prefer safety for suppress_fa and "
            "memory relabel patches."
        ),
    }


def make_client(args: argparse.Namespace) -> OpenAI:
    api_keys = APIKeys.from_env()
    api_key = (
        args.api_key
        or os.environ.get("DASHSCOPE_API_KEY")
        or os.environ.get("BAILIAN_API_KEY")
        or os.environ.get("ALIYUN_BAILIAN_API_KEY")
        or api_keys.dashscope_api_key
    )
    base_url = args.base_url or os.environ.get("DASHSCOPE_BASE_URL") or api_keys.dashscope_base_url
    if not api_key:
        raise SystemExit("DashScope/Bailian API key is required")
    return OpenAI(api_key=api_key, base_url=base_url)


def call_llm(client: OpenAI, model: str, row: dict[str, Any], temperature: float) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(prompt_payload(row), ensure_ascii=False)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    payload = json.loads(extract_json(content))
    decision = str(payload.get("decision", "")).strip()
    if decision not in {"accept", "reject", "defer", "quarantine"}:
        raise ValueError(f"Invalid LLM decision: {decision!r}")
    usage = getattr(response, "usage", None)
    return {
        "decision": decision,
        "reason": str(payload.get("reason", "unspecified")),
        "confidence": float(payload.get("confidence", 0.0)),
        "constraints": payload.get("constraints", []),
        "next_action": str(payload.get("next_action", "")),
        "raw_content": content,
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
    }


def extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        return text[start : end + 1]
    return text


def write_outputs(rows: list[dict[str, Any]], output_jsonl: Path, output_csv: Path, summary_output: Path) -> None:
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    fieldnames = [
        "patch_id",
        "model",
        "rule_decision",
        "rule_reason",
        "llm_decision",
        "llm_reason",
        "llm_confidence",
        "agreement",
        "patch_type",
        "source",
        "duration",
        "abnormal_flags",
        "llm_constraints",
        "llm_next_action",
        "call_seconds",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "error",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    decision_counts = Counter(row.get("llm_decision", "error") for row in rows)
    rule_decision_counts = Counter(row.get("rule_decision", "unknown") for row in rows)
    patch_type_counts = Counter(row.get("patch_type", "unknown") for row in rows)
    decision_by_patch_type = Counter(
        f"{row.get('patch_type', 'unknown')}::{row.get('llm_decision', 'error')}" for row in rows
    )
    agreement_count = sum(1 for row in rows if row.get("agreement") is True)
    call_seconds = [float(row["call_seconds"]) for row in rows if row.get("call_seconds") not in {"", None}]
    call_seconds_sorted = sorted(call_seconds)
    p95_index = int(round((len(call_seconds_sorted) - 1) * 0.95)) if call_seconds_sorted else 0
    total_tokens = sum(int(row.get("total_tokens") or 0) for row in rows)
    summary = {
        "items": len(rows),
        "decision_counts": dict(decision_counts),
        "rule_decision_counts": dict(rule_decision_counts),
        "patch_type_counts": dict(patch_type_counts),
        "decision_by_patch_type": dict(decision_by_patch_type),
        "agreement_rate": agreement_count / len(rows) if rows else 0.0,
        "avg_call_seconds": sum(call_seconds) / len(call_seconds) if call_seconds else 0.0,
        "p95_call_seconds": call_seconds_sorted[p95_index] if call_seconds_sorted else 0.0,
        "total_call_seconds": sum(call_seconds),
        "total_tokens": total_tokens,
        "output_jsonl": str(output_jsonl),
        "output_csv": str(output_csv),
    }
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", required=True, type=Path)
    parser.add_argument("--mode", choices=["export", "call"], default="export")
    parser.add_argument("--model", choices=ALLOWED_MODELS, default="qwen3.6-flash-2026-04-16")
    parser.add_argument("--max-items", type=int, default=20)
    parser.add_argument("--include-accept", action="store_true")
    parser.add_argument("--selection", choices=["risk-first", "mixed"], default="risk-first")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--output-jsonl", type=Path, default=Path("outputs/llm_policy_agent/results.jsonl"))
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--summary-output", type=Path, default=None)
    args = parser.parse_args()

    selected = pick_items(load_jsonl(args.decisions), args.max_items, args.include_accept, args.selection)
    if not selected:
        raise SystemExit("No decisions selected for LLM audit")

    output_csv = args.output_csv or args.output_jsonl.with_suffix(".csv")
    summary_output = args.summary_output or args.output_jsonl.with_name(args.output_jsonl.stem + "_summary.json")

    if args.mode == "export":
        rows = [
            {
                "patch_id": row["patch_id"],
                "model": args.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(prompt_payload(row), ensure_ascii=False)},
                ],
                "rule_decision": row["decision"],
                "rule_reason": row["reason"],
            }
            for row in selected
        ]
        args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.output_jsonl.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("Exported %d LLM policy prompts to %s" % (len(rows), args.output_jsonl))
        return

    client = make_client(args)
    output_rows = []
    for row in selected:
        base = {
            "patch_id": row["patch_id"],
            "model": args.model,
            "rule_decision": row["decision"],
            "rule_reason": row["reason"],
            "patch_type": row["patch_type"],
            "source": row["source"],
            "duration": row["duration"],
            "abnormal_flags": "|".join(row.get("abnormal_flags", [])),
        }
        try:
            started = time.perf_counter()
            llm = call_llm(client, args.model, row, args.temperature)
            call_seconds = time.perf_counter() - started
            base.update(
                {
                    "llm_decision": llm["decision"],
                    "llm_reason": llm["reason"],
                    "llm_confidence": llm["confidence"],
                    "agreement": llm["decision"] == row["decision"],
                    "llm_constraints": "|".join(str(item) for item in llm.get("constraints", [])),
                    "llm_next_action": llm["next_action"],
                    "call_seconds": round(call_seconds, 3),
                    "prompt_tokens": llm.get("prompt_tokens"),
                    "completion_tokens": llm.get("completion_tokens"),
                    "total_tokens": llm.get("total_tokens"),
                    "raw_content": llm["raw_content"],
                    "error": "",
                }
            )
        except Exception as exc:
            call_seconds = time.perf_counter() - started if "started" in locals() else 0.0
            base.update(
                {
                    "llm_decision": "error",
                    "llm_reason": "call_failed",
                    "llm_confidence": 0.0,
                    "agreement": False,
                    "llm_constraints": "",
                    "llm_next_action": "",
                    "call_seconds": round(call_seconds, 3),
                    "prompt_tokens": "",
                    "completion_tokens": "",
                    "total_tokens": "",
                    "raw_content": "",
                    "error": repr(exc),
                }
            )
        output_rows.append(base)

    write_outputs(output_rows, args.output_jsonl, output_csv, summary_output)
    print("LLM Policy Agent eval")
    print("model=%s items=%d jsonl=%s csv=%s" % (args.model, len(output_rows), args.output_jsonl, output_csv))
    print("summary=%s" % summary_output)
    print("decision_counts", dict(Counter(row.get("llm_decision", "error") for row in output_rows)))
    agreement = sum(1 for row in output_rows if row.get("agreement") is True) / len(output_rows)
    print("agreement=%.1f%%" % (agreement * 100))


if __name__ == "__main__":
    main()
