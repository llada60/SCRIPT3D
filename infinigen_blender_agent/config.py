"""Runtime configuration for the external agent process."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INFINIGEN_ROOT = PROJECT_ROOT / "third_party" / "infinigen"
DEFAULT_BLENDER_BIN = DEFAULT_INFINIGEN_ROOT / "Blender.app/Contents/MacOS/Blender"


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("INFINIGEN_AGENT_BLENDER_HOST", "127.0.0.1")
    port: int = int(os.getenv("INFINIGEN_AGENT_BLENDER_PORT", "9876"))
    infinigen_root: Path = Path(os.getenv("INFINIGEN_AGENT_INFINIGEN_ROOT", DEFAULT_INFINIGEN_ROOT))
    blender_bin: Path = Path(os.getenv("INFINIGEN_AGENT_BLENDER_BIN", DEFAULT_BLENDER_BIN))
    render_dir: Path = Path(os.getenv("INFINIGEN_AGENT_RENDER_DIR", PROJECT_ROOT / "renders"))
    socket_timeout_s: float = float(os.getenv("INFINIGEN_AGENT_SOCKET_TIMEOUT", "120"))


def get_settings() -> Settings:
    return Settings()
