from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brief2ship.cli import main
from brief2ship.discovery import discover
from brief2ship.discovery_checkpoint import write_checkpoint
from brief2ship.discovery_models import Candidate, DiscoveryConfig, DiscoveryResult, InspectionResult, RequirementCheck, SourceReceipt
from brief2ship.discovery_render import render_discovery_summary, render_discovery_text


def fixture_result(status="inconclusive", decision="inconclusive"):
    selected = Candidate("github", "fixture/tool", "https://github.com/fixture/tool",
                         canonical_id="repo:fixture/tool@abc", required_checks=["verify offline operation"])
    return DiscoveryResult(
        query="offline tool", started_at="fixture", completed_at="fixture", config={},
        candidates=[selected], sources=[SourceReceipt("github", "ok", 1, 1)],
        overall_recommendation=decision, recommendation_reason="fixture",
        decision_status=status, discovery_status="complete",
        selected_candidate_id=selected.canonical_id if status != "inconclusive" else None,
        incomplete_reasons=["capability evidence missing"] if status == "inconclusive" else [],
    )


class WorkflowTests(unittest.TestCase):
    def test_explicit_refresh_is_not_bypassed_by_resume(self):
        config = DiscoveryConfig(sources=("pypi",), refresh_cache=True, per_source=1)
        cached = Candidate("pypi", "old", "https://pypi.org/project/old/", license="MIT")
        fresh = Candidate("pypi", "new", "https://pypi.org/project/new/", license="MIT")
        with tempfile.TemporaryDirectory() as directory, patch(
            "brief2ship.discovery.search_pypi", return_value=([fresh], SourceReceipt("pypi", "ok", 1, 1))
        ) as search, patch("brief2ship.discovery.enrich_osv", return_value=None):
            first = Path(directory) / "first"
            write_checkpoint(first, "retry", config, {"pypi": ([cached], SourceReceipt("pypi", "ok", 1, 1))})
            result = discover("retry", config, output_dir=Path(directory) / "retry", resume_from=first)
            self.assertTrue(search.call_args.kwargs["refresh"])
            self.assertEqual(["new"], [item.name for item in result.evaluated_candidates])

    def test_no_output_creates_directory_and_prints_actionable_text(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "brief2ship.cli.tempfile.mkdtemp", return_value=directory
        ), patch("brief2ship.cli.discover_candidates", return_value=fixture_result()) as run:
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(["discover", "offline tool", "--sources", "github"])
            self.assertEqual(5, code)
            self.assertEqual(2, run.call_args.args[1].inspect_top)
            self.assertIn("Decision: inconclusive", stdout.getvalue())
            self.assertIn("no build decision is authorized", stdout.getvalue())
            self.assertTrue((Path(directory) / "discovery.json").exists())

    def test_summary_remains_json_when_progress_is_enabled(self):
        def fake_run(query, config, *, output_dir, progress):
            progress("github: searching")
            return fixture_result()

        with tempfile.TemporaryDirectory() as directory, patch("brief2ship.cli.discover_candidates", side_effect=fake_run):
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(["discover", "offline tool", "--summary", "--progress", "--output", directory])
            self.assertEqual(5, code)
            self.assertEqual("inconclusive", json.loads(stdout.getvalue())["decision"])
            self.assertIn("github: searching", stderr.getvalue())

    def test_human_and_json_handoffs_preserve_all_decision_states(self):
        for status, decision in (("inconclusive", "inconclusive"), ("provisional", "fork"), ("complete", "fork")):
            with self.subTest(status=status):
                result = fixture_result(status, decision)
                payload = json.loads(render_discovery_summary(result, Path("receipt")))
                text = render_discovery_text(result, Path("receipt"))
                self.assertIn(f"({status})", text)
                self.assertIn(payload["next_action"], text)
                self.assertIn("verify offline operation", text)
                self.assertEqual(status, payload["decision_status"])
                self.assertEqual(status != "inconclusive", payload["selected_candidate_id"] is not None)

    def test_text_handoff_includes_pinned_version_commit_and_observation_times(self):
        result = fixture_result("provisional", "fork")
        result.candidates[0].version = "1.2.3"
        result.candidates[0].inspection = InspectionResult("fixture", commit="abcdef123")
        result.config["source_observed_at"] = {"github": "2026-09-11T01:00:00+00:00"}
        payload = json.loads(render_discovery_summary(result, Path("receipt")))
        text = render_discovery_text(result, Path("receipt"))
        self.assertIn(f"Version: {payload['selected_version']}", text)
        self.assertIn(f"Commit: {payload['selected_commit']}", text)
        self.assertIn("Observed github: 2026-09-11T01:00:00+00:00", text)

    def test_text_handoff_sanitizes_new_identity_fields(self):
        result = fixture_result("provisional", "fork")
        result.candidates[0].version = "1.2.3\x1b\nInjected"
        result.config["source_observed_at"] = {"github\nInjected": "timestamp\x1b\nInjected"}
        text = render_discovery_text(result, Path("receipt"))
        self.assertIn("Version: 1.2.3 Injected", text)
        self.assertIn("Observed github Injected: timestamp Injected", text)
        self.assertNotIn("\x1b", text)

    def test_text_preserves_structured_requirement_results_and_evidence(self):
        for status in ("pass", "fail", "unknown"):
            with self.subTest(status=status):
                result = fixture_result("complete", "build-clean")
                result.selected_candidate_id = None
                result.candidates[0].requirement_checks = [RequirementCheck(
                    "Python", status, ["topics: supports-python", "static declaration"],
                )]
                payload = json.loads(render_discovery_summary(result, Path("receipt")))
                text = render_discovery_text(result, Path("receipt"))
                for check in payload["requirement_checks"]:
                    self.assertIn(f"Requirement: {check['requirement']} ({check['status']})", text)
                    for evidence in check["evidence"]:
                        self.assertIn(f"Evidence: {evidence}", text)

    def test_text_sanitizes_requirement_results_and_evidence(self):
        result = fixture_result()
        result.candidates[0].requirement_checks = [RequirementCheck(
            "Python\x1b\nInjected", "unknown", ["source\u202e\nInjected"],
        )]
        text = render_discovery_text(result, Path("receipt"))
        self.assertIn("Requirement: Python Injected (unknown)", text)
        self.assertIn("Evidence: source Injected", text)
        self.assertNotIn("\x1b", text)
        self.assertNotIn("\u202e", text)

    def test_inspection_failure_does_not_erase_other_candidates_or_checkpoint(self):
        candidates = [Candidate("github", f"fixture/tool{index}", f"https://github.com/fixture/tool{index}",
                                description="offline tool", license="MIT") for index in (1, 2)]
        receipt = SourceReceipt("github", "ok", 2, 2)
        inspections = [AttributeError("malformed fixture"), InspectionResult("fixture", status="inspected")]
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "brief2ship.discovery.PROVIDERS", {"github": lambda *args: (candidates, receipt)}
        ), patch("brief2ship.discovery.enrich_osv", return_value=None), patch(
            "brief2ship.discovery.RepositoryInspector.inspect", side_effect=inspections
        ):
            result = discover("offline tool", DiscoveryConfig(sources=("github",), per_source=2, inspect_top=2),
                              output_dir=Path(directory))
            self.assertEqual({"failed", "inspected"}, {item.inspection.status for item in result.evaluated_candidates})
            self.assertTrue((Path(directory) / "checkpoint.json").exists())
            self.assertEqual(2, len(result.inspection_decisions))

    def test_missing_metadata_license_does_not_starve_relevant_inspection(self):
        candidates = [
            Candidate("github", "fixture/retry", "https://github.com/fixture/retry",
                      description="retry exponential backoff", license=None),
            Candidate("github", "fixture/unrelated", "https://github.com/fixture/unrelated",
                      description="unrelated image toolkit", license="MIT"),
        ]
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "brief2ship.discovery.PROVIDERS",
            {"github": lambda *args: (candidates, SourceReceipt("github", "ok", 2, 2))},
        ), patch("brief2ship.discovery.enrich_osv", return_value=None), patch(
            "brief2ship.discovery.RepositoryInspector.inspect", return_value=InspectionResult("fixture", status="inspected")
        ) as inspect:
            discover("retry exponential backoff", DiscoveryConfig(sources=("github",), per_source=2, inspect_top=1),
                     output_dir=Path(directory))
            self.assertEqual("fixture/retry", inspect.call_args.args[0].name)


if __name__ == "__main__":
    unittest.main()
