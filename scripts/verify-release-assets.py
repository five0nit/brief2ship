#!/usr/bin/env python3
"""Verify the exact Brief2Ship release assets and SHA256SUMS contract."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import re
import sys
from pathlib import Path

_HASH_LINE = re.compile(r"(?P<digest>[0-9a-f]{64})  (?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(directory: Path, version: str) -> tuple[str, str]:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError(f"invalid release version: {version!r}")
    if not directory.is_dir():
        raise ValueError(f"release directory does not exist: {directory}")

    wheel = f"brief2ship-{version}-py3-none-any.whl"
    sdist = f"brief2ship-{version}.tar.gz"
    expected = {wheel, sdist, "SHA256SUMS"}
    actual = {path.name for path in directory.iterdir()}
    if actual != expected:
        raise ValueError(
            f"release directory must contain exactly {sorted(expected)!r}; observed {sorted(actual)!r}"
        )

    for name in expected:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"release asset must be a regular non-symlink file: {name}")

    lines = (directory / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    if len(lines) != 2:
        raise ValueError(f"SHA256SUMS must contain exactly two lines; observed {len(lines)}")

    declared: dict[str, str] = {}
    for line in lines:
        match = _HASH_LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid SHA256SUMS line: {line!r}")
        name = match.group("name")
        if name in declared:
            raise ValueError(f"duplicate SHA256SUMS entry: {name}")
        declared[name] = match.group("digest")

    if set(declared) != {wheel, sdist}:
        raise ValueError(
            f"SHA256SUMS must name exactly {[wheel, sdist]!r}; observed {sorted(declared)!r}"
        )

    for name, expected_digest in declared.items():
        observed = _sha256(directory / name)
        if not hmac.compare_digest(observed, expected_digest):
            raise ValueError(
                f"SHA-256 mismatch for {name}: expected {expected_digest}, observed {observed}"
            )

    return wheel, sdist


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    try:
        wheel, sdist = verify(args.directory, args.version)
    except ValueError as exc:
        print(f"release asset verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"Release assets verified: {wheel}, {sdist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
