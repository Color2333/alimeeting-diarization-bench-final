"""qwen3-asr-flash: transcription only, no speaker diarization."""

import time
import logging
from typing import Optional

from openai import OpenAI

from .base import BaseModel, DiarizationResult
from ..config import APIKeys

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = "请将这段音频转成文字，准确转录所有内容。"


class ASRFlashModel(BaseModel):
    name = "qwen3-asr-flash"

    def __init__(self, api_keys: Optional[APIKeys] = None):
        self.api_keys = api_keys or APIKeys.from_env()
        self.client = OpenAI(
            api_key=self.api_keys.dashscope_api_key,
            base_url=self.api_keys.dashscope_base_url,
        )

    def predict(
        self,
        audio_path: str,
        speaker_count: Optional[int] = None,
        prompt_variant: str = "default",
        transcript_reference: Optional[str] = None,
    ) -> DiarizationResult:
        import base64

        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        start = time.time()
        try:
            response = self.client.chat.completions.create(
                model="qwen3-asr-flash",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": f"data:audio/wav;base64,{audio_b64}"
                                },
                            }
                        ],
                    }
                ],
                temperature=0.0,
            )
            latency = time.time() - start
            text = response.choices[0].message.content.strip()
            return DiarizationResult(
                success=True,
                text=text,
                latency=latency,
                spk_count=0,
            )
        except Exception as e:
            return DiarizationResult(
                success=False, error=str(e), latency=time.time() - start
            )
