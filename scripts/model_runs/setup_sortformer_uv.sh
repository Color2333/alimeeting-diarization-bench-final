#!/bin/bash
# Build an isolated uv environment for NVIDIA NeMo Sortformer inference.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT_DIR/.uv-cache}"
UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$ROOT_DIR/.uv-python}"

cd "$ROOT_DIR"

UV_CACHE_DIR="$UV_CACHE_DIR" \
UV_PYTHON_INSTALL_DIR="$UV_PYTHON_INSTALL_DIR" \
uv venv .venv_sortformer --python 3.11

UV_CACHE_DIR="$UV_CACHE_DIR" \
UV_PYTHON_INSTALL_DIR="$UV_PYTHON_INSTALL_DIR" \
uv pip install --python .venv_sortformer/bin/python 'nemo_toolkit[asr]'

UV_CACHE_DIR="$UV_CACHE_DIR" \
UV_PYTHON_INSTALL_DIR="$UV_PYTHON_INSTALL_DIR" \
uv pip install --python .venv_sortformer/bin/python \
  -e . --no-deps meeteval kaldialign openai dashscope oss2 python-dotenv \
  crcmod aliyun-python-sdk-kms aliyun-python-sdk-core pycryptodome \
  jmespath cryptography

UV_CACHE_DIR="$UV_CACHE_DIR" \
UV_PYTHON_INSTALL_DIR="$UV_PYTHON_INSTALL_DIR" \
uv pip install --python .venv_sortformer/bin/python --reinstall openai dashscope

MPLCONFIGDIR=/private/tmp/matplotlib .venv_sortformer/bin/python - <<'PY'
from nemo.collections.asr.models import SortformerEncLabelModel
print("Sortformer uv environment is ready:", SortformerEncLabelModel)
PY
