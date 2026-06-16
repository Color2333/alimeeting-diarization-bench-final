"""
Central configuration for AliMeeting Diarization Bench.
All paths and API keys loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Paths:
    """Data paths configuration."""

    manifest_dir: Path
    audio_dir: Path
    output_dir: Path

    @classmethod
    def from_env(cls) -> "Paths":
        return cls(
            manifest_dir=Path(
                os.environ.get(
                    "ALIMEETING_MANIFEST_DIR",
                    os.path.expanduser("~/data/AliMeeting/AliMeeting_manifests"),
                )
            ),
            audio_dir=Path(
                os.environ.get(
                    "ALIMEETING_AUDIO_DIR",
                    os.path.expanduser(
                        "~/data/AliMeeting/Eval_Ali/Eval_Ali_far/audio_dir"
                    ),
                )
            ),
            output_dir=Path(
                os.environ.get(
                    "ALIMEETING_OUTPUT_DIR",
                    os.path.expanduser("~/data/AliMeeting/batch_results"),
                )
            ),
        )


@dataclass
class APIKeys:
    """API keys configuration."""

    dashscope_api_key: str
    dashscope_base_url: str
    oss_access_key_id: str | None
    oss_access_key_secret: str | None
    oss_bucket: str
    oss_region: str
    oss_endpoint: str
    hf_token: str | None
    gpt_api_key: str | None

    @classmethod
    def from_env(cls) -> "APIKeys":
        return cls(
            dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY", ""),
            dashscope_base_url=os.environ.get(
                "DASHSCOPE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            oss_access_key_id=os.environ.get("OSS_ACCESS_KEY_ID"),
            oss_access_key_secret=os.environ.get("OSS_ACCESS_KEY_SECRET"),
            oss_bucket=os.environ.get("OSS_BUCKET", "speaker-color-test"),
            oss_region=os.environ.get("OSS_REGION", "cn-beijing"),
            oss_endpoint=os.environ.get("OSS_ENDPOINT", "oss-cn-beijing.aliyuncs.com"),
            hf_token=os.environ.get("HF_TOKEN"),
            gpt_api_key=os.environ.get("GPT_API_KEY"),
        )


# Default instances
DEFAULT_PATHS = Paths.from_env()
DEFAULT_API_KEYS = APIKeys.from_env()
