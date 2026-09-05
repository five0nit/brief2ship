from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brief2ship.discovery_local import search_local


class LocalDiscoveryTests(unittest.TestCase):
    def _project(self, root: Path, name: str, readme: str) -> Path:
        project = root / name
        (project / "tests").mkdir(parents=True)
        (project / ".git").mkdir()
        (project / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\ndependencies = []\n',
            encoding="utf-8",
        )
        (project / "README.md").write_text(readme, encoding="utf-8")
        (project / "LICENSE").write_bytes((Path(__file__).resolve().parents[1] / "LICENSE").read_bytes())
        (project / "SECURITY.md").write_text("# Security\n", encoding="utf-8")
        (project / "tests/test_smoke.py").write_text("VALUE = 1\n", encoding="utf-8")
        (project / ".git/config").write_text(
            "[remote \"origin\"]\n"
            f"    url = https://github.com/example/{name}.git\n",
            encoding="utf-8",
        )
        return project

    def test_local_search_finds_and_describes_real_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self._project(
                root,
                "telegram-agent-kit",
                "# Telegram Agent Kit\n\nLocal bot starter with receipts.\n",
            )
            candidates, receipt = search_local(
                "telegram agent starter",
                [str(root)],
                limit=5,
            )

        self.assertEqual("ok", receipt.status)
        self.assertEqual(1, receipt.returned)
        self.assertEqual("local", candidates[0].source)
        self.assertEqual(str(project.resolve()), candidates[0].local_path)
        self.assertEqual(project.resolve().as_uri(), candidates[0].url)
        self.assertEqual("https://github.com/example/telegram-agent-kit", candidates[0].repository_url)
        self.assertEqual((Path(__file__).resolve().parents[1] / "LICENSE").read_bytes().decode("utf-8"), candidates[0].license)
        self.assertEqual("Python", candidates[0].language)
        self.assertTrue(candidates[0].security_policy)
        self.assertIn("repository test files", candidates[0].test_signals)

    def test_local_search_is_deterministic_and_skips_vendor_trees(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._project(root, "zulu-starter", "# Shared Starter\n")
            self._project(root, "alpha-starter", "# Shared Starter\n")
            vendor = root / "node_modules/noisy-starter"
            vendor.mkdir(parents=True)
            (vendor / "package.json").write_text("{}", encoding="utf-8")

            first, _ = search_local("shared starter", [str(root)], limit=1)
            second, _ = search_local("shared starter", [str(root)], limit=1)

        self.assertEqual(["local/alpha-starter"], [candidate.name for candidate in first])
        self.assertEqual(
            [candidate.to_dict() for candidate in first],
            [candidate.to_dict() for candidate in second],
        )

    def test_local_search_records_invalid_roots_without_crashing(self):
        candidates, receipt = search_local(
            "anything",
            ["/definitely/missing/brief2ship-local-root"],
            limit=5,
        )

        self.assertEqual([], candidates)
        self.assertEqual("failed", receipt.status)
        self.assertIn("not a directory", receipt.error or "")

    def test_local_search_never_emits_credential_bearing_git_remote(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self._project(root, "safe-project", "# Safe Project\n")
            (project / ".git/config").write_text(
                '[remote "origin"]\n'
                "    url = https://oauth2:TOPSECRET@gitlab.example.com/group/repo.git\n",
                encoding="utf-8",
            )

            candidates, _ = search_local("safe project", [str(root)], limit=5)

        self.assertEqual(1, len(candidates))
        self.assertIsNone(candidates[0].repository_url)
        self.assertNotIn("TOPSECRET", str(candidates[0].to_dict()))

    @unittest.skipIf(os.name == "nt", "symlink creation may require Windows elevation")
    def test_local_search_does_not_follow_symlinked_git_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "symlink-project"
            project.mkdir()
            (project / "pyproject.toml").write_text(
                '[project]\nname="symlink-project"\n',
                encoding="utf-8",
            )
            (project / "README.md").write_text("# Symlink Project\n", encoding="utf-8")
            outside = root / "outside-git"
            outside.mkdir()
            (outside / "config").write_text(
                '[remote "origin"]\n    url = https://github.com/secret/outside.git\n',
                encoding="utf-8",
            )
            (project / ".git").symlink_to(outside, target_is_directory=True)

            candidates, _ = search_local("symlink project", [str(root)], limit=5)

        self.assertEqual(1, len(candidates))
        self.assertIsNone(candidates[0].repository_url)

    def test_local_scan_is_breadth_first_so_deep_sibling_cannot_starve_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cursor = root / "a-deep"
            for index in range(10):
                cursor = cursor / f"nested-{index}"
                cursor.mkdir(parents=True)
            target = self._project(
                root,
                "z-target-starter",
                "# Target Starter\n",
            )

            with patch("brief2ship.discovery_local._MAX_DIRECTORIES", 5):
                candidates, receipt = search_local(
                    "target starter",
                    [str(root)],
                    limit=5,
                )

        self.assertEqual([str(target.resolve())], [candidate.local_path for candidate in candidates])
        self.assertTrue(any("stopped" in warning for warning in receipt.warnings))
        self.assertEqual("partial", receipt.status)

    def test_local_scan_round_robins_roots_under_global_directory_cap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            broad = root / "a-broad"
            narrow = root / "b-narrow"
            broad.mkdir()
            narrow.mkdir()
            for index in range(4):
                (broad / f"branch-{index}").mkdir()
            target = self._project(
                narrow,
                "target-tool",
                "# Target Tool\n",
            )

            with patch("brief2ship.discovery_local._MAX_DIRECTORIES", 4):
                candidates, receipt = search_local(
                    "target tool",
                    [str(broad), str(narrow)],
                    limit=5,
                )

        self.assertEqual([str(target.resolve())], [candidate.local_path for candidate in candidates])
        self.assertTrue(any("stopped" in warning for warning in receipt.warnings))
        self.assertEqual("partial", receipt.status)

    def test_local_scan_caps_entries_per_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(10):
                (root / f"entry-{index}.txt").write_text("x", encoding="utf-8")

            with patch("brief2ship.discovery_local._MAX_ENTRIES_PER_DIRECTORY", 3):
                _, receipt = search_local("anything", [str(root)], limit=5)

        self.assertTrue(any("entry cap" in warning for warning in receipt.warnings))

    def test_local_scan_honors_wall_clock_deadline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clock = iter((0.0, 1.0))
            _, receipt = search_local(
                "anything",
                [str(root)],
                limit=5,
                timeout_seconds=0.5,
                monotonic=lambda: next(clock),
            )

        self.assertTrue(any("deadline" in warning for warning in receipt.warnings))


if __name__ == "__main__":
    unittest.main()
