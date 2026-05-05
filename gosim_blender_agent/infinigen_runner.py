"""Out-of-process helpers for generating Infinigen scenes and assets."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import Settings, get_settings


@dataclass(frozen=True)
class CompletedRun:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


class InfinigenRunner:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def generate_single_bedroom(self, output_folder: str | Path, seed: int = 0) -> CompletedRun:
        output = Path(output_folder)
        cmd = [
            sys.executable,
            "-m",
            "infinigen.launch_blender",
            "-m",
            "infinigen_examples.generate_indoors",
            "--",
            "--seed",
            str(seed),
            "--task",
            "coarse",
            "--output_folder",
            str(output),
            "-g",
            "fast_solve.gin",
            "singleroom.gin",
            "-p",
            "compose_indoors.terrain_enabled=False",
            "restrict_solving.restrict_parent_rooms='[\"Bedroom\"]'",
            "compose_indoors.solve_steps_large=80",
            "compose_indoors.solve_steps_medium=80",
            "compose_indoors.solve_steps_small=80",
        ]
        return self._run(cmd)

    def generate_asset(self, factory: str, output_folder: str | Path, seed: int = 0) -> CompletedRun:
        cmd = [
            sys.executable,
            "-m",
            "infinigen.launch_blender",
            "-m",
            "infinigen_examples.generate_individual_assets",
            "--",
            "-o",
            str(output_folder),
            "-f",
            factory,
            "-n",
            "1",
            "--seed",
            str(seed),
            "--save_blend",
            "-r",
            "none",
        ]
        return self._run(cmd)

    def _run(self, cmd: list[str]) -> CompletedRun:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.settings.infinigen_root) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            cmd,
            cwd=self.settings.infinigen_root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return CompletedRun(cmd=cmd, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)

