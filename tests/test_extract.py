import unittest

from brief2ship.extract import extract_content
from brief2ship.errors import ExtractionError
from brief2ship.models import FetchResult, RobotsPolicy


def fetched(body: bytes, content_type: str = "text/html", charset: str = "utf-8") -> FetchResult:
    return FetchResult(
        requested_url="https://example.com/article",
        final_url="https://example.com/article",
        fetched_at="2026-07-30T00:00:00+00:00",
        status_code=200,
        content_type=content_type,
        charset=charset,
        body=body,
        bytes_read=len(body),
        sha256="0" * 64,
        robots=RobotsPolicy("https://example.com/robots.txt", True, None, 200),
    )


class ExtractTests(unittest.TestCase):
    def test_stdlib_extracts_readable_content_and_links(self):
        html = b"""<html><head><title>  Good title </title><style>bad</style></head><body>
        <nav>discard</nav><main><h1>Heading</h1><p>Alpha &amp; beta.</p><li>Item</li>
        <a href='/two#x'>Two</a><script>discard()</script></main></body></html>"""
        result = extract_content(fetched(html), "stdlib")
        self.assertEqual("Good title", result.title)
        self.assertIn("Heading", result.text)
        self.assertIn("Alpha & beta.", result.text)
        self.assertIn("• Item", result.text)
        self.assertNotIn("discard", result.text)
        self.assertEqual(("https://example.com/two",), result.links)

    def test_plain_text_bypasses_html_parser(self):
        result = extract_content(fetched(b" evidence  here ", "text/plain"), "auto")
        self.assertEqual("evidence here", result.text)
        self.assertEqual("plain-text", result.extractor)

    def test_plain_text_strips_terminal_and_bidi_controls(self):
        hostile = (
            "safe\x1b]8;;https://evil.invalid\x07label\x1b]8;;\x07"
            "\u061c\u200e\u200f\u202eevil"
        ).encode()
        result = extract_content(
            fetched(hostile, "text/plain"),
            "auto",
        )
        self.assertNotIn("\x1b", result.text)
        self.assertNotIn("\x07", result.text)
        self.assertNotIn("\u202e", result.text)
        self.assertNotIn("\u061c", result.text)
        self.assertNotIn("\u200e", result.text)
        self.assertNotIn("\u200f", result.text)
        self.assertIn("safe", result.text)

    def test_unknown_response_charset_is_expected_extraction_failure(self):
        with self.assertRaisesRegex(ExtractionError, "unsupported response charset"):
            extract_content(fetched(b"evidence", "text/plain", "not-a-codec"), "auto")

    def test_auto_falls_back_when_optional_extractor_unavailable_or_fails(self):
        result = extract_content(fetched(b"<html><body><p>Useful</p></body></html>"), "auto")
        self.assertTrue(result.text)
        self.assertIn(result.extractor, {"stdlib", "trafilatura"})
        if result.extractor == "stdlib":
            self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
