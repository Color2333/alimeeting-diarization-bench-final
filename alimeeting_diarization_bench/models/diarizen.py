"""DiariZen: WavLM-based open-source diarization pipeline."""

import time
import logging
from typing import Optional

from .base import BaseModel, DiarizationResult

logger = logging.getLogger(__name__)


class DiariZenModel(BaseModel):
    name = "diarizen-large-v2"
    model_id = "BUT-FIT/diarizen-wavlm-large-s80-md-v2"

    def __init__(self, model_id: Optional[str] = None):
        try:
            from diarizen.pipelines.inference import DiariZenPipeline
        except ImportError as e:
            raise ImportError(
                "DiariZen is not installed. Install it from "
                "https://github.com/BUTSpeechFIT/DiariZen before using "
                "the diarizen-large-v2 model."
            ) from e

        self.model_id = model_id or self.model_id
        try:
            self.pipeline = DiariZenPipeline.from_pretrained(self.model_id)
        except TypeError as e:
            if "unexpected keyword argument 'config'" in str(e):
                raise RuntimeError(
                    "DiariZen loaded, but the installed pyannote.audio version is "
                    "incompatible with DiariZen's custom pipeline. Use DiariZen's "
                    "bundled pyannote-audio fork or an isolated DiariZen environment."
                ) from e
            raise
        logger.info("DiariZen pipeline loaded: %s", self.model_id)

    def predict(
        self,
        audio_path: str,
        speaker_count: Optional[int] = None,
        prompt_variant: str = "default",
        transcript_reference: Optional[str] = None,
    ) -> DiarizationResult:
        start = time.time()
        try:
            diarization = self.pipeline(audio_path)
            latency = time.time() - start

            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append(
                    {
                        "begin_time": turn.start,
                        "end_time": turn.end,
                        "speaker_id": speaker,
                        "text": "",
                    }
                )

            spk_count = len(set(s["speaker_id"] for s in segments))
            return DiarizationResult(
                success=True,
                segments=segments,
                text="",
                spk_count=spk_count,
                latency=latency,
            )
        except Exception as e:
            return DiarizationResult(
                success=False,
                error=str(e),
                latency=time.time() - start,
            )
