import unittest

from brief2ship.crawl import crawl_site
from brief2ship.errors import PolicyError
from brief2ship.models import ScrapeConfig
from tests.support import fixture_site


class CrawlTests(unittest.TestCase):
    def config(self):
        return ScrapeConfig(allow_private=True, extractor="stdlib", min_delay=0)

    def test_same_origin_bounded_crawl_and_robots_cache(self):
        sleeps = []
        with fixture_site() as (base, handler):
            result = crawl_site(
                f"{base}/article",
                config=self.config(),
                max_pages=5,
                max_depth=1,
                sleep=sleeps.append,
            )
        self.assertEqual(2, len(result.pages))
        self.assertEqual(0, len(result.failures))
        self.assertEqual(1, handler.requests.count("/robots.txt"))
        self.assertNotIn("/external", handler.requests)
        self.assertTrue(sleeps)

    def test_page_cap_is_hard_bounded(self):
        with fixture_site() as (base, _):
            result = crawl_site(
                f"{base}/article",
                config=self.config(),
                max_pages=1,
                max_depth=3,
                sleep=lambda _: None,
            )
        self.assertEqual(1, len(result.pages))

    def test_page_cap_counts_failed_attempts_not_only_successes(self):
        with fixture_site() as (base, handler):
            result = crawl_site(
                f"{base}/many",
                config=self.config(),
                max_pages=3,
                max_depth=1,
                sleep=lambda _: None,
            )
        self.assertEqual(1, len(result.pages))
        self.assertEqual(2, len(result.failures))
        self.assertEqual(3, result.to_dict()["attempted_count"])
        page_requests = [path for path in handler.requests if path != "/robots.txt"]
        self.assertEqual(3, len(page_requests))

    def test_blocked_page_becomes_failure_without_fetching_content(self):
        with fixture_site() as (base, handler):
            result = crawl_site(
                f"{base}/blocked",
                config=self.config(),
                sleep=lambda _: None,
            )
        self.assertEqual([], result.pages)
        self.assertEqual("RobotsDenied", result.failures[0].error_type)
        self.assertEqual(["/robots.txt"], handler.requests)

    def test_cached_robots_document_is_re_evaluated_for_each_path(self):
        with fixture_site() as (base, handler):
            result = crawl_site(
                f"{base}/index-with-blocked",
                config=self.config(),
                max_pages=5,
                max_depth=1,
                sleep=lambda _: None,
            )
        self.assertEqual(2, len(result.pages))
        self.assertEqual("RobotsDenied", result.failures[0].error_type)
        self.assertEqual(1, handler.requests.count("/robots.txt"))
        self.assertNotIn("/blocked", handler.requests)

    def test_caps_rejected(self):
        with self.assertRaises(PolicyError):
            crawl_site("https://example.com", max_pages=21)
        with self.assertRaises(PolicyError):
            crawl_site("https://example.com", max_depth=4)


if __name__ == "__main__":
    unittest.main()
