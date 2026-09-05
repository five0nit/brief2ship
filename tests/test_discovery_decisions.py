from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from brief2ship.discovery import discover
from brief2ship.discovery_models import Candidate, DiscoveryConfig, InspectionResult, SourceReceipt
from brief2ship.discovery_render import write_discovery


def candidate(name: str = "web-scraper", description: str = "web scraper") -> Candidate:
    return Candidate(
        source="github", name=f"example/{name}",
        url=f"https://github.com/example/{name}",
        repository_url=f"https://github.com/example/{name}",
        description=description, license="MIT",
        updated_at=datetime.now(timezone.utc).isoformat(),
        dependency_count=0, language="Python",
    )


class DecisionTests(unittest.TestCase):
    def run_discovery(self, candidates, *, limit=5, inspect_top=0, failure=False, partial=False):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        github = Mock(return_value=(
            candidates, SourceReceipt("github", "failed" if failure else "ok", 5,
                                      returned=len(candidates), error="fixture outage" if failure else None),
        ))
        providers = {"github": github}
        sources = ("github",)
        if partial:
            providers["npm"] = Mock(return_value=([], SourceReceipt("npm", "failed", 5, error="fixture outage")))
            sources += ("npm",)
        inspector = Mock()
        inspector.inspect.side_effect = lambda item, run_tests=False: InspectionResult(
            repository_url=item.repository_url or "", status="inspected", commit="fixture-commit",
            license=item.license, dependency_count=0,
        )
        with patch.dict("brief2ship.discovery.PROVIDERS", providers), patch(
            "brief2ship.discovery.RepositoryInspector", return_value=inspector,
        ):
            result = discover("web scraper", DiscoveryConfig(
                sources=sources, per_source=5, limit=limit, inspect_top=inspect_top,
            ), output_dir=root / "receipt")
        return result, root / "receipt"

    def test_failed_sources_never_authorize_clean_build(self):
        result, _ = self.run_discovery([], failure=True)
        self.assertEqual("inconclusive", result.overall_recommendation)
        self.assertEqual("inconclusive", result.decision_status)
        self.assertEqual("failed", result.discovery_status)
        self.assertTrue(result.incomplete_reasons)

    def test_successful_empty_search_is_not_proof_of_no_reusable_code(self):
        result, _ = self.run_discovery([])
        self.assertEqual("complete", result.discovery_status)
        self.assertEqual("inconclusive", result.overall_recommendation)
        self.assertIsNone(result.selected_candidate_id)

    def test_uninspected_lead_is_not_run_level_reuse_choice(self):
        result, _ = self.run_discovery([candidate()])
        self.assertEqual("inconclusive", result.overall_recommendation)
        self.assertIsNone(result.selected_candidate_id)
        self.assertTrue(any("inspection" in value for value in result.incomplete_reasons))

    def test_output_limit_does_not_change_decision_or_drop_evidence(self):
        decisions = []
        for limit in (1, 2):
            irrelevant = candidate("aaa-unrelated", "healthy utility")
            irrelevant.stars = 1_000_000
            irrelevant.security_policy = True
            result, _ = self.run_discovery([irrelevant, candidate()], limit=limit, inspect_top=1)
            decisions.append((result.overall_recommendation, result.selected_candidate_id))
            self.assertEqual(2, len(result.evaluated_candidates))
            self.assertEqual(limit, len(result.candidates))
            self.assertEqual("selective-reuse", result.overall_recommendation)
            self.assertEqual("provisional", result.decision_status)
            self.assertEqual(1, len(result.inspection_decisions))
        self.assertEqual(decisions[0], decisions[1])

    def test_partial_provider_failure_is_not_hidden_by_reusable_candidate(self):
        result, _ = self.run_discovery([candidate()], inspect_top=1, partial=True)
        self.assertEqual("partial", result.discovery_status)
        self.assertEqual("inconclusive", result.overall_recommendation)
        self.assertTrue(any("npm" in value for value in result.incomplete_reasons))

    def test_full_json_markdown_and_artifacts_retain_all_candidates(self):
        result, output = self.run_discovery(
            [candidate(), candidate("aaa-unrelated", "utility"), candidate("bbb-unrelated", "utility")],
            limit=1, inspect_top=1,
        )
        receipt = write_discovery(result, output)
        payload = json.loads((output / "discovery.json").read_text())
        self.assertEqual(1, len(payload["candidates"]))
        self.assertEqual(3, len(payload["evaluated_candidates"]))
        self.assertEqual(3, len(list((output / "candidates").glob("*.json"))))
        markdown = receipt.read_text()
        self.assertIn("example/aaa-unrelated", markdown)
        self.assertIn("Inspection allocation", markdown)
        self.assertIn("provisional", markdown)

    def test_unrecognized_license_text_is_not_supported_negative_evidence(self):
        item = candidate("unrelated", "utility")
        item.license = "unknown; contact author"
        result, _ = self.run_discovery([item], inspect_top=1)
        self.assertEqual("inconclusive", result.overall_recommendation)

    def test_ready_candidate_maps_to_complete_run_status(self):
        from brief2ship.discovery_decision import decide
        item = candidate()
        item.recommendation = "selective-reuse"
        item.recommendation_status = "ready"
        item.inspection = InspectionResult(repository_url=item.repository_url or "", status="inspected")
        outcome = decide([item], [SourceReceipt("github", "ok", 1, returned=1)])
        self.assertEqual("complete", outcome.status)

    def test_clean_build_requires_completed_negative_inspection(self):
        result, _ = self.run_discovery([candidate("unrelated", "utility")], inspect_top=1)
        self.assertEqual("build-clean", result.overall_recommendation)
        self.assertEqual("complete", result.decision_status)
        self.assertIsNone(result.selected_candidate_id)

    def test_failed_inspection_retained_and_does_not_authorize_clean_build(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(
            "brief2ship.discovery.PROVIDERS", {"github": Mock(return_value=(
                [candidate()], SourceReceipt("github", "ok", 1, returned=1),
            ))},
        ), patch("brief2ship.discovery.RepositoryInspector") as inspector:
            inspector.return_value.inspect.return_value = InspectionResult(
                repository_url="https://github.com/example/web-scraper", status="blocked",
                warnings=["fixture unavailable"],
            )
            result = discover("web scraper", DiscoveryConfig(sources=("github",), inspect_top=1), output_dir=Path(root))
        self.assertEqual("inconclusive", result.overall_recommendation)
        self.assertEqual("blocked", result.inspection_decisions[0]["status"])
        inspection = result.evaluated_candidates[0].inspection
        self.assertIsNotNone(inspection)
        self.assertEqual("blocked", inspection.status if inspection else None)


if __name__ == "__main__":
    unittest.main()
