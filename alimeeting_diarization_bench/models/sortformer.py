"""NVIDIA NeMo Sortformer diarization wrapper."""

import logging
import re
import time
from hashlib import sha1
from typing import Optional

import torch

from .base import BaseModel, DiarizationResult

logger = logging.getLogger(__name__)


class SortformerModel(BaseModel):
    name = "nemo-sortformer-4spk-v1"
    model_id = "nvidia/diar_sortformer_4spk-v1"

    STREAMING_PRESETS = {
        "very_high_latency": {
            "chunk_len": 340,
            "chunk_right_context": 40,
            "fifo_len": 40,
            "spkcache_update_period": 300,
            "spkcache_len": 188,
            "nominal_latency_sec": 30.4,
        },
        "high_latency": {
            "chunk_len": 124,
            "chunk_right_context": 1,
            "fifo_len": 124,
            "spkcache_update_period": 124,
            "spkcache_len": 188,
            "nominal_latency_sec": 10.0,
        },
        "low_latency": {
            "chunk_len": 6,
            "chunk_right_context": 7,
            "fifo_len": 188,
            "spkcache_update_period": 144,
            "spkcache_len": 188,
            "nominal_latency_sec": 1.04,
        },
        "ultra_low_latency": {
            "chunk_len": 3,
            "chunk_right_context": 1,
            "fifo_len": 188,
            "spkcache_update_period": 144,
            "spkcache_len": 188,
            "nominal_latency_sec": 0.32,
        },
    }

    def __init__(
        self,
        model_id: Optional[str] = None,
        pipeline_params: Optional[dict] = None,
    ):
        try:
            from nemo.collections.asr.models import SortformerEncLabelModel
        except ImportError as e:
            raise ImportError(
                "NVIDIA NeMo ASR is not installed. Install NeMo with ASR support "
                "before using nemo-sortformer-4spk-v1."
            ) from e

        self.pipeline_params = pipeline_params or {}
        self.model_id = model_id or self.pipeline_params.get("model_id") or self.model_id
        if self.pipeline_params.get("streaming", False) and "model_id" not in self.pipeline_params:
            self.model_id = "nvidia/diar_streaming_sortformer_4spk-v2"

        self.name = self._build_model_name()
        self.params_tag = self._build_params_tag()
        self.model = SortformerEncLabelModel.from_pretrained(self.model_id)
        if torch.cuda.is_available():
            self.model = self.model.to(torch.device("cuda"))
        self.model.eval()
        self._apply_streaming_config()
        logger.info("Sortformer model loaded: %s params=%s", self.model_id, self.pipeline_params)

    def predict(
        self,
        audio_path: str,
        speaker_count: Optional[int] = None,
        prompt_variant: str = "default",
        transcript_reference: Optional[str] = None,
    ) -> DiarizationResult:
        start = time.time()
        try:
            predicted = self.model.diarize(audio=audio_path, batch_size=1)
            latency = time.time() - start
            segments = _parse_sortformer_output(predicted)
            return DiarizationResult(
                success=True,
                segments=segments,
                text="",
                spk_count=len({s["speaker_id"] for s in segments}),
                latency=latency,
                raw_output=str(predicted),
            )
        except Exception as e:
            return DiarizationResult(
                success=False,
                error=str(e),
                latency=time.time() - start,
            )

    def _build_model_name(self) -> str:
        if "diar_streaming_sortformer" in self.model_id:
            return "nemo-streaming-sortformer-4spk"
        return self.name

    def _build_params_tag(self) -> str:
        if not self.pipeline_params:
            return ""
        preset = self.pipeline_params.get("latency_preset")
        if preset:
            return f"preset_{preset}"
        digest = sha1(str(sorted(self.pipeline_params.items())).encode()).hexdigest()[:8]
        return f"params_{digest}"

    def _apply_streaming_config(self) -> None:
        preset_name = self.pipeline_params.get("latency_preset")
        config = {}
        if preset_name:
            if preset_name not in self.STREAMING_PRESETS:
                raise ValueError(
                    "Unknown Sortformer latency_preset: %s. Available: %s"
                    % (preset_name, sorted(self.STREAMING_PRESETS))
                )
            config.update(self.STREAMING_PRESETS[preset_name])

        for key in (
            "chunk_len",
            "chunk_right_context",
            "fifo_len",
            "spkcache_update_period",
            "spkcache_len",
        ):
            if key in self.pipeline_params:
                config[key] = self.pipeline_params[key]

        if not config:
            return

        modules = getattr(self.model, "sortformer_modules", None)
        if modules is None:
            logger.warning("Sortformer model has no sortformer_modules; streaming config ignored")
            return

        for key, value in config.items():
            if key == "nominal_latency_sec":
                continue
            if hasattr(modules, key):
                setattr(modules, key, int(value))
            else:
                logger.warning("Sortformer module has no attribute %s; ignored", key)
        if hasattr(modules, "_check_streaming_parameters"):
            modules._check_streaming_parameters()


def _parse_sortformer_output(predicted) -> list[dict]:
    """Parse NeMo Sortformer diarize() output into benchmark segments."""
    if predicted is None:
        return []

    if isinstance(predicted, tuple):
        predicted = predicted[0]

    # Single-file inference usually returns a list for that file, while batched
    # inference may return a one-element nested list.
    if (
        isinstance(predicted, list)
        and len(predicted) == 1
        and isinstance(predicted[0], list)
    ):
        predicted = predicted[0]

    segments = []
    for item in predicted:
        parsed = _parse_sortformer_item(item)
        if parsed:
            segments.append(parsed)
    return segments


def _parse_sortformer_item(item) -> Optional[dict]:
    if isinstance(item, dict):
        start = item.get("start") or item.get("begin") or item.get("begin_time")
        end = item.get("end") or item.get("stop") or item.get("end_time")
        speaker = item.get("speaker") or item.get("speaker_id") or item.get("label")
        if start is not None and end is not None and speaker is not None:
            return {
                "begin_time": float(start),
                "end_time": float(end),
                "speaker_id": str(speaker),
                "text": "",
            }

    if isinstance(item, (list, tuple)) and len(item) >= 3:
        return {
            "begin_time": float(item[0]),
            "end_time": float(item[1]),
            "speaker_id": str(item[2]),
            "text": "",
        }

    text = str(item).strip()
    match = re.search(
        r"([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)\s+(\S+)", text
    )
    if not match:
        return None

    return {
        "begin_time": float(match.group(1)),
        "end_time": float(match.group(2)),
        "speaker_id": match.group(3),
        "text": "",
    }
