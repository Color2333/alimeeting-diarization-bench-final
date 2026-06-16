#!/usr/bin/env python3
"""Audit local runtime environment for pending live runs without API calls."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT_JSON = Path("outputs/research_progress_snapshot/live_runtime_environment_audit.json")
OUTPUT_MD = Path("outputs/research_progress_snapshot/live_runtime_environment_audit.md")
OUTPUT_CSV = Path("outputs/research_progress_snapshot/live_runtime_environment_audit.csv")
DASHSCOPE_ENV_NAMES = ["DASHSCOPE_API_KEY", "BAILIAN_API_KEY", "ALIYUN_BAILIAN_API_KEY"]
BASE_URL_ENV_NAMES = ["DASHSCOPE_BASE_URL"]
REQUIRED_MODULES = [
    "openai",
    "numpy",
    "soundfile",
    "alimeeting_diarization_bench.config",
    "scripts.llm_policy_agent_eval",
    "scripts.omni_audio_guard_smoke",
]
REQUIRED_SCRIPTS = [
    "scripts/llm_window_batch_policy_eval.py",
    "scripts/omni_guard_window_batch.py",
    "scripts/refresh_latest_research_artifacts.py",
]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_escape(value: object) -> str:
    text = str(value)
    if any(ch in text for ch in [",", "\n", '"']):
        return '"' + text.replace('"', '""') + '"'
    return text


def env_presence(names: list[str]) -> dict[str, bool]:
    return {name: bool(os.environ.get(name)) for name in names}


def module_rows() -> list[dict[str, Any]]:
    rows = []
    for name in REQUIRED_MODULES:
        spec = importlib.util.find_spec(name)
        rows.append(
            {
                "check_id": f"module:{name}",
                "check_type": "module",
                "target": name,
                "status": "pass" if spec else "fail",
                "detail": "import_spec_found" if spec else "import_spec_missing",
            }
        )
    return rows


def script_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in REQUIRED_SCRIPTS:
        exists = (root / path).exists()
        rows.append(
            {
                "check_id": f"script:{path}",
                "check_type": "script",
                "target": path,
                "status": "pass" if exists else "fail",
                "detail": "script_exists" if exists else "script_missing",
            }
        )
    return rows


def output_dir_rows(root: Path, command_audit: dict[str, Any]) -> list[dict[str, Any]]:
    targets = {
        "outputs/research_progress_snapshot",
        "outputs/runtime_safe_llm_window_batch",
        "outputs/omni_guard",
    }
    for row in command_audit.get("rows", []):
        output = row.get("output_jsonl")
        if output:
            targets.add(str(Path(output).parent))
    rows = []
    for target in sorted(targets):
        path = root / target
        exists = path.exists()
        writable = exists and os.access(path, os.W_OK)
        rows.append(
            {
                "check_id": f"output_dir:{target}",
                "check_type": "output_dir",
                "target": target,
                "status": "pass" if writable else "fail",
                "detail": "exists_and_writable" if writable else ("missing" if not exists else "not_writable"),
            }
        )
    return rows


def audio_rows(root: Path) -> list[dict[str, Any]]:
    rows = read_csv(root / "outputs/research_progress_snapshot/omni_expansion_manifest.csv")
    missing = [row.get("audio", "") for row in rows if row.get("audio_exists") != "1"]
    return [
        {
            "check_id": "omni48_audio_manifest",
            "check_type": "audio_manifest",
            "target": "outputs/research_progress_snapshot/omni_expansion_manifest.csv",
            "status": "pass" if rows and not missing else "fail",
            "detail": f"rows={len(rows)} missing_audio={len(missing)}",
        }
    ]


def python_row() -> dict[str, Any]:
    version_ok = sys.version_info >= (3, 10)
    return {
        "check_id": "python_version",
        "check_type": "python",
        "target": ".".join(str(part) for part in sys.version_info[:3]),
        "status": "pass" if version_ok else "fail",
        "detail": "requires_python>=3.10",
    }


def build_audit(root: Path) -> dict[str, Any]:
    readiness = read_json(root / "outputs/research_progress_snapshot/live_run_readiness.json")
    command_audit = read_json(root / "outputs/research_progress_snapshot/live_command_surface_audit.json")
    resume_audit = read_json(root / "outputs/research_progress_snapshot/live_resume_state_audit.json")
    input_audit = read_json(root / "outputs/research_progress_snapshot/live_input_integrity_audit.json")
    dashscope_env = env_presence(DASHSCOPE_ENV_NAMES)
    base_url_env = env_presence(BASE_URL_ENV_NAMES)
    credential_ready = any(dashscope_env.values())
    checks = [python_row()] + module_rows() + script_rows(root) + output_dir_rows(root, command_audit) + audio_rows(root)
    failed = [row for row in checks if row["status"] != "pass"]
    local_runtime_ready = not failed
    readiness_blockers = [
        blocker
        for row in readiness.get("runs", [])
        for blocker in row.get("blockers", [])
        if "AllocationQuota" in str(blocker) or "quota" in str(blocker).lower()
    ]
    blockers = []
    if not local_runtime_ready:
        blockers.append("local_runtime_preflight_failed")
    if not credential_ready:
        blockers.append("missing_dashscope_or_bailian_api_key_env")
    if readiness_blockers:
        blockers.append("known_provider_quota_or_capacity_blocker")

    status = "runtime_ready_waiting_credentials_or_quota"
    if not local_runtime_ready:
        status = "local_runtime_preflight_failed"
    elif credential_ready and not readiness_blockers:
        status = "local_runtime_and_credentials_ready"

    return {
        "runtime_contract": "live_runtime_environment_audit_no_live_calls",
        "secret_policy": "env_presence_only_no_secret_values_written",
        "status": status,
        "source_contracts": {
            "live_run_readiness": readiness.get("runtime_contract", ""),
            "live_command_surface_audit": command_audit.get("runtime_contract", ""),
            "live_resume_state_audit": resume_audit.get("runtime_contract", ""),
            "live_input_integrity_audit": input_audit.get("runtime_contract", ""),
        },
        "environment": {
            "python_executable": sys.executable,
            "python_version": ".".join(str(part) for part in sys.version_info[:3]),
            "dashscope_like_api_key_present": credential_ready,
            "dashscope_env_present": dashscope_env,
            "base_url_env_present": base_url_env,
            "config_defaults_not_counted_as_credentials": True,
        },
        "blockers": blockers,
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            "passed_checks": sum(1 for row in checks if row["status"] == "pass"),
            "failed_checks": len(failed),
            "module_checks": sum(1 for row in checks if row["check_type"] == "module"),
            "module_passed": sum(1 for row in checks if row["check_type"] == "module" and row["status"] == "pass"),
            "script_checks": sum(1 for row in checks if row["check_type"] == "script"),
            "script_passed": sum(1 for row in checks if row["check_type"] == "script" and row["status"] == "pass"),
            "output_dir_checks": sum(1 for row in checks if row["check_type"] == "output_dir"),
            "output_dir_passed": sum(1 for row in checks if row["check_type"] == "output_dir" and row["status"] == "pass"),
            "audio_manifest_passed": all(row["status"] == "pass" for row in checks if row["check_type"] == "audio_manifest"),
            "credential_ready": credential_ready,
            "known_provider_quota_blockers": len(readiness_blockers),
            "command_ready_count": int(command_audit.get("summary", {}).get("command_ready_count", 0)),
            "resume_clean_run_surfaces": int(resume_audit.get("summary", {}).get("clean_run_surfaces", 0)),
            "input_ready_surfaces": int(input_audit.get("summary", {}).get("input_ready_surfaces", 0)),
            "live_calls_performed_by_builder": 0,
            "no_secret_values_written": True,
            "no_new_metric_claim": True,
        },
    }


def write_csv(audit: dict[str, Any], path: Path) -> None:
    fieldnames = ["check_id", "check_type", "target", "status", "detail"]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(fieldnames)]
    for row in audit["checks"]:
        lines.append(",".join(csv_escape(row.get(key, "")) for key in fieldnames))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    env = audit["environment"]
    lines = [
        "# Live Runtime Environment Audit",
        "",
        f"- Runtime contract: `{audit['runtime_contract']}`",
        f"- Secret policy: `{audit['secret_policy']}`",
        f"- Status: `{audit['status']}`",
        f"- Checks passed: `{summary['passed_checks']}` / `{summary['check_count']}`",
        f"- Module checks passed: `{summary['module_passed']}` / `{summary['module_checks']}`",
        f"- Script checks passed: `{summary['script_passed']}` / `{summary['script_checks']}`",
        f"- Output dir checks passed: `{summary['output_dir_passed']}` / `{summary['output_dir_checks']}`",
        f"- Credential ready: `{summary['credential_ready']}`",
        f"- Known provider quota blockers: `{summary['known_provider_quota_blockers']}`",
        f"- Command-ready count: `{summary['command_ready_count']}`",
        f"- Resume clean-run surfaces: `{summary['resume_clean_run_surfaces']}`",
        f"- Input-ready surfaces: `{summary['input_ready_surfaces']}`",
        f"- Python: `{env['python_version']}`",
        f"- Live calls performed by builder: `{summary['live_calls_performed_by_builder']}`",
        f"- No new metric claim: `{summary['no_new_metric_claim']}`",
        "",
        "| Check | Type | Target | Status | Detail |",
        "|---|---|---|---|---|",
    ]
    for row in audit["checks"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['check_type']}` | `{row['target']}` | `{row['status']}` | {row['detail']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This preflight checks local Python/runtime/import/script/path readiness only.",
            "- It writes env presence booleans only and never writes secret values.",
            "- A local runtime pass does not remove credential, quota, live output, scoring, promotion, or traceability gates.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    audit = build_audit(ROOT)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(audit, args.output_md)
    write_csv(audit, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
