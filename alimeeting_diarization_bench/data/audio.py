"""
Audio processing utilities.
"""

import tempfile
from pathlib import Path
from typing import Tuple

import numpy as np
import soundfile as sf


def slice_audio(
    audio_path: str | Path,
    offset: float,
    duration: float,
    channel: int = 0,
    sr: int = 16000,
) -> Tuple[np.ndarray, int]:
    audio_path = Path(audio_path)
    start_sample = int(offset * sr)
    num_samples = int(duration * sr)

    audio, _ = sf.read(
        audio_path,
        start=start_sample,
        frames=num_samples,
        dtype="float32",
    )

    if audio.ndim > 1:
        audio = audio[:, channel]

    return audio, sr


def save_temp_clip(
    audio: np.ndarray,
    sr: int,
    suffix: str = ".wav",
    delete: bool = False,
) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=delete)
    sf.write(tmp.name, audio, sr)
    tmp.close()
    return tmp.name


def slice_and_save_temp(
    audio_path: str | Path,
    offset: float,
    duration: float,
    channel: int = 0,
    sr: int = 16000,
) -> str:
    audio, sr = slice_audio(audio_path, offset, duration, channel, sr)
    return save_temp_clip(audio, sr)
