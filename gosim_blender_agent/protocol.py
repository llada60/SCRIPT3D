"""Small JSON-over-TCP protocol shared by the agent and Blender addon."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Request:
    command: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class Response:
    ok: bool
    result: Any = None
    error: str | None = None

    def require_ok(self) -> Any:
        if not self.ok:
            raise RuntimeError(self.error or "Blender command failed")
        return self.result


def encode_request(command: str, payload: dict[str, Any] | None = None) -> bytes:
    body = {"command": command, "payload": payload or {}}
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


def decode_response(data: bytes) -> Response:
    raw = json.loads(data.decode("utf-8"))
    return Response(ok=bool(raw.get("ok")), result=raw.get("result"), error=raw.get("error"))

