#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFINIGEN_ROOT="${INFINIGEN_AGENT_INFINIGEN_ROOT:-$ROOT/third_party/infinigen}"
BLENDER_BIN="${INFINIGEN_AGENT_BLENDER_BIN:-$INFINIGEN_ROOT/Blender.app/Contents/MacOS/Blender}"
PYTHON_BIN="${INFINIGEN_AGENT_PYTHON:-}"

if [[ -z "$PYTHON_BIN" && -x "/opt/miniconda3/envs/infinigen/bin/python" ]]; then
  PYTHON_BIN="/opt/miniconda3/envs/infinigen/bin/python"
fi
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi

export INFINIGEN_AGENT_INFINIGEN_ROOT="$INFINIGEN_ROOT"
export INFINIGEN_AGENT_BLENDER_HOST="${INFINIGEN_AGENT_BLENDER_HOST:-127.0.0.1}"
export INFINIGEN_AGENT_BLENDER_PORT="${INFINIGEN_AGENT_BLENDER_PORT:-9876}"
export PYTHONNOUSERSITE="${PYTHONNOUSERSITE:-1}"

if [[ -n "$PYTHON_BIN" ]]; then
  INFINIGEN_AGENT_PYTHON_SITE_PACKAGES="$("$PYTHON_BIN" - <<'PY'
import os
import site

paths = []
for getter in (site.getsitepackages, lambda: [site.getusersitepackages()]):
    try:
        paths.extend(getter())
    except Exception:
        pass

seen = set()
existing = []
for path in paths:
    if path and path not in seen and os.path.isdir(path):
        seen.add(path)
        existing.append(path)

print(os.pathsep.join(existing))
PY
)"
  export INFINIGEN_AGENT_PYTHON_SITE_PACKAGES
  if [[ -n "$INFINIGEN_AGENT_PYTHON_SITE_PACKAGES" ]]; then
    export PYTHONPATH="$INFINIGEN_AGENT_PYTHON_SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
  fi
fi

exec "$BLENDER_BIN" --python "$ROOT/addon.py" "$@"
