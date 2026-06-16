#!/usr/bin/env python3
"""Run the offline realtime diarization system regression loop.

This command refreshes the runtime-safe feature/search artifacts, reruns the
all-cached system demo, refreshes headroom analysis, then executes the system
self-check. It performs no live model/API calls.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run_step(name: str, command: list[str], cwd: Path) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    duration = time.time() - started
    stdout_tail = "\n".join(proc.stdout.splitlines()[-20:])
    stderr_tail = "\n".join(proc.stderr.splitlines()[-20:])
    return {
        "name": name,
        "command": command,
        "returncode": proc.returncode,
        "duration_sec": duration,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "status": "pass" if proc.returncode == 0 else "fail",
    }


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    metrics = payload.get("metrics_summary", {})
    self_check = payload.get("self_check_summary", {})
    lines = [
        "# Realtime System Regression",
        "",
        f"- Status: `{payload['status']}`",
        f"- Steps: `{payload['passed_steps']}/{payload['total_steps']}` passed",
        f"- Duration: `{payload['duration_sec']:.2f}s`",
        f"- Final DER: `{metrics.get('final_der_pct', 'n/a')}`",
        f"- Best-baseline margin: `{metrics.get('delta_vs_best_baseline_pp', 'n/a')}` pp",
        f"- Beats all baselines: `{metrics.get('beats_all_baselines', 'n/a')}`",
        f"- Self-check: `{self_check.get('status', 'missing')}` (`fail={self_check.get('fail_count', 'n/a')}`, `warn={self_check.get('warn_count', 'n/a')}`)",
        "",
        "## Steps",
        "",
        "| Status | Step | Duration | Command |",
        "|---|---|---:|---|",
    ]
    for row in payload["steps"]:
        lines.append(
            "| `{status}` | `{name}` | {duration:.2f}s | `{command}` |".format(
                status=row["status"],
                name=row["name"],
                duration=row["duration_sec"],
                command=" ".join(row["command"]),
            )
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This regression is an offline replay over cached Fast/Slow outputs and derived runtime-safe artifacts.",
            "- A `warn` self-check status is acceptable while selector robustness remains below the promotion gate; any `fail` should block metric claims.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_outputs() -> tuple[dict[str, Any], dict[str, Any]]:
    metrics_path = ROOT / "outputs/system_demo/all_cached_recordings/metrics.json"
    self_check_path = ROOT / "outputs/system_self_check/realtime_system_self_check.json"
    metrics = read_json(metrics_path)
    self_check = read_json(self_check_path)
    m = metrics.get("metrics", {})
    metrics_summary = {
        "path": str(metrics_path),
        "variant": metrics.get("variant"),
        "evaluation_status": metrics.get("evaluation_status"),
        "windows_processed": metrics.get("windows_processed"),
        "recordings_processed": metrics.get("recordings_processed"),
        "final_der": m.get("final_der"),
        "final_der_pct": f"{float(m['final_der']) * 100:.2f}%" if m.get("final_der") is not None else None,
        "best_baseline": metrics.get("best_baseline"),
        "delta_vs_best_baseline_pp": m.get("der_delta_vs_best_baseline_pp"),
        "beats_all_baselines": metrics.get("baseline_win_summary", {}).get("beats_all_baselines"),
        "selector_validation_status": metrics.get("selector_validation", {}).get("status"),
        "selector_search_status": metrics.get("selector_policy_search", {}).get("status"),
        "rare_selector_status": read_json(
            ROOT / "outputs/rare_selector_search/rare_selector_policy_search.json"
        ).get("status"),
        "slow_sanitization_status": metrics.get("slow_sanitization_search", {}).get("status"),
        "speaker_track_sanitization_status": read_json(
            ROOT / "outputs/speaker_track_sanitization_search/speaker_track_sanitization_policy_search.json"
        ).get("status"),
        "audio_guided_sanitization_status": read_json(
            ROOT / "outputs/audio_guided_sanitization_search/audio_guided_sanitization_policy_search.json"
        ).get("status"),
        "audio_boundary_adjustment_status": read_json(
            ROOT / "outputs/audio_boundary_adjustment_search/audio_boundary_adjustment_policy_search.json"
        ).get("status"),
        "timeline_integrity_status": read_json(
            ROOT / "outputs/timeline_integrity/final_timeline_integrity.json"
        ).get("status"),
        "clipped_baseline_audit_status": read_json(
            ROOT / "outputs/clipped_baseline_audit/clipped_baseline_audit.json"
        ).get("status"),
        "baseline_leaderboard_audit_status": read_json(
            ROOT / "outputs/baseline_leaderboard_audit/baseline_leaderboard_audit.json"
        ).get("status"),
        "runtime_overlay_contributions_status": read_json(
            ROOT / "outputs/runtime_overlay_contributions/runtime_overlay_contributions.json"
        ).get("status"),
        "selector_robustness_diagnosis_status": read_json(
            ROOT / "outputs/selector_robustness_diagnosis/selector_robustness_diagnosis.json"
        ).get("status"),
        "batch_smoke_status": read_json(
            ROOT / "outputs/realtime_batch/smoke/batch_summary.json"
        ).get("status"),
        "batch_all_cached_status": read_json(
            ROOT / "outputs/realtime_batch/all_cached/batch_summary.json"
        ).get("status"),
        "batch_consistency_status": read_json(
            ROOT / "outputs/realtime_batch/audit/realtime_batch_consistency.json"
        ).get("status"),
        "recording_level_stability_status": read_json(
            ROOT / "outputs/recording_level_stability/recording_level_stability.json"
        ).get("status"),
        "recording_balanced_overlay_search_status": read_json(
            ROOT / "outputs/recording_balanced_overlay_search/recording_balanced_overlay_search.json"
        ).get("status"),
        "recording_context_overlay_search_status": read_json(
            ROOT / "outputs/recording_context_overlay_search/recording_balanced_overlay_search.json"
        ).get("status"),
        "external_candidate_surface_search_status": read_json(
            ROOT / "outputs/external_candidate_surface_search/external_candidate_surface_search.json"
        ).get("status"),
        "external_candidate_source_inventory_status": read_json(
            ROOT / "outputs/external_candidate_source_inventory/external_candidate_source_inventory.json"
        ).get("status"),
        "external_candidate_reproduction_plan_status": read_json(
            ROOT / "outputs/external_candidate_reproduction_plan/external_candidate_reproduction_plan.json"
        ).get("status"),
        "recording_stability_blockers_status": read_json(
            ROOT / "outputs/recording_stability_blockers/recording_stability_blockers.json"
        ).get("status"),
        "next_experiment_queue_contract": read_json(
            ROOT / "outputs/research_progress_snapshot/next_experiment_queue.json"
        ).get("runtime_contract"),
    }
    self_check_summary = {
        "path": str(self_check_path),
        "status": self_check.get("status"),
        "pass_count": self_check.get("pass_count"),
        "warn_count": self_check.get("warn_count"),
        "fail_count": self_check.get("fail_count"),
    }
    promotion_gate = read_json(ROOT / "outputs/system_promotion_gate/system_promotion_gate.json")
    metrics_summary["promotion_gate_status"] = promotion_gate.get("status")
    metrics_summary["promotion_status"] = promotion_gate.get("promotion_status")
    metrics_summary["true_heldout_readiness_status"] = read_json(
        ROOT / "outputs/true_heldout_readiness/true_heldout_readiness.json"
    ).get("status")
    return metrics_summary, self_check_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/system_regression"))
    parser.add_argument("--skip-slow-sanitization", action="store_true", help="Skip the slower sanitizer search when only refreshing main metrics.")
    parser.add_argument("--skip-speaker-track-sanitization", action="store_true", help="Skip the speaker-track sanitizer search.")
    parser.add_argument("--skip-rare-selector", action="store_true", help="Skip rare selector overlay search.")
    parser.add_argument("--skip-audio-guided-sanitization", action="store_true", help="Skip audio-guided sanitizer search.")
    parser.add_argument("--skip-audio-boundary-adjustment", action="store_true", help="Skip audio-guided boundary adjustment search.")
    args = parser.parse_args()

    python = sys.executable
    steps: list[tuple[str, list[str]]] = [
        ("audio_window_features", [python, "scripts/build_audio_window_features.py"]),
        ("selector_validation", [python, "scripts/validate_guarded_slow_selector.py"]),
        ("selector_policy_search", [python, "scripts/search_system_selector_policies.py"]),
    ]
    if not args.skip_rare_selector:
        steps.append(("rare_selector_overlay_search", [python, "scripts/search_rare_selector_overlay_policies.py"]))
    if not args.skip_slow_sanitization:
        steps.append(("slow_sanitization_search", [python, "scripts/search_slow_sanitization_policies.py"]))
    if not args.skip_speaker_track_sanitization:
        steps.append(("speaker_track_sanitization_search", [python, "scripts/search_speaker_track_sanitization_policies.py"]))
    if not args.skip_audio_guided_sanitization:
        steps.append(("audio_guided_sanitization_search", [python, "scripts/search_audio_guided_sanitization_policies.py"]))
    if not args.skip_audio_boundary_adjustment:
        steps.append(("audio_boundary_adjustment_search", [python, "scripts/search_audio_boundary_adjustment_policies.py"]))
    steps.extend(
        [
            (
                "all_cached_system_demo",
                [
                    python,
                    "scripts/run_realtime_diarization_system.py",
                    "--all-cached-recordings",
                    "--output-dir",
                    "outputs/system_demo/all_cached_recordings",
                ],
            ),
            (
                "realtime_batch_smoke",
                [
                    python,
                    "scripts/run_realtime_batch.py",
                    "--recording-ids",
                    "R8003_M8001,R8009_M8019",
                    "--output-dir",
                    "outputs/realtime_batch/smoke",
                ],
            ),
            (
                "realtime_batch_all_cached",
                [
                    python,
                    "scripts/run_realtime_batch.py",
                    "--all-cached-recordings",
                    "--output-dir",
                    "outputs/realtime_batch/all_cached",
                ],
            ),
            ("realtime_batch_consistency", [python, "scripts/audit_realtime_batch_consistency.py"]),
            ("timeline_integrity", [python, "scripts/check_timeline_integrity.py"]),
            ("clipped_baseline_audit", [python, "scripts/audit_clipped_baselines.py"]),
            ("baseline_leaderboard_audit", [python, "scripts/audit_baseline_leaderboard.py"]),
            ("runtime_overlay_contributions", [python, "scripts/audit_runtime_overlay_contributions.py"]),
            ("recording_level_stability", [python, "scripts/audit_recording_level_stability.py"]),
            ("recording_balanced_overlay_search", [python, "scripts/search_recording_balanced_overlays.py"]),
            (
                "recording_context_overlay_search",
                [
                    python,
                    "scripts/search_recording_balanced_overlays.py",
                    "--previous-window-context",
                    "--output-dir",
                    "outputs/recording_context_overlay_search",
                ],
            ),
            ("external_candidate_surface_search", [python, "scripts/search_external_candidate_surfaces.py"]),
            ("external_candidate_source_inventory", [python, "scripts/audit_external_candidate_source_inventory.py"]),
            ("external_candidate_reproduction_plan", [python, "scripts/build_external_candidate_reproduction_plan.py"]),
            ("baseline_headroom_audit", [python, "scripts/audit_baseline_headroom.py"]),
            ("system_promotion_gate", [python, "scripts/build_system_promotion_gate.py"]),
            ("true_heldout_readiness", [python, "scripts/diagnose_true_heldout_readiness.py"]),
            ("selector_robustness_diagnosis", [python, "scripts/diagnose_selector_robustness.py"]),
            ("recording_stability_blockers", [python, "scripts/diagnose_recording_stability_blockers.py"]),
            ("next_experiment_queue", [python, "scripts/build_research_next_experiment_queue.py"]),
            ("system_self_check", [python, "scripts/check_realtime_system_outputs.py"]),
        ]
    )

    started = time.time()
    results = []
    for name, command in steps:
        print(f"==> {name}", flush=True)
        result = run_step(name, command, ROOT)
        results.append(result)
        print(f"<== {name} {result['status']} ({result['duration_sec']:.2f}s)", flush=True)
        if result["returncode"] != 0:
            break

    metrics_summary, self_check_summary = summarize_outputs()
    duration = time.time() - started
    passed = sum(1 for row in results if row["status"] == "pass")
    failed = [row for row in results if row["status"] == "fail"]
    payload = {
        "runtime_contract": "offline_realtime_system_regression_no_live_calls",
        "status": "fail" if failed else "pass",
        "duration_sec": duration,
        "total_steps": len(results),
        "passed_steps": passed,
        "steps": results,
        "metrics_summary": metrics_summary,
        "self_check_summary": self_check_summary,
        "expected_warning_boundary": "self_check may warn until selector robustness is promoted",
    }

    out_dir = ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "realtime_system_regression.json"
    md_path = out_dir / "realtime_system_regression.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "status={status} steps={passed}/{total} final={final} self_check={self_check}".format(
            status=payload["status"],
            passed=payload["passed_steps"],
            total=payload["total_steps"],
            final=metrics_summary.get("final_der_pct"),
            self_check=self_check_summary.get("status"),
        )
    )
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
