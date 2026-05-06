"""Blender addon entrypoint for the standalone Infinigen project.

This replaces the original LLM-Blender-Agent Rodin/Hunyuan addon entry with the
Infinigen-aware addon while keeping the expected root `addon.py` filename.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


_ADDON_PATH = Path(__file__).resolve().parent / "blender_addon" / "infinigen_agent_addon.py"
_SPEC = importlib.util.spec_from_file_location("infinigen_agent_addon", _ADDON_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)

bl_info = _MODULE.bl_info


def register():
    _MODULE.register()


def unregister():
    _MODULE.unregister()


if __name__ == "__main__":
    register()
