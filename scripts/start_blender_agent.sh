#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFINIGEN_ROOT="${GOSIM_INFINIGEN_ROOT:-$ROOT/third_party/infinigen}"
BLENDER_BIN="${GOSIM_BLENDER_BIN:-$INFINIGEN_ROOT/Blender.app/Contents/MacOS/Blender}"

export GOSIM_INFINIGEN_ROOT="$INFINIGEN_ROOT"
export GOSIM_BLENDER_HOST="${GOSIM_BLENDER_HOST:-127.0.0.1}"
export GOSIM_BLENDER_PORT="${GOSIM_BLENDER_PORT:-9876}"
export PYTHONNOUSERSITE="${PYTHONNOUSERSITE:-1}"

exec "$BLENDER_BIN" --python "$ROOT/addon.py" "$@"
