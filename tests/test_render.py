import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from brief2ship.errors import OutputError
from brief2ship.models import CrawlResult, ScrapeResult
from brief2ship.render import atomic_write, render_json, render_markdown, render_text, write_crawl


def result(url: str = "https://example.com/article") -> ScrapeResult:
    return ScrapeResult(
        requested_url=url,
        final_url=url,
        fetched_at="2026-07-30T00:00:00+00:00",
        status_code=200,
        content_type="text/html",
        title="Evidence",
        text="Useful text.",
        links=["https://example.com/two"],
        extractor="stdlib",
        bytes_read=12,
        sha256="a" * 64,
        robots_url="https://example.com/robots.txt",
        robots_allowed=True,
        crawl_delay=1.0,
        warnings=["fixture"],
    )


class RenderTests(unittest.TestCase):
    def test_json_is_parseable_and_contains_provenance(self):
        payload = json.loads(render_json(result()))
        self.assertEqual("stdlib", payload["extractor"])
        self.assertEqual("a" * 64, payload["sha256"])
        self.assertTrue(payload["robots_allowed"])

    def test_markdown_contains_provenance_and_content(self):
        output = render_markdown(result())
        self.assertIn("## Provenance", output)
        self.assertIn("SHA-256", output)
        self.assertIn("Useful text.", output)

    def test_markdown_fences_untrusted_content_and_strips_controls(self):
        hostile = replace(
            result(),
            title="![title](https://tracker.invalid/title)",
            text=(
                "![pixel](https://tracker.invalid/pixel)\n```\n"
                "\x1b]8;;https://evil.invalid\x07label\u061c\u200e\u200f\u202e"
            ),
            warnings=["![warning](https://tracker.invalid/warning)"],
        )
        output = render_markdown(hostile)
        self.assertTrue(output.startswith("# Brief2Ship scrape receipt\n"))
        self.assertNotIn("\x1b", output)
        self.assertNotIn("\x07", output)
        for control in ("\u061c", "\u200e", "\u200f", "\u202e"):
            self.assertNotIn(control, output)
        content = output.split("## Extracted content\n\n", 1)[1]
        self.assertTrue(content.startswith("````text\n"))
        self.assertTrue(content.rstrip().endswith("````"))

    def test_text_contains_content_only(self):
        self.assertEqual("Useful text.\n", render_text(result()))

    def test_text_strips_terminal_controls(self):
        hostile = replace(result(), text="safe\x1b]0;owned\x07text")
        self.assertEqual("safe]0;ownedtext\n", render_text(hostile))

    def test_atomic_write_replaces_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.txt"
            atomic_write(path, "one")
            atomic_write(path, "two")
            self.assertEqual("two", path.read_text(encoding="utf-8"))

    def test_write_crawl_creates_manifest_and_page_receipts(self):
        crawl = CrawlResult(
            start_url="https://example.com/",
            started_at="start",
            completed_at="end",
            max_pages=5,
            max_depth=1,
            delay_seconds=1,
            pages=[result()],
            failures=[],
        )
        with tempfile.TemporaryDirectory() as tmp:
            manifest = write_crawl(crawl, tmp)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(1, payload["page_count"])
            self.assertTrue((Path(tmp) / "pages/0001.json").is_file())
            self.assertTrue((Path(tmp) / "pages/0001.md").is_file())

    def test_write_crawl_refuses_non_empty_directory(self):
        crawl = CrawlResult(
            start_url="https://example.com/",
            started_at="start",
            completed_at="end",
            max_pages=1,
            max_depth=0,
            delay_seconds=1,
            pages=[result()],
            failures=[],
        )
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "stale.json").write_text("stale", encoding="utf-8")
            with self.assertRaisesRegex(OutputError, "must be empty"):
                write_crawl(crawl, tmp)


if __name__ == "__main__":
    unittest.main()
