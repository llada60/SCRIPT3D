"""UI-only chatbot persona metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any


ASSET_DIR = Path(__file__).resolve().parent / "assets"


def _asset_path(filename: str) -> str:
    return str(ASSET_DIR / filename)


USER_AVATAR = _asset_path("avatar_user_circle.png")
GENERATION_AGENT_AVATAR = _asset_path("avatar_generation_agent_circle.png")
VISUAL_VERIFIER_AVATAR = _asset_path("avatar_visual_verifier_circle.png")


PERSONAS = {
    "user": {
        "header": "user",
        "avatar": USER_AVATAR,
        "placement": "end",
        "shape": "round",
        "variant": "borderless",
    },
    "generation": {
        "header": "3D Generation Agent",
        "avatar": GENERATION_AGENT_AVATAR,
        "placement": "start",
        "shape": "round",
        "variant": "borderless",
    },
    "verifier": {
        "header": "Visual Verifier Agent",
        "avatar": VISUAL_VERIFIER_AVATAR,
        "placement": "start",
        "shape": "round",
        "variant": "borderless",
    },
}


def apply_persona(message: dict[str, Any], persona: str) -> dict[str, Any]:
    message.update(PERSONAS[persona])
    return message


def user_message(content: Any, **extra: Any) -> dict[str, Any]:
    return apply_persona({"role": "user", "content": content, **extra}, "user")


def generation_message(content: Any = None, **extra: Any) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", **extra}
    if content is not None:
        message["content"] = content
    return apply_persona(message, "generation")


def verifier_message(content: Any = None, **extra: Any) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", **extra}
    if content is not None:
        message["content"] = content
    return apply_persona(message, "verifier")
