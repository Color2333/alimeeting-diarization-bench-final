#!/usr/bin/env python3
"""Diagnose why the current selector is not yet robust enough for promotion."""

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
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Selector Robustness Diagnosis",
        "",
        f"- Runtime contract: `{payload['runtime_contract']}`",
        f"- Status: `{payload['status']}`",
        f"- Diagnosis: `{payload['diagnosis']}`",
        f"- Base selector positive recordings: `{payload['base_selector']['positive_recordings_vs_slow']}/{payload['base_selector']['recordings']}`",
        f"- Base selector holdout positive splits: `{payload['base_selector']['holdout_positive_splits_vs_slow']}/{payload['base_selector']['holdout_splits']}`",
        f"- Rare runtime selected windows: `{payload['rare_overlay']['runtime_selected_windows']}`",
        f"- Rare runtime max recording share: `{payload['rare_overlay']['runtime_max_selected_recording_share']:.1%}`",
        f"- Rare holdout positive splits: `{payload['rare_overlay']['holdout_positive_splits_vs_base']}/{payload['rare_overlay']['holdout_splits']}`",
        "",
        "## Blocking Reasons",
        "",
    ]
    for reason in payload["blocking_reasons"]:
        lines.append(f"- `{reason}`")
    lines.extend(
        [
            "",
            "## Next Optimization Direction",
            "",
        ]
    )
    for item in payload["next_optimization_targets"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Rare Runtime Selected Windows",
            "",
            "| Window | Recording | Base DER | Overlay DER | Delta |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in payload["rare_overlay"]["runtime_selected_window_details"]:
        lines.append(
            "| `{window_id}` | `{recording_id}` | {base:.2%} | {overlay:.2%} | {delta:.2f}pp |".format(
                window_id=row["window_id"],
                recording_id=row["recording_id"],
                base=as_float(row.get("base_der")),
                overlay=as_float(row.get("overlay_der")),
                delta=as_float(row.get("delta_vs_base_pp")),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def recording_from_window_id(window_id: str) -> str:
    return window_id.split(":", 1)[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-selector-validation", type=Path, default=Path("outputs/system_selector_validation/guarded_slow_selector_validation.json"))
    parser.add_argument("--rare-selector-search", type=Path, default=Path("outputs/rare_selector_search/rare_selector_policy_search.json"))
    parser.add_argument("--selector-policy-holdout", type=Path, default=Path("outputs/system_selector_search/system_selector_policy_holdout.csv"))
    parser.add_argument("--rare-policy-holdout", type=Path, default=Path("outputs/rare_selector_search/rare_selector_policy_holdout.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/selector_robustness_diagnosis"))
    args = parser.parse_args()

    base = read_json(args.base_selector_validation)
    rare = read_json(args.rare_selector_search)
    selector_holdout = read_csv(args.selector_policy_holdout)
    rare_holdout = read_csv(args.rare_policy_holdout)

    per_recording = base.get("per_recording", [])
    base_positive_recordings = [row for row in per_recording if row.get("beats_slow") is True]
    base_holdout = base.get("recording_holdout", [])
    base_holdout_positive = [row for row in base_holdout if row.get("heldout_beats_slow") is True]

    runtime_policy = rare.get("runtime_policy", {})
    selected = []
    for row in runtime_policy.get("selected_window_details", []):
        window_id = str(row.get("window_id", ""))
        selected.append({**row, "recording_id": recording_from_window_id(window_id)})
    selected_by_recording = Counter(row["recording_id"] for row in selected)
    max_selected_share = max(selected_by_recording.values(), default=0) / len(selected) if selected else 0.0
    total_rare_delta = sum(as_float(row.get("delta_vs_base_pp")) for row in selected)
    max_window_delta_share = (
        max([as_float(row.get("delta_vs_base_pp")) for row in selected], default=0.0) / total_rare_delta
        if total_rare_delta > 0
        else 0.0
    )

    rare_holdout_positive = [row for row in rare_holdout if str(row.get("heldout_beats_base")).lower() == "true"]
    rare_holdout_losses = [
        row
        for row in rare_holdout
        if as_float(row.get("heldout_delta_vs_base_pp")) < -1e-9
    ]
    rare_zero_selection_splits = [
        row for row in rare_holdout if int(as_float(row.get("heldout_selected_windows"))) == 0
    ]

    blocking_reasons = []
    if len(base_holdout_positive) < len(base_holdout):
        blocking_reasons.append("base_selector_gain_not_recording_stable")
    if base.get("bootstrap", {}).get("delta_ci_low") == 0:
        blocking_reasons.append("base_selector_bootstrap_lower_bound_not_positive")
    if len(rare_holdout_positive) < len(rare_holdout):
        blocking_reasons.append("rare_overlay_holdout_not_positive")
    if rare_zero_selection_splits:
        blocking_reasons.append("rare_overlay_often_selects_no_heldout_windows")
    if rare_holdout_losses:
        blocking_reasons.append("rare_overlay_has_negative_heldout_split")
    if max_selected_share >= 0.5 or max_window_delta_share >= 0.5:
        blocking_reasons.append("rare_overlay_development_gain_concentrated")

    status = "promotion_ready" if not blocking_reasons else "diagnosed_not_robust"
    payload = {
        "runtime_contract": "selector_robustness_diagnosis_no_live_calls_no_new_scoring",
        "status": status,
        "diagnosis": "selector_gain_is_real_on_development_pool_but_not_stable_across_recordings",
        "base_selector": {
            "status": base.get("status"),
            "recordings": len(per_recording),
            "positive_recordings_vs_slow": len(base_positive_recordings),
            "positive_recording_ids": [row.get("recording_id") for row in base_positive_recordings],
            "holdout_splits": len(base_holdout),
            "holdout_positive_splits_vs_slow": len(base_holdout_positive),
            "bootstrap": base.get("bootstrap", {}),
            "holdout_summary": base.get("recording_holdout_summary", {}),
        },
        "selector_policy_search": {
            "holdout_splits": len(selector_holdout),
            "positive_splits_vs_slow": sum(1 for row in selector_holdout if str(row.get("heldout_beats_slow")).lower() == "true"),
            "negative_split_ids": [
                row.get("heldout_recording_id")
                for row in selector_holdout
                if as_float(row.get("heldout_delta_vs_slow_pp")) < -1e-9
            ],
        },
        "rare_overlay": {
            "status": rare.get("status"),
            "runtime_selected_windows": len(selected),
            "runtime_selected_recording_counts": dict(selected_by_recording),
            "runtime_max_selected_recording_share": max_selected_share,
            "runtime_max_window_delta_share": max_window_delta_share,
            "runtime_selected_window_details": selected,
            "holdout_splits": len(rare_holdout),
            "holdout_positive_splits_vs_base": len(rare_holdout_positive),
            "holdout_zero_selection_splits": len(rare_zero_selection_splits),
            "holdout_negative_splits": [
                {
                    "heldout_recording_id": row.get("heldout_recording_id"),
                    "heldout_delta_vs_base_pp": as_float(row.get("heldout_delta_vs_base_pp")),
                    "heldout_selected_windows": int(as_float(row.get("heldout_selected_windows"))),
                    "selected_policy_id": row.get("selected_policy_id"),
                }
                for row in rare_holdout_losses
            ],
            "runtime_bootstrap": rare.get("runtime_bootstrap", {}),
            "holdout_summary": rare.get("holdout_summary", {}),
        },
        "blocking_reasons": blocking_reasons,
        "next_optimization_targets": [
            "prefer features that fire on multiple recordings rather than sparse single-recording gains",
            "require leave-one-recording selected-window coverage before promoting a rare overlay",
            "treat additional threshold tuning on the same 120-window pool as low-value unless it improves holdout splits",
            "prioritize calibrated VAD/speaker-activity features or new held-out recordings for stronger selector evidence",
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "selector_robustness_diagnosis.json"
    md_path = args.output_dir / "selector_robustness_diagnosis.md"
    write_json(json_path, payload)
    write_markdown(md_path, payload)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "status={status} base_holdout={base_pos}/{base_total} rare_holdout={rare_pos}/{rare_total} reasons={reasons}".format(
            status=status,
            base_pos=len(base_holdout_positive),
            base_total=len(base_holdout),
            rare_pos=len(rare_holdout_positive),
            rare_total=len(rare_holdout),
            reasons=len(blocking_reasons),
        )
    )


if __name__ == "__main__":
    main()
