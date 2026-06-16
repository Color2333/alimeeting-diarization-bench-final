"""Installed command wrappers for the final submission scripts."""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

SCRIPT_MAP = {
    "quick-start": REPO_ROOT / "scripts" / "entrypoints" / "quick_start.py",
    "realtime": REPO_ROOT / "scripts" / "entrypoints" / "run_realtime_diarization_system.py",
    "batch": REPO_ROOT / "scripts" / "entrypoints" / "run_realtime_batch.py",
    "regression": REPO_ROOT / "scripts" / "entrypoints" / "run_realtime_system_regression.py",
    "self-check": REPO_ROOT / "scripts" / "entrypoints" / "check_realtime_system_outputs.py",
    "timeline-check": REPO_ROOT / "scripts" / "entrypoints" / "check_timeline_integrity.py",
}


def _run_script(command: str) -> None:
    script = SCRIPT_MAP[command]
    if not script.exists():
        raise SystemExit(
            f"Cannot find {script}. Run this command from an editable checkout "
            "installed with `python -m pip install -e .`."
        )
    sys.argv[0] = str(script)
    runpy.run_path(str(script), run_name="__main__")


def quick_start() -> None:
    _run_script("quick-start")


def realtime() -> None:
    _run_script("realtime")


def batch() -> None:
    _run_script("batch")


def regression() -> None:
    _run_script("regression")


def self_check() -> None:
    _run_script("self-check")


def timeline_check() -> None:
    _run_script("timeline-check")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dispatch final AliMeeting diarization submission commands."
    )
    parser.add_argument(
        "command",
        choices=sorted(SCRIPT_MAP),
        help="Submission command to run.",
    )
    args, remaining = parser.parse_known_args()
    sys.argv = [f"alimeeting-final {args.command}", *remaining]
    _run_script(args.command)


if __name__ == "__main__":
    main()
