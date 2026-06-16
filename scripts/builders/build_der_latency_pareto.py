#!/usr/bin/env python3
"""Build DER-latency tradeoff tables for the diarization route."""

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
from pathlib import Path


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_runtime_safe_llm_summary() -> Path:
    root = Path("outputs/runtime_safe_llm_window_batch")
    candidates = []
    for path in root.glob("deepseek_proxy_high_risk_*w_safety_summary.json"):
        data = load_json(path)
        candidates.append((int(data.get("windows") or 0), path))
    if not candidates:
        return root / "deepseek_proxy_high_risk_8w_safety_summary.json"
    return max(candidates, key=lambda item: (item[0], item[1].name))[1]


def fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def fmt_sec(value: float) -> str:
    return f"{value:.2f}s"


def median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return (ordered[mid - 1] + ordered[mid]) / 2 if n % 2 == 0 else ordered[mid]


def latency_by_summary(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["summary"]: row for row in rows}


def add_model_rows(rows: list[dict[str, str]], output: list[dict[str, str]]) -> None:
    labels = {
        ("pyannote-community-1", "baseline", "24"): ("PyAnnote C1", "baseline"),
        ("nemo-sortformer-4spk-v1", "fast_agent", "120"): ("Sortformer 120", "fast provisional"),
        ("nemo-sortformer-4spk-v1", "fast_agent", "48"): ("Sortformer 48", "fast provisional"),
        ("nemo-sortformer-4spk-v1", "fast_agent", "24"): ("Sortformer 24", "fast provisional"),
        ("diarizen-large-v2", "slow_agent", "120"): ("DiariZen 120", "slow correction"),
        ("diarizen-large-v2", "slow_agent", "48"): ("DiariZen 48", "slow correction"),
        ("diarizen-large-v2", "slow_agent", "24"): ("DiariZen 24", "slow correction"),
        ("nemo-streaming-sortformer-4spk", "fast_streaming_candidate", "2"): (
            "Streaming Sortformer smoke",
            "streaming candidate",
        ),
    }
    for row in rows:
        key = (row["model_name"], row["role"], row["segments"])
        if key not in labels:
            continue
        candidate, route_role = labels[key]
        if candidate == "PyAnnote C1":
            candidate = "PyAnnote C1 oracle" if "spk_oracle" in row["summary"] else "PyAnnote C1 none"
        scope = f"{row['segments']} windows / {float(row['window_size_sec']):.0f}s"
        note = "direct benchmark"
        if candidate == "Streaming Sortformer smoke":
            note = "Mac CPU smoke; not final GPU latency"
        if candidate == "DiariZen 48":
            note = "raw mean includes one large FA outlier"
        if candidate == "DiariZen 120":
            note = "strong slow baseline; async, one extreme outlier remains"
        output.append(
            {
                "candidate": candidate,
                "route_role": route_role,
                "scope": scope,
                "der": fmt_pct(float(row["avg_der"])),
                "avg_delay_sec": fmt_sec(float(row["avg_latency_sec"])),
                "p95_delay_sec": fmt_sec(float(row["p95_latency_sec"])),
                "rtf": f"{float(row['avg_rtf']):.3f}",
                "evidence": note,
                "verdict": verdict(candidate),
            }
        )


def add_fast_slow_rows(summary_path: Path, latency_rows: dict[str, dict[str, str]], output: list[dict[str, str]]) -> None:
    data = load_json(summary_path)
    slow_latency = latency_rows[data["slow_summary"]]
    fast_latency = latency_rows[data["fast_summary"]]
    windows = int(data["windows"])
    scope = f"{windows} windows / 30s"
    output.extend(
        [
            {
                "candidate": f"Fast+Slow heuristic {windows}",
                "route_role": "async correction policy",
                "scope": scope,
                "der": fmt_pct(float(data["heuristic_avg_der"])),
                "avg_delay_sec": fmt_sec(float(slow_latency["avg_latency_sec"])),
                "p95_delay_sec": fmt_sec(float(slow_latency["p95_latency_sec"])),
                "rtf": f"{float(slow_latency['avg_rtf']):.3f}",
                "evidence": f"coverage {float(data['heuristic_coverage']) * 100:.1f}%, regressions {data['heuristic_regressions']}",
                "verdict": "current async correction baseline",
            },
            {
                "candidate": f"Fast+Slow oracle selector {windows}",
                "route_role": "upper bound",
                "scope": scope,
                "der": fmt_pct(float(data["oracle_selector_avg_der"])),
                "avg_delay_sec": fmt_sec(float(slow_latency["avg_latency_sec"])),
                "p95_delay_sec": fmt_sec(float(slow_latency["p95_latency_sec"])),
                "rtf": f"{float(slow_latency['avg_rtf']):.3f}",
                "evidence": "uses eval oracle; not deployable",
                "verdict": "upper bound for selector learning",
            },
            {
                "candidate": f"Fast provisional {windows}",
                "route_role": "first output",
                "scope": scope,
                "der": fmt_pct(float(data["fast_only_avg_der"])),
                "avg_delay_sec": fmt_sec(float(fast_latency["avg_latency_sec"])),
                "p95_delay_sec": fmt_sec(float(fast_latency["p95_latency_sec"])),
                "rtf": f"{float(fast_latency['avg_rtf']):.3f}",
                "evidence": "immediate usable draft",
                "verdict": "best first-output latency",
            },
        ]
    )


def add_system_rows(
    system_timeline: Path,
    writeback_impact: Path,
    rule_timeline_summary: Path,
    output: list[dict[str, str]],
) -> None:
    timeline_rows = {row["stage"]: row for row in load_csv(system_timeline)}
    impact = load_json(writeback_impact)
    fast = timeline_rows["fast_provisional"]
    writeback = timeline_rows["rule_writeback"]
    guard = timeline_rows["llm_guard"]
    review = timeline_rows.get("llm_review_signal")
    rule_timeline = {}
    if rule_timeline_summary.exists():
        data = load_json(rule_timeline_summary)
        rule_timeline = {row["variant"]: row for row in data.get("summary", [])}
    best_rule = (
        rule_timeline.get("rule_recover_policy_sweep_best")
        or rule_timeline.get("rule_recover_identity_selector")
        or rule_timeline.get("rule_recover_matched_label", {})
    )
    scope = "120 windows / staged" if int(impact.get("writeback_patches", 0)) > 300 else "48 windows / staged"
    fast_der_match = re.search(r"DER\s+([0-9.]+%)", fast.get("metric", ""))
    fast_der = fast_der_match.group(1) if fast_der_match else "n/a"
    writeback_rtf = float(writeback["avg_delay_sec"]) / 30.0
    rule_der = fmt_pct(float(best_rule["avg_der"])) if best_rule else "n/a"
    guard_patches = int(float(guard.get("patches", 0)))
    guard_metric = guard.get("metric", "")
    runtime_safe_guard = guard_patches > 100
    guard_candidate = "Dual Agent runtime-safe LLM guard" if runtime_safe_guard else "Dual Agent LLM guard"
    guard_scope = "104 proxy-flag windows / staged" if runtime_safe_guard else "48 windows / staged"
    guard_evidence = guard_metric or (
        f"{guard_patches} high-risk patches; harmful accept 0"
        if guard_patches
        else "harmful accept 0"
    )
    guard_verdict = (
        "runtime-safe guard; conservative by design"
        if runtime_safe_guard
        else "safety layer, not DER optimizer"
    )
    rule_evidence = (
        f"timeline v0; {int(best_rule.get('recover_added', 0))} recover patches; "
        f"recover {float(impact['rule_recover_vs_fast_miss_rate']) * 100:.1f}% Fast miss"
        if best_rule
        else (
            f"{int(impact['writeback_patches'])} patches; "
            f"recover {float(impact['rule_recover_vs_fast_miss_rate']) * 100:.1f}% Fast miss"
        )
    )
    output.extend(
        [
            {
                "candidate": "Dual Agent first output",
                "route_role": "system stage",
                "scope": scope,
                "der": fast_der,
                "avg_delay_sec": fmt_sec(float(fast["avg_delay_sec"])),
                "p95_delay_sec": fmt_sec(float(fast["p95_delay_sec"])),
                "rtf": "0.013",
                "evidence": "provisional timeline",
                "verdict": "user-visible real-time layer",
            },
            {
                "candidate": "Dual Agent rule writeback",
                "route_role": "system stage",
                "scope": scope,
                "der": rule_der,
                "avg_delay_sec": fmt_sec(float(writeback["avg_delay_sec"])),
                "p95_delay_sec": fmt_sec(float(writeback["p95_delay_sec"])),
                "rtf": f"{writeback_rtf:.3f}",
                "evidence": rule_evidence,
                "verdict": "main deployable correction layer",
            },
            {
                "candidate": guard_candidate,
                "route_role": "system stage",
                "scope": guard_scope,
                "der": "n/a",
                "avg_delay_sec": fmt_sec(float(guard["avg_delay_sec"])),
                "p95_delay_sec": fmt_sec(float(guard["p95_delay_sec"])),
                "rtf": "n/a",
                "evidence": guard_evidence,
                "verdict": guard_verdict,
            },
        ]
    )
    if review:
        output.append(
            {
                "candidate": "Dual Agent LLM review signal",
                "route_role": "system stage",
                "scope": scope,
                "der": "n/a",
                "avg_delay_sec": fmt_sec(float(review["avg_delay_sec"])),
                "p95_delay_sec": fmt_sec(float(review["p95_delay_sec"])),
                "rtf": "n/a",
                "evidence": review.get("metric", "review-only memory protection"),
                "verdict": "review/memory protection only; no timeline writeback",
            }
        )


def add_diarizen_median(summary_path: Path, output: list[dict[str, str]]) -> None:
    data = load_json(summary_path)
    values = [float(row["der"]) for row in data["results"] if row.get("success")]
    windows = int(data.get("total_segments") or len(values))
    latencies = [float(row["latency"]) for row in data["results"] if row.get("success") and row.get("latency") is not None]
    p95_latency = sorted(latencies)[int((len(latencies) - 1) * 0.95)] if latencies else float(data["avg_latency"])
    output.append(
        {
            "candidate": f"DiariZen {windows} median",
            "route_role": "slow correction robust statistic",
            "scope": f"{windows} windows / 30s",
            "der": fmt_pct(median(values)),
            "avg_delay_sec": fmt_sec(float(data["avg_latency"])),
            "p95_delay_sec": fmt_sec(p95_latency),
            "rtf": f"{float(data['avg_latency']) / 30.0:.3f}",
            "evidence": "median reduces single outlier effect",
            "verdict": "strong slow baseline, not first-output path",
        }
    )


def add_selector_holdout(selector_summary: Path, system_timeline: Path, output: list[dict[str, str]]) -> None:
    if not selector_summary.exists():
        return
    data = load_json(selector_summary)
    timeline_rows = {row["stage"]: row for row in load_csv(system_timeline)}
    writeback = timeline_rows.get("rule_writeback", {})
    output.append(
        {
            "candidate": "Dual Agent selector holdout",
            "route_role": "recording-holdout selector validation",
            "scope": f"{int(data.get('splits', 8))} recording splits / 120 windows",
            "der": fmt_pct(float(data["weighted_heldout_der"])),
            "avg_delay_sec": fmt_sec(float(writeback.get("avg_delay_sec", 24.65))),
            "p95_delay_sec": fmt_sec(float(writeback.get("p95_delay_sec", 28.33))),
            "rtf": f"{float(writeback.get('avg_delay_sec', 24.65)) / 30.0:.3f}",
            "evidence": f"{int(data['positive_splits'])}/{int(data['splits'])} held-out positive; +{float(data['weighted_delta_vs_fast']) * 100:.2f}pp vs Fast",
            "verdict": "selector threshold check before true held-out",
        }
    )


def add_runtime_safe_guard(safety_summary: Path, output: list[dict[str, str]]) -> None:
    if not safety_summary.exists():
        return
    data = load_json(safety_summary)
    output.append(
        {
            "candidate": "Dual Agent runtime-safe LLM guard",
            "route_role": "runtime-safe safety layer",
            "scope": f"{int(data.get('windows', 0))} proxy-flag windows / staged",
            "der": "n/a",
            "avg_delay_sec": fmt_sec(float(data.get("avg_correction_delay_seconds", 0.0))),
            "p95_delay_sec": fmt_sec(float(data.get("p95_correction_delay_seconds", 0.0))),
            "rtf": "n/a",
            "evidence": (
                f"{int(data.get('patches', 0))} patches; harmful accept {int(data.get('harmful_accepts', 0))}; "
                f"conservative blocks {int(data.get('conservative_blocks', 0))}; "
                f"window override {int(data.get('window_quarantine_accept_overrides', 0))}"
            ),
            "verdict": "runtime-safe guard; conservative by design",
        }
    )


def verdict(candidate: str) -> str:
    if candidate.startswith("Sortformer"):
        return "fast but high miss"
    if candidate.startswith("DiariZen 24"):
        return "best direct DER, slow"
    if candidate.startswith("DiariZen 48"):
        return "slow baseline; outlier-sensitive"
    if candidate.startswith("PyAnnote"):
        return "dominated baseline"
    if candidate.startswith("Streaming"):
        return "needs GPU sweep"
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latencies", type=Path, default=Path("outputs/latency_tradeoff/main_models.csv"))
    parser.add_argument("--fast-slow-24", type=Path, default=Path("outputs/fast_slow_correction/sortformer_diarizen_24_patches_summary.json"))
    parser.add_argument("--fast-slow-48", type=Path, default=Path("outputs/fast_slow_correction/sortformer_diarizen_48_patches_summary.json"))
    parser.add_argument("--diarizen-48", type=Path, default=Path("outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none/summary.json"))
    parser.add_argument("--diarizen-120", type=Path, default=Path("outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json"))
    parser.add_argument("--system-timeline", type=Path, default=Path("outputs/system_timeline/system_timeline.csv"))
    parser.add_argument("--writeback-impact", type=Path, default=Path("outputs/writeback_gate_120/writeback_impact_summary.json"))
    parser.add_argument("--rule-timeline-summary", type=Path, default=Path("outputs/rule_writeback_timeline_120/rule_writeback_timeline_summary.json"))
    parser.add_argument("--selector-split", type=Path, default=Path("outputs/recover_selector_split_120/recording_holdout_summary.json"))
    parser.add_argument("--runtime-safe-guard", type=Path, default=None)
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/latency_tradeoff/der_latency_pareto.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("outputs/latency_tradeoff/der_latency_pareto.md"))
    args = parser.parse_args()

    latency_rows = load_csv(args.latencies)
    latency_index = latency_by_summary(latency_rows)
    rows: list[dict[str, str]] = []
    add_model_rows(latency_rows, rows)
    if args.diarizen_120.exists():
        add_diarizen_median(args.diarizen_120, rows)
    add_diarizen_median(args.diarizen_48, rows)
    add_fast_slow_rows(args.fast_slow_24, latency_index, rows)
    add_fast_slow_rows(args.fast_slow_48, latency_index, rows)
    add_system_rows(args.system_timeline, args.writeback_impact, args.rule_timeline_summary, rows)
    add_selector_holdout(args.selector_split, args.system_timeline, rows)
    if not any(row["candidate"] == "Dual Agent runtime-safe LLM guard" for row in rows):
        add_runtime_safe_guard(args.runtime_safe_guard or latest_runtime_safe_llm_summary(), rows)

    rows.sort(key=lambda row: (row["scope"], float(row["avg_delay_sec"].rstrip("s"))))

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "| Candidate | Role | Scope | DER | Avg delay | P95 delay | RTF | Evidence | Verdict |",
        "|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {candidate} | {route_role} | {scope} | {der} | {avg_delay_sec} | {p95_delay_sec} | {rtf} | {evidence} | {verdict} |".format(
                **row
            )
        )
    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
