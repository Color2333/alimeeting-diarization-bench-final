"""Fun-ASR: native speaker diarization via DashScope async transcription."""

import time
import json
import logging
from http import HTTPStatus
from urllib import request as urlrequest
from typing import Optional

import dashscope
from dashscope.audio.asr import Transcription

from .base import BaseModel, DiarizationResult
from ..config import APIKeys
from ..utils.oss import upload_to_oss

logger = logging.getLogger(__name__)


class FunASRModel(BaseModel):
    name = "fun-asr"

    def __init__(self, api_keys: Optional[APIKeys] = None):
        self.api_keys = api_keys or APIKeys.from_env()
        dashscope.api_key = self.api_keys.dashscope_api_key

    def predict(
        self,
        audio_path: str,
        speaker_count: Optional[int] = None,
        prompt_variant: str = "default",
        transcript_reference: Optional[str] = None,
    ) -> DiarizationResult:
        oss_key = f"alimeeting/{audio_path.split('/')[-1]}"
        try:
            audio_url = upload_to_oss(audio_path, oss_key, self.api_keys)
        except Exception as e:
            return DiarizationResult(success=False, error=f"OSS upload failed: {e}")

        kwargs = {
            "model": "fun-asr",
            "file_urls": [audio_url],
            "language_hints": ["zh", "en"],
            "diarization_enabled": True,
            "timestamp_alignment_enabled": True,
        }
        if speaker_count:
            kwargs["speaker_count"] = speaker_count

        start = time.time()
        task_resp = Transcription.async_call(**kwargs)
        if task_resp.status_code != HTTPStatus.OK:
            return DiarizationResult(
                success=False,
                error=f"Submit failed: {getattr(task_resp, 'message', 'unknown')}",
            )

        task_id = task_resp.output.task_id
        for _ in range(100):
            time.sleep(3)
            poll = Transcription.fetch(task=task_id)
            status = poll.output.get("task_status", "UNKNOWN")
            if status == "SUCCEEDED":
                break
            if status == "FAILED":
                return DiarizationResult(
                    success=False,
                    error=f"Task failed: {poll.output.get('message')}",
                    latency=time.time() - start,
                )
        else:
            return DiarizationResult(
                success=False, error="Timeout", latency=time.time() - start
            )

        latency = time.time() - start
        results = poll.output.get("results", [])
        if not results or not results[0].get("transcription_url"):
            return DiarizationResult(success=False, error="No results", latency=latency)

        result = json.loads(
            urlrequest.urlopen(results[0]["transcription_url"]).read().decode("utf-8")
        )
        sentences = []
        for t in result.get("transcripts", []):
            for s in t.get("sentences", []):
                sentences.append(
                    {
                        "begin_time": s.get("begin_time", 0) / 1000.0,
                        "end_time": s.get("end_time", 0) / 1000.0,
                        "speaker_id": str(s.get("speaker_id", "unknown")),
                        "text": s.get("text", ""),
                    }
                )

        text = " ".join(s["text"] for s in sentences)
        spk_count = len(set(s["speaker_id"] for s in sentences))

        return DiarizationResult(
            success=True,
            segments=sentences,
            text=text,
            spk_count=spk_count,
            latency=latency,
        )
