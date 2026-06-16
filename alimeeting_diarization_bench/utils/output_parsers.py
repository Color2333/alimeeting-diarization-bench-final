"""Shared output parsers for model responses."""

from ..models.omni_plus import parse_omni_output as parse_omni_plus_output
from ..models.gpt4o_audio import parse_gpt_output


def parse_fun_asr_sentences(result_json: dict) -> list:
    """Parse Fun-ASR / paraformer-v2 transcript JSON into segment dicts."""
    sentences = []
    for t in result_json.get("transcripts", []):
        for s in t.get("sentences", []):
            sentences.append(
                {
                    "begin_time": s.get("begin_time", 0) / 1000.0,
                    "end_time": s.get("end_time", 0) / 1000.0,
                    "speaker_id": str(s.get("speaker_id", "unknown")),
                    "text": s.get("text", ""),
                }
            )
    return sentences
