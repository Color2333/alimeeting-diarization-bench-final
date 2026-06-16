#!/bin/bash
# Build an isolated uv environment for DiariZen inference.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DIARIZEN_SRC="${DIARIZEN_SRC:-/private/tmp/diarizen_src}"
UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT_DIR/.uv-cache}"
UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$ROOT_DIR/.uv-python}"

cd "$ROOT_DIR"

if [ ! -d "$DIARIZEN_SRC" ]; then
  git clone --depth 1 https://github.com/BUTSpeechFIT/DiariZen.git "$DIARIZEN_SRC"
fi

UV_CACHE_DIR="$UV_CACHE_DIR" \
UV_PYTHON_INSTALL_DIR="$UV_PYTHON_INSTALL_DIR" \
uv venv .venv_diarizen --python 3.10

UV_CACHE_DIR="$UV_CACHE_DIR" \
UV_PYTHON_INSTALL_DIR="$UV_PYTHON_INSTALL_DIR" \
uv pip install --python .venv_diarizen/bin/python \
  'torch==2.1.1' 'torchaudio==2.1.1' 'numpy==1.26.4' \
  toml scipy soundfile huggingface_hub einops librosa matplotlib joblib \
  pandas pyyaml tqdm 'accelerate==1.6.0' h5py torchinfo tabulate flit

UV_CACHE_DIR="$UV_CACHE_DIR" \
UV_PYTHON_INSTALL_DIR="$UV_PYTHON_INSTALL_DIR" \
uv pip install --python .venv_diarizen/bin/python \
  -e "$DIARIZEN_SRC/pyannote-audio" -e "$DIARIZEN_SRC"

UV_CACHE_DIR="$UV_CACHE_DIR" \
UV_PYTHON_INSTALL_DIR="$UV_PYTHON_INSTALL_DIR" \
uv pip install --python .venv_diarizen/bin/python --reinstall \
  'torch==2.1.1' 'torchaudio==2.1.1'

UV_CACHE_DIR="$UV_CACHE_DIR" \
UV_PYTHON_INSTALL_DIR="$UV_PYTHON_INSTALL_DIR" \
uv pip install --python .venv_diarizen/bin/python \
  -e . --no-deps meeteval kaldialign openai dashscope oss2 python-dotenv \
  crcmod aliyun-python-sdk-kms aliyun-python-sdk-core pycryptodome

UV_CACHE_DIR="$UV_CACHE_DIR" \
UV_PYTHON_INSTALL_DIR="$UV_PYTHON_INSTALL_DIR" \
uv pip install --python .venv_diarizen/bin/python --reinstall openai dashscope

MPLCONFIGDIR=/private/tmp/matplotlib .venv_diarizen/bin/python - <<'PY'
from diarizen.pipelines.inference import DiariZenPipeline
print("DiariZen uv environment is ready:", DiariZenPipeline)
PY
