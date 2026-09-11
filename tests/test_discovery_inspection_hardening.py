from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from brief2ship.discovery import discover
from brief2ship.discovery_http import DiscoveryHttpClient, HttpPayload
from brief2ship.discovery_inspection import RepositoryInspector, inspect_tree
from brief2ship.discovery_models import Candidate, DiscoveryConfig
from brief2ship.discovery_render import write_discovery


class HydrationClient(DiscoveryHttpClient):
    """Keep search valid while returning malformed repository hydration data."""

    def __init__(self, malformed):
        super().__init__()
        self.malformed = malformed
        self.requested = []

    def get_json(self, url, **kwargs):
        self.requested.append(url)
        metadata = {
            "private": False, "archived": False, "size": 50,
            "language": "Python", "pushed_at": "2026-08-01T00:00:00Z",
            "homepage": "https://example.invalid", "stargazers_count": 10,
            "topics": ["retry"], "license": {"spdx_id": "MIT"},
        }
        if "/search/repositories?" in url:
            data = {"items": [
                {**metadata, "full_name": f"fixture/{name}",
                 "html_url": f"https://github.com/fixture/{name}",
                 "description": "retry exponential backoff"}
                for name in ("bad", "good")
            ]}
        elif "/contributors?" in url:
            data = [{"login": "fixture"}]
        elif "/search/issues?" in url:
            data = {"total_count": 0}
        elif url == "https://api.github.com/repos/fixture/bad":
            data = {**metadata, **self.malformed}
        elif url == "https://api.github.com/repos/fixture/good":
            data = metadata
        else:
            raise AssertionError(f"unexpected request: {url}")
        return data, HttpPayload(200, url, {}, json.dumps(data).encode())

    def request(self, url, **kwargs):
        self.requested.append(url)
        if not url.endswith("/community/profile"):
            raise AssertionError(f"unexpected request: {url}")
        return HttpPayload(200, url, {}, b'{"files":{}}')


def clone_fixture(command, **kwargs):
    """Model a checkout without network access or candidate execution."""
    if "clone" in command:
        root = Path(command[-1])
        root.mkdir(parents=True)
        (root / "package.json").write_text('{"dependencies":{}}', encoding="utf-8")
        (root / "README.md").write_text("retry exponential backoff", encoding="utf-8")
    return subprocess.CompletedProcess(command, 0, "a" * 40 + "\n", "")


class HydrationHardeningTests(unittest.TestCase):
    def test_discovery_preserves_receipts_after_malformed_hydration(self):
        for field in ("language", "pushed_at"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                client = HydrationClient({field: {"bad": "shape"}})
                output = Path(temporary) / "receipts"
                with patch("brief2ship.discovery_inspection.subprocess.run", side_effect=clone_fixture) as run:
                    result = discover(
                        "retry exponential backoff",
                        DiscoveryConfig(sources=("github",), per_source=2, inspect_top=2),
                        output_dir=output, client=client,
                    )
                    write_discovery(result, output)
                candidates = {item.name: item for item in result.evaluated_candidates}
                self.assertEqual({"fixture/bad", "fixture/good"}, set(candidates))
                bad, good = candidates["fixture/bad"], candidates["fixture/good"]
                assert bad.inspection is not None and good.inspection is not None
                self.assertEqual("failed", bad.inspection.status)
                self.assertIn(field, bad.inspection.warnings[0])
                self.assertEqual("Python", bad.language)
                self.assertEqual("2026-08-01T00:00:00Z", bad.updated_at)
                self.assertEqual("inspected", good.inspection.status)
                self.assertIsNotNone(good.score)
                self.assertEqual(2, len(result.inspection_decisions))
                self.assertEqual("ok", result.sources[0].status)
                clones = [call.args[0] for call in run.call_args_list if "clone" in call.args[0]]
                self.assertEqual(1, len(clones))
                self.assertIn("https://github.com/fixture/good", clones[0])
                self.assertTrue((output / "checkpoint.json").is_file())
                receipt = json.loads((output / "discovery.json").read_text(encoding="utf-8"))
                self.assertEqual(2, len(receipt["evaluated_candidates"]))
                self.assertEqual(2, len(list((output / "candidates").glob("*.json"))))

    def test_malformed_metadata_is_rejected_before_candidate_mutation(self):
        cases = (
            ("language", {"bad": "shape"}), ("pushed_at", ["bad"]),
            ("homepage", ["bad"]), ("archived", "false"), ("private", "false"),
            ("license", {"spdx_id": ["MIT"]}),
        )
        for field, value in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                candidate = Candidate(
                    "github", "fixture/bad", "https://github.com/fixture/bad",
                    repository_url="https://github.com/fixture/bad",
                    language="Rust", updated_at="2025-01-01T00:00:00Z", stars=1,
                )
                before = candidate.to_dict()
                client = HydrationClient({field: value})
                with patch("brief2ship.discovery_inspection.subprocess.run") as run:
                    result = RepositoryInspector(client, Path(temporary)).inspect(candidate)
                self.assertEqual("failed", result.status)
                self.assertIn(field, result.warnings[0])
                self.assertEqual(before, candidate.to_dict())
                self.assertEqual(["https://api.github.com/repos/fixture/bad"], client.requested)
                run.assert_not_called()

    def test_nullable_hydrated_fields_preserve_valid_search_evidence(self):
        client = HydrationClient({"language": None, "pushed_at": None, "homepage": None, "license": None})
        candidate = Candidate(
            "github", "fixture/bad", "https://github.com/fixture/bad",
            repository_url="https://github.com/fixture/bad", language="Rust",
            updated_at="2025-01-01T00:00:00Z", homepage="https://example.invalid/old", license="MIT",
        )
        with tempfile.TemporaryDirectory() as temporary:
            warning = RepositoryInspector(client, Path(temporary))._hydrate_github(candidate)
        self.assertIsNone(warning)
        self.assertEqual("Rust", candidate.language)
        self.assertEqual("2025-01-01T00:00:00Z", candidate.updated_at)
        self.assertEqual("https://example.invalid/old", candidate.homepage)
        self.assertEqual("MIT", candidate.license)


class DependencyEvidenceHardeningTests(unittest.TestCase):
    def test_unsupported_dependency_syntax_remains_unknown(self):
        fixtures = (
            ("requirements.txt", "-r absent.txt\n"),
            ("requirements.txt", "--requirement=absent.txt\n"),
            ("requirements.txt", "-c absent.txt\n"),
            ("requirements.txt", "--index-url https://example.invalid/simple\n"),
            ("requirements.txt", "invalid dependency declaration\n"),
            ("requirements.txt", "runtime>=1; python_version < '3.12'\n"),
            ("go.mod", "module fixture\nrequire bad dependency declaration\n"),
            ("go.mod", "module fixture\nrequire (\n bad dependency declaration\n)\n"),
            ("go.mod", "module fixture\nrequire (\n example.com/dep v1.0.0\n"),
            ("go.mod", "module fixture\nrequire example.com/dep vbroken\n"),
        )
        for filename, text in fixtures:
            with self.subTest(filename=filename, text=text), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / filename).write_text(text, encoding="utf-8")
                (root / "package.json").write_text('{"dependencies":{}}', encoding="utf-8")
                result = inspect_tree(root, root.as_uri())
                self.assertIsNone(result.dependency_count)
                self.assertTrue(any(filename in warning for warning in result.warnings))

    def test_supported_dependency_syntax_retains_counts(self):
        fixtures = (
            ("requirements.txt", "# no runtime requirements\n", 0),
            ("requirements.txt", "runtime>=1,<2\nother[extra]==1.2.3 # comment\n", 2),
            ("go.mod", "module fixture\ngo 1.23\n", 0),
            ("go.mod", "module fixture\nrequire example.com/one v1.0.0\nrequire (\n // comment\n example.com/two v2.0.0 // indirect\n)\n", 2),
        )
        for filename, text, expected in fixtures:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / filename).write_text(text, encoding="utf-8")
                result = inspect_tree(root, root.as_uri())
                self.assertEqual(expected, result.dependency_count)
                self.assertEqual([], result.warnings)

    def test_unsupported_recognized_manifest_invalidates_known_dependency_sum(self):
        for filename in ("setup.cfg", "setup.py", "pom.xml", "build.gradle", "build.gradle.kts"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "package.json").write_text('{"dependencies":{}}', encoding="utf-8")
                (root / filename).write_text("unsupported dependency declaration", encoding="utf-8")
                result = inspect_tree(root, root.as_uri())
                self.assertIsNone(result.dependency_count)
                self.assertIn(filename, result.manifest_files)
                self.assertTrue(any(filename in warning for warning in result.warnings))

    def test_oversized_requirements_invalidates_known_dependency_sum(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "package.json").write_text('{"dependencies":{}}', encoding="utf-8")
            (root / "requirements.txt").write_text("runtime>=1\n" * 10, encoding="utf-8")
            with patch("brief2ship.discovery_inspection._MAX_READ_BYTES", 64):
                result = inspect_tree(root, root.as_uri())
            self.assertIsNone(result.dependency_count)
            self.assertTrue(any("requirements.txt" in warning for warning in result.warnings))

    def test_unreadable_requirements_invalidates_known_dependency_sum(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            requirements = root / "requirements.txt"
            requirements.write_text("runtime>=1\n", encoding="utf-8")
            (root / "package.json").write_text('{"dependencies":{"known":"1"}}', encoding="utf-8")
            original_open = os.open

            def fail_requirements(path, *args, **kwargs):
                if Path(path) == requirements:
                    raise PermissionError("unreadable requirements fixture")
                return original_open(path, *args, **kwargs)

            with patch("brief2ship.discovery_inspection.os.open", side_effect=fail_requirements):
                result = inspect_tree(root, root.as_uri())
            self.assertIsNone(result.dependency_count)
            self.assertTrue(any("requirements.txt" in warning for warning in result.warnings))

    def test_traversal_caps_invalidate_observed_zero_dependencies(self):
        cases = (
            ("_MAX_FILES", 1), ("_MAX_INSPECTION_DIRECTORIES", 1),
            ("_MAX_INSPECTION_DEPTH", 0), ("_MAX_ENTRIES_PER_DIRECTORY", 1),
        )
        for constant, value in cases:
            with self.subTest(constant=constant), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self._traversal_fixture(root)
                scandir = os.scandir

                @contextmanager
                def ordered_scandir(path):
                    with scandir(path) as entries:
                        yield iter(sorted(entries, key=lambda entry: entry.name))

                with patch(f"brief2ship.discovery_inspection.{constant}", value), patch(
                    "brief2ship.discovery_inspection.os.scandir", side_effect=ordered_scandir
                ):
                    result = inspect_tree(root, root.as_uri())
                self.assertIn("package.json", result.manifest_files)
                self.assertEqual("partial", result.status)
                self.assertIsNone(result.dependency_count)

    def test_deadline_invalidates_observed_zero_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._traversal_fixture(root)
            with patch("brief2ship.discovery_inspection.time.monotonic", side_effect=[0, 0, 60]):
                result = inspect_tree(root, root.as_uri())
            self.assertIn("package.json", result.manifest_files)
            self.assertEqual("partial", result.status)
            self.assertIsNone(result.dependency_count)

    def test_unreadable_traversal_invalidates_observed_zero_dependencies(self):
        for failure in ("directory", "entry"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self._traversal_fixture(root)
                scandir = os.scandir

                @contextmanager
                def unreadable_scandir(path):
                    if failure == "directory" and Path(path).name == "zzz-hidden":
                        raise PermissionError("unreadable directory fixture")
                    with scandir(path) as scanner:
                        entries = list(scanner)
                    if failure == "entry" and Path(path) == root:
                        for index, entry in enumerate(entries):
                            if entry.name == "zzz-hidden":
                                unreadable = Mock(wraps=entry)
                                unreadable.name = entry.name
                                unreadable.is_symlink.side_effect = PermissionError("unreadable entry fixture")
                                entries[index] = unreadable
                    yield iter(entries)

                with patch("brief2ship.discovery_inspection.os.scandir", side_effect=unreadable_scandir):
                    result = inspect_tree(root, root.as_uri())
                self.assertIn("package.json", result.manifest_files)
                self.assertEqual("partial", result.status)
                self.assertIsNone(result.dependency_count)

    def test_feature_evidence_cap_does_not_invalidate_complete_dependency_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "package.json").write_text('{"dependencies":{"known":"1"}}', encoding="utf-8")
            (root / "README.md").write_text("retry backoff websocket extra", encoding="utf-8")
            with patch("brief2ship.discovery_inspection._MAX_FEATURE_TERMS", 2):
                result = inspect_tree(root, root.as_uri())
            self.assertEqual("partial", result.status)
            self.assertEqual(1, result.dependency_count)
            self.assertEqual(["retry", "backoff"], result.feature_terms)

    def test_malformed_nested_poetry_declarations_remain_unknown(self):
        declarations = (
            '[123]', '["^1"]', '[{version="^1"}, 123]', '[[{version="^1"}]]',
            '{version=123}', '{extras=[123]}', '{optional="false"}',
            '{git=["https://example.invalid/repo"]}', '{unknown={nested="bad"}}',
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "pyproject.toml").write_text(
                    f'[tool.poetry.dependencies]\npython="^3.11"\nbad={declaration}\n', encoding="utf-8"
                )
                result = inspect_tree(root, root.as_uri())
                self.assertIsNone(result.dependency_count)
                self.assertTrue(any("pyproject.toml" in warning for warning in result.warnings))

    def test_supported_poetry_declarations_count_packages_not_alternatives(self):
        declarations = (
            '"^1"', '{version="^1", extras=["speed"], optional=true}',
            '[{version="^1", python="<3.12"}, {version="^2", python=">=3.12"}]',
            '{path="../runtime", develop=true}',
            '{git="https://example.invalid/runtime", rev="main", allow-prereleases=false}',
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "pyproject.toml").write_text(
                    f'[tool.poetry.dependencies]\npython="^3.11"\nruntime={declaration}\n', encoding="utf-8"
                )
                result = inspect_tree(root, root.as_uri())
                self.assertEqual(1, result.dependency_count)
                self.assertEqual([], result.warnings)

    @staticmethod
    def _traversal_fixture(root):
        (root / "package.json").write_text('{"dependencies":{}}', encoding="utf-8")
        hidden = root / "zzz-hidden"
        hidden.mkdir()
        (hidden / "requirements.txt").write_text("runtime>=1\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
