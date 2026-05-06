"""Small smoke test for the Infinigen Agent Blender socket client."""

from __future__ import annotations

import json

from .client import BlenderClient


def main() -> None:
    client = BlenderClient()
    print(json.dumps(client.get_scene_info(), ensure_ascii=False, indent=2))
    print(json.dumps(client.rebuild_scene_index(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
