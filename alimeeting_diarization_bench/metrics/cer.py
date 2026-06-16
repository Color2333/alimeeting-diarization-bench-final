"""CER calculation using kaldialign."""

import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


def calc_cer(
    gt_text: str,
    pred_text: str,
    language: str = "chinese",
) -> Optional[Dict]:
    if not gt_text or not pred_text:
        return None

    try:
        import kaldialign

        if language == "chinese":
            ref = list(gt_text.replace(" ", ""))
            hyp = list(pred_text.replace(" ", ""))
        else:
            ref = gt_text.split()
            hyp = pred_text.split()

        if not ref:
            return None

        ERR = "*"
        ali = kaldialign.align(ref, hyp, ERR)

        ins = sum(1 for r, h in ali if r == ERR)
        del_ = sum(1 for r, h in ali if h == ERR)
        sub = sum(1 for r, h in ali if r != ERR and h != ERR and h != r)
        total_errors = ins + del_ + sub

        return {
            "wer": round(total_errors / len(ref), 4),
            "insertions": ins,
            "deletions": del_,
            "substitutions": sub,
            "length": len(ref),
        }
    except Exception as e:
        logger.warning(f"CER calculation failed: {e}")
        return None
