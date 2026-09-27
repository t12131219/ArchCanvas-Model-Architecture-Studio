#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${repository_dir}/.venv/bin/python"

if [[ ! -x "${python_bin}" ]]; then
  python_bin="$(command -v python3 || command -v python)"
fi

exec "${python_bin}" "${repository_dir}/tools/start_studio.py" "$@"
