#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export INFINIGEN_AGENT_INFINIGEN_ROOT="${INFINIGEN_AGENT_INFINIGEN_ROOT:-$ROOT/third_party/infinigen}"
export INFINIGEN_AGENT_BLENDER_HOST="${INFINIGEN_AGENT_BLENDER_HOST:-127.0.0.1}"
export INFINIGEN_AGENT_BLENDER_PORT="${INFINIGEN_AGENT_BLENDER_PORT:-9876}"

PYTHON_BIN="${INFINIGEN_AGENT_PYTHON:-}"
if [[ -z "$PYTHON_BIN" && -x "/opt/miniconda3/envs/infinigen/bin/python" ]]; then
  PYTHON_BIN="/opt/miniconda3/envs/infinigen/bin/python"
fi
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || command -v python)"
fi

if ! "$PYTHON_BIN" -c "import gradio" >/dev/null 2>&1; then
  echo "Missing UI dependencies in $PYTHON_BIN"
  echo "Install them with:"
  echo "  $PYTHON_BIN -m pip install -r requirements.txt"
  exit 1
fi

exec "$PYTHON_BIN" -m ui.main
