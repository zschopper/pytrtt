#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="$task_root/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$task_root/.tools/python"
export UV_PYTHON_BIN_DIR="$task_root/.tools/bin"
export UV_NO_MODIFY_PATH=1
cd -- "$task_root"
export PYENV_ROOT="$task_root/.tools/pyenv"
export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
export UV_PYTHON="$("$PYENV_ROOT/bin/pyenv" which python)"
export UV_PYTHON_DOWNLOADS=never
exec "$task_root/.tools/bin/uv" "$@"
