from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from json import dumps
from pathlib import Path
from unittest.mock import patch

from brief2ship.discovery_http import DiscoveryHttpClient, HttpPayload
from brief2ship.discovery_inspection import (
    RepositoryInspector,
    _bounded_tree_size,
    _clone_environment,
    _gnu_timeout_binary,
    _safe_text,
    inspect_tree,
    run_sandboxed_tests,
)
from brief2ship.discovery_models import Candidate


class InspectorClient(DiscoveryHttpClient):
    def get_json(
        self,
        url,
        *,
        headers=None,
        max_bytes=5_000_000,
    ) -> tuple[object, HttpPayload]:  # noqa: ARG002
        data = {
            "size": 50,
            "archived": False,
            "pushed_at": "2026-07-29T00:00:00Z",
            "stargazers_count": 10,
            "forks_count": 2,
            "open_issues_count": 1,
            "language": "Python",
            "topics": ["fixture"],
            "license": {"spdx_id": "MIT"},
        }
        return data, HttpPayload(200, url, {}, dumps(data).encode())

    def request(self, url, **kwargs):
        data = {"files": {"security": {"url": "https://example.invalid/security"}}}
        return HttpPayload(200, url, {}, dumps(data).encode())


class InspectionTests(unittest.TestCase):
    def _fixture(self, root: Path) -> None:
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / ".github/workflows").mkdir(parents=True)
        (root / "docs").mkdir()
        (root / "examples").mkdir()
        (root / "pyproject.toml").write_text(
            '[project]\nname="fixture"\ndependencies=["one", "two"]\n', encoding="utf-8"
        )
        (root / "LICENSE").write_bytes((Path(__file__).resolve().parents[1] / "LICENSE").read_bytes())
        (root / "README.md").write_text("fixture", encoding="utf-8")
        (root / "src/tool.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "tests/test_ok.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertEqual(1,1)\n",
            encoding="utf-8",
        )
        (root / "tests/test_sandbox.py").write_text(
            "import os,socket,unittest\n"
            "class SandboxT(unittest.TestCase):\n"
            " def test_host_home_hidden(self): self.assertEqual([],os.listdir('/home'))\n"
            " def test_network_blocked(self):\n"
            "  with self.assertRaises(OSError): socket.create_connection(('1.1.1.1',53),timeout=0.1)\n"
            " def test_filesystem_is_read_only(self):\n"
            "  for path in ('/work/generated.tmp','/tmp/generated.tmp','/home/generated.tmp','/generated.tmp'):\n"
            "   with self.subTest(path=path), self.assertRaises(OSError): open(path,'w').write('no')\n",
            encoding="utf-8",
        )
        (root / ".github/workflows/ci.yml").write_text("name: ci\n", encoding="utf-8")
        (root / "docs/guide.md").write_text("guide", encoding="utf-8")
        (root / "examples/demo.py").write_text("print('demo')\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"],
            cwd=root,
            check=True,
        )

    def test_static_inspection_collects_real_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._fixture(root)
            result = inspect_tree(root, "https://github.com/example/fixture")
        self.assertEqual(result.status, "inspected")
        self.assertEqual(result.license, (Path(__file__).resolve().parents[1] / "LICENSE").read_text(encoding="utf-8"))
        self.assertEqual(result.dependency_count, 2)
        self.assertIn("pyproject.toml", result.manifest_files)
        self.assertEqual(len(result.test_files), 2)
        self.assertEqual(len(result.ci_files), 1)
        self.assertIn("fixture", result.feature_terms)
        self.assertTrue(result.test_command)
        self.assertTrue(result.commit)

    def test_static_inspection_marks_entry_cap_partial(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(5):
                (root / f"file-{index}.py").write_text("VALUE = 1\n", encoding="utf-8")
            with patch(
                "brief2ship.discovery_inspection._MAX_ENTRIES_PER_DIRECTORY",
                2,
            ):
                result = inspect_tree(root, "file:///fixture")

        self.assertEqual("partial", result.status)
        self.assertTrue(any("entry cap" in warning for warning in result.warnings))

    def test_tree_size_fails_closed_on_directory_entry_cap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(5):
                (root / f"file-{index}.txt").write_text("x", encoding="utf-8")
            with patch(
                "brief2ship.discovery_inspection._MAX_ENTRIES_PER_DIRECTORY",
                2,
            ):
                measured = _bounded_tree_size(root)

        self.assertGreater(measured, 250_000 * 1_024)

    @unittest.skipIf(os.name == "nt", "symlink creation may require Windows elevation")
    def test_safe_text_does_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside.txt"
            outside.write_text("secret", encoding="utf-8")
            link = root / "link.txt"
            link.symlink_to(outside)

            self.assertEqual("", _safe_text(link))

    def test_github_hydration_records_contributors_watchers_and_homepage(self):
        class MetricsClient(InspectorClient):
            def get_json(
                self,
                url,
                *,
                headers=None,
                max_bytes=5_000_000,
            ) -> tuple[object, HttpPayload]:  # noqa: ARG002
                if "/contributors?" in url:
                    data = [{"login": "one"}, {"login": "two"}]
                    return data, HttpPayload(200, url, {}, dumps(data).encode())
                if "/search/issues?" in url:
                    data = {"total_count": 4, "items": []}
                    return data, HttpPayload(200, url, {}, dumps(data).encode())
                data = {
                    "size": 50,
                    "archived": False,
                    "pushed_at": "2026-09-01T00:00:00Z",
                    "stargazers_count": 100,
                    "forks_count": 12,
                    "subscribers_count": 7,
                    "open_issues_count": 3,
                    "homepage": "https://example.com/demo",
                    "license": {"spdx_id": "MIT"},
                }
                return data, HttpPayload(200, url, {}, dumps(data).encode())

        candidate = Candidate(
            source="github",
            name="owner/tool",
            url="https://github.com/owner/tool",
            repository_url="https://github.com/owner/tool",
        )

        warning = RepositoryInspector(
            MetricsClient(),
            Path("/tmp/unused"),
        )._hydrate_github(candidate)

        self.assertIsNone(warning)
        self.assertEqual(7, candidate.watchers)
        self.assertEqual(2, candidate.contributors)
        self.assertEqual("https://example.com/demo", candidate.homepage)
        self.assertEqual(4, candidate.open_issues)
        self.assertTrue(candidate.open_issues_exact)

    def test_merged_package_with_local_path_is_inspected_in_place(self):
        class NoNetworkClient(DiscoveryHttpClient):
            def get_json(self, *args, **kwargs):  # noqa: ANN002, ANN003
                raise AssertionError("network metadata must not be requested")

            def request(self, *args, **kwargs):  # noqa: ANN002, ANN003
                raise AssertionError("network metadata must not be requested")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "pyproject.toml").write_text(
                '[project]\nname="local-package"\ndependencies=[]\n',
                encoding="utf-8",
            )
            (root / "README.md").write_text("# Local Package\n", encoding="utf-8")
            candidate = Candidate(
                source="pypi",
                name="local-package",
                url="https://pypi.org/project/local-package/",
                repository_url="https://github.com/owner/local-package",
                local_path=str(root),
            )

            result = RepositoryInspector(
                NoNetworkClient(),
                root / "clones",
            ).inspect(candidate)

        self.assertEqual("inspected", result.status)
        self.assertEqual(str(root.resolve()), result.clone_path)

    def test_no_command_is_blocked_not_executed(self):
        with tempfile.TemporaryDirectory() as temporary:
            receipt = run_sandboxed_tests(Path(temporary), [])
        self.assertEqual(receipt.status, "blocked")
        self.assertEqual(receipt.sandbox, "not-run")

    def test_repository_inspector_uses_bounded_clone_then_static_evidence(self):
        calls = []
        observed_clone_env = {}

        def fake_run(command, **kwargs):
            calls.append(command)
            if "clone" in command:
                observed_clone_env.update(kwargs["env"])
                target = Path(command[-1])
                target.mkdir(parents=True)
                (target / "tests").mkdir()
                (target / "pyproject.toml").write_text(
                    '[project]\nname="fixture"\ndependencies=[]\n', encoding="utf-8"
                )
                (target / "README.md").write_text("fixture scraper", encoding="utf-8")
                (target / "LICENSE").write_bytes((Path(__file__).resolve().parents[1] / "LICENSE").read_bytes())
                (target / "tests/test_ok.py").write_text("import unittest\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")
            return subprocess.CompletedProcess(command, 0, "a" * 40 + "\n", "")

        candidate = Candidate(
            source="github",
            name="owner/fixture",
            url="https://github.com/owner/fixture",
            repository_url="https://github.com/owner/fixture",
        )
        with tempfile.TemporaryDirectory() as temporary, patch(
            "brief2ship.discovery_inspection.subprocess.run", side_effect=fake_run
        ):
            result = RepositoryInspector(InspectorClient(), Path(temporary)).inspect(candidate)
        self.assertEqual("inspected", result.status)
        self.assertEqual((Path(__file__).resolve().parents[1] / "LICENSE").read_text(encoding="utf-8"), candidate.license)
        self.assertTrue(candidate.security_policy)
        clone = next(command for command in calls if "clone" in command)
        self.assertIn("--depth=1", clone)
        self.assertIn("--filter=blob:limit=1m", clone)
        self.assertIn("--no-tags", clone)
        self.assertIn("http.followRedirects=false", clone)
        self.assertEqual("/dev/null", observed_clone_env["GIT_CONFIG_GLOBAL"])
        self.assertNotIn("GH_TOKEN", observed_clone_env)

    def test_clone_timeout_wrapper_requires_posix_gnu_timeout(self):
        windows_timeout = r"C:\Windows\System32\timeout.exe"
        with patch("brief2ship.discovery_inspection.os.name", "nt"), patch(
            "brief2ship.discovery_inspection.shutil.which", return_value=windows_timeout
        ) as which:
            self.assertIsNone(_gnu_timeout_binary())
            which.assert_not_called()

        gnu_probe = subprocess.CompletedProcess(
            ["/usr/bin/timeout", "--version"], 0, "timeout (GNU coreutils) 9.1\n", ""
        )
        with patch("brief2ship.discovery_inspection.os.name", "posix"), patch(
            "brief2ship.discovery_inspection.shutil.which", return_value="/usr/bin/timeout"
        ), patch("brief2ship.discovery_inspection.subprocess.run", return_value=gnu_probe):
            self.assertEqual("/usr/bin/timeout", _gnu_timeout_binary())

        incompatible_probe = subprocess.CompletedProcess(
            ["/usr/bin/timeout", "--version"], 1, "", "unknown option"
        )
        with patch("brief2ship.discovery_inspection.os.name", "posix"), patch(
            "brief2ship.discovery_inspection.shutil.which", return_value="/usr/bin/timeout"
        ), patch("brief2ship.discovery_inspection.subprocess.run", return_value=incompatible_probe):
            self.assertIsNone(_gnu_timeout_binary())

    def test_windows_clone_environment_keeps_runtime_roots_but_not_tokens(self):
        with patch("brief2ship.discovery_inspection.os.name", "nt"), patch.dict(
            os.environ,
            {
                "PATH": r"C:\Windows\System32",
                "SYSTEMROOT": r"C:\Windows",
                "WINDIR": r"C:\Windows",
                "GH_TOKEN": "must-not-leak",
                "GITHUB_TOKEN": "must-not-leak",
            },
            clear=True,
        ):
            environment = _clone_environment(r"C:\Temp\brief2ship")
        self.assertEqual(r"C:\Windows", environment["SYSTEMROOT"])
        self.assertEqual(r"C:\Windows", environment["WINDIR"])
        self.assertEqual(r"C:\Temp\brief2ship", environment["HOME"])
        self.assertNotIn("GH_TOKEN", environment)
        self.assertNotIn("GITHUB_TOKEN", environment)

    def test_private_repository_metadata_blocks_before_clone(self):
        class PrivateClient(InspectorClient):
            def get_json(self, url, *, headers=None, max_bytes=5_000_000):  # noqa: ARG002
                data = {"private": True, "size": 1, "archived": False}
                return data, HttpPayload(200, url, {}, dumps(data).encode())

        candidate = Candidate(
            source="github", name="secret/private",
            url="https://github.com/secret/private",
            repository_url="https://github.com/secret/private",
        )
        with tempfile.TemporaryDirectory() as temporary, patch(
            "brief2ship.discovery_inspection.subprocess.run"
        ) as run:
            result = RepositoryInspector(PrivateClient(), Path(temporary)).inspect(candidate)
        self.assertEqual("blocked", result.status)
        self.assertIn("private", result.warnings[0])
        run.assert_not_called()

    def test_static_dependency_count_excludes_development_only_sections(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "package.json").write_text(
                '{"dependencies":{"runtime":"1"},"devDependencies":{"dev":"1"},'
                '"scripts":{"test":"node test.js"}}',
                encoding="utf-8",
            )
            result = inspect_tree(root, "https://github.com/example/js")
        self.assertEqual(1, result.dependency_count)
        self.assertNotIn("--runInBand", result.test_command)

    def test_repository_inspector_blocks_oversized_repository_before_clone(self):
        class OversizedClient(InspectorClient):
            def get_json(self, url, *, headers=None, max_bytes=5_000_000):  # noqa: ARG002
                data = {"size": 999_999, "archived": False}
                return data, HttpPayload(200, url, {}, dumps(data).encode())

        candidate = Candidate(
            source="github",
            name="owner/huge",
            url="https://github.com/owner/huge",
            repository_url="https://github.com/owner/huge",
        )
        with tempfile.TemporaryDirectory() as temporary, patch(
            "brief2ship.discovery_inspection.subprocess.run"
        ) as run:
            result = RepositoryInspector(OversizedClient(), Path(temporary)).inspect(candidate)
        self.assertEqual("blocked", result.status)
        self.assertIn("exceeds", result.warnings[0])
        run.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "Bubblewrap command construction is POSIX-only")
    def test_sandbox_uses_a_read_only_filesystem(self):
        completed = subprocess.CompletedProcess([], 0, "", "")
        with tempfile.TemporaryDirectory() as temporary, patch(
            "brief2ship.discovery_inspection.shutil.which",
            side_effect=lambda name: f"/usr/bin/{name}",
        ), patch(
            "brief2ship.discovery_inspection.subprocess.run",
            return_value=completed,
        ) as run:
            root = Path(temporary)
            (root / "test_sample.py").write_text("pass\n", encoding="utf-8")
            receipt = run_sandboxed_tests(
                root,
                ["/usr/bin/python3", "-m", "unittest"],
            )

        command = run.call_args.args[0]
        self.assertEqual("passed", receipt.status)
        self.assertIn("read-only-filesystem", receipt.sandbox)
        self.assertIn("--as=536870912", command)
        self.assertIn("--remount-ro", command)
        self.assertIn("/work", command)
        self.assertNotIn("/input", command)
        self.assertNotIn("--tmpfs", command)
        self.assertNotIn("--bind", command)

    @unittest.skipUnless(
        shutil.which("bwrap") and shutil.which("prlimit") and shutil.which("timeout"),
        "Linux Bubblewrap sandbox not available",
    )
    def test_python_tests_run_without_network_or_host_home(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._fixture(root)
            result = inspect_tree(root, "https://github.com/example/fixture")
            receipt = run_sandboxed_tests(root, result.test_command, timeout_seconds=20)
            self.assertEqual(receipt.status, "passed", receipt.stderr_tail)
            self.assertIn("bubblewrap", receipt.sandbox)
            self.assertFalse((root / "generated.tmp").exists())


if __name__ == "__main__":
    unittest.main()
