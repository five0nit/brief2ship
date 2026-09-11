from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from brief2ship.discovery_http import DiscoverySourceError
from brief2ship.discovery_providers import search_pypi
from tests.test_discovery_providers import FakeClient


class PyPIRetrievalTests(unittest.TestCase):
    def client(self, records: dict[str, dict[str, object]]) -> FakeClient:
        client = FakeClient()
        client.simple = b"".join(
            f'<a href="/simple/{name}/">{name}</a>'.encode() for name in records
        )
        for name, metadata in records.items():
            client.routes[f"https://pypi.org/pypi/{name}/json"] = {
                "info": {"name": name, "version": "1.0.0", **metadata},
                "releases": {},
            }
        return client

    def discover(self, query: str, limit: int, client: FakeClient):
        with tempfile.TemporaryDirectory() as root:
            return search_pypi(query, limit, client, cache_dir=Path(root))

    def test_non_obvious_name_is_retrieved_from_observed_hint_and_metadata(self):
        client = self.client({
            "Scrapy": {"summary": "Fixture web scraper framework"},
            "unrelated": {"summary": "Other fixture"},
        })

        candidates, receipt = self.discover("web scraper", 2, client)

        self.assertEqual(["Scrapy"], [candidate.name for candidate in candidates])
        self.assertEqual(["https://pypi.org/pypi/Scrapy/json"], client.requested_json)
        self.assertEqual(["web scraper"], receipt.queries)
        self.assertEqual("ok", receipt.status)
        self.assertTrue(any("curated discovery hints for web scraping: Scrapy" in message for message in receipt.warnings))
        self.assertTrue(any("not full-text index search or exhaustive coverage" in message for message in receipt.warnings))
        self.assertEqual("Fixture web scraper framework", candidates[0].description)
        self.assertIsNone(candidates[0].license)
        self.assertIsNone(candidates[0].dependency_count)
        evidence = candidates[0].retrieval_evidence
        self.assertEqual(["curated-hint:web scraping"], evidence["routes"])
        self.assertEqual("https://pypi.org/pypi/Scrapy/json", evidence["metadata_url"])
        self.assertEqual([], evidence["matched_terms"]["name"])
        self.assertEqual(["scraper", "web"], evidence["matched_terms"]["summary"])

    def test_command_line_hint_does_not_require_package_name_match(self):
        client = self.client({"click": {"summary": "Fixture command line argument parsing"}})

        candidates, receipt = self.discover("command line argument parser", 1, client)

        self.assertEqual(["click"], [candidate.name for candidate in candidates])
        self.assertTrue(any("command-line arguments: click" in message for message in receipt.warnings))

    def test_hydrated_summary_keywords_and_description_rerank_name_ties(self):
        for field in ("summary", "keywords", "description"):
            with self.subTest(field=field):
                client = self.client({
                    "aaa-web": {"summary": "Fixture theme colors"},
                    "zzz-web": {field: "web scraper"},
                })

                candidates, receipt = self.discover("web scraper", 1, client)

                self.assertEqual(["zzz-web"], [candidate.name for candidate in candidates])
                self.assertEqual(2, len(client.requested_json))
                self.assertEqual(1, receipt.returned)
                self.assertEqual(1, candidates[0].source_rank)
                evidence = candidates[0].retrieval_evidence
                self.assertEqual(["scraper", "web"], evidence["matched_terms"][field])
                self.assertEqual(["web scraper"], evidence["supporting_excerpts"][field])
                self.assertEqual(3, evidence["hydration_budget"])
                self.assertEqual(2, evidence["hydration_shortlist_count"])

    def test_hints_and_lexical_matches_share_a_bounded_hydration_budget(self):
        client = self.client({
            **{f"fixture-web-{index:03}": {"summary": "Fixture web theme"} for index in range(100)},
            "scrapy": {"summary": "Fixture web scraper"},
            "beautifulsoup4": {"summary": "Fixture HTML parser"},
            "trafilatura": {"summary": "Fixture web extraction"},
        })

        candidates, receipt = self.discover("web scraper", 2, client)

        self.assertEqual(6, len(client.requested_json))
        self.assertEqual(6, len(set(client.requested_json)))
        self.assertIn("https://pypi.org/pypi/scrapy/json", client.requested_json)
        self.assertTrue(any("fixture-web-" in endpoint for endpoint in client.requested_json))
        self.assertEqual("scrapy", candidates[0].name)
        self.assertEqual([1, 2], [candidate.source_rank for candidate in candidates])
        self.assertTrue(any("capped at 6 JSON requests" in message for message in receipt.warnings))

    def test_unobserved_hints_do_not_create_requests_or_candidates(self):
        client = self.client({"unrelated": {"summary": "Fixture"}})

        candidates, receipt = self.discover("web scraper", 2, client)

        self.assertEqual([], candidates)
        self.assertEqual([], client.requested_json)
        self.assertEqual("ok", receipt.status)
        self.assertTrue(any("hydrating 0 name(s)" in message for message in receipt.warnings))

    def test_failed_hint_hydration_remains_partial_with_real_other_results(self):
        client = self.client({
            "fixture-web": {"summary": "Fixture web scraper"},
            "scrapy": {},
        })
        endpoint = "https://pypi.org/pypi/scrapy/json"
        client.routes[endpoint] = DiscoverySourceError("fixture outage")

        candidates, receipt = self.discover("web scraper", 2, client)

        self.assertEqual(["fixture-web"], [candidate.name for candidate in candidates])
        self.assertEqual("partial", receipt.status)
        self.assertIn(endpoint, receipt.endpoints)
        self.assertIn("fixture outage", receipt.error or "")

    def test_missing_or_mismatched_identity_is_not_evidence_for_a_hint(self):
        for info in ({"summary": "web scraper"}, {"name": "other-project", "summary": "web scraper"}):
            with self.subTest(info=info):
                client = self.client({"scrapy": {}})
                client.routes["https://pypi.org/pypi/scrapy/json"] = {"info": info}

                candidates, receipt = self.discover("web scraper", 1, client)

                self.assertEqual([], candidates)
                self.assertEqual("partial", receipt.status)
                self.assertIn("identity was missing or mismatched", receipt.error or "")

    def test_python_runtime_name_matches_do_not_crowd_out_topic_candidates(self):
        client = self.client({
            **{f"python-fixture-{index:03}": {} for index in range(100)},
            "scrapy": {"summary": "Fixture web scraper"},
        })

        candidates, receipt = self.discover("Python web scraper", 1, client)

        self.assertEqual(["scrapy"], [candidate.name for candidate in candidates])
        self.assertEqual(["https://pypi.org/pypi/scrapy/json"], client.requested_json)
        self.assertEqual("ok", receipt.status)

    def test_package_aliases_do_not_duplicate_hydration_or_result(self):
        client = self.client({
            "web_parser": {"summary": "Fixture web scraper"},
            "web-parser": {"summary": "Fixture web scraper"},
        })

        candidates, receipt = self.discover("web scraper", 2, client)

        self.assertEqual(1, len(candidates))
        self.assertEqual(1, len(client.requested_json))
        self.assertEqual(1, receipt.returned)

    def test_detail_requests_remain_capped_for_large_result_limits(self):
        client = self.client({f"web-{index:03}": {"summary": "Fixture web scraper"} for index in range(100)})

        candidates, receipt = self.discover("web scraper", 20, client)

        self.assertEqual(60, len(client.requested_json))
        self.assertEqual(20, len(candidates))
        self.assertTrue(any("capped at 60 JSON requests" in message for message in receipt.warnings))

    def test_description_ranking_and_supporting_excerpts_remain_bounded(self):
        client = self.client({
            "aaa-web": {"description": "x" * 17_000 + " scraper"},
            "zzz-web": {"description": "x " * 500 + "web scraper " + "x " * 20_000},
        })

        candidates, _ = self.discover("web scraper", 2, client)

        self.assertEqual(["zzz-web", "aaa-web"], [candidate.name for candidate in candidates])
        for candidate in candidates:
            self.assertEqual(16_384, candidate.retrieval_evidence["description_characters_considered"])
            excerpts = candidate.retrieval_evidence["supporting_excerpts"]["description"]
            self.assertTrue(all(len(excerpt) <= 240 for excerpt in excerpts))
            self.assertLessEqual(len(excerpts), 3)
        self.assertEqual([], candidates[1].retrieval_evidence["matched_terms"]["description"])
        self.assertEqual([], candidates[1].retrieval_evidence["supporting_excerpts"]["description"])

    def test_http_client_pool_preserves_metadata_relevant_non_name_hint(self):
        # Synthetic metadata fixture modeled on the observed failure shape;
        # these descriptions are test data, not a saved live PyPI response.
        client = self.client({
            "alt-stack-http-client-httpx": {"summary": "HTTP client integration"},
            "aas-http-client": {"summary": "HTTP client integration"},
            "aas-python-http-client": {"summary": "HTTP client integration"},
            "httpx": {"summary": "The next generation HTTP client.", "description": "An HTTP client with sync and async APIs."},
            "requests": {"summary": "HTTP for Humans."},
            "aiohttp": {},
        })
        client.routes["https://pypi.org/pypi/aiohttp/json"] = DiscoverySourceError(
            "source declared 9150000 bytes; cap is 3000000"
        )

        candidates, receipt = self.discover("Python HTTP client", 3, client)

        self.assertEqual(3, len(candidates))
        self.assertIn("httpx", [candidate.name for candidate in candidates])
        self.assertEqual("partial", receipt.status)
        self.assertIn("cap is 3000000", receipt.error or "")
        httpx = next(candidate for candidate in candidates if candidate.name == "httpx")
        policy = httpx.retrieval_evidence["pool_selection"]
        self.assertEqual(["client", "http"], policy["metadata_matching_terms"])
        self.assertEqual("reserve-one-metadata-relevant-non-name-hint", policy["policy"])
        self.assertTrue(any("comparison diversity reserved one slot for httpx" in warning for warning in receipt.warnings))

    def test_diversity_does_not_promote_a_hint_without_metadata_relevance(self):
        client = self.client({
            "aaa-http-client": {"summary": "HTTP client"},
            "bbb-http-client": {"summary": "HTTP client"},
            "httpx": {"summary": "Fixture decorative colors"},
        })

        candidates, _ = self.discover("HTTP client", 2, client)

        self.assertEqual(["aaa-http-client", "bbb-http-client"], [candidate.name for candidate in candidates])

    def test_irrelevant_hint_is_filtered_even_when_result_slots_are_empty(self):
        for limit in (1, 2):
            for with_name_match in (False, True):
                with self.subTest(limit=limit, with_name_match=with_name_match):
                    records: dict[str, dict[str, object]] = {
                        "scrapy": {"summary": "Fixture decorative colors"}
                    }
                    if with_name_match:
                        records["fixture-web"] = {"summary": "web scraper"}
                    client = self.client(records)

                    candidates, receipt = self.discover("web scraper", limit, client)

                    expected = ["fixture-web"] if with_name_match else []
                    self.assertEqual(expected, [candidate.name for candidate in candidates])
                    endpoint = "https://pypi.org/pypi/scrapy/json"
                    self.assertIn(endpoint, client.requested_json)
                    self.assertIn(endpoint, receipt.endpoints)
                    self.assertEqual(len(expected), receipt.returned)
                    self.assertEqual("ok", receipt.status)
                    self.assertTrue(any("filtered scrapy" in warning for warning in receipt.warnings))

    def test_hint_metadata_relevance_is_observed_in_each_supported_field(self):
        for field in ("summary", "keywords", "description"):
            with self.subTest(field=field):
                client = self.client({"scrapy": {field: "scraper"}})

                candidates, _ = self.discover("web scraper", 1, client)

                self.assertEqual(["scrapy"], [candidate.name for candidate in candidates])
                evidence = candidates[0].retrieval_evidence
                self.assertEqual(["scraper"], evidence["matched_terms"][field])
                self.assertEqual(["curated-hint:web scraping"], evidence["routes"])

    def test_exact_package_is_hydrated_first_under_a_saturated_name_budget(self):
        for query, name in (("httpx", "httpx"), ("HTTPX", "httpx"), ("web_scraper", "Web.Scraper")):
            for limit in (1, 2):
                with self.subTest(query=query, limit=limit):
                    client = self.client({
                        **{f"aaa-{name}-{index:03}": {"summary": "web scraper"} for index in range(20)},
                        name: {},
                        "scrapy": {"summary": "web scraper"},
                    })

                    candidates, receipt = self.discover(query, limit, client)

                    endpoint = f"https://pypi.org/pypi/{name}/json"
                    self.assertEqual(endpoint, client.requested_json[0])
                    self.assertEqual(limit * 3, len(client.requested_json))
                    self.assertEqual(len(client.requested_json), len(set(client.requested_json)))
                    self.assertEqual(name, candidates[0].name)
                    self.assertEqual(1, candidates[0].retrieval_evidence["rank_basis"]["exact_name"])
                    self.assertIn("package-name-match", candidates[0].retrieval_evidence["routes"])
                    self.assertEqual(limit, receipt.returned)
                    self.assertEqual("ok", receipt.status)

    def test_meaningful_topic_beats_generic_names_before_hydration(self):
        for generic in ("library", "libraries", "package", "tool", "framework"):
            with self.subTest(generic=generic):
                client = self.client({
                    **{f"aaa-{generic}-{index:03}": {"summary": f"Python {generic}"} for index in range(20)},
                    "zzz-retry": {"summary": "retry failed operations"},
                })

                candidates, receipt = self.discover(f"Python retry {generic}", 3, client)

                endpoint = "https://pypi.org/pypi/zzz-retry/json"
                self.assertEqual(endpoint, client.requested_json[0])
                self.assertLessEqual(len(client.requested_json), 9)
                self.assertEqual("zzz-retry", candidates[0].name)
                self.assertEqual("ok", receipt.status)
                self.assertEqual(["package-name-match"], candidates[0].retrieval_evidence["routes"])

    def test_topic_metadata_outranks_generic_term_coverage(self):
        for field in ("summary", "keywords", "description"):
            with self.subTest(field=field):
                client = self.client({
                    "aaa-retry-library-package": {
                        "summary": "Python library package",
                        "keywords": "library package",
                        "description": "library package",
                    },
                    "zzz-retry": {field: "retry"},
                })

                candidates, _ = self.discover("Python retry library package", 1, client)

                self.assertEqual(["zzz-retry"], [candidate.name for candidate in candidates])
                self.assertEqual(2, len(client.requested_json))
                evidence = candidates[0].retrieval_evidence
                self.assertEqual(["retry"], evidence["matched_terms"][field])
                self.assertEqual(["retry"], evidence["query_terms"])
                self.assertEqual(["library", "package", "python"], evidence["ignored_query_terms"])

    def test_generic_terms_alone_do_not_make_hint_metadata_relevant(self):
        client = self.client({"scrapy": {"summary": "Python library package"}})

        candidates, receipt = self.discover("Python web scraper library package", 2, client)

        self.assertEqual([], candidates)
        self.assertEqual(["https://pypi.org/pypi/scrapy/json"], client.requested_json)
        self.assertEqual("ok", receipt.status)

    def test_generic_only_and_short_exact_names_remain_discoverable(self):
        for name in ("library", "python", "a", "x", "the"):
            with self.subTest(name=name):
                client = self.client({
                    **{f"aaa-{name}-{index:03}": {} for index in range(10)},
                    name: {},
                })

                candidates, _ = self.discover(name, 1, client)

                self.assertEqual([name], [candidate.name for candidate in candidates])
                self.assertEqual(f"https://pypi.org/pypi/{name}/json", client.requested_json[0])
                self.assertLessEqual(len(client.requested_json), 3)
                self.assertEqual(["package-name-match"], candidates[0].retrieval_evidence["routes"])

    def test_diversity_preserves_exact_package_name_and_single_result_behavior(self):
        records = {
            "web-scraper": {"summary": "web scraper"},
            "aaa-web-scraper": {"summary": "web scraper"},
            "scrapy": {"summary": "web scraper"},
        }
        for limit in (1, 2):
            with self.subTest(limit=limit):
                candidates, _ = self.discover("web-scraper", limit, self.client(records))

                self.assertEqual("web-scraper", candidates[0].name)
                self.assertEqual(limit, len(candidates))
                if limit == 2:
                    self.assertEqual("scrapy", candidates[1].name)


if __name__ == "__main__":
    unittest.main()
