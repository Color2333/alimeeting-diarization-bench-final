"""Collar comparison: re-calculate DER with varying collar values from existing checkpoints."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from ..config import Paths
from ..data.manifests import load_manifests
from ..data.ground_truth import build_gt_der_segments
from ..metrics.der import calc_der
from ..utils.checkpoint import checkpoint_key

logger = logging.getLogger(__name__)


def calc_der_with_collar(
    checkpoint_entry: dict,
    supervisions: dict,
    collar: float,
) -> Optional[dict]:
    """Re-calculate DER for a single checkpoint entry with a specific collar value.

    Args:
        checkpoint_entry: Dict with keys 'recording_id', 'window_size',
                         'segment_idx', 'offset', 'duration', 'pred_segments'.
        supervisions: Dict mapping recording_id to list of supervision dicts.
        collar: Collar value in seconds.

    Returns:
        Dict with der, miss_rate, fa_rate, conf_rate, scored_time or None on failure.
    """
    rec_id = checkpoint_entry.get("recording_id")
    if not rec_id:
        return None

    sups = supervisions.get(rec_id)
    if not sups:
        return None

    offset = checkpoint_entry.get("offset", 0.0)
    duration = checkpoint_entry.get("duration", 30)

    gt_der_segments = build_gt_der_segments(sups, offset, duration)
    if not gt_der_segments:
        return None

    pred_segments_raw = checkpoint_entry.get("pred_segments", [])
    if not pred_segments_raw:
        return None

    pred_der_segments = [
        {
            "start": s["begin_time"],
            "end": s["end_time"],
            "speaker": s["speaker_id"],
        }
        for s in pred_segments_raw
        if s["end_time"] > s["begin_time"]
    ]
    if not pred_der_segments:
        return None

    return calc_der(
        gt_der_segments, pred_der_segments, session_id=rec_id, collar=collar
    )


def compare_collars(
    checkpoint_path: Path,
    manifest_dir: Path | None = None,
    collars: list[float] | None = None,
) -> dict:
    """Compare DER across different collar values for all segments in a checkpoint.

    Args:
        checkpoint_path: Path to checkpoint.json.
        manifest_dir: Path to manifests for loading ground truth.
        collars: List of collar values to test.

    Returns:
        Dict mapping collar value (float) -> {
            avg_der, avg_miss, avg_fa, avg_conf,
            n_segments, per_segment: [...]
        }
    """
    if collars is None:
        collars = [0.0, 0.25, 0.5]

    with open(checkpoint_path, "r", encoding="utf-8") as f:
        checkpoint = json.load(f)

    logger.info(
        "Loaded %d checkpoint entries from %s", len(checkpoint), checkpoint_path
    )

    _, supervisions = load_manifests(manifest_dir)

    results: Dict[float, dict] = {}
    for collar in collars:
        per_segment: List[dict] = []
        der_values: List[float] = []
        miss_values: List[float] = []
        fa_values: List[float] = []
        conf_values: List[float] = []

        for key, entry in checkpoint.items():
            if not entry.get("success") or not entry.get("pred_segments"):
                continue

            der_result = calc_der_with_collar(entry, supervisions, collar)
            if der_result is None:
                continue

            per_segment.append(
                {
                    "key": key,
                    "recording_id": entry.get("recording_id"),
                    "collar": collar,
                    **der_result,
                }
            )
            der_values.append(der_result["der"])
            miss_values.append(der_result["miss_rate"])
            fa_values.append(der_result["fa_rate"])
            conf_values.append(der_result["conf_rate"])

        n = len(der_values)
        results[collar] = {
            "avg_der": sum(der_values) / n if n else 0.0,
            "avg_miss": sum(miss_values) / n if n else 0.0,
            "avg_fa": sum(fa_values) / n if n else 0.0,
            "avg_conf": sum(conf_values) / n if n else 0.0,
            "n_segments": n,
            "per_segment": per_segment,
        }
        logger.info(
            "Collar=%.2fs: DER=%.2f%% over %d segments",
            collar,
            results[collar]["avg_der"] * 100,
            n,
        )

    return results
