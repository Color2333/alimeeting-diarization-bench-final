#!/usr/bin/env python3
"""Diagnose true-heldout readiness for selector promotion.

This is a no-metric-claim readiness artifact. It combines the candidate scan,
sealed split validation, true-heldout protocol, and promotion gate into one
small report so development-pool wins are not confused with generalized wins.
"""

from __future__ import annotations

# Keep final modules import-compatible when executed with python -m.
import sys as _sys
from pathlib import Path as _Path
_SCRIPT_ROOT = _Path(__file__).resolve().parent
_REPO_ROOT = _Path(__file__).resolve().parents[2]
for _candidate in [_REPO_ROOT, _SCRIPT_ROOT, *_SCRIPT_ROOT.iterdir()]:
    if _candidate.is_dir():
        _value = str(_candidate)
        if _value not in _sys.path:
            _sys.path.insert(0, _value)

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def gate(gate_id: str, passed: bool, evidence: Any) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "pass" if passed else "blocked",
        "evidence": evidence,
    }


def split_exists(split_validation: dict[str, Any], protocol: dict[str, Any]) -> bool:
    summary = split_validation.get("summary", {})
    sealed_state = protocol.get("sealed_split_state", {})
    return bool(summary.get("split_exists") or sealed_state.get("exists"))


def determine_status(
    split_validation: dict[str, Any],
    protocol: dict[str, Any],
    minimum: int,
    true_heldout_recordings: int,
    eligible_local_candidates: int,
) -> str:
    split_status = split_validation.get("status")
    protocol_status = protocol.get("protocol_status")
    exists = split_exists(split_validation, protocol)
    ready_statuses = {"pass", "ready_for_selector_true_heldout_scoring", "ready_for_true_heldout_scoring"}

    if split_status in ready_statuses and true_heldout_recordings >= minimum:
        return "ready_for_true_heldout_scoring"
    if not exists and eligible_local_candidates < minimum:
        return "blocked_missing_sealed_split_and_new_recordings"
    if not exists:
        return "blocked_missing_sealed_split"
    if protocol_status == "needs_new_recording_split" or split_status:
        return "blocked_invalid_sealed_split"
    return "blocked_unknown_true_heldout_state"


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# True-Heldout Readiness",
        "",
        f"- Status: `{payload['status']}`",
        f"- Split file: `{summary['split_file']}`",
        f"- True-heldout recordings: `{summary['true_heldout_recordings']}/{summary['minimum_true_heldout_recordings']}`",
        f"- Eligible local candidates: `{summary['eligible_local_candidates']}`",
        f"- Missing new recordings: `{summary['missing_new_recordings_to_minimum']}`",
        f"- Promotion gate: `{summary['promotion_gate_status']}` (`{summary['promotion_status']}`)",
        f"- No metric claim: `{summary['no_metric_claim']}`",
        "",
        "## Gates",
        "",
        "| Status | Gate | Evidence |",
        "|---|---|---|",
    ]
    for row in payload["gates"]:
        lines.append(f"| `{row['status']}` | `{row['gate_id']}` | `{json.dumps(row['evidence'], sort_keys=True)}` |")
    lines.extend(
        [
            "",
            "## Next Actions",
            "",
        ]
    )
    for action in payload["recommended_next_actions"]:
        lines.append(f"- `{action}`")
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This report is readiness-only: it does not run DER scoring or support a generalized metric claim.",
            "- Development-pool baseline wins remain useful, but promotion needs a sealed true-heldout split with new recordings.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-scan",
        type=Path,
        default=Path("outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.json"),
    )
    parser.add_argument(
        "--split-validation",
        type=Path,
        default=Path("outputs/research_progress_snapshot/selector_true_heldout_split_validation.json"),
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("outputs/research_progress_snapshot/selector_true_heldout_protocol.json"),
    )
    parser.add_argument(
        "--promotion-gate",
        type=Path,
        default=Path("outputs/system_promotion_gate/system_promotion_gate.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/true_heldout_readiness"))
    args = parser.parse_args()

    candidate_scan = read_json(args.candidate_scan)
    split_validation = read_json(args.split_validation)
    protocol = read_json(args.protocol)
    promotion_gate = read_json(args.promotion_gate)

    scan_summary = candidate_scan.get("summary", {})
    split_summary = split_validation.get("summary", {})
    sealed_state = protocol.get("sealed_split_state", {})
    minimum = as_int(
        split_validation.get("minimum_true_heldout_recordings")
        or candidate_scan.get("minimum_true_heldout_recordings")
        or protocol.get("minimum_true_heldout_recordings"),
        default=8,
    )
    true_heldout_recordings = max(
        as_int(split_summary.get("true_heldout_recordings")),
        as_int(sealed_state.get("true_heldout_recording_count")),
    )
    eligible_local_candidates = max(
        as_int(split_summary.get("eligible_local_candidates")),
        as_int(scan_summary.get("eligible_true_heldout_recordings")),
        as_int(candidate_scan.get("candidate_scan", {}).get("eligible_true_heldout_recordings")),
    )
    missing_new_recordings = max(
        0,
        minimum - max(true_heldout_recordings, eligible_local_candidates),
        as_int(split_summary.get("missing_new_recordings_to_minimum")),
        as_int(scan_summary.get("missing_new_recordings_to_minimum")),
    )
    missing_required_columns = as_int(split_summary.get("missing_required_columns"))
    overlap_with_development = as_int(split_summary.get("overlap_with_development"))
    exists = split_exists(split_validation, protocol)
    no_metric_claim = all(
        [
            candidate_scan.get("summary", {}).get("no_metric_claim", candidate_scan.get("no_metric_claim", True)) is True,
            split_validation.get("summary", {}).get("no_metric_claim", split_validation.get("no_metric_claim", True)) is True,
            protocol.get("no_metric_claim", True) is True,
        ]
    )

    status = determine_status(
        split_validation=split_validation,
        protocol=protocol,
        minimum=minimum,
        true_heldout_recordings=true_heldout_recordings,
        eligible_local_candidates=eligible_local_candidates,
    )

    gates = [
        gate("sealed_split_exists", exists, split_validation.get("split_file") or protocol.get("split_file")),
        gate(
            "required_columns_present",
            exists and missing_required_columns == 0,
            {
                "missing_required_columns": missing_required_columns,
                "required_columns": split_validation.get("required_columns") or protocol.get("required_split_columns"),
            },
        ),
        gate("true_heldout_count", true_heldout_recordings >= minimum, f"{true_heldout_recordings}/{minimum}"),
        gate(
            "no_development_overlap",
            exists and overlap_with_development == 0,
            {
                "overlap_with_development": overlap_with_development,
                "overlap_recordings": split_validation.get("overlap_with_development_recordings", []),
            },
        ),
        gate(
            "local_candidate_pool_available",
            eligible_local_candidates >= minimum,
            {
                "eligible_local_candidates": eligible_local_candidates,
                "minimum_true_heldout_recordings": minimum,
            },
        ),
        gate("no_metric_claim", no_metric_claim, "readiness-only; no DER or support scoring"),
    ]

    payload = {
        "runtime_contract": "true_heldout_readiness_no_metric_claim",
        "status": status,
        "summary": {
            "split_file": split_validation.get("split_file") or protocol.get("split_file"),
            "minimum_true_heldout_recordings": minimum,
            "split_exists": exists,
            "true_heldout_recordings": true_heldout_recordings,
            "eligible_local_candidates": eligible_local_candidates,
            "missing_new_recordings_to_minimum": missing_new_recordings,
            "development_recordings": as_int(scan_summary.get("development_recordings"))
            or as_int(protocol.get("development_evidence", {}).get("dev_recording_count")),
            "local_dev_overlap": as_int(scan_summary.get("local_dev_overlap")),
            "promotion_gate_status": promotion_gate.get("status"),
            "promotion_status": promotion_gate.get("promotion_status"),
            "candidate_scan_status": candidate_scan.get("status"),
            "split_validation_status": split_validation.get("status"),
            "protocol_status": protocol.get("protocol_status"),
            "no_metric_claim": no_metric_claim,
        },
        "gates": gates,
        "blockers": [
            row["gate_id"]
            for row in gates
            if row["status"] == "blocked" and row["gate_id"] != "local_candidate_pool_available"
        ]
        + (["not_enough_new_local_recordings"] if eligible_local_candidates < minimum else []),
        "recommended_next_actions": [
            f"add_{missing_new_recordings}_new_recordings_outside_development_pool",
            "create_data_selector_true_heldout_split_csv",
            "run_fast_slow_extraction_without_changing_selector_thresholds",
            "score_frozen_selector_on_true_heldout",
        ],
        "inputs": {
            "candidate_scan": str(args.candidate_scan),
            "split_validation": str(args.split_validation),
            "protocol": str(args.protocol),
            "promotion_gate": str(args.promotion_gate),
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "true_heldout_readiness.json"
    md_path = args.output_dir / "true_heldout_readiness.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "status={status} split_exists={split_exists} true_heldout={heldout}/{minimum} missing_new={missing}".format(
            status=payload["status"],
            split_exists=payload["summary"]["split_exists"],
            heldout=payload["summary"]["true_heldout_recordings"],
            minimum=payload["summary"]["minimum_true_heldout_recordings"],
            missing=payload["summary"]["missing_new_recordings_to_minimum"],
        )
    )


if __name__ == "__main__":
    main()
