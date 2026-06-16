#!/usr/bin/env python3
"""Build the protocol artifact for true held-out selector validation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPLIT = Path("data/selector_true_heldout_split.csv")
FIXED_POLICY = "ratio_le_0.65_else_uncovered"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "n/a"


def split_rows_by_role(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped = {"train": [], "dev": [], "true_heldout": []}
    for row in rows:
        role = row.get("split", row.get("role", "")).strip()
        if role in grouped:
            grouped[role].append(row)
    return grouped


def build_protocol(root: Path, split_file: Path, min_new_recordings: int) -> dict[str, Any]:
    holdout = read_json(root / "outputs/recover_selector_split_120/recording_holdout_summary.json")
    per_recording = read_csv(root / "outputs/realtime_contract_recording_stability_120/per_recording.csv")
    candidate_scan = read_json(root / "outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.json")
    split_path = split_file if split_file.is_absolute() else root / split_file
    split_rows = read_csv(split_path)
    grouped_split = split_rows_by_role(split_rows)
    dev_recordings = sorted({row["group"] for row in per_recording if row.get("group")})
    true_heldout_recordings = sorted({row.get("recording_id", row.get("group", "")) for row in grouped_split["true_heldout"] if row.get("recording_id", row.get("group", ""))})
    train_recordings = sorted({row.get("recording_id", row.get("group", "")) for row in grouped_split["train"] if row.get("recording_id", row.get("group", ""))})
    overlap_with_dev = sorted(set(true_heldout_recordings) & set(dev_recordings))
    overlap_with_train = sorted(set(true_heldout_recordings) & set(train_recordings))
    split_has_required_columns = False
    required_columns = ["recording_id", "split", "source_manifest", "audio_path"]
    if split_rows:
        split_has_required_columns = all(column in split_rows[0] for column in required_columns)
    missing_audio = [
        row.get("audio_path", "")
        for row in grouped_split["true_heldout"]
        if row.get("audio_path") and not Path(row["audio_path"]).expanduser().exists()
    ]

    blockers = []
    if not split_path.exists():
        blockers.append("missing_sealed_split_file")
    if split_path.exists() and not split_has_required_columns:
        blockers.append("sealed_split_missing_required_columns")
    if len(true_heldout_recordings) < min_new_recordings:
        blockers.append("not_enough_true_heldout_recordings")
    if overlap_with_dev:
        blockers.append("true_heldout_overlaps_development_recordings")
    if overlap_with_train:
        blockers.append("true_heldout_overlaps_train_recordings")
    if missing_audio:
        blockers.append("true_heldout_audio_missing")

    status = "ready_to_run_fixed_policy" if not blockers else "needs_new_recording_split"
    gates = [
        {
            "gate_id": "sealed_split_exists",
            "status": "pass" if split_path.exists() else "blocked",
            "evidence": str(split_file),
            "requirement": "Provide a sealed split CSV before running any metric claim.",
        },
        {
            "gate_id": "true_heldout_not_in_dev",
            "status": "pass" if split_path.exists() and not overlap_with_dev else "blocked",
            "evidence": ", ".join(overlap_with_dev) if overlap_with_dev else "no overlap detected" if split_path.exists() else "split missing",
            "requirement": "No true-heldout recording can appear in the 120-window development/selector pool.",
        },
        {
            "gate_id": "fixed_policy_before_scoring",
            "status": "pass",
            "evidence": FIXED_POLICY,
            "requirement": "Use the frozen selector policy selected before true-heldout scoring.",
        },
        {
            "gate_id": "runtime_feature_surface",
            "status": "pass",
            "evidence": "fast_speech / slow_speech / speaker counts / recover patch deployable features",
            "requirement": "Selector inputs must not include DER, GT speaker count, oracle labels, or support from held-out scoring.",
        },
        {
            "gate_id": "metric_success_threshold",
            "status": "pending",
            "evidence": f"target delta > 0 vs Fast on at least {min_new_recordings} recordings",
            "requirement": "Weighted DER below Fast, with Miss/FA/Conf and arrival latency reported per recording.",
        },
    ]
    return {
        "runtime_contract": "selector_true_heldout_protocol_no_metric_claim",
        "protocol_status": status,
        "fixed_policy": FIXED_POLICY,
        "split_file": str(split_file),
        "required_split_columns": required_columns,
        "minimum_true_heldout_recordings": min_new_recordings,
        "development_evidence": {
            "dev_recordings": dev_recordings,
            "dev_recording_count": len(dev_recordings),
            "dev_windows": sum(int(row.get("windows") or 0) for row in per_recording),
            "recording_holdout_splits": holdout.get("splits"),
            "recording_holdout_positive_splits": holdout.get("positive_splits"),
            "recording_holdout_weighted_der": holdout.get("weighted_heldout_der"),
            "recording_holdout_fast_der": holdout.get("weighted_fast_der"),
            "recording_holdout_delta_vs_fast": holdout.get("weighted_delta_vs_fast"),
            "development_scope": "dev_only_validation_same_sampled_pool",
        },
        "sealed_split_state": {
            "exists": split_path.exists(),
            "rows": len(split_rows),
            "split_has_required_columns": split_has_required_columns,
            "train_recordings": train_recordings,
            "true_heldout_recordings": true_heldout_recordings,
            "true_heldout_recording_count": len(true_heldout_recordings),
            "overlap_with_dev_recordings": overlap_with_dev,
            "overlap_with_train_recordings": overlap_with_train,
            "missing_audio_count": len(missing_audio),
            "missing_audio": missing_audio[:20],
        },
        "candidate_scan": {
            "runtime_contract": candidate_scan.get("runtime_contract", ""),
            "status": candidate_scan.get("status", "not_built"),
            "local_recordings": candidate_scan.get("summary", {}).get("local_recordings", 0),
            "eligible_true_heldout_recordings": candidate_scan.get("summary", {}).get("eligible_true_heldout_recordings", 0),
            "missing_new_recordings_to_minimum": candidate_scan.get("summary", {}).get("missing_new_recordings_to_minimum", min_new_recordings),
            "recommendation": candidate_scan.get("recommendation", ""),
        },
        "blockers": blockers,
        "success_gates": gates,
        "run_plan": [
            "Create data/selector_true_heldout_split.csv with new recording ids and audio paths.",
            "Run Fast/Slow window extraction on the sealed true-heldout recordings without changing selector thresholds.",
            f"Apply fixed selector policy {FIXED_POLICY} to materialized timeline variants.",
            "Report weighted DER/Miss/FA/Conf and rule-writeback arrival latency per recording.",
            "Promote selector claim only if weighted DER beats Fast and leakage checks pass.",
        ],
        "no_metric_claim": True,
    }


def write_gate_csv(protocol: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["gate_id", "status", "requirement", "evidence"])
        writer.writeheader()
        writer.writerows(protocol["success_gates"])


def write_markdown(protocol: dict[str, Any], path: Path) -> None:
    dev = protocol["development_evidence"]
    split = protocol["sealed_split_state"]
    candidate = protocol.get("candidate_scan", {})
    lines = [
        "# Selector True-Heldout Protocol",
        "",
        f"- Runtime contract: `{protocol['runtime_contract']}`",
        f"- Protocol status: `{protocol['protocol_status']}`",
        f"- Fixed policy: `{protocol['fixed_policy']}`",
        f"- Split file: `{protocol['split_file']}`",
        f"- Minimum true-heldout recordings: `{protocol['minimum_true_heldout_recordings']}`",
        f"- No metric claim: `{protocol['no_metric_claim']}`",
        "",
        "## Current Development Evidence",
        "",
        f"- Development recordings: `{dev['dev_recording_count']}`",
        f"- Development windows: `{dev['dev_windows']}`",
        f"- Recording holdout: `{dev['recording_holdout_positive_splits']}/{dev['recording_holdout_splits']}` positive",
        f"- Weighted DER: `{pct(dev['recording_holdout_weighted_der'])}` vs Fast `{pct(dev['recording_holdout_fast_der'])}`; delta `{pct(dev['recording_holdout_delta_vs_fast'])}`",
        f"- Scope: `{dev['development_scope']}`",
        "",
        "## Sealed Split State",
        "",
        f"- Exists: `{split['exists']}`",
        f"- Rows: `{split['rows']}`",
        f"- Required columns present: `{split['split_has_required_columns']}`",
        f"- True-heldout recordings: `{split['true_heldout_recording_count']}`",
        f"- Overlap with development recordings: `{len(split['overlap_with_dev_recordings'])}`",
        f"- Missing audio: `{split['missing_audio_count']}`",
        f"- Blockers: `{', '.join(protocol['blockers']) if protocol['blockers'] else 'none'}`",
        "",
        "## Candidate Scan",
        "",
        f"- Scan status: `{candidate.get('status', 'not_built')}`",
        f"- Local recordings: `{candidate.get('local_recordings', 0)}`",
        f"- Eligible true-heldout recordings: `{candidate.get('eligible_true_heldout_recordings', 0)}`",
        f"- Missing new recordings to minimum: `{candidate.get('missing_new_recordings_to_minimum', protocol['minimum_true_heldout_recordings'])}`",
        f"- Recommendation: {candidate.get('recommendation', '')}",
        "",
        "## Gates",
        "",
        "| Gate | Status | Requirement | Evidence |",
        "|---|---|---|---|",
    ]
    for gate in protocol["success_gates"]:
        requirement = str(gate["requirement"]).replace("|", "/")
        evidence = str(gate["evidence"]).replace("|", "/")
        lines.append(f"| `{gate['gate_id']}` | `{gate['status']}` | {requirement} | {evidence} |")
    lines.extend(["", "## Run Plan", ""])
    for idx, item in enumerate(protocol["run_plan"], start=1):
        lines.append(f"{idx}. {item}")
    lines.extend(
        [
            "",
            "## Development Recordings Already Used",
            "",
            ", ".join(f"`{recording}`" for recording in dev["dev_recordings"]),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--min-new-recordings", type=int, default=8)
    parser.add_argument("--output-json", type=Path, default=Path("outputs/research_progress_snapshot/selector_true_heldout_protocol.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/research_progress_snapshot/selector_true_heldout_protocol.md"))
    parser.add_argument("--output-gates-csv", type=Path, default=Path("outputs/research_progress_snapshot/selector_true_heldout_protocol_gates.csv"))
    args = parser.parse_args()

    protocol = build_protocol(ROOT, args.split_file, args.min_new_recordings)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(protocol, args.output_md)
    write_gate_csv(protocol, args.output_gates_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_gates_csv}")
    print(json.dumps({"status": protocol["protocol_status"], "blockers": protocol["blockers"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
