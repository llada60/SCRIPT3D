"""Client for the GOSIM Blender addon socket server."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

from .config import Settings, get_settings
from .protocol import decode_response, encode_request


class BlenderClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def request(self, command: str, payload: dict[str, Any] | None = None) -> Any:
        data = encode_request(command, payload)
        with socket.create_connection(
            (self.settings.host, self.settings.port),
            timeout=self.settings.socket_timeout_s,
        ) as sock:
            sock.settimeout(self.settings.socket_timeout_s)
            sock.sendall(data)
            sock.shutdown(socket.SHUT_WR)
            chunks: list[bytes] = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        return decode_response(b"".join(chunks)).require_ok()

    def ping(self) -> Any:
        return self.request("ping")

    def open_blend(self, path: str | Path) -> Any:
        return self.request("open_blend", {"path": str(path)})

    def save_blend(self, path: str | Path | None = None) -> Any:
        return self.request("save_blend", {"path": str(path) if path else None})

    def get_scene_info(self) -> Any:
        return self.request("get_scene_info")

    def rebuild_scene_index(self, save_path: str | Path | None = None) -> Any:
        return self.request(
            "rebuild_scene_index",
            {"save_path": str(save_path) if save_path else None},
        )

    def query_objects(self, text: str = "", category: str | None = None) -> Any:
        return self.request("query_objects", {"text": text, "category": category})

    def add_infinigen_asset(
        self,
        category_or_factory: str,
        seed: int = 0,
        location: tuple[float, float, float] | None = None,
        scale: float = 1.0,
    ) -> Any:
        return self.request(
            "add_infinigen_asset",
            {
                "category_or_factory": category_or_factory,
                "seed": seed,
                "location": list(location or (0.0, 0.0, 0.0)),
                "scale": scale,
            },
        )

    def move_object(self, target: str, direction: str, distance: float) -> Any:
        return self.request(
            "move_object",
            {"target": target, "direction": direction, "distance": distance},
        )

    def scale_object(self, target: str, factor: float) -> Any:
        return self.request("scale_object", {"target": target, "factor": factor})

    def rotate_object(self, target: str, axis: str, angle_degrees: float) -> Any:
        return self.request(
            "rotate_object",
            {"target": target, "axis": axis, "angle_degrees": angle_degrees},
        )

    def delete_object(self, target: str) -> Any:
        return self.request("delete_object", {"target": target})

    def set_material(
        self,
        target: str,
        color: str | None = None,
        material_name: str | None = None,
    ) -> Any:
        return self.request(
            "set_material",
            {"target": target, "color": color, "material_name": material_name},
        )

    def place_on(self, source: str, target: str) -> Any:
        return self.request("place_on", {"source": source, "target": target})

    def place_near(self, source: str, target: str, side: str = "right", gap: float = 0.2) -> Any:
        return self.request(
            "place_near",
            {"source": source, "target": target, "side": side, "gap": gap},
        )

    def place_against_wall(self, target: str, wall: str | None = None, gap: float = 0.05) -> Any:
        return self.request(
            "place_against_wall",
            {"target": target, "wall": wall, "gap": gap},
        )

    def render_scene(self, path: str | Path | None = None, resolution: tuple[int, int] = (1280, 720)) -> Any:
        return self.request(
            "render_scene",
            {
                "path": str(path) if path else None,
                "resolution": list(resolution),
            },
        )

