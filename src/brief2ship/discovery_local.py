"""Bounded, read-only discovery of existing local project roots."""

from __future__ import annotations

import configparser
import os
import re
import stat
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from .discovery_models import Candidate, SourceReceipt
from .discovery_providers import canonical_repository_url
from .discovery_scoring import tokenize

_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "target",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
_PROJECT_MARKERS = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "package.json",
    "cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "composer.json",
    "gemfile",
    "mix.exs",
}
_MAX_ROOTS = 5
_MAX_DIRECTORIES = 10_000
_MAX_CANDIDATES = 500
_MAX_ENTRIES_PER_DIRECTORY = 10_000
_MAX_FILES_PER_DIRECTORY = 2_000
_MAX_DEPTH = 16
_MAX_READ_BYTES = 65_536
_UNSAFE_CONTROLS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]"
)


def _safe_text(path: Path) -> str:
    descriptor: int | None = None
    try:
        before = os.lstat(path)
        if stat.S_ISLNK(before.st_mode):
            return ""
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_size > _MAX_READ_BYTES
            or (before.st_dev, before.st_ino) != (observed.st_dev, observed.st_ino)
        ):
            return ""
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = None
            data = handle.read(_MAX_READ_BYTES + 1)
        if len(data) > _MAX_READ_BYTES:
            return ""
        return _UNSAFE_CONTROLS.sub("", data.decode("utf-8", errors="replace"))
    except OSError:
        return ""
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _description(path: Path) -> str:
    for name in ("README.md", "README.rst", "README.txt", "README"):
        text = _safe_text(path / name)
        if not text:
            continue
        for raw in text.splitlines()[:20]:
            line = re.sub(r"^[#=*`>\-\s]+", "", raw).strip()
            if line:
                return re.sub(r"\s+", " ", line)[:240]
    return "Local workspace project"


def _license(path: Path) -> str | None:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md"):
        text = _safe_text(path / name).lower()
        if not text:
            continue
        if "mit license" in text:
            return "MIT"
        if "apache license" in text and "version 2" in text:
            return "Apache-2.0"
        if "mozilla public license" in text and "2.0" in text:
            return "MPL-2.0"
        if "gnu general public license" in text:
            return "GPL"
        if "redistribution and use in source and binary forms" in text:
            return "BSD"
        return None
    return None


def _language(markers: set[str], filenames: set[str]) -> str | None:
    if {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"} & markers:
        return "Python"
    if "package.json" in markers:
        return "JavaScript"
    if "cargo.toml" in markers:
        return "Rust"
    if "go.mod" in markers:
        return "Go"
    if {"pom.xml", "build.gradle", "build.gradle.kts"} & markers:
        return "Java"
    suffixes = {Path(name).suffix.lower() for name in filenames}
    for suffix, language in (
        (".py", "Python"),
        (".ts", "TypeScript"),
        (".js", "JavaScript"),
        (".rs", "Rust"),
        (".go", "Go"),
        (".java", "Java"),
        (".kt", "Kotlin"),
    ):
        if suffix in suffixes:
            return language
    return None


def _origin_remote(path: Path) -> str | None:
    git_directory = path / ".git"
    if git_directory.is_symlink() or not git_directory.is_dir():
        return None
    config_path = git_directory / "config"
    try:
        git_root = git_directory.resolve(strict=True)
        resolved_config = config_path.resolve(strict=True)
    except OSError:
        return None
    if not resolved_config.is_relative_to(git_root):
        return None
    text = _safe_text(config_path)
    if not text:
        return None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(text)
    except configparser.Error:
        return None
    section = 'remote "origin"'
    if not parser.has_option(section, "url"):
        return None
    return canonical_repository_url(parser.get(section, "url", fallback=""))


def _updated_at(path: Path, marker_names: set[str]) -> str | None:
    observed: list[float] = []
    for name in sorted(marker_names | {"readme.md", "license"}):
        candidate = path / name
        try:
            if candidate.is_file() and not candidate.is_symlink():
                observed.append(candidate.stat().st_mtime)
        except OSError:
            continue
    try:
        observed.append(path.stat().st_mtime)
    except OSError:
        pass
    if not observed:
        return None
    return datetime.fromtimestamp(max(observed), timezone.utc).isoformat()


def _candidate(path: Path, root: Path, query_tokens: set[str], filenames: set[str]) -> Candidate | None:
    marker_names = {name for name in filenames if name in _PROJECT_MARKERS}
    has_git = (path / ".git").is_dir() or (path / ".git").is_file()
    if not marker_names and not has_git:
        return None
    description = _description(path)
    language = _language(marker_names, filenames)
    relative = path.relative_to(root)
    display = path.name if relative == Path(".") else relative.as_posix()
    haystack = tokenize(" ".join((display, description, language or "", " ".join(marker_names))))
    overlap = len(query_tokens & haystack)
    if query_tokens and overlap == 0:
        return None
    all_match = bool(query_tokens) and query_tokens <= haystack
    repository_url = _origin_remote(path)
    local_path = str(path.resolve())
    test_signals = []
    try:
        child_directories = {
            child.name.lower()
            for child in path.iterdir()
            if child.is_dir() and not child.is_symlink()
        }
    except OSError:
        child_directories = set()
    if "tests" in child_directories:
        test_signals.append("repository test files")
    return Candidate(
        source="local",
        name=f"local/{path.name}",
        url=path.resolve().as_uri(),
        local_path=local_path,
        repository_url=repository_url,
        description=description,
        license=_license(path),
        updated_at=_updated_at(path, marker_names),
        language=language,
        topics=sorted(marker_names),
        security_policy=(path / "SECURITY.md").is_file(),
        test_signals=test_signals,
        portability_signals=[f"local {language} project"] if language else ["local project"],
        reuse_signals=["existing local workspace", "project manifest"],
        raw_relevance=float(overlap + (100 if all_match else 0)),
        aliases=[local_path],
    )


def search_local(
    query: str,
    roots: list[str] | tuple[str, ...],
    *,
    limit: int,
    timeout_seconds: float = 60.0,
    monotonic: Callable[[], float] = time.monotonic,
) -> tuple[list[Candidate], SourceReceipt]:
    receipt = SourceReceipt("local", "ok", limit)
    if not roots:
        receipt.status = "failed"
        receipt.error = "local source requires at least one local root"
        return [], receipt
    if len(roots) > _MAX_ROOTS:
        receipt.status = "failed"
        receipt.error = f"local source accepts at most {_MAX_ROOTS} roots"
        return [], receipt

    resolved_roots: list[Path] = []
    for value in roots:
        path = Path(value).expanduser().resolve()
        if not path.is_dir():
            receipt.warnings.append(f"local root is not a directory: {path}")
            continue
        resolved_roots.append(path)
        receipt.endpoints.append(str(path))
    if not resolved_roots:
        receipt.status = "failed"
        receipt.error = receipt.warnings[0] if receipt.warnings else "no valid local roots"
        return [], receipt

    query_tokens = tokenize(query)
    found: list[Candidate] = []
    directories = 0
    deadline = monotonic() + timeout_seconds
    queues: list[deque[tuple[Path, int]]] = [
        deque([(root, 0)]) for root in resolved_roots
    ]
    seen_directories: set[Path] = set()
    warned: set[str] = set()
    stop_reason: str | None = None

    def warn_once(key: str, message: str) -> None:
        if key not in warned:
            warned.add(key)
            receipt.warnings.append(message)

    while any(queues) and stop_reason is None:
        for root, queue in zip(resolved_roots, queues, strict=True):
            if not queue:
                continue
            if directories >= _MAX_DIRECTORIES:
                stop_reason = f"directory cap {_MAX_DIRECTORIES}"
                break
            if monotonic() >= deadline:
                stop_reason = f"deadline {timeout_seconds:.2f}s"
                break
            path, depth = queue.popleft()
            if path in seen_directories:
                continue
            seen_directories.add(path)
            directories += 1

            entries: list[os.DirEntry[str]] = []
            try:
                with os.scandir(path) as scanner:
                    for entry in scanner:
                        if monotonic() >= deadline:
                            stop_reason = f"deadline {timeout_seconds:.2f}s"
                            break
                        if len(entries) >= _MAX_ENTRIES_PER_DIRECTORY:
                            warn_once(
                                "entry-cap",
                                f"local directory entry cap {_MAX_ENTRIES_PER_DIRECTORY} reached",
                            )
                            break
                        entries.append(entry)
            except OSError:
                continue
            if stop_reason is not None:
                break
            entries.sort(key=lambda entry: entry.name.lower())
            filenames: set[str] = set()
            child_directories: list[Path] = []
            for entry in entries:
                name = entry.name
                try:
                    if entry.is_file(follow_symlinks=False):
                        if len(filenames) < _MAX_FILES_PER_DIRECTORY:
                            filenames.add(name.lower())
                        else:
                            warn_once(
                                "file-cap",
                                f"local file-name cap {_MAX_FILES_PER_DIRECTORY} reached",
                            )
                    elif (
                        entry.is_dir(follow_symlinks=False)
                        and name not in _SKIP_DIRS
                        and not name.startswith(".")
                    ):
                        child_directories.append(Path(entry.path))
                except OSError:
                    continue
            if depth < _MAX_DEPTH:
                queue.extend((child, depth + 1) for child in child_directories)
            elif child_directories:
                warn_once(
                    "depth-cap",
                    f"local scan depth cap {_MAX_DEPTH} reached",
                )

            candidate = _candidate(path, root, query_tokens, filenames)
            if candidate is not None:
                found.append(candidate)
                if len(found) >= _MAX_CANDIDATES:
                    stop_reason = f"candidate cap {_MAX_CANDIDATES}"
                    break
    if stop_reason:
        receipt.warnings.append(
            f"local scan stopped at {stop_reason}"
        )

    found.sort(
        key=lambda candidate: (
            -(candidate.raw_relevance or 0.0),
            candidate.name.lower(),
            candidate.local_path or "",
        )
    )
    candidates = found[:limit]
    receipt.returned = len(candidates)
    if not candidates:
        receipt.status = "empty"
    return candidates, receipt
