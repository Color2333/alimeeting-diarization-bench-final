"""DER calculation using meeteval."""

import logging
from typing import List, Dict, Optional

from meeteval.io import RTTM
from meeteval.der import md_eval

from ..data.ground_truth import segments_to_rttm_string

logger = logging.getLogger(__name__)


def calc_der(
    gt_segments: List[Dict],
    pred_segments: List[Dict],
    session_id: str,
    collar: float = 0.0,
) -> Optional[Dict]:
    if not gt_segments or not pred_segments:
        return None

    try:
        gt_filtered = [s for s in gt_segments if s["end"] > s["start"]]
        pred_filtered = [s for s in pred_segments if s["end"] > s["start"]]

        if not gt_filtered or not pred_filtered:
            return None

        gt_rttm = RTTM.parse(segments_to_rttm_string(gt_filtered, session_id))
        pred_rttm = RTTM.parse(segments_to_rttm_string(pred_filtered, session_id))

        result = md_eval.md_eval_22(
            reference=gt_rttm, hypothesis=pred_rttm, collar=collar
        )

        scored_time = float(result.scored_speaker_time)
        if scored_time <= 0:
            return None

        return {
            "der": round(float(result.error_rate), 4),
            "miss_rate": round(float(result.missed_speaker_time) / scored_time, 4),
            "fa_rate": round(float(result.falarm_speaker_time) / scored_time, 4),
            "conf_rate": round(float(result.speaker_error_time) / scored_time, 4),
            "scored_time": round(scored_time, 2),
        }
    except Exception as e:
        logger.warning(f"DER calculation failed: {e}")
        return None
