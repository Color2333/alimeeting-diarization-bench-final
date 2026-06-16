"""PyAnnote 3.1: local speaker diarization via pyannote.audio pipeline."""

import time
import logging
import hashlib
import json
from copy import deepcopy
from typing import Optional

import torch
import soundfile as sf
try:
    from huggingface_hub import HfFolder
except ImportError:
    HfFolder = None
    from huggingface_hub import get_token as hf_get_token

from .base import BaseModel, DiarizationResult
from ..config import APIKeys

logger = logging.getLogger(__name__)


class PyAnnoteModel(BaseModel):
    name = "pyannote-3.1"
    model_id = "pyannote/speaker-diarization-3.1"
    supports_speaker_bounds = True

    def __init__(
        self,
        api_keys: Optional[APIKeys] = None,
        pipeline_params: Optional[dict] = None,
    ):
        from pyannote.audio import Pipeline

        token = (api_keys or APIKeys.from_env()).hf_token
        if not token:
            token = HfFolder.get_token() if HfFolder else hf_get_token()
        if not token:
            raise ValueError("HF_TOKEN not set")

        self.pipeline = Pipeline.from_pretrained(self.model_id, token=token)
        self.pipeline_params = pipeline_params or {}
        self.params_tag = self._params_tag(self.pipeline_params)
        if self.pipeline_params:
            params = deepcopy(self.pipeline.parameters(instantiated=True))
            self._deep_update(params, self.pipeline_params)
            self.pipeline.instantiate(params)
            logger.info("Applied PyAnnote params: %s", self.pipeline_params)

        if torch.cuda.is_available():
            self.pipeline.to(torch.device("cuda"))
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.pipeline.to(torch.device("mps"))
            self.device = "mps"
        else:
            self.device = "cpu"

        logger.info(f"PyAnnote 3.1 loaded on {self.device}")

    @staticmethod
    def _deep_update(base: dict, updates: dict) -> None:
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                PyAnnoteModel._deep_update(base[key], value)
            else:
                base[key] = value

    @staticmethod
    def _params_tag(params: dict) -> str:
        if not params:
            return ""
        payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]
        return f"params_{digest}"

    def predict(
        self,
        audio_path: str,
        speaker_count: Optional[int] = None,
        speaker_count_min: Optional[int] = None,
        speaker_count_max: Optional[int] = None,
        prompt_variant: str = "default",
        transcript_reference: Optional[str] = None,
    ) -> DiarizationResult:
        audio, sr = sf.read(audio_path, dtype="float32")
        if audio.ndim > 1:
            audio = audio[:, 0]
        waveform = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
        audio_input = {"waveform": waveform, "sample_rate": sr}

        kwargs = {}
        if speaker_count and speaker_count > 0:
            kwargs["num_speakers"] = speaker_count
        elif speaker_count_min or speaker_count_max:
            if speaker_count_min and speaker_count_min > 0:
                kwargs["min_speakers"] = speaker_count_min
            if speaker_count_max and speaker_count_max > 0:
                kwargs["max_speakers"] = speaker_count_max

        start = time.time()
        try:
            output = self.pipeline(audio_input, **kwargs)
            latency = time.time() - start

            diarization = (
                output.speaker_diarization
                if hasattr(output, "speaker_diarization")
                else output
            )

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
                success=False, error=str(e), latency=time.time() - start
            )


class PyAnnoteCommunityModel(PyAnnoteModel):
    """PyAnnote Community-1: newer open-source diarization pipeline."""

    name = "pyannote-community-1"
    model_id = "pyannote/speaker-diarization-community-1"
