"""Bounded repository cloning, static inspection, and sandboxed test execution."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from collections import deque
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

from .discovery_http import DiscoveryHttpClient, DiscoverySourceError
from .discovery_licenses import read_license_evidence
from .discovery_models import Candidate, InspectionResult, TestReceipt
from .discovery_providers import canonical_repository_url

_MANIFEST_NAMES = {
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "requirements.txt",
    "package.json",
    "cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
}
_SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java", ".kt"}
_SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".venv", "venv", "__pycache__"}
_MAX_FILES = 20_000
_MAX_REPOSITORY_KB = 250_000
_MAX_READ_BYTES = 2_000_000
_MAX_DISK_FILES = 100_000
_MAX_ENTRIES_PER_DIRECTORY = 10_000
_MAX_INSPECTION_DIRECTORIES = 20_000
_MAX_INSPECTION_DEPTH = 32
_MAX_INSPECTION_SECONDS = 30.0


def _gnu_timeout_binary() -> str | None:
    """Return GNU timeout on POSIX; reject incompatible namesakes such as Windows timeout.exe."""
    if os.name != "posix":
        return None
    candidate = shutil.which("timeout")
    if not candidate:
        return None
    try:
        probe = subprocess.run(
            [candidate, "--version"],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    version_text = f"{probe.stdout}\n{probe.stderr}"
    return candidate if probe.returncode == 0 and "GNU coreutils" in version_text else None


def _clone_environment(home: str) -> dict[str, str]:
    """Build a secret-minimal Git environment while preserving required OS runtime roots."""
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "HOME": home,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "true",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_LFS_SKIP_SMUDGE": "1",
    }
    if os.name == "nt":
        for key in ("SYSTEMROOT", "WINDIR"):
            if value := os.environ.get(key):
                environment[key] = value
    return environment


def _github_identity(url: str | None) -> tuple[str, str] | None:
    canonical = canonical_repository_url(url)
    if not canonical:
        return None
    parts = urlsplit(canonical)
    if parts.hostname != "github.com":
        return None
    segments = [segment for segment in parts.path.split("/") if segment]
    return (segments[0], segments[1]) if len(segments) == 2 else None


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.")
    return cleaned[:100] or "candidate"


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
        return data.decode("utf-8", errors="replace")
    except OSError:
        return ""
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _bounded_tree_size(root: Path) -> int:
    total = 0
    files = 0
    directories = 0
    deadline = time.monotonic() + _MAX_INSPECTION_SECONDS
    queue: deque[tuple[Path, int]] = deque([(root, 0)])
    while queue:
        if time.monotonic() >= deadline or directories >= _MAX_INSPECTION_DIRECTORIES:
            return _MAX_REPOSITORY_KB * 1_024 + 1
        directory, depth = queue.popleft()
        directories += 1
        entries = 0
        try:
            with os.scandir(directory) as scanner:
                for entry in scanner:
                    entries += 1
                    if entries > _MAX_ENTRIES_PER_DIRECTORY:
                        return _MAX_REPOSITORY_KB * 1_024 + 1
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if depth >= _MAX_INSPECTION_DEPTH:
                                return _MAX_REPOSITORY_KB * 1_024 + 1
                            queue.append((Path(entry.path), depth + 1))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        files += 1
                        if files > _MAX_DISK_FILES:
                            return _MAX_REPOSITORY_KB * 1_024 + 1
                        total += entry.stat(follow_symlinks=False).st_size
                        if total > _MAX_REPOSITORY_KB * 1_024:
                            return total
                    except OSError:
                        return _MAX_REPOSITORY_KB * 1_024 + 1
        except OSError:
            return _MAX_REPOSITORY_KB * 1_024 + 1
    return total


def _detect_license(root: Path) -> str | None:
    return read_license_evidence(root, _safe_text)


def _dependencies_from_manifest(path: Path) -> int | None:
    text = _safe_text(path)
    if not text:
        return None
    name = path.name.lower()
    try:
        if name == "package.json":
            data = json.loads(text)
            return sum(
                len(data.get(key) or {})
                for key in ("dependencies", "peerDependencies", "optionalDependencies")
                if isinstance(data.get(key) or {}, dict)
            )
        if name in {"pyproject.toml", "cargo.toml"}:
            data = tomllib.loads(text)
            if name == "pyproject.toml":
                project = data.get("project") or {}
                poetry = ((data.get("tool") or {}).get("poetry") or {})
                poetry_dependencies = poetry.get("dependencies") or {}
                poetry_count = (
                    sum(1 for key in poetry_dependencies if str(key).lower() != "python")
                    if isinstance(poetry_dependencies, dict)
                    else 0
                )
                return len(project.get("dependencies") or []) + poetry_count
            dependencies = data.get("dependencies") or {}
            return len(dependencies) if isinstance(dependencies, dict) else None
        if name.startswith("requirements") and name.endswith(".txt"):
            return len(
                [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith(("#", "-r", "--"))]
            )
        if name == "go.mod":
            direct = len(re.findall(r"(?m)^\s*require\s+\S+\s+v\S+", text))
            blocks = re.findall(r"(?ms)^require\s*\((.*?)^\)", text)
            return direct + sum(len([line for line in block.splitlines() if line.strip()]) for block in blocks)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, TypeError, ValueError):
        return None
    return None


def _detect_test_command(root: Path, manifests: list[str], test_files: list[str]) -> list[str]:
    names = {Path(value).name.lower() for value in manifests}
    if "package.json" in names and Path("/usr/bin/npm").is_file():
        try:
            package = json.loads(_safe_text(root / "package.json"))
        except json.JSONDecodeError:
            package = {}
        script = (package.get("scripts") or {}).get("test") if isinstance(package, dict) else None
        if script and "no test specified" not in str(script).lower():
            return ["/usr/bin/npm", "test", "--offline", "--ignore-scripts"]
    if "cargo.toml" in names and Path("/usr/bin/cargo").is_file():
        return ["/usr/bin/cargo", "test", "--offline"]
    if "go.mod" in names and Path("/usr/bin/go").is_file():
        return ["/usr/bin/go", "test", "./..."]
    if test_files and any(path.endswith(".py") for path in test_files):
        python = "/usr/bin/python3" if Path("/usr/bin/python3").is_file() else sys.executable
        return [python, "-m", "unittest", "discover", "-s", "tests", "-v"]
    return []


def inspect_tree(root: Path, repository_url: str) -> InspectionResult:
    result = InspectionResult(repository_url=repository_url, clone_path=str(root), status="inspected")
    dependency_counts: list[int] = []
    file_count = 0
    language_suffixes: set[str] = set()
    feature_terms: set[str] = set()
    deadline = time.monotonic() + _MAX_INSPECTION_SECONDS
    directories = 0
    queue: deque[tuple[Path, int]] = deque([(root, 0)])
    stop = False
    warned: set[str] = set()

    def partial(key: str, message: str) -> None:
        result.status = "partial"
        if key not in warned:
            warned.add(key)
            result.warnings.append(message)

    while queue and not stop:
        if time.monotonic() >= deadline:
            partial("deadline", "inspection stopped at wall-clock deadline")
            break
        if directories >= _MAX_INSPECTION_DIRECTORIES:
            partial(
                "directories",
                f"inspection stopped at {_MAX_INSPECTION_DIRECTORIES} directories",
            )
            break
        directory, depth = queue.popleft()
        directories += 1
        entries: list[os.DirEntry[str]] = []
        try:
            with os.scandir(directory) as scanner:
                for entry in scanner:
                    if len(entries) >= _MAX_ENTRIES_PER_DIRECTORY:
                        partial(
                            "entries",
                            f"inspection directory entry cap {_MAX_ENTRIES_PER_DIRECTORY} reached",
                        )
                        break
                    entries.append(entry)
        except OSError as exc:
            partial("read-error", f"inspection skipped unreadable directory: {exc}")
            continue
        entries.sort(key=lambda entry: entry.name.lower())
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in _SKIP_DIRS:
                        continue
                    if depth >= _MAX_INSPECTION_DEPTH:
                        partial(
                            "depth",
                            f"inspection depth cap {_MAX_INSPECTION_DEPTH} reached",
                        )
                    else:
                        queue.append((Path(entry.path), depth + 1))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
            except OSError:
                partial("entry-error", "inspection skipped an unreadable filesystem entry")
                continue

            file_count += 1
            if file_count > _MAX_FILES:
                partial("files", f"inspection stopped at {_MAX_FILES} files")
                stop = True
                break
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            lower = relative.lower()
            filename = entry.name
            if path.suffix.lower() in _SOURCE_SUFFIXES:
                result.source_file_count += 1
                language_suffixes.add(path.suffix.lower())
            if filename.lower() in _MANIFEST_NAMES or lower.startswith("requirements") and lower.endswith(".txt"):
                result.manifest_files.append(relative)
                count = _dependencies_from_manifest(path)
                if count is not None:
                    dependency_counts.append(count)
            if lower.startswith(("tests/", "test/", "spec/", "specs/")) or re.search(r"(^|/)(test_|.*[._]test\.)", lower):
                if len(result.test_files) < 200:
                    result.test_files.append(relative)
            if lower.startswith(".github/workflows/") or lower in {".gitlab-ci.yml", "azure-pipelines.yml", "circle.yml"}:
                result.ci_files.append(relative)
            if lower.startswith(("docs/", "doc/")) or filename.lower().startswith("readme"):
                if len(result.docs_files) < 200:
                    result.docs_files.append(relative)
                if filename.lower().startswith("readme"):
                    feature_terms.update(re.findall(r"[a-z0-9][a-z0-9_.-]{1,40}", _safe_text(path).lower()))
            if lower.startswith(("examples/", "example/", "samples/", "demo/")):
                if len(result.example_files) < 200:
                    result.example_files.append(relative)
    result.dependency_count = sum(dependency_counts) if dependency_counts else None
    result.license = _detect_license(root)
    suffix_map = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".rs": "Rust", ".go": "Go", ".java": "Java", ".kt": "Kotlin"}
    result.languages = sorted({suffix_map[value] for value in language_suffixes if value in suffix_map})
    result.feature_terms = sorted(feature_terms)[:200]
    result.test_command = _detect_test_command(root, result.manifest_files, result.test_files)
    try:
        process = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if process.returncode == 0:
            result.commit = process.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return result


def run_sandboxed_tests(root: Path, command: list[str], *, timeout_seconds: int = 90) -> TestReceipt:
    if not command:
        return TestReceipt(status="blocked", limitation="no supported offline test command detected")
    bwrap = shutil.which("bwrap")
    prlimit = shutil.which("prlimit")
    timeout_command = shutil.which("timeout")
    if not bwrap or not prlimit or not timeout_command or os.name != "posix":
        return TestReceipt(
            status="blocked",
            command=command,
            sandbox="unavailable",
            limitation="Bubblewrap, prlimit, and timeout are required; unsafe fallback is forbidden",
        )
    current_tasks = 0
    proc = Path("/proc")
    if proc.is_dir():
        for status in proc.glob("[0-9]*/status"):
            try:
                values = status.read_text(encoding="utf-8", errors="replace").splitlines()
                if any(line.startswith("Uid:") and int(line.split()[1]) == os.getuid() for line in values):
                    current_tasks += len(list(status.parent.joinpath("task").iterdir()))
            except (OSError, ValueError, IndexError):
                continue
    process_limit = min(4_096, max(32, current_tasks + 16))
    temporary_workspace = Path(tempfile.mkdtemp(prefix="brief2ship-sandbox-"))
    execution_root = temporary_workspace / "work"
    empty_root = temporary_workspace / "empty"
    try:
        shutil.copytree(
            root,
            execution_root,
            symlinks=True,
            ignore=shutil.ignore_patterns(*_SKIP_DIRS),
        )
        empty_root.mkdir()
    except OSError as exc:
        shutil.rmtree(temporary_workspace, ignore_errors=True)
        return TestReceipt(
            status="blocked",
            command=command,
            sandbox="copy-failed",
            limitation=f"could not create disposable sandbox worktree: {exc}",
        )
    sandbox = [
        prlimit,
        f"--nproc={process_limit}",
        "--as=536870912",
        "--cpu=60",
        "--fsize=104857600",
        "--",
        timeout_command,
        "--signal=KILL",
        str(timeout_seconds),
        bwrap,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind-try",
        "/bin",
        "/bin",
        "--ro-bind-try",
        "/lib",
        "/lib",
        "--ro-bind-try",
        "/lib64",
        "/lib64",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--ro-bind",
        str(empty_root.resolve()),
        "/tmp",
        "--ro-bind",
        str(empty_root.resolve()),
        "/home",
        "--ro-bind",
        str(execution_root.resolve()),
        "/work",
        "--remount-ro",
        "/",
        "--chdir",
        "/work",
        "--setenv",
        "HOME",
        "/home",
        "--setenv",
        "PATH",
        "/usr/bin:/bin",
        "--setenv",
        "LANG",
        "C.UTF-8",
        "--setenv",
        "PIP_NO_INDEX",
        "1",
        "--setenv",
        "npm_config_offline",
        "true",
        "--setenv",
        "CARGO_NET_OFFLINE",
        "true",
        "--",
        *command,
    ]
    stdout_file = tempfile.NamedTemporaryFile(
        prefix="brief2ship-test-out-", dir=temporary_workspace, delete=False
    )
    stderr_file = tempfile.NamedTemporaryFile(
        prefix="brief2ship-test-err-", dir=temporary_workspace, delete=False
    )
    stdout_path, stderr_path = Path(stdout_file.name), Path(stderr_file.name)
    started = time.monotonic()
    try:
        with stdout_file, stderr_file:
            process = subprocess.run(
                sandbox,
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                timeout=timeout_seconds + 10,
                check=False,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            )
        duration = round(time.monotonic() - started, 3)
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")[-20_000:]
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")[-20_000:]
        combined = f"{stdout}\n{stderr}".lower()
        if process.returncode == 0 and re.search(r"ran 0 tests|no tests (?:ran|found)|\b0 passed\b", combined):
            status = "zero_tests"
        elif process.returncode == 0:
            status = "passed"
        elif process.returncode in {124, 137} and duration >= timeout_seconds * 0.9:
            status = "timeout"
        elif process.returncode < 0:
            status = "signaled"
        else:
            status = "failed"
        return TestReceipt(
            status=status,
            command=command,
            exit_code=process.returncode,
            duration_seconds=duration,
            stdout_tail=stdout,
            stderr_tail=stderr,
            sandbox="bubblewrap/no-network/cleared-env/disposable-worktree/read-only-filesystem/resource-limited",
        )
    except subprocess.TimeoutExpired as exc:
        return TestReceipt(
            status="timeout",
            command=command,
            duration_seconds=round(time.monotonic() - started, 3),
            stderr_tail=str(exc),
            sandbox="bubblewrap/no-network/cleared-env/disposable-worktree/read-only-filesystem/resource-limited",
        )
    except OSError as exc:
        return TestReceipt(
            status="sandbox_error",
            command=command,
            duration_seconds=round(time.monotonic() - started, 3),
            stderr_tail=str(exc),
            sandbox="bubblewrap/no-network/cleared-env/disposable-worktree/read-only-filesystem/resource-limited",
        )
    finally:
        stdout_path.unlink(missing_ok=True)
        stderr_path.unlink(missing_ok=True)
        shutil.rmtree(temporary_workspace, ignore_errors=True)


class RepositoryInspector:
    def __init__(self, client: DiscoveryHttpClient, root: Path) -> None:
        self.client = client
        self.root = root

    def _hydrate_github(self, candidate: Candidate) -> str | None:
        identity = _github_identity(candidate.repository_url)
        if not identity:
            return "only canonical public GitHub HTTPS repositories can be cloned"
        owner, repo = identity
        endpoint = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
        try:
            data, _ = self.client.get_json(
                endpoint,
                headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
            )
        except DiscoverySourceError as exc:
            return str(exc)
        if not isinstance(data, dict):
            return "GitHub repository metadata was not an object"
        if data.get("private"):
            return "private GitHub repositories are outside the public discovery policy"
        candidate.repository_size_kb = int(data.get("size") or 0)
        candidate.archived = bool(data.get("archived"))
        candidate.updated_at = data.get("pushed_at") or candidate.updated_at
        candidate.stars = int(data.get("stargazers_count") or candidate.stars or 0)
        candidate.forks = int(data.get("forks_count") or candidate.forks or 0)
        candidate.watchers = int(data.get("subscribers_count") or candidate.watchers or 0)
        candidate.open_issues = int(data.get("open_issues_count") or candidate.open_issues or 0)
        candidate.open_issues_exact = False
        candidate.homepage = str(data.get("homepage") or candidate.homepage or "") or None
        candidate.language = data.get("language") or candidate.language
        candidate.topics = sorted(set(candidate.topics + [str(value) for value in data.get("topics") or []]))
        license_data = data.get("license") or {}
        candidate.license = candidate.license or str(license_data.get("spdx_id") or "") or None
        contributors_endpoint = f"{endpoint}/contributors?per_page=1&anon=true"
        try:
            contributors, contributors_payload = self.client.get_json(
                contributors_endpoint,
                headers={"Accept": "application/vnd.github+json"},
            )
            if isinstance(contributors, list):
                candidate.contributors = len(contributors)
                link = contributors_payload.headers.get("link") or ""
                last = re.search(r"[?&]page=(\d+)>;\s*rel=\"last\"", link)
                if last:
                    candidate.contributors = int(last.group(1))
        except (DiscoverySourceError, ValueError):
            candidate.contributors = None
        issues_endpoint = "https://api.github.com/search/issues?" + urlencode(
            {
                "q": f"repo:{owner}/{repo} is:issue is:open",
                "per_page": 1,
            }
        )
        try:
            issues, _ = self.client.get_json(
                issues_endpoint,
                headers={"Accept": "application/vnd.github+json"},
            )
            if isinstance(issues, dict) and isinstance(issues.get("total_count"), int):
                candidate.open_issues = int(issues["total_count"])
                candidate.open_issues_exact = True
        except DiscoverySourceError:
            pass
        profile_endpoint = f"{endpoint}/community/profile"
        try:
            profile_payload = self.client.request(
                profile_endpoint,
                headers={"Accept": "application/vnd.github+json"},
                allowed_statuses=(200, 404),
            )
            if profile_payload.status == 200:
                profile = profile_payload.json()
                files = profile.get("files") if isinstance(profile, dict) else {}
                candidate.security_policy = bool((files or {}).get("security"))
            else:
                candidate.security_policy = False
        except DiscoverySourceError:
            candidate.security_policy = None
        return None

    @staticmethod
    def _apply_inspection_evidence(
        candidate: Candidate,
        result: InspectionResult,
    ) -> None:
        package_scope = candidate.source in {"pypi", "npm", "crates", "huggingface"}
        if result.license and not package_scope:
            if candidate.license and candidate.license != result.license:
                candidate.repository_evidence["prior_metadata_license"] = candidate.license
            candidate.license = result.license
            candidate.license_kind = "file"
        if result.dependency_count is not None and not package_scope:
            candidate.dependency_count = result.dependency_count
        if result.test_files:
            candidate.test_signals.append("repository test files")
        if result.ci_files:
            candidate.test_signals.append("repository CI")
        if result.docs_files:
            candidate.reuse_signals.append("repository documentation")
        if result.example_files:
            candidate.reuse_signals.append("repository examples")

    def _inspect_local(
        self,
        candidate: Candidate,
        *,
        run_tests: bool,
    ) -> InspectionResult:
        if not candidate.local_path:
            return InspectionResult(
                repository_url=candidate.url,
                status="blocked",
                warnings=["local candidate has no local_path"],
            )
        supplied = Path(candidate.local_path).expanduser()
        try:
            resolved = supplied.resolve(strict=True)
        except OSError as exc:
            return InspectionResult(
                repository_url=candidate.url,
                status="blocked",
                warnings=[f"local candidate could not be resolved: {exc}"],
            )
        if supplied.is_symlink() or not resolved.is_dir():
            return InspectionResult(
                repository_url=candidate.url,
                status="blocked",
                warnings=["local candidate must be a real directory, not a symlink"],
            )
        checkout_bytes = _bounded_tree_size(resolved)
        if checkout_bytes > _MAX_REPOSITORY_KB * 1_024:
            return InspectionResult(
                repository_url=candidate.url,
                status="blocked",
                warnings=["local repository exceeds retained disk/file inspection limits"],
            )
        result = inspect_tree(
            resolved,
            candidate.repository_url or candidate.url,
        )
        result.clone_path = str(resolved)
        self._apply_inspection_evidence(candidate, result)
        if run_tests:
            result.test_receipt = run_sandboxed_tests(resolved, result.test_command)
        return result

    def inspect(self, candidate: Candidate, *, run_tests: bool = False) -> InspectionResult:
        if candidate.deprecated or candidate.gated or candidate.disabled:
            return InspectionResult(
                repository_url=candidate.repository_url or "",
                status="blocked",
                warnings=["candidate is deprecated, gated, yanked, or disabled"],
            )
        if candidate.local_path:
            return self._inspect_local(candidate, run_tests=run_tests)
        repository_url = canonical_repository_url(candidate.repository_url)
        if not repository_url:
            return InspectionResult(
                repository_url=candidate.repository_url or "",
                status="blocked",
                warnings=["candidate has no canonical repository URL"],
            )
        candidate.repository_url = repository_url
        warning = self._hydrate_github(candidate)
        if warning:
            return InspectionResult(repository_url=repository_url, status="blocked", warnings=[warning])
        if candidate.archived:
            return InspectionResult(repository_url=repository_url, status="blocked", warnings=["repository is archived"])
        if candidate.repository_size_kb is None or candidate.repository_size_kb > _MAX_REPOSITORY_KB:
            return InspectionResult(
                repository_url=repository_url,
                status="blocked",
                warnings=[f"repository size is unknown or exceeds {_MAX_REPOSITORY_KB} KB"],
            )
        self.root.mkdir(parents=True, exist_ok=True)
        repository_suffix = hashlib.sha256(repository_url.encode("utf-8")).hexdigest()[:12]
        target = self.root / f"{_slug(candidate.name)}-{repository_suffix}"
        if target.exists():
            return InspectionResult(repository_url=repository_url, status="blocked", warnings=[f"clone target already exists: {target}"])
        env = _clone_environment(str(self.root.resolve()))
        command = [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "credential.helper=",
            "-c",
            "filter.lfs.smudge=",
            "-c",
            "filter.lfs.required=false",
            "-c",
            "http.followRedirects=false",
            "clone",
            "--depth=1",
            "--filter=blob:limit=1m",
            "--no-tags",
            "--single-branch",
            repository_url,
            str(target),
        ]
        timeout_binary = _gnu_timeout_binary()
        bounded_command = (
            [timeout_binary, "--signal=KILL", "--kill-after=5", "120", *command]
            if timeout_binary
            else command
        )
        try:
            process = subprocess.run(
                bounded_command,
                text=True,
                capture_output=True,
                timeout=130,
                check=False,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return InspectionResult(repository_url=repository_url, status="failed", warnings=[f"clone failed: {exc}"])
        if process.returncode != 0:
            return InspectionResult(
                repository_url=repository_url,
                status="failed",
                warnings=[f"clone failed: {process.stderr[-2_000:].strip()}"],
            )
        checkout_bytes = _bounded_tree_size(target)
        if checkout_bytes > _MAX_REPOSITORY_KB * 1_024:
            shutil.rmtree(target, ignore_errors=True)
            return InspectionResult(
                repository_url=repository_url,
                status="blocked",
                warnings=["cloned repository exceeded retained disk/file limits and was deleted"],
            )
        result = inspect_tree(target, repository_url)
        self._apply_inspection_evidence(candidate, result)

        if run_tests:
            result.test_receipt = run_sandboxed_tests(target, result.test_command)
        return result
