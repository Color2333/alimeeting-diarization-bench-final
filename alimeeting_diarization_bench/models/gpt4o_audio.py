"""gpt-4o-audio-preview: speaker diarization via LLM prompt."""

import re
import time
import logging
from typing import Optional, List

from openai import OpenAI

from .base import BaseModel, DiarizationResult
from ..config import APIKeys

logger = logging.getLogger(__name__)

GPT_PROMPT = """Please transcribe this Chinese meeting audio and perform speaker diarization.
Output ONLY in this exact format (one line per segment):
[SpeakerN] HH:MM:SS.mmm - HH:MM:SS.mmm: transcribed text

Rules:
1. Number each unique speaker (Speaker1, Speaker2, etc.)
2. Provide precise timestamps
3. Transcribe ALL spoken content accurately
4. Do not add any commentary or explanation"""


def parse_gpt_output(text: str) -> List[dict]:
    segments = []
    for line in text.strip().split("\n"):
        m = re.match(
            r"\[Speaker(\d+)\]\s*(\d{2}:\d{2}:\d{2}\.\d{3})\s*-\s*(\d{2}:\d{2}:\d{2}\.\d{3}):\s*(.*)",
            line.strip(),
        )
        if m:
            segments.append(
                {
                    "begin_time": _parse_ts(m.group(2)),
                    "end_time": _parse_ts(m.group(3)),
                    "speaker_id": f"Speaker{m.group(1)}",
                    "text": m.group(4).strip(),
                }
            )
    return segments


def _parse_ts(ts: str) -> float:
    parts = ts.replace(",", ".").split(":")
    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])


class GPT4oAudioModel(BaseModel):
    name = "gpt-4o-audio-preview"

    def __init__(self, api_keys: Optional[APIKeys] = None):
        self.api_keys = api_keys or APIKeys.from_env()
        key = self.api_keys.gpt_api_key
        if not key:
            raise ValueError("GPT_API_KEY not set")
        self.client = OpenAI(api_key=key)

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
                model="gpt-4o-audio-preview",
                modalities=["text"],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {"data": audio_b64, "format": "wav"},
                            },
                            {"type": "text", "text": GPT_PROMPT},
                        ],
                    }
                ],
            )
            latency = time.time() - start
            output = response.choices[0].message.content
            segments = parse_gpt_output(output)
            text = " ".join(s["text"] for s in segments)
            spk_count = len(set(s["speaker_id"] for s in segments))

            return DiarizationResult(
                success=True,
                segments=segments,
                text=text,
                spk_count=spk_count,
                latency=latency,
                raw_output=output,
            )
        except Exception as e:
            return DiarizationResult(
                success=False, error=str(e), latency=time.time() - start
            )
