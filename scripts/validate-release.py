#!/usr/bin/env python3
"""Run Brief2Ship's dependency-free release contract."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(label: str, command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f"==> {label}")
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def main() -> int:
    environment = os.environ.copy()
    source_path = str(ROOT / "src")
    environment["PYTHONPATH"] = source_path + os.pathsep + environment.get("PYTHONPATH", "")
    run("compile package", [sys.executable, "-m", "compileall", "-q", "src/brief2ship"])
    run(
        "module entrypoint",
        [sys.executable, "-m", "brief2ship", "--version"],
        env=environment,
    )
    run("documentation contract", [sys.executable, "scripts/validate-docs.py"])
    run(
        "unit and local integration tests",
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        env=environment,
    )
    run("task-quality regression benchmark", [sys.executable, "scripts/benchmark-discovery.py"], env=environment)
    print("Brief2Ship release validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
