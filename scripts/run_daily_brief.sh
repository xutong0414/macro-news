#!/usr/bin/env bash
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "${script_dir}/.." && pwd)"

cd "$repo_root"

python_bin="${PYTHON_BIN:-python3}"
export PYTHONPATH="${repo_root}/src:${PYTHONPATH:-}"

"$python_bin" -m macro_news run \
  --send \
  --use-llm \
  --live-market-data \
  --live-calendar \
  --live-theme-radar \
  "$@"
