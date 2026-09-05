#!/usr/bin/env python3
"""Run the full release contract from the built source archive."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="brief2ship-sdist-check-") as temporary:
        destination = Path(temporary)
        with tarfile.open(args.archive, "r:gz") as archive:
            archive.extractall(destination, filter="data")
        roots = list(destination.iterdir())
        if len(roots) != 1 or not roots[0].is_dir():
            raise RuntimeError("source archive must contain exactly one project root")
        result = subprocess.run(
            [sys.executable, "scripts/validate-release.py"], cwd=roots[0], env=environment, check=False,
        )
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
