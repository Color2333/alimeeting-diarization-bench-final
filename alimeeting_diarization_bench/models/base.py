"""Base model interface for speaker diarization."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DiarizationResult:
    success: bool
    segments: List[dict] = field(default_factory=list)
    text: str = ""
    spk_count: int = 0
    latency: float = 0.0
    error: Optional[str] = None
    raw_output: Optional[str] = None


class BaseModel:
    """Base class for diarization models."""

    name: str = "base"
    params_tag: str = ""

    def predict(
        self,
        audio_path: str,
        speaker_count: Optional[int] = None,
        prompt_variant: str = "default",
        transcript_reference: Optional[str] = None,
    ) -> DiarizationResult:
        raise NotImplementedError

    def segments_to_der_format(self, result: DiarizationResult) -> List[dict]:
        return [
            {
                "start": s["begin_time"],
                "end": s["end_time"],
                "speaker": s["speaker_id"],
                "text": s.get("text", ""),
            }
            for s in result.segments
            if s["end_time"] > s["begin_time"]
        ]
