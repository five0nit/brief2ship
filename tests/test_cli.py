import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brief2ship import __version__
from brief2ship.cli import main
from brief2ship.discovery_models import Candidate, DiscoveryResult, SourceReceipt
from brief2ship.discovery_scoring import score_candidate
from tests.support import fixture_site


class CliTests(unittest.TestCase):
    def run_cli(self, args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_doctor_is_parseable_and_free(self):
        code, stdout, stderr = self.run_cli(["doctor"])
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        payload = json.loads(stdout)
        self.assertEqual(__version__, payload["brief2ship_version"])
        self.assertFalse(payload["paid_api_required"])
        self.assertEqual("required/fail-closed", payload["robots_policy"])

    def test_scrape_stdout_json(self):
        with fixture_site() as (base, _):
            code, stdout, stderr = self.run_cli(
                ["scrape", f"{base}/article", "--allow-private", "--extractor", "stdlib"]
            )
        self.assertEqual(0, code, stderr)
        payload = json.loads(stdout)
        self.assertEqual("Fixture Article", payload["title"])

    def test_unicode_stdout_is_utf8_even_when_process_starts_as_ascii(self):
        raw_stdout = io.BytesIO()
        ascii_stdout = io.TextIOWrapper(raw_stdout, encoding="ascii")
        stderr = io.StringIO()
        with patch("sys.stdout", ascii_stdout), patch(
            "sys.stderr",
            stderr,
        ), patch(
            "brief2ship.cli.scrape_url",
            return_value=object(),
        ), patch(
            "brief2ship.cli.render_result",
            return_value='{"title":"naïve"}\n',
        ):
            code = main(["scrape", "https://example.com/"])
            ascii_stdout.flush()

        self.assertEqual(0, code, stderr.getvalue())
        self.assertEqual(
            '{"title":"naïve"}\n',
            raw_stdout.getvalue().decode("utf-8"),
        )

    def test_private_target_blocked_without_override(self):
        code, stdout, stderr = self.run_cli(["scrape", "http://127.0.0.1/"])
        self.assertEqual(3, code)
        self.assertEqual("", stdout)
        self.assertIn("blocked", stderr)

    def test_scrape_writes_markdown(self):
        with fixture_site() as (base, _), tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "receipt.md"
            code, stdout, stderr = self.run_cli(
                [
                    "scrape",
                    f"{base}/article",
                    "--allow-private",
                    "--extractor",
                    "stdlib",
                    "--format",
                    "markdown",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(0, code, stderr)
            self.assertEqual(str(output.resolve()), stdout.strip())
            self.assertIn("## Provenance", output.read_text(encoding="utf-8"))

    def test_crawl_writes_manifest(self):
        with fixture_site() as (base, _), tempfile.TemporaryDirectory() as tmp:
            code, stdout, stderr = self.run_cli(
                [
                    "crawl",
                    f"{base}/article",
                    "--allow-private",
                    "--extractor",
                    "stdlib",
                    "--delay",
                    "0",
                    "--output",
                    tmp,
                ]
            )
            self.assertEqual(0, code, stderr)
            manifest = Path(stdout.strip())
            self.assertTrue(manifest.is_file())
            self.assertEqual(2, json.loads(manifest.read_text(encoding="utf-8"))["page_count"])

    def test_partial_crawl_writes_manifest_but_returns_failure(self):
        with fixture_site() as (base, _), tempfile.TemporaryDirectory() as tmp:
            code, stdout, stderr = self.run_cli(
                [
                    "crawl",
                    f"{base}/many",
                    "--allow-private",
                    "--extractor",
                    "stdlib",
                    "--delay",
                    "0",
                    "--max-pages",
                    "2",
                    "--output",
                    tmp,
                ]
            )
            manifest = Path(stdout.strip())
            payload = json.loads(manifest.read_text(encoding="utf-8"))

        self.assertEqual(4, code, stderr)
        self.assertEqual(1, payload["page_count"])
        self.assertEqual(1, payload["failure_count"])

    def test_discover_writes_ranked_receipt(self):
        candidate = Candidate(
            source="github",
            name="owner/tool",
            url="https://github.com/owner/tool",
            repository_url="https://github.com/owner/tool",
            description="safe web scraper",
            license="MIT",
        )
        score_candidate("safe web scraper", candidate)
        result = DiscoveryResult(
            query="safe web scraper",
            started_at="2026-07-30T00:00:00+00:00",
            completed_at="2026-07-30T00:00:01+00:00",
            config={},
            candidates=[candidate],
            sources=[SourceReceipt("github", "ok", 1, 1)],
            overall_recommendation=candidate.recommendation,
            recommendation_reason="test",
        )
        with tempfile.TemporaryDirectory() as temporary, patch(
            "brief2ship.cli.discover_candidates", return_value=result
        ):
            output = Path(temporary) / "discovery"
            code, stdout, stderr = self.run_cli(
                ["discover", "safe web scraper", "--sources", "github", "--output", str(output)]
            )
            self.assertEqual(0, code, stderr)
            self.assertEqual((output / "discovery.md").resolve(), Path(stdout.strip()))
            self.assertTrue((output / "discovery.json").is_file())

    def test_discover_accepts_local_only_workspace_search(self):
        captured = {}

        def fake_discover(query, config, *, output_dir):
            captured["query"] = query
            captured["config"] = config
            candidate = Candidate(
                source="local",
                name="local/tool",
                url=Path(temporary).resolve().as_uri(),
                local_path=str(Path(temporary).resolve()),
                description="local tool",
                license="MIT",
            )
            score_candidate(query, candidate)
            return DiscoveryResult(
                query=query,
                started_at="2026-09-03T00:00:00+00:00",
                completed_at="2026-09-03T00:00:01+00:00",
                config={},
                candidates=[candidate],
                sources=[SourceReceipt("local", "ok", 1, 1)],
                overall_recommendation="selective-reuse",
                recommendation_reason="test",
            )

        with tempfile.TemporaryDirectory() as temporary, patch(
            "brief2ship.cli.discover_candidates",
            side_effect=fake_discover,
        ):
            output = Path(temporary) / "receipt"
            code, stdout, stderr = self.run_cli(
                [
                    "discover",
                    "local tool",
                    "--sources",
                    "local",
                    "--local",
                    temporary,
                    "--output",
                    str(output),
                ]
            )

        self.assertEqual(0, code, stderr)
        self.assertEqual(("local",), captured["config"].sources)
        self.assertEqual(
            (str(Path(temporary).resolve()),),
            captured["config"].local_roots,
        )
        self.assertEqual((output / "discovery.md").resolve(), Path(stdout.strip()))

    def test_discover_test_execution_needs_explicit_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            code, stdout, stderr = self.run_cli(
                [
                    "discover",
                    "safe web scraper",
                    "--sources",
                    "github",
                    "--inspect-top",
                    "1",
                    "--test-top",
                    "1",
                    "--output",
                    str(Path(temporary) / "result"),
                ]
            )
        self.assertEqual(4, code)
        self.assertEqual("", stdout)
        self.assertIn("allow-untrusted-tests", stderr)


if __name__ == "__main__":
    unittest.main()
