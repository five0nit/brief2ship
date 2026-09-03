from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from brief2ship.discovery_http import DiscoveryHttpClient, HttpPayload
from brief2ship.discovery_providers import (
    canonical_repository_url,
    enrich_osv,
    search_crates,
    search_github,
    search_huggingface,
    search_npm,
    search_pypi,
)


class FakeClient(DiscoveryHttpClient):
    def __init__(self):
        super().__init__()
        self.routes: dict[str, object] = {}
        self.simple = b'<a href="/simple/safe-web-scraper/">safe-web-scraper</a><a href="/simple/other/">other</a>'

    def get_json(self, url, *, headers=None, max_bytes=5_000_000):  # noqa: ARG002
        value = self.routes[url]
        return value, HttpPayload(200, url, {"x-ratelimit-remaining": "42"}, json.dumps(value).encode())

    def post_json(self, url, body, *, max_bytes=5_000_000) -> tuple[object, HttpPayload]:  # noqa: ARG002
        value = {
            "vulns": [{
                "id": "OSV-TEST-1",
                "summary": "fixture issue",
                "modified": "2026-07-01T00:00:00Z",
                "aliases": ["CVE-TEST"],
                "severity": [{"type": "CVSS_V3", "score": "7.5"}],
            }]
        } if body["package"]["name"] == "unsafe" else {}
        return value, HttpPayload(200, url, {}, json.dumps(value).encode())

    def request(self, url, **kwargs):
        if url == "https://pypi.org/simple/":
            return HttpPayload(200, url, {}, self.simple)
        return HttpPayload(404, url, {}, b"{}")


class ProviderTests(unittest.TestCase):
    def test_repository_url_canonicalization(self):
        self.assertEqual(canonical_repository_url("git+https://github.com/Owner/Repo.git#readme"), "https://github.com/Owner/Repo")
        self.assertEqual(canonical_repository_url("git@github.com:Owner/Repo.git"), "https://github.com/Owner/Repo")
        self.assertIsNone(canonical_repository_url("file:///tmp/repo"))
        self.assertIsNone(
            canonical_repository_url(
                "https://oauth2:secret@gitlab.example.com/group/repo.git"
            )
        )
        self.assertEqual(
            "https://gitlab.example.com/group/repo",
            canonical_repository_url(
                "https://gitlab.example.com/group/repo.git?token=secret#readme"
            ),
        )

    def test_github_provider(self):
        client = FakeClient()
        endpoint = "https://api.github.com/search/repositories?q=web+scraper&per_page=1&page=1"
        client.routes[endpoint] = {"items": [{
            "id": 7, "full_name": "owner/repo", "html_url": "https://github.com/owner/repo",
            "description": "web scraper", "license": {"spdx_id": "MIT"}, "pushed_at": "2026-07-01T00:00:00Z",
            "stargazers_count": 50, "forks_count": 5, "open_issues_count": 2, "archived": False,
            "language": "Python", "topics": ["scraping"], "score": 1.0, "size": 123,
        }, {
            "id": 8, "full_name": "secret/private", "html_url": "https://github.com/secret/private",
            "private": True,
        }]}
        candidates, receipt = search_github("web scraper", 1, client)
        self.assertEqual(receipt.status, "ok")
        self.assertEqual(receipt.returned, 1)
        self.assertTrue(any("private" in warning for warning in receipt.warnings))
        self.assertEqual(receipt.rate_limit_remaining, 42)
        self.assertEqual(candidates[0].repository_size_kb, 123)

    def test_github_retries_zero_result_sentence_with_bounded_focus_query(self):
        client = FakeClient()
        original = (
            "https://api.github.com/search/repositories?"
            "q=repo-first+multi-ecosystem+code+discovery+and+reuse+scoring&"
            "per_page=1&page=1"
        )
        focused = (
            "https://api.github.com/search/repositories?"
            "q=repo+discovery+scoring&per_page=1&page=1"
        )
        client.routes[original] = {"items": []}
        client.routes[focused] = {
            "items": [
                {
                    "id": 9,
                    "full_name": "owner/repo-discovery",
                    "html_url": "https://github.com/owner/repo-discovery",
                    "description": "repository discovery and scoring",
                    "license": {"spdx_id": "MIT"},
                    "pushed_at": "2026-07-01T00:00:00Z",
                }
            ]
        }

        candidates, receipt = search_github(
            "repo-first multi-ecosystem code discovery and reuse scoring",
            1,
            client,
        )

        self.assertEqual(["owner/repo-discovery"], [candidate.name for candidate in candidates])
        self.assertEqual([original, focused], receipt.endpoints)
        self.assertTrue(any("focused fallback" in warning for warning in receipt.warnings))

    def test_pypi_provider_uses_simple_index_and_package_json(self):
        client = FakeClient()
        endpoint = "https://pypi.org/pypi/safe-web-scraper/json"
        client.routes[endpoint] = {
            "info": {
                "name": "safe-web-scraper", "version": "1.0.0", "summary": "web scraper",
                "license_expression": "MIT", "requires_dist": ["one", "two", "docs; extra == 'docs'"],
                "package_url": "https://pypi.org/project/safe-web-scraper/",
                "project_urls": {"Source": "https://github.com/owner/repo"}, "keywords": "scrape robots",
            },
            "releases": {"1.0.0": [{"upload_time_iso_8601": "2026-07-01T00:00:00Z"}]},
        }
        with tempfile.TemporaryDirectory() as temporary:
            candidates, receipt = search_pypi("safe web scraper", 1, client, cache_dir=Path(temporary))
        self.assertEqual(receipt.status, "ok")
        self.assertEqual(candidates[0].dependency_count, 2)
        self.assertEqual(candidates[0].repository_url, "https://github.com/owner/repo")

    def test_pypi_name_ties_are_alphabetical_not_reverse_alphabetical(self):
        client = FakeClient()
        client.simple = (
            b'<a href="/simple/safe-zulu/">safe-zulu</a>'
            b'<a href="/simple/safe-alpha/">safe-alpha</a>'
        )
        for name in ("safe-alpha", "safe-zulu"):
            client.routes[f"https://pypi.org/pypi/{name}/json"] = {
                "info": {
                    "name": name,
                    "version": "1.0.0",
                    "summary": "safe package",
                    "license_expression": "MIT",
                    "requires_dist": [],
                    "package_url": f"https://pypi.org/project/{name}/",
                },
                "releases": {
                    "1.0.0": [{"upload_time_iso_8601": "2026-07-01T00:00:00Z"}]
                },
            }

        with tempfile.TemporaryDirectory() as temporary:
            candidates, _ = search_pypi(
                "safe",
                1,
                client,
                cache_dir=Path(temporary),
            )

        self.assertEqual(["safe-alpha"], [candidate.name for candidate in candidates])

    def test_npm_crates_and_huggingface_providers(self):
        client = FakeClient()
        npm_search = "https://registry.npmjs.org/-/v1/search?text=web+scraper&size=1"
        client.routes[npm_search] = {"objects": [{
            "package": {"name": "web-scraper", "version": "1.0.0", "description": "scrape", "date": "2026-07-01T00:00:00Z", "links": {"npm": "https://npmjs.com/web-scraper", "repository": "https://github.com/owner/npm"}},
            "score": {"final": 0.9},
        }]}
        client.routes["https://registry.npmjs.org/web-scraper"] = {"versions": {"1.0.0": {"license": "MIT", "dependencies": {"a": "1"}, "devDependencies": {"b": "1"}}}}
        npm, _ = search_npm("web scraper", 1, client)
        self.assertEqual(npm[0].dependency_count, 1)

        crates_search = "https://crates.io/api/v1/crates?q=web+scraper&sort=relevance&per_page=1&page=1"
        client.routes[crates_search] = {"crates": [{"id": "web-scraper", "max_stable_version": "1.0.0", "description": "scrape", "license": "MIT", "repository": "https://github.com/owner/crate", "updated_at": "2026-07-01T00:00:00Z", "downloads": 10}]}
        client.routes["https://crates.io/api/v1/crates/web-scraper/1.0.0/dependencies"] = {"dependencies": [{"crate_id": "a"}]}
        crates, _ = search_crates("web scraper", 1, client)
        self.assertEqual(crates[0].dependency_count, 1)

        for plural in ("models", "datasets", "spaces"):
            endpoint = f"https://huggingface.co/api/{plural}?search=web+scraper&limit=1&full=true"
            client.routes[endpoint] = [{"id": f"owner/{plural}", "downloads": 5, "likes": 1, "lastModified": "2026-07-01T00:00:00Z", "tags": ["license:mit"]}]
        hf, receipt = search_huggingface("web scraper", 3, client)
        self.assertEqual(receipt.returned, 3)
        self.assertEqual({item.license for item in hf}, {"mit"})

    def test_osv_findings_are_preserved(self):
        from brief2ship.discovery_models import Candidate

        candidate = Candidate(source="npm", name="unsafe", version="1.0.0", url="https://npmjs.com/unsafe")
        warning = enrich_osv(candidate, FakeClient())
        self.assertIsNone(warning)
        self.assertTrue(candidate.vulnerabilities_checked)
        self.assertEqual(candidate.vulnerabilities, ["OSV-TEST-1"])
        self.assertEqual(candidate.vulnerability_evidence[0]["aliases"], ["CVE-TEST"])

    def test_malformed_osv_response_remains_unknown(self):
        class MalformedClient(FakeClient):
            def post_json(self, url, body, *, max_bytes=5_000_000) -> tuple[object, HttpPayload]:  # noqa: ARG002
                value = {"vulns": {"id": "bad"}}
                return value, HttpPayload(200, url, {}, json.dumps(value).encode())

        from brief2ship.discovery_models import Candidate

        candidate = Candidate(source="npm", name="tool", version="1.0.0", url="https://npmjs.com/tool")
        warning = enrich_osv(candidate, MalformedClient())
        self.assertIn("not a list", warning or "")
        self.assertFalse(candidate.vulnerabilities_checked)


if __name__ == "__main__":
    unittest.main()
