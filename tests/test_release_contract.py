import re
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
        self.assertEqual("0.6.1", version)
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
        self.assertIn("`docs/releases/v0.6.1-single-search-skill-receipt.md`", readme)
        self.assertIn("outside built packages", readme)


if __name__ == "__main__":
    unittest.main()
