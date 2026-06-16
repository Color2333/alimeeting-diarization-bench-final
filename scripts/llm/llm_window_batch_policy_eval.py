#!/usr/bin/env python3
"""Run a window-batched LLM Policy Agent over diarization patch decisions."""

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alimeeting_diarization_bench.config import APIKeys
from scripts.llm_policy_agent_eval import ALLOWED_MODELS, extract_json


SYSTEM_PROMPT = """You are a window-batched policy agent for a speaker diarization system.
You do NOT perform diarization. You only arbitrate structured correction patches
for one completed audio window.

Allowed patch decisions:
- accept: apply the patch
- reject: do not apply the patch
- defer: wait for more context, memory cleanup, or semantic evidence
- quarantine: isolate the patch/window because it may contaminate the timeline

Allowed window decisions:
- clean: no special action needed
- review: keep patches pending for later evidence
- quarantine: isolate the whole window from automatic writeback

Hard rules:
- Never invent or alter timestamps.
- Return a decision for every supplied patch_id exactly once.
- Never accept suppress_fast_candidate unless evidence is strong.
- Short segments should not update speaker memory.
- If memory is low confidence, defer relabel decisions.
- If a window has deployable proxy abnormal flags, prefer quarantine or defer.
- When many patches in the same window share prediction-proxy risk flags, prefer a
  window-level quarantine over many independent accepts.
- If window_decision is quarantine, every patch decision must be quarantine or defer,
  never accept.

Return only valid JSON:
{
  "window_decision": "clean|review|quarantine",
  "window_reason": "short_snake_case",
  "confidence": 0.0,
  "patch_decisions": [
    {
      "patch_id": "...",
      "decision": "accept|reject|defer|quarantine",
      "reason": "short_snake_case",
      "confidence": 0.0,
      "constraints": ["..."],
      "next_action": "short_action"
    }
  ]
}
"""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_window_evidence(path: Path | None) -> dict[tuple[str, int, int], dict[str, Any]]:
    evidence = {}
    rows = load_csv(path)
    if not rows:
        return evidence
    if "evidence_source" in rows[0] and "reason" in rows[0]:
        grouped: dict[tuple[str, int, int], list[dict[str, str]]] = {}
        for row in rows:
            key = (row["recording_id"], int(row["window_size"]), int(row["segment_idx"]))
            grouped.setdefault(key, []).append(row)
        for key, items in grouped.items():
            reasons = sorted({reason for row in items for reason in row.get("reason", "").split(",") if reason})
            evidence[key] = {
                "proxy_flag_count": len(reasons),
                "proxy_flags": reasons,
                "proxy_models": sorted({row.get("model_name", "") for row in items}),
                "fast_spk_count_pred": int(float(items[0].get("fast_spk_count_pred") or 0)),
                "slow_spk_count_pred": int(float(items[0].get("slow_spk_count_pred") or 0)),
                "fast_speech_sec": round(float(items[0].get("fast_speech") or 0.0), 3),
                "slow_speech_sec": round(float(items[0].get("slow_speech") or 0.0), 3),
                "fast_slow_disagreement_sec": round(float(items[0].get("fast_slow_disagreement_sec") or 0.0), 3),
            }
        return evidence
    for row in rows:
        key = (row["recording_id"], int(row["window_size"]), int(row["segment_idx"]))
        evidence[key] = {
            "fast_spk_count_pred": int(float(row["fast_spk_count_pred"])),
            "slow_spk_count_pred": int(float(row["slow_spk_count_pred"])),
            "fast_segments": int(float(row["fast_segments"])),
            "slow_segments": int(float(row["slow_segments"])),
            "fast_speech_sec": round(float(row["fast_speech"]), 3),
            "slow_speech_sec": round(float(row["slow_speech"]), 3),
            "fast_slow_disagreement_sec": round(float(row["fast_slow_disagreement_sec"]), 3),
            "fast_miss_recovery_rate_eval_only": round(float(row["fast_miss_recovery_rate"]), 3),
            "fast_fa_suppression_rate_eval_only": round(float(row["fast_fa_suppression_rate"]), 3),
        }
    return evidence


def load_memory_evidence(path: Path | None) -> dict[str, dict[str, Any]]:
    evidence = {}
    for row in load_csv(path):
        if "sortformer" not in row.get("model_name", ""):
            continue
        evidence[row["recording_id"]] = {
            "global_speakers": int(float(row["global_speakers"])),
            "assigned_speech_rate": round(float(row["assigned_speech_rate"]), 3),
            "global_identity_accuracy_eval_only": round(float(row["global_identity_accuracy"]), 3),
        }
    return evidence


def load_asr_evidence(path: Path | None) -> dict[tuple[str, int, int], dict[str, Any]]:
    evidence = {}
    for row in load_csv(path):
        key = (row["recording_id"], int(row["window_size"]), int(row["segment_idx"]))
        evidence[key] = {
            "evidence_source": row.get("evidence_source", "asr_transcript"),
            "utterance_count": int(float(row.get("utterance_count") or 0)),
            "char_count": int(float(row.get("char_count") or 0)),
            "has_question": bool(int(float(row.get("has_question") or 0))),
            "has_addressing": bool(int(float(row.get("has_addressing") or 0))),
            "has_self_reference": bool(int(float(row.get("has_self_reference") or 0))),
            "asr_speaker_count": int(float(row.get("asr_speaker_count") or 0)),
            "transcript_excerpt": row.get("transcript_excerpt", ""),
        }
    return evidence


def load_voiceprint_patch_evidence(path: Path | None) -> dict[str, dict[str, Any]]:
    evidence = {}
    for row in load_csv(path):
        evidence[row["patch_id"]] = {
            "top1_global_speaker": row.get("top1_global_speaker", ""),
            "top1_similarity": round(float(row.get("top1_similarity") or 0.0), 4),
            "top2_global_speaker": row.get("top2_global_speaker", ""),
            "top2_similarity": round(float(row.get("top2_similarity") or 0.0), 4),
            "similarity_margin": round(float(row.get("similarity_margin") or 0.0), 4),
            "memory_confidence": round(float(row.get("memory_confidence") or 0.0), 4),
            "confidence_bucket": row.get("confidence_bucket", ""),
            "enrollment_source": row.get("enrollment_source", ""),
        }
    return evidence


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


def has_high_error_flag(row: dict[str, Any]) -> bool:
    return any("high_der" in flag or "high_fa" in flag for flag in row.get("abnormal_flags", []))


def has_slow_quarantine_flag(row: dict[str, Any]) -> bool:
    return any(flag.startswith("slow_high_der") or flag.startswith("slow_high_fa") for flag in row.get("abnormal_flags", []))


def policy_predicate(name: str) -> Callable[[dict[str, Any]], bool]:
    if name == "all":
        return lambda row: True
    if name == "high_risk_quarantine":
        return (
            lambda row: has_high_error_flag(row)
            or has_slow_quarantine_flag(row)
            or row["decision"] == "quarantine"
            or row["patch_type"] == "suppress_fast_candidate"
        )
    if name == "proxy_flagged_window":
        return (
            lambda row: "window_has_deployable_proxy_flags" in row.get("constraints", [])
            or bool(row.get("abnormal_flags"))
        )
    if name == "semantic_label_smoothing":
        return lambda row: row["reason"] in {
            "memory_low_confidence_relabel_deferred",
            "recover_segment_too_short",
            "do_not_suppress_without_strong_evidence",
        }
    if name == "non_accept_review":
        return lambda row: row["decision"] != "accept"
    raise ValueError(f"Unsupported trigger policy: {name}")


def group_windows(
    rows: list[dict[str, Any]],
    trigger_policy: str,
    max_windows: int | None,
    window_offset: int = 0,
    window_ids: set[str] | None = None,
    patch_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    pred = policy_predicate(trigger_policy)
    selected = [row for row in rows if pred(row)]
    if patch_ids is not None:
        selected = [row for row in selected if row["patch_id"] in patch_ids]
    grouped: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
    for row in selected:
        key = (row["recording_id"], int(row["window_size"]), int(row["segment_idx"]))
        grouped.setdefault(key, []).append(row)

    windows = []
    for key, patches in grouped.items():
        window_id = f"{key[0]}:{key[1]}:{key[2]}"
        if window_ids and window_id not in window_ids:
            continue
        patches.sort(key=lambda row: row["decision_index"])
        abnormal_flags = sorted({flag for row in patches for flag in row.get("abnormal_flags", [])})
        windows.append(
            {
                "recording_id": key[0],
                "window_size": key[1],
                "segment_idx": key[2],
                "patch_count": len(patches),
                "abnormal_flags": abnormal_flags,
                "patches": patches,
            }
        )
    windows.sort(key=lambda item: (-item["patch_count"], item["recording_id"], item["segment_idx"]))
    if window_offset:
        windows = windows[window_offset:]
    return windows[:max_windows] if max_windows is not None else windows


def split_window(window: dict[str, Any], max_patches_per_call: int | None) -> list[dict[str, Any]]:
    if not max_patches_per_call or max_patches_per_call <= 0 or window["patch_count"] <= max_patches_per_call:
        item = dict(window)
        item["sub_batch_index"] = 0
        item["sub_batch_count"] = 1
        item["parent_patch_count"] = window["patch_count"]
        return [item]
    patches = list(window["patches"])
    chunks = [patches[idx : idx + max_patches_per_call] for idx in range(0, len(patches), max_patches_per_call)]
    split_items = []
    for idx, chunk in enumerate(chunks):
        item = dict(window)
        item["patches"] = chunk
        item["patch_count"] = len(chunk)
        item["sub_batch_index"] = idx
        item["sub_batch_count"] = len(chunks)
        item["parent_patch_count"] = window["patch_count"]
        split_items.append(item)
    return split_items


def split_windows(windows: list[dict[str, Any]], max_patches_per_call: int | None) -> list[dict[str, Any]]:
    split_items = []
    for window in windows:
        split_items.extend(split_window(window, max_patches_per_call))
    return split_items


def window_id(window: dict[str, Any], include_sub_batch: bool = False) -> str:
    base = f"{window['recording_id']}:{window['window_size']}:{window['segment_idx']}"
    if include_sub_batch and int(window.get("sub_batch_count", 1)) > 1:
        return f"{base}:part{int(window.get('sub_batch_index', 0)) + 1}of{int(window.get('sub_batch_count', 1))}"
    return base


def prompt_payload(
    window: dict[str, Any],
    window_evidence: dict[tuple[str, int, int], dict[str, Any]] | None = None,
    memory_evidence: dict[str, dict[str, Any]] | None = None,
    asr_evidence: dict[tuple[str, int, int], dict[str, Any]] | None = None,
    voiceprint_patch_evidence: dict[str, dict[str, Any]] | None = None,
    include_eval_only: bool = False,
) -> dict[str, Any]:
    key = (window["recording_id"], int(window["window_size"]), int(window["segment_idx"]))
    context: dict[str, Any] = {
        "deployable_window_evidence": {},
        "deployable_memory_evidence": {},
        "deployable_asr_semantic_evidence": {},
    }
    raw_window_evidence = (window_evidence or {}).get(key, {})
    if raw_window_evidence:
        context["deployable_window_evidence"] = {
            k: v for k, v in raw_window_evidence.items() if not k.endswith("_eval_only")
        }
        if include_eval_only:
            context["eval_only_window_evidence"] = {
                k: v for k, v in raw_window_evidence.items() if k.endswith("_eval_only")
            }
    raw_memory_evidence = (memory_evidence or {}).get(window["recording_id"], {})
    if raw_memory_evidence:
        context["deployable_memory_evidence"] = {
            k: v for k, v in raw_memory_evidence.items() if not k.endswith("_eval_only")
        }
        if include_eval_only:
            context["eval_only_memory_evidence"] = {
                k: v for k, v in raw_memory_evidence.items() if k.endswith("_eval_only")
            }
    raw_asr_evidence = (asr_evidence or {}).get(key, {})
    if raw_asr_evidence:
        context["deployable_asr_semantic_evidence"] = raw_asr_evidence

    payload = {
        "window": {
            "recording_id": window["recording_id"],
            "window_size": window["window_size"],
            "segment_idx": window["segment_idx"],
            "patch_count": window["patch_count"],
            "parent_patch_count": window.get("parent_patch_count", window["patch_count"]),
            "sub_batch_index": window.get("sub_batch_index", 0),
            "sub_batch_count": window.get("sub_batch_count", 1),
            "abnormal_flags": window["abnormal_flags"],
        },
        "evidence_context": context,
        "patches": [
            {
                "patch_id": row["patch_id"],
                "source": row["source"],
                "patch_type": row["patch_type"],
                "start": row["start"],
                "end": row["end"],
                "duration": row["duration"],
                "speaker": row["speaker"],
                "matched_source": row.get("matched_source"),
                "matched_speaker": row.get("matched_speaker"),
                "support_ratio": row.get("support_ratio"),
                "rule_decision": row["decision"],
                "rule_reason": row["reason"],
                "rule_confidence": row["confidence"],
                "rule_constraints": row.get("constraints", []),
                "rule_next_action": row.get("next_action"),
                "abnormal_flags": row.get("abnormal_flags", []),
                "voiceprint_evidence": (voiceprint_patch_evidence or {}).get(row["patch_id"], {}),
            }
            for row in window["patches"]
        ],
        "task": (
            "Audit all patches for this one completed window. Return one "
            "window-level decision and one constrained decision per patch."
        )
        + (
            " Use deployable_window_evidence and deployable_memory_evidence when present. "
            "Do not treat eval_only fields as deployable runtime inputs."
            if (
                context["deployable_window_evidence"]
                or context["deployable_memory_evidence"]
                or context["deployable_asr_semantic_evidence"]
                or voiceprint_patch_evidence
            )
            else ""
        ),
    }
    if int(window.get("sub_batch_count", 1)) > 1:
        payload["task"] += (
            " This is a deterministic sub-batch of a larger window. Decide only the supplied patch_ids; "
            "do not infer decisions for patches absent from this sub-batch."
        )
    return payload


def validate_payload(payload: dict[str, Any], window: dict[str, Any]) -> dict[str, Any]:
    if payload.get("window_decision") not in {"clean", "review", "quarantine"}:
        raise ValueError(f"Invalid window_decision: {payload.get('window_decision')!r}")
    patch_ids = {row["patch_id"] for row in window["patches"]}
    decisions = payload.get("patch_decisions")
    if not isinstance(decisions, list):
        raise ValueError("patch_decisions must be a list")
    seen = set()
    for item in decisions:
        patch_id = item.get("patch_id")
        decision = item.get("decision")
        if patch_id not in patch_ids:
            raise ValueError(f"Unknown patch_id from LLM: {patch_id!r}")
        if patch_id in seen:
            raise ValueError(f"Duplicate patch_id from LLM: {patch_id!r}")
        if decision not in {"accept", "reject", "defer", "quarantine"}:
            raise ValueError(f"Invalid patch decision: {decision!r}")
        seen.add(patch_id)
    missing = patch_ids - seen
    if missing:
        raise ValueError(f"Missing patch decisions: {sorted(missing)[:3]}")
    if payload["window_decision"] == "quarantine":
        normalized_decisions = []
        for item in decisions:
            if item["decision"] == "accept":
                item = dict(item)
                item["original_decision"] = "accept"
                item["decision"] = "quarantine"
                item["reason"] = f"window_quarantine_overrode_{item.get('reason', 'accept')}"
                item["next_action"] = "hold_review"
            normalized_decisions.append(item)
        payload["patch_decisions"] = normalized_decisions
    return payload


def call_llm(
    client: OpenAI,
    args: argparse.Namespace,
    window: dict[str, Any],
    window_evidence: dict[tuple[str, int, int], dict[str, Any]],
    memory_evidence: dict[str, dict[str, Any]],
    asr_evidence: dict[tuple[str, int, int], dict[str, Any]],
    voiceprint_patch_evidence: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=args.model,
        temperature=args.temperature,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    prompt_payload(
                        window,
                        window_evidence=window_evidence,
                        memory_evidence=memory_evidence,
                        asr_evidence=asr_evidence,
                        voiceprint_patch_evidence=voiceprint_patch_evidence,
                        include_eval_only=args.include_eval_only_evidence,
                    ),
                    ensure_ascii=False,
                ),
            },
        ],
    )
    content = response.choices[0].message.content or "{}"
    payload = validate_payload(json.loads(extract_json(content)), window)
    usage = getattr(response, "usage", None)
    return {
        "payload": payload,
        "raw_content": content,
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
    }


def evaluate_window_call(
    client: OpenAI,
    args: argparse.Namespace,
    window: dict[str, Any],
    window_evidence: dict[tuple[str, int, int], dict[str, Any]],
    memory_evidence: dict[str, dict[str, Any]],
    asr_evidence: dict[tuple[str, int, int], dict[str, Any]],
    voiceprint_patch_evidence: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    base = {
        "window_id": window_id(window, include_sub_batch=True),
        "parent_window_id": window_id(window),
        "sub_batch_index": window.get("sub_batch_index", 0),
        "sub_batch_count": window.get("sub_batch_count", 1),
        "parent_patch_count": window.get("parent_patch_count", window["patch_count"]),
        "model": args.model,
        "patch_count": window["patch_count"],
        "max_call_attempts": max(1, int(args.max_call_attempts)),
        "retry_backoff_seconds": float(args.retry_backoff_seconds),
    }
    started = time.perf_counter()
    last_exc: Exception | None = None
    for attempt in range(1, max(1, int(args.max_call_attempts)) + 1):
        try:
            result = call_llm(
                client,
                args,
                window,
                window_evidence,
                memory_evidence,
                asr_evidence,
                voiceprint_patch_evidence,
            )
            call_seconds = time.perf_counter() - started
            patch_counts = Counter(item["decision"] for item in result["payload"]["patch_decisions"])
            base.update(
                {
                    "window_decision": result["payload"]["window_decision"],
                    "window_reason": result["payload"].get("window_reason", ""),
                    "confidence": result["payload"].get("confidence", 0.0),
                    "patch_decisions": result["payload"]["patch_decisions"],
                    "patch_decision_counts": " / ".join(f"{key} {patch_counts[key]}" for key in sorted(patch_counts)),
                    "call_seconds": round(call_seconds, 3),
                    "call_attempts": attempt,
                    "prompt_tokens": result.get("prompt_tokens"),
                    "completion_tokens": result.get("completion_tokens"),
                    "total_tokens": result.get("total_tokens"),
                    "raw_content": result["raw_content"],
                    "error": "",
                }
            )
            return base
        except Exception as exc:
            last_exc = exc
            if attempt < max(1, int(args.max_call_attempts)) and float(args.retry_backoff_seconds) > 0:
                time.sleep(float(args.retry_backoff_seconds))
    base.update(
        {
            "window_decision": "error",
            "window_reason": "call_failed",
            "patch_decisions": [],
            "patch_decision_counts": "",
            "call_seconds": round(time.perf_counter() - started, 3),
            "call_attempts": max(1, int(args.max_call_attempts)),
            "prompt_tokens": "",
            "completion_tokens": "",
            "total_tokens": "",
            "raw_content": "",
            "error": repr(last_exc),
        }
    )
    return base


def write_outputs(
    rows: list[dict[str, Any]],
    output_jsonl: Path,
    output_csv: Path,
    summary_output: Path,
    wall_seconds: float | None = None,
    parallel_workers: int = 1,
    skipped_existing_calls: int = 0,
    newly_requested_calls: int | None = None,
) -> None:
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    fieldnames = [
        "window_id",
        "parent_window_id",
        "sub_batch_index",
        "sub_batch_count",
        "model",
        "patch_count",
        "parent_patch_count",
        "window_decision",
        "window_reason",
        "call_seconds",
        "call_attempts",
        "max_call_attempts",
        "retry_backoff_seconds",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "patch_decision_counts",
        "error",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    successful = [row for row in rows if not row.get("error")]
    errors = [row for row in rows if row.get("error")]
    summary = {
        "windows": len({row.get("parent_window_id") or row.get("window_id") for row in rows}),
        "calls": len(rows),
        "successful_windows": len({row.get("parent_window_id") or row.get("window_id") for row in successful}),
        "successful_calls": len(successful),
        "patches": sum(int(row.get("patch_count") or 0) for row in rows),
        "split_calls": sum(1 for row in rows if int(row.get("sub_batch_count") or 1) > 1),
        "window_decision_counts": dict(Counter(row.get("window_decision", "error") for row in rows)),
        "error_count": len(errors),
        "error_types": dict(Counter(str(row.get("error", "")).split("(", 1)[0] for row in errors)),
        "avg_call_seconds": sum(float(row.get("call_seconds") or 0.0) for row in successful) / len(successful) if successful else 0.0,
        "wall_seconds": round(wall_seconds, 3) if wall_seconds is not None else None,
        "parallel_workers": parallel_workers,
        "skipped_existing_calls": skipped_existing_calls,
        "newly_requested_calls": len(rows) - skipped_existing_calls if newly_requested_calls is None else newly_requested_calls,
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in successful),
        "output_jsonl": str(output_jsonl),
        "output_csv": str(output_csv),
    }
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def existing_successful_rows_by_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows = load_jsonl(path)
    successful: dict[str, dict[str, Any]] = {}
    for row in rows:
        call_id = str(row.get("window_id") or "")
        if not call_id:
            continue
        if row.get("error") or row.get("window_decision") in {"", "error", None}:
            continue
        successful.setdefault(call_id, row)
    return successful


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", required=True, type=Path)
    parser.add_argument("--mode", choices=["export", "call"], default="export")
    parser.add_argument(
        "--trigger-policy",
        choices=["all", "high_risk_quarantine", "proxy_flagged_window", "semantic_label_smoothing", "non_accept_review"],
        default="high_risk_quarantine",
    )
    parser.add_argument("--window-id", action="append", default=[], help="Optional recording_id:window_size:segment_idx filter. Can be repeated.")
    parser.add_argument("--window-id-file", type=Path, default=None, help="Optional newline-delimited recording_id:window_size:segment_idx filter.")
    parser.add_argument("--patch-id-file", type=Path, default=None, help="Optional newline-delimited patch_id filter for exact patch-surface replay.")
    parser.add_argument("--model", choices=ALLOWED_MODELS, default="deepseek-v4-flash")
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--window-offset", type=int, default=0, help="Skip this many selected windows after deterministic sorting.")
    parser.add_argument(
        "--max-patches-per-call",
        type=int,
        default=None,
        help="Split selected windows into deterministic sub-batches with at most this many patches per LLM call.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--parallel-workers", type=int, default=1, help="Number of concurrent LLM calls in call mode.")
    parser.add_argument("--max-call-attempts", type=int, default=1, help="Bounded attempts per live API call; failed rows still persist after final attempt.")
    parser.add_argument("--retry-backoff-seconds", type=float, default=0.0, help="Sleep between failed call attempts.")
    parser.add_argument(
        "--skip-existing-output",
        action="store_true",
        help="In call mode, reuse successful rows already present in --output-jsonl and only call missing/failed window ids.",
    )
    parser.add_argument("--window-evidence", type=Path, default=None)
    parser.add_argument("--memory-evidence", type=Path, default=None)
    parser.add_argument("--asr-evidence", type=Path, default=None)
    parser.add_argument("--voiceprint-evidence", type=Path, default=None)
    parser.add_argument("--include-eval-only-evidence", action="store_true")
    parser.add_argument("--output-jsonl", type=Path, default=Path("outputs/llm_window_batch/results.jsonl"))
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--summary-output", type=Path, default=None)
    args = parser.parse_args()

    window_ids = set(args.window_id)
    if args.window_id_file:
        window_ids.update(
            line.strip()
            for line in args.window_id_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    patch_ids = None
    if args.patch_id_file:
        patch_ids = {
            line.strip()
            for line in args.patch_id_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

    windows = group_windows(
        load_jsonl(args.decisions),
        args.trigger_policy,
        args.max_windows,
        window_offset=args.window_offset,
        window_ids=window_ids or None,
        patch_ids=patch_ids,
    )
    windows = split_windows(windows, args.max_patches_per_call)
    window_evidence = load_window_evidence(args.window_evidence)
    memory_evidence = load_memory_evidence(args.memory_evidence)
    asr_evidence = load_asr_evidence(args.asr_evidence)
    voiceprint_patch_evidence = load_voiceprint_patch_evidence(args.voiceprint_evidence)
    if not windows:
        raise SystemExit("No windows selected for batch LLM audit")

    output_csv = args.output_csv or args.output_jsonl.with_suffix(".csv")
    summary_output = args.summary_output or args.output_jsonl.with_name(args.output_jsonl.stem + "_summary.json")

    if args.mode == "export":
        args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.output_jsonl.open("w", encoding="utf-8") as f:
            for window in windows:
                f.write(
                    json.dumps(
                        {
                            "window_id": window_id(window, include_sub_batch=True),
                            "parent_window_id": window_id(window),
                            "sub_batch_index": window.get("sub_batch_index", 0),
                            "sub_batch_count": window.get("sub_batch_count", 1),
                            "patch_count": window["patch_count"],
                            "parent_patch_count": window.get("parent_patch_count", window["patch_count"]),
                            "model": args.model,
                            "messages": [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {
                                    "role": "user",
                                    "content": json.dumps(
                                        prompt_payload(
                                            window,
                                            window_evidence=window_evidence,
                                            memory_evidence=memory_evidence,
                                            asr_evidence=asr_evidence,
                                            voiceprint_patch_evidence=voiceprint_patch_evidence,
                                            include_eval_only=args.include_eval_only_evidence,
                                        ),
                                        ensure_ascii=False,
                                    ),
                                },
                            ],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        print(f"Exported {len(windows)} window-batch prompts to {args.output_jsonl}")
        return

    existing_success = existing_successful_rows_by_id(args.output_jsonl) if args.skip_existing_output else {}
    target_ids = [window_id(window, include_sub_batch=True) for window in windows]
    pending_windows = [window for window in windows if window_id(window, include_sub_batch=True) not in existing_success]
    skipped_existing_calls = len(windows) - len(pending_windows)

    wall_started = time.perf_counter()
    new_output_rows = []
    if not pending_windows:
        new_output_rows = []
    elif args.parallel_workers <= 1:
        client = make_client(args)
        new_output_rows = [
            evaluate_window_call(
                client,
                args,
                window,
                window_evidence,
                memory_evidence,
                asr_evidence,
                voiceprint_patch_evidence,
            )
            for window in pending_windows
        ]
    else:
        def worker(window: dict[str, Any]) -> dict[str, Any]:
            return evaluate_window_call(
                make_client(args),
                args,
                window,
                window_evidence,
                memory_evidence,
                asr_evidence,
                voiceprint_patch_evidence,
            )

        with ThreadPoolExecutor(max_workers=args.parallel_workers) as executor:
            futures = {executor.submit(worker, window): idx for idx, window in enumerate(pending_windows)}
            completed: list[tuple[int, dict[str, Any]]] = []
            for future in as_completed(futures):
                completed.append((futures[future], future.result()))
        new_output_rows = [row for _, row in sorted(completed, key=lambda item: item[0])]
    wall_seconds = time.perf_counter() - wall_started
    new_rows_by_id = {str(row.get("window_id")): row for row in new_output_rows}
    output_rows = []
    for call_id in target_ids:
        if call_id in existing_success:
            output_rows.append(existing_success[call_id])
        elif call_id in new_rows_by_id:
            output_rows.append(new_rows_by_id[call_id])

    write_outputs(
        output_rows,
        args.output_jsonl,
        output_csv,
        summary_output,
        wall_seconds=wall_seconds,
        parallel_workers=max(1, args.parallel_workers),
        skipped_existing_calls=skipped_existing_calls,
        newly_requested_calls=len(pending_windows),
    )
    print(f"LLM window-batch eval model={args.model} windows={len(output_rows)}")
    print(f"skipped_existing_calls={skipped_existing_calls} newly_requested_calls={len(pending_windows)}")
    print(f"jsonl={args.output_jsonl}")
    print(f"csv={output_csv}")
    print(f"summary={summary_output}")


if __name__ == "__main__":
    main()
