"""Installed command wrappers for the final submission modules."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from .final import (
    quick_start as quick_start_module,
    realtime_batch as realtime_batch_module,
    realtime_system as realtime_system_module,
    regression as regression_module,
    self_check as self_check_module,
    timeline_integrity as timeline_integrity_module,
)


SCRIPT_MAP = {
    "quick-start": quick_start_module.main,
    "realtime": realtime_system_module.main,
    "batch": realtime_batch_module.main,
    "regression": regression_module.main,
    "self-check": self_check_module.main,
    "timeline-check": timeline_integrity_module.main,
}


def _run_module(command: str) -> None:
    main_func: Callable[[], None] = SCRIPT_MAP[command]
    main_func()


def quick_start() -> None:
    _run_module("quick-start")


def realtime() -> None:
    _run_module("realtime")


def batch() -> None:
    _run_module("batch")


def regression() -> None:
    _run_module("regression")


def self_check() -> None:
    _run_module("self-check")


def timeline_check() -> None:
    _run_module("timeline-check")


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
    _run_module(args.command)


if __name__ == "__main__":
    main()
