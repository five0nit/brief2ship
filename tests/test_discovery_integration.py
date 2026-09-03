from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from brief2ship.discovery import discover, prepare_output_directory
from brief2ship.discovery_http import DiscoveryHttpClient, HttpPayload
from brief2ship.discovery_models import (
    Candidate,
    DiscoveryConfig,
    DiscoveryResult,
    InspectionResult,
    SourceReceipt,
)
from brief2ship.discovery_render import render_discovery_markdown, write_discovery
from brief2ship.discovery_scoring import score_candidate
from brief2ship.errors import OutputError


class IntegrationClient(DiscoveryHttpClient):
    def __init__(self):
        super().__init__()

    def request(self, url, **kwargs):
        if url == "https://pypi.org/simple/":
            return HttpPayload(200, url, {}, b'<a href="x">safe-web-scraper</a>')
        return HttpPayload(404, url, {}, b"{}")

    def get_json(self, url, *, headers=None, max_bytes=5_000_000):  # noqa: ARG002
        if "api.github.com/search/repositories" in url:
            data = {"items": [{
                "id": 1, "full_name": "owner/github-tool", "html_url": "https://github.com/owner/github-tool",
                "description": "safe web scraper", "license": {"spdx_id": "MIT"},
                "pushed_at": "2026-07-29T00:00:00Z", "stargazers_count": 100, "size": 20,
                "language": "Python", "topics": ["scraper"],
            }]}
            headers_out = {"x-ratelimit-remaining": "40"}
        elif "pypi.org/pypi/" in url:
            data = {"info": {
                "name": "safe-web-scraper", "version": "1.0.0", "summary": "safe web scraper",
                "license_expression": "MIT", "requires_dist": [], "package_url": "https://pypi.org/project/safe-web-scraper/",
                "project_urls": {"Source": "https://github.com/owner/pypi-tool"}, "keywords": "safe scraper",
            }, "releases": {"1.0.0": [{"upload_time_iso_8601": "2026-07-28T00:00:00Z"}]}}
            headers_out = {}
        elif "registry.npmjs.org/-/v1/search" in url:
            data = {"objects": [{"package": {
                "name": "safe-npm-scraper", "version": "1.0.0", "description": "safe web scraper",
                "date": "2026-07-27T00:00:00Z", "links": {"npm": "https://npmjs.com/safe-npm-scraper", "repository": "https://github.com/owner/npm-tool"},
            }, "score": {"final": 0.9}}]}
            headers_out = {}
        elif url.endswith("registry.npmjs.org/safe-npm-scraper"):
            data = {"versions": {"1.0.0": {"license": "MIT", "dependencies": {}}}}
            headers_out = {}
        elif "crates.io/api/v1/crates?" in url:
            data = {"crates": [{
                "id": "safe-crate-scraper", "max_stable_version": "1.0.0", "description": "safe web scraper",
                "license": "MIT", "repository": "https://github.com/owner/crate-tool",
                "updated_at": "2026-07-26T00:00:00Z", "downloads": 50,
            }]}
            headers_out = {}
        elif url.endswith("/safe-crate-scraper/1.0.0/dependencies"):
            data = {"dependencies": []}
            headers_out = {}
        elif "huggingface.co/api/" in url:
            kind = "model" if "/models?" in url else "dataset" if "/datasets?" in url else "space"
            data = [{"id": f"owner/safe-{kind}", "downloads": 10, "likes": 2, "lastModified": "2026-07-25T00:00:00Z", "tags": ["license:mit", "scraper"]}]
            headers_out = {}
        else:
            raise KeyError(url)
        return data, HttpPayload(200, url, headers_out, json.dumps(data).encode())

    def post_json(self, url, body, *, max_bytes=5_000_000):  # noqa: ARG002
        return {}, HttpPayload(200, url, {}, b"{}")


class DiscoveryIntegrationTests(unittest.TestCase):
    def test_all_sources_produce_ranked_deterministic_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "result"
            result = discover(
                "safe web scraper",
                DiscoveryConfig(per_source=1, limit=10),
                output_dir=output,
                cache_dir=root / "cache",
                client=IntegrationClient(),
            )
            receipt = write_discovery(result, output)
            payload = json.loads((output / "discovery.json").read_text(encoding="utf-8"))
            markdown = receipt.read_text(encoding="utf-8")
        self.assertEqual({source.source for source in result.sources}, {"github", "pypi", "npm", "crates", "huggingface"})
        self.assertGreaterEqual(len(result.candidates), 5)
        self.assertEqual(payload["query"], "safe web scraper")
        self.assertEqual(payload["schema_version"], "brief2ship-discovery-v1")
        self.assertEqual(payload["scoring_contract"], "brief2ship-score-v1")
        self.assertEqual(payload["sandbox_policy"], "brief2ship-bwrap-v2")
        self.assertEqual(payload["config"]["total_timeout"], 180.0)
        self.assertIn("coverage", payload["candidates"][0]["score"])
        self.assertIn("recommendation_status", payload["candidates"][0])
        self.assertIn("Ranked candidates", markdown)
        scores = [candidate.score.total if candidate.score else -1 for candidate in result.candidates]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_output_directory_must_start_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "old.txt").write_text("old", encoding="utf-8")
            with self.assertRaises(OutputError):
                prepare_output_directory(root)

    def test_inspection_count_is_not_truncated_by_output_limit(self):
        candidates = [
            Candidate(
                source="github",
                name=f"owner/tool-{index}",
                url=f"https://github.com/owner/tool-{index}",
                repository_url=f"https://github.com/owner/tool-{index}",
                description="safe web scraper",
                license="MIT",
                updated_at="2026-07-29T00:00:00Z",
            )
            for index in range(2)
        ]
        provider = Mock(
            return_value=(candidates, SourceReceipt("github", "ok", 2, returned=2))
        )
        inspector = Mock()
        inspector.inspect.side_effect = lambda candidate, run_tests=False: InspectionResult(
            repository_url=candidate.repository_url or "",
            status="inspected",
        )

        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            "brief2ship.discovery.PROVIDERS",
            {"github": provider},
            clear=False,
        ), patch(
            "brief2ship.discovery.RepositoryInspector",
            return_value=inspector,
        ):
            result = discover(
                "safe web scraper",
                DiscoveryConfig(
                    sources=("github",),
                    per_source=2,
                    limit=1,
                    inspect_top=2,
                ),
                output_dir=Path(temporary) / "result",
                client=IntegrationClient(),
            )

        self.assertEqual(2, inspector.inspect.call_count)
        self.assertEqual(1, len(result.candidates))

    def test_inspection_shortlist_prioritizes_feature_fit_over_popularity(self):
        candidates = [
            Candidate(
                source="github",
                name="owner/popular-unrelated",
                url="https://github.com/owner/popular-unrelated",
                repository_url="https://github.com/owner/popular-unrelated",
                description="general utility",
                license="MIT",
                updated_at="2026-07-29T00:00:00Z",
                stars=1_000_000,
                dependency_count=0,
                security_policy=True,
                test_signals=["tests"],
                portability_signals=["cross-platform"],
                reuse_signals=["docs", "examples", "package"],
            ),
            Candidate(
                source="github",
                name="owner/robots-aware-package-discovery",
                url="https://github.com/owner/robots-aware-package-discovery",
                repository_url="https://github.com/owner/robots-aware-package-discovery",
                description="robots-aware package discovery",
                license="MIT",
            ),
        ]
        provider = Mock(
            return_value=(candidates, SourceReceipt("github", "ok", 2, returned=2))
        )
        inspected: list[str] = []
        inspector = Mock()

        def inspect(candidate, run_tests=False):
            inspected.append(candidate.name)
            return InspectionResult(
                repository_url=candidate.repository_url or "",
                status="inspected",
            )

        inspector.inspect.side_effect = inspect
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            "brief2ship.discovery.PROVIDERS",
            {"github": provider},
            clear=False,
        ), patch(
            "brief2ship.discovery.RepositoryInspector",
            return_value=inspector,
        ):
            discover(
                "robots-aware package discovery",
                DiscoveryConfig(
                    sources=("github",),
                    per_source=2,
                    limit=1,
                    inspect_top=1,
                ),
                output_dir=Path(temporary) / "result",
                client=IntegrationClient(),
            )

        self.assertEqual(["owner/robots-aware-package-discovery"], inspected)

    def test_local_only_discovery_inspects_existing_project_without_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "local-agent-starter"
            (project / "tests").mkdir(parents=True)
            (project / "pyproject.toml").write_text(
                '[project]\nname="local-agent-starter"\ndependencies=[]\n',
                encoding="utf-8",
            )
            (project / "README.md").write_text(
                "# Local Agent Starter\n",
                encoding="utf-8",
            )
            (project / "LICENSE").write_text("MIT License\n", encoding="utf-8")
            (project / "tests/test_one.py").write_text("VALUE = 1\n", encoding="utf-8")

            result = discover(
                "local agent starter",
                DiscoveryConfig(
                    sources=("local",),
                    local_roots=(str(root),),
                    per_source=5,
                    limit=5,
                    inspect_top=1,
                ),
                output_dir=root / "receipt",
                client=IntegrationClient(),
            )

        self.assertEqual(1, len(result.candidates))
        candidate = result.candidates[0]
        self.assertEqual("local", candidate.source)
        self.assertEqual("inspected", candidate.inspection.status if candidate.inspection else None)
        self.assertEqual(str(project.resolve()), candidate.local_path)
        self.assertEqual(0, candidate.dependency_count)
        self.assertEqual("local", result.sources[0].source)
        self.assertEqual("ok", result.sources[0].status)

    def test_malformed_source_is_recorded_without_traceback(self):
        class MalformedClient(IntegrationClient):
            def get_json(self, url, *, headers=None, max_bytes=5_000_000):  # noqa: ARG002
                data = {"items": [{"full_name": "bad/value", "stargazers_count": "not-an-int"}]}
                return data, HttpPayload(200, url, {}, json.dumps(data).encode())

        with tempfile.TemporaryDirectory() as temporary:
            result = discover(
                "safe web scraper",
                DiscoveryConfig(sources=("github",), per_source=1, limit=1),
                output_dir=Path(temporary) / "result",
                client=MalformedClient(),
            )
        self.assertEqual([], result.candidates)
        self.assertEqual("failed", result.sources[0].status)
        self.assertIn("invalid source response", result.sources[0].error or "")

    def test_markdown_keeps_untrusted_candidate_text_in_inert_code_spans(self):
        candidate = Candidate(
            source="github",
            name="bad`name|![track](https://example.invalid/x)",
            url="https://github.com/example/repo",
            description="\x1b]0;owned\x07\u061c\u200e\u200f\u202e",
        )
        score_candidate("bad name", candidate, now=datetime(2026, 7, 30, tzinfo=timezone.utc))
        result = DiscoveryResult(
            query="bad name",
            started_at="2026-07-30T00:00:00+00:00",
            completed_at="2026-07-30T00:00:01+00:00",
            config={},
            candidates=[candidate],
            sources=[SourceReceipt("github", "ok", 1, 1)],
            overall_recommendation=candidate.recommendation,
            recommendation_reason="test",
        )
        markdown = render_discovery_markdown(result)
        self.assertNotIn("\x1b", markdown)
        for control in ("\u061c", "\u200e", "\u200f", "\u202e"):
            self.assertNotIn(control, markdown)
        self.assertIn("``bad`name\\|![track](https://example.invalid/x)``", markdown)
        self.assertNotIn("| bad`name|", markdown)


if __name__ == "__main__":
    unittest.main()
