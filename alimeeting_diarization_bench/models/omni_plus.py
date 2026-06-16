"""qwen3.5-omni-plus: multimodal diarization via prompt engineering."""

import re
import time
import logging
from typing import Optional, List

from openai import OpenAI

from .base import BaseModel, DiarizationResult
from ..config import APIKeys

logger = logging.getLogger(__name__)

PROMPTS = {
    "baseline": """请将这段音频转为SRT字幕格式，每个说话人的每段话单独一个编号。
格式如下：
1
00:00:00,000 --> 00:00:05,000
[Speaker1]
说话内容...

请确保时间戳准确，正确区分不同说话人""",
    "agent_guided": """请将这段音频转为SRT字幕格式，标注说话人和时间戳。
参考转录文本（供你参考内容）:
{transcript}

输出格式:
1
00:00:00,000 --> 00:00:05,000
[Speaker1]
说话内容...""",
    "agent_spkhint": """请将这段音频转为SRT字幕格式，标注说话人和时间戳。
这段音频中有 {speaker_count} 个说话人。
参考转录文本:
{transcript}

输出格式:
1
00:00:00,000 --> 00:00:05,000
[Speaker1]
说话内容...""",
}


def parse_omni_output(output: str) -> List[dict]:
    segments = []

    srt_pattern = re.compile(
        r"(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n"
        r"\[?([Ss]peaker?\s*\.?\s*)(\d+)\]?\s*\n(.*?)(?=\n\n\d+\s*\n|\Z)",
        re.DOTALL,
    )
    for m in srt_pattern.finditer(output):
        segments.append(
            {
                "begin_time": _parse_ts(m.group(2)),
                "end_time": _parse_ts(m.group(3)),
                "speaker_id": f"Speaker{int(m.group(5))}",
                "text": m.group(6).strip(),
            }
        )

    if not segments:
        compact = re.compile(
            r"\[?\s*([Ss]peaker?\s*\.?\s*)(\d+)\s*\]?\s*[\|\：\:]\s*(.*?)(?=\n\[?[Ss]peaker|$)",
            re.DOTALL,
        )
        for m in compact.finditer(output):
            segments.append(
                {
                    "begin_time": 0,
                    "end_time": 5,
                    "speaker_id": f"Speaker{int(m.group(2))}",
                    "text": m.group(3).strip(),
                }
            )

    return segments


def _parse_ts(ts: str) -> float:
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return 0.0


class OmniPlusModel(BaseModel):
    name = "qwen3.5-omni-plus"

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
        prompt_variant: str = "baseline",
        transcript_reference: Optional[str] = None,
    ) -> DiarizationResult:
        import base64

        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        template = PROMPTS.get(prompt_variant, PROMPTS["baseline"])
        prompt = template.format(
            speaker_count=speaker_count or "",
            transcript=transcript_reference or "",
        )

        start = time.time()
        try:
            response = self.client.chat.completions.create(
                model="qwen3.5-omni-plus",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": f"data:audio/wav;base64,{audio_b64}"
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                temperature=0.1,
            )
            latency = time.time() - start
            output = response.choices[0].message.content
            segments = parse_omni_output(output)
            text = " ".join(s.get("text", "") for s in segments)
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
