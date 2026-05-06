"""Command-line interface for the Infinigen Blender agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import InfinigenAgent
from .client import BlenderClient
from .config import get_settings
from .infinigen_runner import InfinigenRunner


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ping")
    sub.add_parser("chat").add_argument("text")
    sub.add_parser("index")

    render = sub.add_parser("render")
    render.add_argument("--path", default=None)

    open_cmd = sub.add_parser("open")
    open_cmd.add_argument("blend_path")

    bedroom = sub.add_parser("generate-bedroom")
    bedroom.add_argument("--output", required=True)
    bedroom.add_argument("--seed", type=int, default=0)

    args = parser.parse_args()
    settings = get_settings()
    client = BlenderClient(settings)

    if args.command == "ping":
        print(json.dumps(client.ping(), ensure_ascii=False, indent=2))
    elif args.command == "chat":
        result = InfinigenAgent(client).handle(args.text)
        print(result.text)
        if result.preview_path:
            print(result.preview_path)
    elif args.command == "index":
        print(json.dumps(client.rebuild_scene_index(), ensure_ascii=False, indent=2))
    elif args.command == "render":
        path = Path(args.path) if args.path else settings.render_dir / "preview.png"
        print(json.dumps(client.render_scene(path=path), ensure_ascii=False, indent=2))
    elif args.command == "open":
        print(json.dumps(client.open_blend(args.blend_path), ensure_ascii=False, indent=2))
        print(json.dumps(client.rebuild_scene_index(), ensure_ascii=False, indent=2))
    elif args.command == "generate-bedroom":
        run = InfinigenRunner(settings).generate_single_bedroom(args.output, seed=args.seed)
        print(" ".join(run.command))
        print(run.stdout)
        if run.stderr:
            print(run.stderr)
        raise SystemExit(run.returncode)


if __name__ == "__main__":
    main()
