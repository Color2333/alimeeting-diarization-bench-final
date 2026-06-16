"""Checkpoint management."""

import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

CHECKPOINT_FILE = "checkpoint.json"


def load_checkpoint(output_dir: Path) -> Dict[str, Any]:
    cp_path = output_dir / CHECKPOINT_FILE
    if cp_path.exists():
        with open(cp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded checkpoint: {len(data)} entries")
        return data
    logger.info("No checkpoint found, starting fresh")
    return {}


def save_checkpoint(output_dir: Path, data: Dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    cp_path = output_dir / CHECKPOINT_FILE
    with open(cp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def checkpoint_key(
    rec_id: str,
    ws: int,
    seg_idx: int,
    model: str,
    variant: str = "",
) -> str:
    base = f"{rec_id}|ws{ws}|seg{seg_idx}|{model}"
    if variant:
        base += f"|{variant}"
    return base
