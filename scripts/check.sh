#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$task_root"
bash scripts/dev.sh run --locked ruff check pytrtt scripts tests
bash scripts/dev.sh run --locked ruff format --check pytrtt scripts tests
bash scripts/dev.sh run --locked mypy
bash scripts/dev.sh run --locked pymarkdown --config .pymarkdown.json scan \
  README.md AGENTS.md AGENTS.md.1 ai-guidance/*.md ai-guidance/*/*.md
bash scripts/dev.sh run --locked pytest
