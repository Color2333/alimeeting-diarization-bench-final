#!/usr/bin/env python3
"""Build an end-to-end runtime replay manifest for staged diarization artifacts."""

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
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_RUNTIME_TOKENS = (
    "der",
    "gt",
    "oracle",
    "miss_rate",
    "fa_rate",
    "conf_rate",
    "spk_count_gt",
    "gt_speech",
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_sec(value: object) -> str:
    try:
        return f"{float(value):.2f}s"
    except (TypeError, ValueError):
        return "n/a"


def runtime_audit_check(audit: dict[str, Any], artifact: str) -> dict[str, Any]:
    for check in audit.get("checks", []):
        if check.get("artifact") == artifact:
            return check
    return {}


def contains_forbidden_runtime_token(row: dict[str, Any]) -> bool:
    encoded = json.dumps(row, ensure_ascii=False).lower()
    return any(token in encoded for token in FORBIDDEN_RUNTIME_TOKENS)


def build_manifest(root: Path) -> dict[str, Any]:
    timeline = read_json(root / "outputs/system_timeline/summary.json")
    audit = read_json(root / "outputs/runtime_evidence_audit/runtime_evidence_audit.json")
    omni = read_json(root / "outputs/omni_guard/omni_acoustic_fusion_summary.json")
    voiceprint = read_json(root / "outputs/voiceprint_patch_evidence/clean_candidate_120_summary.json")

    rows = [
        {
            "stage": "fast_provisional",
            "agent": "Fast Agent / Sortformer",
            "arrival_avg": fmt_sec(timeline.get("fast_avg_delay_sec")),
            "arrival_p95": fmt_sec(timeline.get("fast_p95_delay_sec")),
            "writeback_right": "timeline_first_output",
            "runtime_action": "emit provisional speaker timeline",
            "runtime_surface": "runtime",
            "source_artifacts": [
                "outputs/system_timeline/system_timeline.csv",
                "outputs/system_timeline/summary.json",
            ],
            "validation_checks": ["four_stage_timeline", "runtime_audit_pass"],
            "audit_artifact": "four-stage system timeline",
            "evidence": "first user-visible timeline stage",
        },
        {
            "stage": "rule_writeback",
            "agent": "Slow Acoustic + Rule Agent",
            "arrival_avg": fmt_sec(timeline.get("rule_writeback_avg_delay_sec")),
            "arrival_p95": fmt_sec(timeline.get("rule_writeback_p95_delay_sec")),
            "writeback_right": "bounded_timeline_writeback",
            "runtime_action": f"write bounded corrections from {int(timeline.get('rule_writeback_patches', 0))} candidate patches",
            "runtime_surface": "runtime",
            "source_artifacts": [
                "outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.csv",
                "outputs/system_timeline/system_timeline.csv",
            ],
            "validation_checks": ["runtime_audit_pass", "four_stage_timeline"],
            "audit_artifact": "runtime-safe policy-agent decisions",
            "evidence": "runtime-safe policy decisions plus staged arrival timing",
        },
        {
            "stage": "llm_guard",
            "agent": "LLM Guard / deepseek-v4-flash",
            "arrival_avg": fmt_sec(timeline.get("llm_guard_avg_delay_sec")),
            "arrival_p95": fmt_sec(timeline.get("llm_guard_p95_delay_sec")),
            "writeback_right": "block_or_quarantine_only",
            "runtime_action": (
                f"guard {int(timeline.get('llm_guard_windows', 0))} proxy windows / "
                f"{int(timeline.get('llm_guard_patches', 0))} patches; harmful accept "
                f"{int(timeline.get('llm_guard_harmful_accepts', 0))}"
            ),
            "runtime_surface": "runtime",
            "source_artifacts": [
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_prompts.jsonl",
                "outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_safety_summary.json",
            ],
            "validation_checks": ["runtime_audit_pass", "split20_live_top3_guard"],
            "audit_artifact": "runtime-safe proxy window-batch prompts",
            "evidence": "LLM can block/quarantine high-risk windows, not generate timestamps",
        },
        {
            "stage": "llm_review_signal",
            "agent": "LLM Review / qwen3.6-flash audit",
            "arrival_avg": fmt_sec(timeline.get("llm_review_avg_delay_sec")),
            "arrival_p95": fmt_sec(timeline.get("llm_review_p95_delay_sec")),
            "writeback_right": "memory_protection_only",
            "runtime_action": (
                f"{int(timeline.get('llm_review_cases', 0))} review cases; timeline writeback blocks "
                f"{int(timeline.get('llm_review_blocks_timeline_writeback', 0))}; memory blocks "
                f"{int(timeline.get('llm_review_blocks_memory_update', 0))}"
            ),
            "runtime_surface": "runtime",
            "source_artifacts": [
                "outputs/timeline_review_audit/llm_review_signal_timeline_audit.csv",
                "outputs/timeline_review_audit/llm_review_signal_timeline_audit_summary.json",
            ],
            "validation_checks": ["review_signal_no_timeline_block", "pareto_has_review_signal"],
            "audit_artifact": "LLM review-signal timeline audit",
            "evidence": "review blocks memory updates without overriding timeline writeback",
        },
        {
            "stage": "omni_label",
            "agent": "Omni Realtime Risk Probe",
            "arrival_avg": fmt_sec(omni.get("avg_flash_call_seconds")),
            "arrival_p95": fmt_sec(omni.get("p95_flash_call_seconds")),
            "writeback_right": "label_and_quarantine_priority_only",
            "runtime_action": (
                f"{int(omni.get('windows', 0))} windows; high sentinel recall "
                f"{omni.get('high_sentinel_recall', 'n/a')}; clean review FP "
                f"{omni.get('clean_review_priority_fp', 'n/a')}"
            ),
            "runtime_surface": "runtime",
            "source_artifacts": [
                "outputs/omni_guard/omni_acoustic_fusion.csv",
                "outputs/omni_guard/omni_acoustic_fusion_summary.json",
            ],
            "validation_checks": ["omni_fusion_label_only_contract", "runtime_audit_pass"],
            "audit_artifact": "Omni fusion no-writeback contract",
            "evidence": "Omni contributes labels or quarantine priority, never timeline writeback",
        },
        {
            "stage": "memory_gate",
            "agent": "Speaker Memory Gate",
            "arrival_avg": "non_blocking",
            "arrival_p95": "non_blocking",
            "writeback_right": "speaker_memory_update_after_gate",
            "runtime_action": (
                f"{int(voiceprint.get('with_voiceprint', 0))}/{int(voiceprint.get('clean_patches', 0))} "
                f"clean patches have voiceprint evidence; LLM candidates {int(voiceprint.get('llm_candidates', 0))}"
            ),
            "runtime_surface": "runtime_candidate_gate",
            "source_artifacts": [
                "outputs/voiceprint_patch_evidence/clean_candidate_120_summary.json",
                "outputs/voiceprint_patch_evidence/clean_candidate_120_voiceprint.csv",
            ],
            "validation_checks": ["claims_manifest_contract", "snapshot_contract"],
            "audit_artifact": "voiceprint_rule_handles_clean_high",
            "evidence": "speaker memory updates are gated after high-confidence voiceprint evidence",
        },
    ]

    for row in rows:
        audit_check = runtime_audit_check(audit, row["audit_artifact"])
        row["runtime_audit_status"] = audit_check.get("status", "claim_manifest_only")
        row["forbidden_runtime_token_scan"] = "fail" if contains_forbidden_runtime_token(row) else "pass"

    failures = [
        row["stage"]
        for row in rows
        if row["runtime_audit_status"] not in {"pass", "claim_manifest_only"}
        or row["forbidden_runtime_token_scan"] != "pass"
    ]

    return {
        "runtime_contract": "end_to_end_runtime_replay_manifest_no_eval_context",
        "rows": rows,
        "summary": {
            "stage_count": len(rows),
            "runtime_pass_rows": sum(1 for row in rows if row["runtime_audit_status"] == "pass"),
            "claim_manifest_only_rows": sum(1 for row in rows if row["runtime_audit_status"] == "claim_manifest_only"),
            "writeback_rows": [
                row["stage"]
                for row in rows
                if row["writeback_right"] in {"timeline_first_output", "bounded_timeline_writeback"}
            ],
            "failed_rows": failures,
        },
    }


def write_markdown(manifest: dict[str, Any], path: Path) -> None:
    lines = [
        "# Runtime Replay Manifest",
        "",
        f"- Runtime contract: `{manifest['runtime_contract']}`",
        f"- Stages: `{manifest['summary']['stage_count']}`",
        f"- Runtime-audit pass rows: `{manifest['summary']['runtime_pass_rows']}`",
        f"- Claim-manifest-only rows: `{manifest['summary']['claim_manifest_only_rows']}`",
        f"- Failed rows: `{len(manifest['summary']['failed_rows'])}`",
        f"- Timeline writeback rows: `{', '.join(manifest['summary']['writeback_rows'])}`",
        "",
        "| Stage | Agent | Arrival avg | Arrival P95 | Writeback right | Runtime action | Runtime audit | Sources | Validation |",
        "|---|---|---:|---:|---|---|---|---|---|",
    ]
    for row in manifest["rows"]:
        sources = "<br>".join(f"`{source}`" for source in row["source_artifacts"])
        checks = ", ".join(f"`{check}`" for check in row["validation_checks"])
        action = str(row["runtime_action"]).replace("|", "/")
        lines.append(
            f"| `{row['stage']}` | {row['agent']} | {row['arrival_avg']} | {row['arrival_p95']} | "
            f"`{row['writeback_right']}` | {action} | `{row['runtime_audit_status']}` / "
            f"`{row['forbidden_runtime_token_scan']}` | {sources} | {checks} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=Path("outputs/research_progress_snapshot/runtime_replay_manifest.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/research_progress_snapshot/runtime_replay_manifest.md"))
    args = parser.parse_args()

    manifest = build_manifest(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(manifest, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
