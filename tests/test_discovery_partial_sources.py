from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from brief2ship.discovery_http import DiscoverySourceError
from brief2ship.discovery_providers import search_npm, search_pypi, search_crates, search_huggingface
from tests.test_discovery_providers import FakeClient


class PartialSourceTests(unittest.TestCase):
    def test_npm_failed_detail_is_partial_and_endpoint_is_retained(self):
        client = FakeClient()
        client.routes['https://registry.npmjs.org/-/v1/search?text=web+scraper&size=1'] = {
            'objects': [{'package': {'name': 'web-scraper', 'version': '1.0.0'}}],
        }
        detail = 'https://registry.npmjs.org/web-scraper'
        client.routes[detail] = DiscoverySourceError('fixture outage')
        candidates, receipt = search_npm('web scraper', 1, client)
        self.assertEqual(1, len(candidates))
        self.assertEqual('partial', receipt.status)
        self.assertIn(detail, receipt.endpoints)
        self.assertIn('fixture outage', receipt.error)
        self.assertIsNone(candidates[0].dependency_count)

    def test_huggingface_malformed_nested_fields_write_receipts(self):
        import json
        from brief2ship.discovery import discover
        from brief2ship.discovery_models import DiscoveryConfig
        from brief2ship.discovery_render import write_discovery
        for bad in ({"cardData": "malformed"}, {"tags": {}}, {"likes": []}, {"gated": {}}):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as directory:
                client = FakeClient()
                for kind in ("models", "datasets", "spaces"):
                    client.routes[f"https://huggingface.co/api/{kind}?search=web+scraper&limit=1&full=true"] = [
                        {"id": "fixture/item", **bad},
                    ]
                result = discover("web scraper", DiscoveryConfig(sources=("huggingface",), per_source=3), output_dir=Path(directory), client=client)
                self.assertEqual("inconclusive", result.overall_recommendation)
                self.assertEqual("partial", result.sources[0].status)
                self.assertEqual(3, len(result.sources[0].endpoints))
                write_discovery(result, Path(directory))
                self.assertEqual("inconclusive", json.loads((Path(directory) / "discovery.json").read_text())["overall_recommendation"])

    def test_pypi_failed_project_request_is_partial(self):
        client = FakeClient()
        detail = 'https://pypi.org/pypi/safe-web-scraper/json'
        client.routes[detail] = DiscoverySourceError('fixture outage')
        with tempfile.TemporaryDirectory() as root:
            _, receipt = search_pypi('web scraper', 1, client, cache_dir=Path(root))
        self.assertEqual('partial', receipt.status)
        self.assertIn(detail, receipt.endpoints)
        self.assertIn('fixture outage', receipt.error)

    def test_crates_failed_dependency_request_is_partial(self):
        client = FakeClient()
        client.routes['https://crates.io/api/v1/crates?q=web+scraper&sort=relevance&per_page=1&page=1'] = {
            'crates': [{'id': 'web-scraper', 'max_stable_version': '1.0.0'}],
        }
        detail = 'https://crates.io/api/v1/crates/web-scraper/1.0.0/dependencies'
        client.routes[detail] = DiscoverySourceError('fixture outage')
        _, receipt = search_crates('web scraper', 1, client)
        self.assertEqual('partial', receipt.status)
        self.assertIn(detail, receipt.endpoints)

    def test_huggingface_one_failed_kind_is_partial_not_complete(self):
        client = FakeClient()
        for kind in ('models', 'datasets', 'spaces'):
            client.routes[f'https://huggingface.co/api/{kind}?search=web+scraper&limit=1&full=true'] = []
        client.routes['https://huggingface.co/api/datasets?search=web+scraper&limit=1&full=true'] = DiscoverySourceError('fixture outage')
        _, receipt = search_huggingface('web scraper', 3, client)
        self.assertEqual('partial', receipt.status)
        self.assertIn('fixture outage', receipt.error)


if __name__ == '__main__':
    unittest.main()
