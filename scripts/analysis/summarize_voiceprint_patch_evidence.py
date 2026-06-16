#!/usr/bin/env python3
"""Summarize patch-level voiceprint evidence and writeback-gate impact."""

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


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Voiceprint Patch Evidence Summary",
        "",
        "| Rows | OK | Missing | High | Medium | Low | Avg confidence | Avg margin | P95 margin | LLM candidates |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        (
            "| {rows} | {ok_rows} | {missing_rows} | {high_rows} | {medium_rows} | {low_rows} | "
            "{avg_memory_confidence:.3f} | {avg_similarity_margin:.3f} | {p95_similarity_margin:.3f} | "
            "{llm_writeback_candidates} |"
        ).format(**summary),
        "",
        "## Gate Blockers",
        "",
        "| Blocker | Semantic patches |",
        "|---|---:|",
    ]
    for blocker, count in summary["semantic_blockers"].items():
        lines.append(f"| {blocker} | {count} |")
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Patch-level top1/top2/margin evidence is now a real deployable input, not only a schema example.",
            "- The current gate still finds zero LLM writeback candidates because semantic patches are mostly abnormal, short, low-support, or low/medium voiceprint confidence.",
            "- Voiceprint high is only a necessary condition for future writeback; it does not grant direct timeline writeback rights.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voiceprint-evidence", type=Path, default=Path("outputs/voiceprint_patch_evidence/real_semantic_all_patch_evidence.csv"))
    parser.add_argument("--gate-summary", type=Path, default=Path("outputs/writeback_gate/gate_summary.json"))
    parser.add_argument("--output-json", type=Path, default=Path("outputs/voiceprint_patch_evidence/patch_evidence_summary.json"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/voiceprint_patch_evidence/patch_evidence_summary.md"))
    args = parser.parse_args()

    rows = load_csv(args.voiceprint_evidence)
    gate = load_json(args.gate_summary)
    buckets = Counter(row.get("confidence_bucket") or "missing" for row in rows)
    statuses = Counter(row.get("evidence_status") or "missing" for row in rows)
    ok_rows = [row for row in rows if row.get("evidence_status") == "ok"]
    margins = [float(row["similarity_margin"]) for row in ok_rows if row.get("similarity_margin")]
    confidences = [float(row["memory_confidence"]) for row in ok_rows if row.get("memory_confidence")]
    category_counts = gate.get("category_counts", {})
    semantic_blockers = gate.get("semantic_blocker_counts", {})

    summary = {
        "voiceprint_evidence": str(args.voiceprint_evidence),
        "gate_summary": str(args.gate_summary),
        "rows": len(rows),
        "ok_rows": len(ok_rows),
        "missing_rows": len(rows) - len(ok_rows),
        "status_counts": dict(statuses),
        "bucket_counts": dict(buckets),
        "high_rows": buckets.get("high", 0),
        "medium_rows": buckets.get("medium", 0),
        "low_rows": buckets.get("low", 0),
        "avg_memory_confidence": mean(confidences),
        "p50_memory_confidence": percentile(confidences, 0.50),
        "p95_memory_confidence": percentile(confidences, 0.95),
        "avg_similarity_margin": mean(margins),
        "p50_similarity_margin": percentile(margins, 0.50),
        "p95_similarity_margin": percentile(margins, 0.95),
        "llm_writeback_candidates": int(category_counts.get("llm_writeback_candidate", 0)),
        "llm_defer_review": int(category_counts.get("llm_defer_review", 0)),
        "semantic_patches": int(gate.get("semantic_patches", 0)),
        "semantic_blockers": semantic_blockers,
        "runtime_contract": "deployable_patch_voiceprint_top1_top2_margin_joined_to_writeback_gate",
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, args.output_md)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
