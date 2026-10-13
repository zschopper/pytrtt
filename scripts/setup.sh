#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$task_root"
mkdir -p .tools/bin
if [[ ! -x .tools/bin/uv ]]; then
    curl -LsSf https://astral.sh/uv/0.13.0/install.sh -o .tools/uv-install.sh
    UV_UNMANAGED_INSTALL="$task_root/.tools/bin" sh .tools/uv-install.sh
fi
export UV_CACHE_DIR="$task_root/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$task_root/.tools/python"
export UV_PYTHON_BIN_DIR="$task_root/.tools/bin"
export UV_NO_MODIFY_PATH=1
.tools/bin/uv python install 3.13.16
if [[ ! -x .tools/pyenv/bin/pyenv ]]; then
    git clone https://github.com/pyenv/pyenv.git .tools/pyenv
    git -C .tools/pyenv checkout --detach d28b750767d440d9ecabac0fef487eb8baf86a08
fi
mkdir -p .tools/pyenv/versions
if [[ ! -e .tools/pyenv/versions/3.13.16 ]]; then
    ln -s ../../python/cpython-3.13-linux-x86_64-gnu .tools/pyenv/versions/3.13.16
fi
PYENV_ROOT="$task_root/.tools/pyenv" .tools/pyenv/bin/pyenv rehash
bash scripts/dev.sh sync --locked --all-groups
bash scripts/check.sh
