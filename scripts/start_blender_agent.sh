#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFINIGEN_ROOT="${GOSIM_INFINIGEN_ROOT:-$ROOT/third_party/infinigen}"
BLENDER_BIN="${GOSIM_BLENDER_BIN:-$INFINIGEN_ROOT/Blender.app/Contents/MacOS/Blender}"
PYTHON_BIN="${GOSIM_PYTHON:-}"

if [[ -z "$PYTHON_BIN" && -x "/opt/miniconda3/envs/infinigen/bin/python" ]]; then
  PYTHON_BIN="/opt/miniconda3/envs/infinigen/bin/python"
fi
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi

export GOSIM_INFINIGEN_ROOT="$INFINIGEN_ROOT"
export GOSIM_BLENDER_HOST="${GOSIM_BLENDER_HOST:-127.0.0.1}"
export GOSIM_BLENDER_PORT="${GOSIM_BLENDER_PORT:-9876}"
export PYTHONNOUSERSITE="${PYTHONNOUSERSITE:-1}"

if [[ -n "$PYTHON_BIN" ]]; then
  GOSIM_PYTHON_SITE_PACKAGES="$("$PYTHON_BIN" - <<'PY'
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
  export GOSIM_PYTHON_SITE_PACKAGES
  if [[ -n "$GOSIM_PYTHON_SITE_PACKAGES" ]]; then
    export PYTHONPATH="$GOSIM_PYTHON_SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
  fi
fi

exec "$BLENDER_BIN" --python "$ROOT/addon.py" "$@"
