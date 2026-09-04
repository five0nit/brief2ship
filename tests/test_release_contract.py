import hashlib
import json
import re
import struct
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    def test_version_is_consistent(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        init = (ROOT / "src/brief2ship/__init__.py").read_text(encoding="utf-8")
        skill = (ROOT / "skills/brief2ship/SKILL.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual("0.6.2", version)
        self.assertEqual(version, pyproject["project"]["version"])
        self.assertIn(f'__version__ = "{version}"', init)
        self.assertIn(f"version: {version}", skill)
        self.assertIn(f"## {version}", changelog)
        for path in (
            ROOT / "src/brief2ship/models.py",
            ROOT / "src/brief2ship/discovery_http.py",
        ):
            self.assertIn(f"Brief2ShipBot/{version}", path.read_text(encoding="utf-8"))

    def test_console_entrypoint_and_zero_core_dependencies(self):
        configuration = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        project = configuration["project"]
        self.assertEqual(
            ["setuptools>=77", "wheel"],
            configuration["build-system"]["requires"],
        )
        self.assertEqual("brief2ship.cli:main", project["scripts"]["brief2ship"])
        self.assertEqual([], project["dependencies"])
        self.assertEqual(["trafilatura>=2.1,<3"], project["optional-dependencies"]["extract"])

    def test_supported_python_versions_are_ci_covered(self):
        configuration = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        classifiers = configuration["project"]["classifiers"]
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        for version in ("3.11", "3.12", "3.13"):
            self.assertIn(f"Programming Language :: Python :: {version}", classifiers)
            self.assertIn(f"'{version}'", ci)

    def test_tier_three_keeps_hyperframes_as_a_conditional_finish_tool(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        skill = (ROOT / "skills/brief2ship/SKILL.md").read_text(encoding="utf-8")
        for surface in (readme, skill):
            self.assertIn("https://github.com/heygen-com/hyperframes", surface)
        self.assertIn("not a general UI component base", skill)

    def test_native_install_claims_replace_private_installer(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertFalse((ROOT / "scripts/install-skill.sh").exists())
        self.assertIn("hermes skills install", readme)
        self.assertIn("hermes --profile qa skills install", readme)
        self.assertNotIn("profiles/" + "generalist1", readme)
        self.assertNotIn("three-tier-build-toolkit", readme.lower())
        self.assertNotIn("shipproof", readme.lower())
        self.assertNotIn("Hermes/OpenClaw", readme)

    def test_four_lanes_and_report_scrape_discovery(self):
        required_lanes = ["App", "Dashboard / Internal tool", "Landing page", "Report / Document"]
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        lanes = (ROOT / "docs/lanes.md").read_text(encoding="utf-8")
        skill = (ROOT / "skills/brief2ship/SKILL.md").read_text(encoding="utf-8")
        for lane in required_lanes:
            self.assertIn(lane, readme)
            self.assertIn(lane, lanes)
            self.assertIn(lane, skill)
        frontmatter = skill.split("---", 2)[1].lower()
        self.assertIn("report", frontmatter)
        self.assertIn("scrap", frontmatter)
        self.assertIn("not a fifth lane", readme)

    def test_safety_contract_is_public_and_specific(self):
        combined = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ["README.md", "docs/free-scraping.md", "skills/brief2ship/SKILL.md"]
        ).lower()
        for phrase in [
            "robots.txt",
            "same-origin",
            "sequential",
            "private",
            "redirect",
            "pinned",
            "proxies",
            "response",
            "captcha",
            "proxy rotation",
            "personal-data harvesting",
            "sha-256",
            "zero-paid-api",
        ]:
            self.assertIn(phrase, combined)

    def test_network_code_has_no_session_or_evasion_headers(self):
        source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "src/brief2ship").glob("*.py"))
        for forbidden in ['"Cookie"', "Proxy-Authorization", "Sec-CH-UA", "playwright", "selenium"]:
            self.assertNotIn(forbidden, source)
        discovery_http = (ROOT / "src/brief2ship/discovery_http.py").read_text(encoding="utf-8")
        self.assertEqual(1, discovery_http.count('["Authorization"]'))
        self.assertIn('urlsplit(url).hostname == "api.github.com"', discovery_http)

    def test_discovery_contract_is_public_and_specific(self):
        combined = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ["README.md", "docs/code-discovery.md", "skills/brief2ship/SKILL.md"]
        )
        for phrase in [
            "brief2ship discover",
            "github,pypi,npm,crates,huggingface",
            "feature match",
            "maintenance/activity",
            "dependency weight",
            "security",
            "test quality",
            "portability",
            "reuse",
            "fork",
            "use-as-library",
            "selective-reuse",
            "reject",
            "build-clean",
            "Bubblewrap",
            "no network",
            "brief2ship-discovery-v1",
            "evidence coverage",
        ]:
            self.assertIn(phrase.lower(), combined.lower())

    def test_brief2ship_is_the_only_repo_search_skill_contract(self):
        public = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in [
                "README.md",
                "docs/code-discovery.md",
                "skills/brief2ship/SKILL.md",
            ]
        )
        self.assertNotIn("repo-first-base-selection", public)
        self.assertIn("--local", public)
        self.assertIn("local workspace", public.lower())
        skill_files = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual([ROOT / "skills/brief2ship/SKILL.md"], skill_files)

    def test_license_names_holder(self):
        self.assertIn(
            "Copyright (c) 2026 Michael Costea and contributors",
            (ROOT / "LICENSE").read_text(encoding="utf-8"),
        )

    def test_public_surfaces_have_no_maintainer_absolute_paths(self):
        roots = [
            ROOT / "README.md",
            ROOT / "CHANGELOG.md",
            ROOT / "CONTRIBUTING.md",
            ROOT / "SECURITY.md",
            *sorted((ROOT / "skills").rglob("*.md")),
            *sorted((ROOT / "templates").rglob("*.md")),
            *sorted((ROOT / "docs").rglob("*.md")),
            *sorted((ROOT / "scripts").glob("*.py")),
        ]
        forbidden = [
            "/home/" + "fiv30nit",
            "C:\\Users\\" + "coste",
            "profiles/" + "generalist1",
            "generalist" + "2",
            "generalist" + "3",
            "voice" + "fast",
        ]
        for path in roots:
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, text, path)

    def test_relative_markdown_links_exist(self):
        failures = []
        for path in [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]:
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                rel = target.split("#", 1)[0]
                if rel and not (path.parent / rel).resolve().exists():
                    failures.append(f"{path.relative_to(ROOT)} -> {target}")
        self.assertEqual([], failures)

    def test_readme_does_not_link_to_receipts_excluded_from_packages(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotRegex(readme, r"\]\(docs/releases/")
        self.assertIn("`docs/releases/v0.6.2-discoverability-receipt.md`", readme)
        self.assertIn("outside built packages", readme)

    def test_discovery_marketing_and_community_surfaces(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertLess(
            readme.index("Stop AI coding agents from rebuilding what already exists"),
            readme.index("## 30-second quickstart"),
        )
        self.assertLess(readme.index("## 30-second quickstart"), readme.index("## Why Brief2Ship?"))
        for rel in [
            "CODE_OF_CONDUCT.md",
            "ROADMAP.md",
            "docs/case-studies.md",
            ".github/ISSUE_TEMPLATE/bug.yml",
            ".github/ISSUE_TEMPLATE/feature.yml",
            ".github/PULL_REQUEST_TEMPLATE.md",
        ]:
            self.assertTrue((ROOT / rel).is_file(), rel)

        png = (ROOT / "docs/assets/social-preview.png").read_bytes()
        self.assertEqual(b"\x89PNG\r\n\x1a\n", png[:8])
        self.assertEqual((1280, 640), struct.unpack(">II", png[16:24]))
        self.assertLess(len(png), 1_000_000)

        gif = (ROOT / "docs/assets/brief2ship-demo.gif").read_bytes()
        self.assertIn(gif[:6], (b"GIF87a", b"GIF89a"))
        self.assertEqual((640, 500), struct.unpack("<HH", gif[6:10]))
        self.assertLess(len(gif), 1_000_000)

    def test_agent_distribution_metadata_matches_release(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads(
            (ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual("brief2ship", plugin["name"])
        self.assertEqual(version, plugin["version"])
        self.assertEqual(version, marketplace["plugins"][0]["version"])
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"brief2ship@v{version}", readme)
        self.assertIn("npx skills add five0nit/brief2ship --skill brief2ship", readme)
        self.assertIn("claude plugin install brief2ship@brief2ship", readme)

    def test_pypi_trusted_publishing_contract(self):
        workflow = (ROOT / ".github/workflows/publish-pypi.yml").read_text(encoding="utf-8")
        self.assertIn("environment:\n      name: pypi", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn(
            "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33",
            workflow,
        )
        self.assertIn("github.ref_name", workflow)
        self.assertIn("github.ref_type", workflow)
        self.assertIn('gh release download "$GITHUB_REF_NAME"', workflow)
        self.assertIn("steps.names.outputs.wheel", workflow)
        self.assertIn("steps.names.outputs.sdist", workflow)
        self.assertNotIn("brief2ship-*.whl", workflow)
        self.assertNotIn("brief2ship-*.tar.gz", workflow)
        self.assertNotIn("python -m build", workflow)
        self.assertLess(
            workflow.index("python -m twine check"),
            workflow.index("python scripts/verify-release-assets.py"),
        )
        self.assertNotIn("types: [published]", workflow)
        self.assertNotIn("secrets.", workflow)

    def test_release_asset_verifier_requires_exact_files_and_checksums(self):
        version = "0.6.2"
        wheel = f"brief2ship-{version}-py3-none-any.whl"
        sdist = f"brief2ship-{version}.tar.gz"
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            (directory / wheel).write_bytes(b"wheel payload")
            (directory / sdist).write_bytes(b"sdist payload")
            sums = "\n".join(
                f"{hashlib.sha256((directory / name).read_bytes()).hexdigest()}  {name}"
                for name in (wheel, sdist)
            )
            (directory / "SHA256SUMS").write_text(sums + "\n", encoding="ascii")
            command = [
                sys.executable,
                str(ROOT / "scripts/verify-release-assets.py"),
                "--directory",
                str(directory),
                "--version",
                version,
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("Release assets verified", completed.stdout)

            (directory / "unexpected.whl").write_bytes(b"not declared")
            rejected = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(0, rejected.returncode)
            self.assertIn("must contain exactly", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
