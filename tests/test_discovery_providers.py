from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from brief2ship.discovery_http import (
    DiscoveryHttpClient,
    DiscoverySourceError,
    HttpPayload,
)
from brief2ship.discovery_providers import (
    canonical_repository_url,
    enrich_osv,
    search_crates,
    search_github,
    search_huggingface,
    search_npm,
    search_pypi,
)
from brief2ship.discovery_query import plan_query


class FakeClient(DiscoveryHttpClient):
    def __init__(self):
        super().__init__()
        self.routes: dict[str, object] = {}
        self.requested_json: list[str] = []
        self.simple = b'<a href="/simple/safe-web-scraper/">safe-web-scraper</a><a href="/simple/other/">other</a>'

    def get_json(self, url, *, headers=None, max_bytes=5_000_000):  # noqa: ARG002
        self.requested_json.append(url)
        value = self.routes[url]
        if isinstance(value, DiscoverySourceError):
            raise value
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

    def test_github_uses_bounded_rank_fusion_even_after_nonzero_results(self):
        client = FakeClient()
        query = "Build a local deterministic web scraper with retry support"
        variants = plan_query(query).variants
        self.assertEqual(3, len(variants))
        endpoints = [
            "https://api.github.com/search/repositories?"
            f"q={variant.replace(' ', '+')}&per_page=2&page=1"
            for variant in variants
        ]
        first = {
            "id": 9,
            "full_name": "owner/first-only",
            "html_url": "https://github.com/owner/first-only",
            "description": "first query result",
        }
        repeated = {
            "id": 10,
            "full_name": "owner/repeated",
            "html_url": "https://github.com/owner/repeated",
            "description": "result present in multiple queries",
        }
        client.routes[endpoints[0]] = {"items": [first, repeated]}
        client.routes[endpoints[1]] = {"items": [repeated]}
        client.routes[endpoints[2]] = {"items": []}

        candidates, receipt = search_github(query, 2, client)

        self.assertEqual(["owner/repeated", "owner/first-only"], [candidate.name for candidate in candidates])
        self.assertEqual([1, 2], [candidate.source_rank for candidate in candidates])
        self.assertEqual(list(variants), receipt.queries)
        self.assertEqual(endpoints, receipt.endpoints)
        self.assertEqual(endpoints, client.requested_json)

    def test_github_records_partial_query_failures_without_losing_results(self):
        client = FakeClient()
        query = "Build a local deterministic web scraper with retry support"
        variants = plan_query(query).variants
        endpoints = [
            "https://api.github.com/search/repositories?"
            f"q={variant.replace(' ', '+')}&per_page=1&page=1"
            for variant in variants
        ]
        client.routes[endpoints[0]] = {"items": [{
            "id": 11,
            "full_name": "owner/survivor",
            "html_url": "https://github.com/owner/survivor",
        }]}
        client.routes[endpoints[1]] = DiscoverySourceError("fixture timeout")
        client.routes[endpoints[2]] = {"items": []}

        candidates, receipt = search_github(query, 1, client)

        self.assertEqual(["owner/survivor"], [candidate.name for candidate in candidates])
        self.assertEqual("partial", receipt.status)
        self.assertEqual(list(variants), receipt.queries)
        self.assertEqual(endpoints, receipt.endpoints)
        self.assertTrue(any("fixture timeout" in warning for warning in receipt.warnings))

    def test_github_all_valid_empty_queries_are_ok_not_failed(self):
        client = FakeClient()
        query = "Build a local deterministic web scraper with retry support"
        variants = plan_query(query).variants
        for variant in variants:
            endpoint = (
                "https://api.github.com/search/repositories?"
                f"q={variant.replace(' ', '+')}&per_page=1&page=1"
            )
            client.routes[endpoint] = {"items": []}

        candidates, receipt = search_github(query, 1, client)

        self.assertEqual([], candidates)
        self.assertEqual("ok", receipt.status)
        self.assertIsNone(receipt.error)

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

    def test_pypi_dependency_metadata_distinguishes_empty_from_unknown(self):
        client = FakeClient()
        names = (
            "evidence-empty",
            "evidence-malformed",
            "evidence-missing",
            "evidence-null",
        )
        client.simple = b"".join(
            f'<a href="/simple/{name}/">{name}</a>'.encode() for name in names
        )
        for name in names:
            info: dict[str, object] = {
                "name": name,
                "version": "1.0.0",
                "summary": "dependency evidence",
                "package_url": f"https://pypi.org/project/{name}/",
            }
            if name == "evidence-empty":
                info["requires_dist"] = []
            elif name == "evidence-malformed":
                info["requires_dist"] = {"unexpected": "mapping"}
            elif name == "evidence-null":
                info["requires_dist"] = None
            client.routes[f"https://pypi.org/pypi/{name}/json"] = {
                "info": info,
                "releases": {"1.0.0": []},
            }

        with tempfile.TemporaryDirectory() as temporary:
            candidates, receipt = search_pypi(
                "evidence",
                4,
                client,
                cache_dir=Path(temporary),
            )

        counts = {candidate.name: candidate.dependency_count for candidate in candidates}
        self.assertEqual(0, counts["evidence-empty"])
        self.assertIsNone(counts["evidence-malformed"])
        self.assertIsNone(counts["evidence-missing"])
        self.assertIsNone(counts["evidence-null"])
        self.assertEqual([1, 2, 3, 4], [candidate.source_rank for candidate in candidates])
        self.assertTrue(any("requires_dist" in warning for warning in receipt.warnings))

    def test_pypi_no_name_matches_is_an_ok_empty_result(self):
        client = FakeClient()
        client.simple = b'<a href="/simple/unrelated/">unrelated</a>'

        with tempfile.TemporaryDirectory() as temporary:
            candidates, receipt = search_pypi(
                "web scraper",
                2,
                client,
                cache_dir=Path(temporary),
            )

        self.assertEqual([], candidates)
        self.assertEqual("ok", receipt.status)
        self.assertIsNone(receipt.error)
        self.assertEqual(["web scraper"], receipt.queries)

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

    def test_npm_dependency_hydration_keeps_failures_and_malformed_data_unknown(self):
        client = FakeClient()
        names = ("detail-empty", "detail-failed", "detail-malformed", "version-missing")
        search_endpoint = (
            "https://registry.npmjs.org/-/v1/search?text=detail&size=4"
        )
        client.routes[search_endpoint] = {
            "objects": [
                {
                    "package": {
                        "name": name,
                        "version": "1.0.0",
                        "links": {"npm": f"https://www.npmjs.com/package/{name}"},
                    }
                }
                for name in names
            ]
        }
        client.routes["https://registry.npmjs.org/detail-empty"] = {
            "versions": {"1.0.0": {}}
        }
        client.routes["https://registry.npmjs.org/detail-failed"] = (
            DiscoverySourceError("fixture detail failure")
        )
        client.routes["https://registry.npmjs.org/detail-malformed"] = {
            "versions": {"1.0.0": {"dependencies": ["not", "a", "mapping"]}}
        }
        client.routes["https://registry.npmjs.org/version-missing"] = {
            "versions": {"2.0.0": {"dependencies": {}}}
        }

        candidates, receipt = search_npm("detail", 4, client)

        counts = {candidate.name: candidate.dependency_count for candidate in candidates}
        self.assertEqual(0, counts["detail-empty"])
        self.assertIsNone(counts["detail-failed"])
        self.assertIsNone(counts["detail-malformed"])
        self.assertIsNone(counts["version-missing"])
        self.assertEqual([1, 2, 3, 4], [candidate.source_rank for candidate in candidates])
        self.assertEqual(["detail"], receipt.queries)
        self.assertTrue(any("fixture detail failure" in warning for warning in receipt.warnings))
        self.assertTrue(any("dependencies" in warning for warning in receipt.warnings))
        self.assertTrue(any("version 1.0.0" in warning for warning in receipt.warnings))

    def test_other_registry_providers_use_one_core_query(self):
        client = FakeClient()
        query = "Build a local web scraper"
        core = plan_query(query).core_query
        npm_search = (
            "https://registry.npmjs.org/-/v1/search?text=web+scraper&size=1"
        )
        client.routes[npm_search] = {"objects": []}
        crates_search = (
            "https://crates.io/api/v1/crates?"
            "q=web+scraper&sort=relevance&per_page=1&page=1"
        )
        client.routes[crates_search] = {"crates": []}
        for plural in ("models", "datasets", "spaces"):
            endpoint = (
                f"https://huggingface.co/api/{plural}?"
                "search=web+scraper&limit=1&full=true"
            )
            client.routes[endpoint] = []

        _, npm_receipt = search_npm(query, 1, client)
        _, crates_receipt = search_crates(query, 1, client)
        _, hf_receipt = search_huggingface(query, 1, client)

        self.assertEqual("web scraper", core)
        self.assertEqual([core], npm_receipt.queries)
        self.assertEqual([core], crates_receipt.queries)
        self.assertEqual([core], hf_receipt.queries)

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
