import unittest

from brief2ship.models import ScrapeConfig
from brief2ship.scrape import Scraper
from tests.support import fixture_site


class ScrapeTests(unittest.TestCase):
    def test_full_round_trip_has_receipts_and_clean_text(self):
        with fixture_site() as (base, _):
            result = Scraper(ScrapeConfig(allow_private=True, extractor="stdlib")).scrape(
                f"{base}/article"
            )
        self.assertEqual("Fixture Article", result.title)
        self.assertIn("Useful heading", result.text)
        self.assertNotIn("Discard navigation", result.text)
        self.assertEqual(64, len(result.sha256))
        self.assertTrue(result.robots_allowed)
        self.assertIn(f"{base}/page2", result.links)


if __name__ == "__main__":
    unittest.main()
