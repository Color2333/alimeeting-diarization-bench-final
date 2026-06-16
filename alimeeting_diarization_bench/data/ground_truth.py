"""
Ground truth segment construction.
"""

from typing import List, Dict


def build_gt_segments(
    supervisions: List[Dict],
    offset: float,
    duration: float,
) -> List[Dict]:
    window_end = offset + duration
    gt_segments = []

    for sup in supervisions:
        sup_start = sup["start"]
        sup_end = sup["start"] + sup["duration"]

        if sup_start >= window_end or sup_end <= offset:
            continue

        clipped_start = max(sup_start, offset)
        clipped_end = min(sup_end, window_end)

        gt_segments.append(
            {
                "speaker": sup["speaker"],
                "start": round(clipped_start - offset, 3),
                "end": round(clipped_end - offset, 3),
                "text": sup.get("text", ""),
            }
        )

    return gt_segments


def build_gt_der_segments(
    supervisions: List[Dict],
    offset: float,
    duration: float,
) -> List[Dict]:
    gt_segs = build_gt_segments(supervisions, offset, duration)
    return [
        {"start": s["start"], "end": s["end"], "speaker": s["speaker"]}
        for s in gt_segs
        if s["end"] > s["start"]
    ]


def build_gt_text(supervisions: List[Dict], offset: float, duration: float) -> str:
    gt_segs = build_gt_segments(supervisions, offset, duration)
    return " ".join(s["text"] for s in gt_segs)


def build_gt_rttm(
    supervisions: List[Dict],
    offset: float,
    duration: float,
    session_id: str,
) -> str:
    gt_segs = build_gt_segments(supervisions, offset, duration)
    lines = []
    for seg in gt_segs:
        dur = seg["end"] - seg["start"]
        if dur <= 0:
            continue
        lines.append(
            f"SPEAKER {session_id} 1 {seg['start']:.3f} {dur:.3f} "
            f"<NA> <NA> {seg['speaker']} <NA> <NA>"
        )
    return "\n".join(lines)


def segments_to_rttm_string(segments: List[Dict], session_id: str) -> str:
    lines = []
    for seg in segments:
        dur = seg["end"] - seg["start"]
        if dur <= 0:
            continue
        lines.append(
            f"SPEAKER {session_id} 1 {seg['start']:.3f} {dur:.3f} "
            f"<NA> <NA> {seg['speaker']} <NA> <NA>"
        )
    return "\n".join(lines)
