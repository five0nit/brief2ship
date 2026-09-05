from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brief2ship.cli import main
from brief2ship.discovery_models import Candidate, DiscoveryResult, SourceReceipt
from brief2ship.discovery_render import render_discovery_summary


class SummaryTests(unittest.TestCase):
    def result(self):
        visible = Candidate("github", "example/lead", "https://example.invalid/lead")
        hidden = Candidate("github", "example/hidden", "https://example.invalid/hidden",
                           hard_blockers=["license missing", "archived"])
        return DiscoveryResult(
            query="web scraper", started_at="fixture", completed_at="fixture", config={},
            candidates=[visible], evaluated_candidates=[visible, hidden],
            sources=[SourceReceipt("github", "failed", 2, returned=2,
                                   error="fixture outage", warnings=["fixture warning"])],
            overall_recommendation="inconclusive", recommendation_reason="fixture outage",
            discovery_status="failed", decision_status="inconclusive",
            incomplete_reasons=["github: fixture outage"],
        )

    def test_summary_does_not_hide_failed_sources_or_non_displayed_blockers(self):
        result = self.result()
        payload = json.loads(render_discovery_summary(result, Path("receipt")))
        self.assertEqual("inconclusive", payload["decision"])
        self.assertEqual("failed", payload["sources"][0]["status"])
        self.assertEqual("fixture outage", payload["sources"][0]["error"])
        self.assertEqual(1, payload["sources"][0]["warning_count"])
        self.assertEqual(2, payload["hard_blocker_count"])
        self.assertEqual(2, payload["evaluated_count"])
        self.assertEqual(1, payload["displayed_count"])
        self.assertIsNone(payload["selected_candidate"])
        self.assertEqual("example/lead", payload["top_candidate"])

    def test_summary_cli_writes_receipts_then_exits_five_for_inconclusive(self):
        with tempfile.TemporaryDirectory() as root, patch("brief2ship.cli.discover_candidates", return_value=self.result()):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["discover", "web scraper", "--summary", "--output", root])
            payload = json.loads(stream.getvalue())
            self.assertEqual(5, code)
            for path in payload["receipts"].values():
                self.assertTrue(Path(path).is_file())

    def test_default_stdout_keeps_single_receipt_path(self):
        with tempfile.TemporaryDirectory() as root, patch("brief2ship.cli.discover_candidates", return_value=self.result()):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["discover", "web scraper", "--output", root])
            self.assertEqual(5, code)
            self.assertEqual(str(Path(root) / "discovery.md"), stream.getvalue().strip())


if __name__ == "__main__":
    unittest.main()
