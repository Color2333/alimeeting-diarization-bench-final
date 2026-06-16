"""
Manifest loading for AliMeeting dataset.
"""

import gzip
import json
import logging
import random
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple

from ..config import Paths

logger = logging.getLogger(__name__)


def load_manifests(
    manifest_dir: Path | None = None,
) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
    if manifest_dir is None:
        manifest_dir = Paths.from_env().manifest_dir

    rec_path = manifest_dir / "alimeeting-far_recordings_eval.jsonl.gz"
    sup_path = manifest_dir / "alimeeting-far_supervisions_eval.jsonl.gz"

    recordings = []
    with gzip.open(rec_path, "rt", encoding="utf-8") as f:
        for line in f:
            recordings.append(json.loads(line.strip()))
    logger.info(f"Loaded {len(recordings)} recordings")

    supervisions_by_recording = defaultdict(list)
    with gzip.open(sup_path, "rt", encoding="utf-8") as f:
        for line in f:
            sup = json.loads(line.strip())
            supervisions_by_recording[sup["recording_id"]].append(sup)

    for rec_id, sups in supervisions_by_recording.items():
        sups.sort(key=lambda x: x["start"])
        logger.info(f"  {rec_id}: {len(sups)} supervisions")

    return recordings, dict(supervisions_by_recording)


def generate_segments(
    recordings: List[Dict],
    window_sizes: List[int] = [30, 60],
    segments_per_meeting: int = 3,
) -> List[Dict]:
    segments = []
    for rec in recordings:
        rec_id = rec["id"]
        audio_path = rec["sources"][0]["source"]
        total_duration = rec["duration"]

        for ws in window_sizes:
            if total_duration <= ws:
                offsets = [0.0]
            else:
                step = (total_duration - ws) / max(segments_per_meeting - 1, 1)
                offsets = [round(step * i, 2) for i in range(segments_per_meeting)]

            for seg_idx, offset in enumerate(offsets):
                segments.append(
                    {
                        "recording_id": rec_id,
                        "audio_path": audio_path,
                        "window_size": ws,
                        "segment_idx": seg_idx,
                        "offset": offset,
                        "duration": ws,
                    }
                )

    logger.info(f"Generated {len(segments)} segments total")
    return segments


def generate_stratified_segments(
    recordings: List[Dict],
    supervisions_by_recording: Dict[str, List[Dict]],
    window_size: int = 30,
    total_samples: int = 120,
    seed: int = 42,
) -> List[Dict]:
    """
    Generate stratified random segments from recordings based on speaker count.

    This function groups recordings by the number of unique speakers, allocates
    samples proportionally to each group (with a minimum guarantee), and randomly
    samples non-overlapping windows from each recording.

    Args:
        recordings: List of recording dicts with 'id', 'sources', and 'duration'
        supervisions_by_recording: Dict mapping recording_id to list of supervision dicts
        window_size: Window size in seconds for each segment (default: 30)
        total_samples: Total number of segments to generate (default: 120)
        seed: Random seed for reproducibility (default: 42)

    Returns:
        List of segment dicts with format:
        {
            "recording_id": str,
            "audio_path": str,
            "window_size": int,
            "segment_idx": int,
            "offset": float,
            "duration": int,
            "spk_count_gt": int
        }
    """
    rng = random.Random(seed)

    # Group recordings by speaker count
    recordings_by_spk: Dict[int, List[Dict]] = defaultdict(list)

    for rec in recordings:
        rec_id = rec["id"]
        sups = supervisions_by_recording.get(rec_id, [])
        spk_count = len(set(s["speaker"] for s in sups))
        recordings_by_spk[spk_count].append(rec)
        logger.info(f"Recording {rec_id}: {spk_count} speakers")

    # Log grouping summary
    logger.info("Recordings grouped by speaker count:")
    for spk_count, recs in sorted(recordings_by_spk.items()):
        logger.info(f"  {spk_count}-speaker: {len(recs)} recordings")

    # Allocate samples proportionally with minimum guarantee
    num_groups = len(recordings_by_spk)
    min_per_group = 10

    # Ensure minimum allocation is feasible
    if total_samples < min_per_group * num_groups:
        logger.warning(
            f"total_samples={total_samples} too small for {num_groups} groups "
            f"with min={min_per_group}. Reducing min to {total_samples // num_groups}"
        )
        min_per_group = total_samples // num_groups

    # Calculate total recording-duration-weighted samples per group
    group_weights = {}
    for spk_count, recs in recordings_by_spk.items():
        # Weight by number of recordings in group
        group_weights[spk_count] = len(recs)

    total_weight = sum(group_weights.values())

    # Allocate samples proportionally, then adjust for minimum
    allocation = {}
    remaining = total_samples

    for spk_count, weight in group_weights.items():
        # Proportional allocation
        prop_samples = int((weight / total_weight) * total_samples)
        # Ensure minimum
        alloc = max(prop_samples, min_per_group)
        # Don't exceed remaining
        alloc = min(
            alloc, remaining - (min_per_group * (num_groups - len(allocation) - 1))
        )
        allocation[spk_count] = alloc
        remaining -= alloc

    # Distribute remaining samples
    while remaining > 0:
        for spk_count in sorted(allocation.keys()):
            if remaining <= 0:
                break
            allocation[spk_count] += 1
            remaining -= 1

    logger.info("Sample allocation by speaker group:")
    for spk_count, samples in sorted(allocation.items()):
        logger.info(f"  {spk_count}-speaker: {samples} segments")

    # Generate segments
    segments = []

    for spk_count, recs in recordings_by_spk.items():
        num_recordings = len(recs)
        samples_for_group = allocation[spk_count]

        # Distribute samples evenly across recordings in group
        samples_per_rec = samples_for_group // num_recordings
        extra = samples_for_group % num_recordings

        for rec_idx, rec in enumerate(recs):
            rec_id = rec["id"]
            audio_path = rec["sources"][0]["source"]
            total_duration = rec["duration"]

            # Calculate number of samples for this recording
            n = samples_per_rec + (1 if rec_idx < extra else 0)

            # Calculate all possible non-overlapping window start offsets (in seconds)
            max_offsets = int(total_duration // window_size)
            available_offsets = [i * window_size for i in range(max_offsets)]

            if not available_offsets:
                logger.warning(
                    f"Recording {rec_id} duration {total_duration}s too short "
                    f"for {window_size}s window. Skipping."
                )
                continue

            # Randomly sample n offsets (with replacement if needed)
            if n > len(available_offsets):
                logger.warning(
                    f"Recording {rec_id}: requesting {n} samples but only "
                    f"{len(available_offsets)} offsets available. Using all."
                )
                sampled_offsets = available_offsets
            else:
                sampled_offsets = rng.sample(available_offsets, n)

            # Create segment dicts
            for seg_idx, offset in enumerate(sorted(sampled_offsets)):
                segments.append(
                    {
                        "recording_id": rec_id,
                        "audio_path": audio_path,
                        "window_size": window_size,
                        "segment_idx": seg_idx,
                        "offset": float(offset),
                        "duration": window_size,
                        "spk_count_gt": spk_count,
                    }
                )

    logger.info(f"Generated {len(segments)} stratified segments total")
    return segments
