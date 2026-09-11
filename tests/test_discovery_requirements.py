"""Synthetic agent-authored counterexamples for decision/requirement semantics."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from brief2ship.discovery_decision import decide
from brief2ship.discovery_models import Candidate, InspectionResult, SourceReceipt, TestReceipt
from brief2ship.discovery_scoring import rank_candidates, score_candidate

NOW = datetime(2026, 9, 11, tzinfo=timezone.utc)


def candidate(name="launcher", description="Android launcher"):
    url = f"https://github.com/fixture/{name}"
    return Candidate(
        source="github", name=f"fixture/{name}", url=url, repository_url=url,
        description=description, license="MIT", updated_at=NOW.isoformat(),
        dependency_count=0, security_policy=True, vulnerabilities_checked=True,
        stars=10_000, language="Python",
        inspection=InspectionResult(
            repository_url=url, status="inspected", commit="synthetic",
            manifest_files=["pyproject.toml"], test_files=["tests/test.py"],
            ci_files=[".github/workflows/test.yml"], docs_files=["README.md"],
            source_file_count=20, test_command=["test"],
            test_receipt=TestReceipt(status="passed"),
        ),
    )


class RequirementTests(unittest.TestCase):
    def test_windows_only_close_competitor_is_excluded_for_android(self):
        desktop = candidate("android-launcher", "Windows-only Android launcher for desktops")
        mobile = candidate("orbit", "Android launcher and home screen")
        mobile.portability_signals = ["supports-android"]
        ranked = rank_candidates("android launcher", [desktop, mobile], now=NOW)
        self.assertIs(mobile, ranked[0])
        self.assertEqual("reject", desktop.recommendation)
        self.assertEqual("fail", desktop.requirement_checks[0].status)
        self.assertIn("Windows-only", desktop.requirement_checks[0].evidence[0])
        result = decide(ranked, [SourceReceipt("github", "ok", 2, returned=2)])
        self.assertEqual(mobile.canonical_id, result.selected_id)

    def test_synonym_miss_never_authorizes_build_clean(self):
        mobile = candidate("mobilehome", "Android home screen application")
        ranked = rank_candidates("android launcher", [mobile], now=NOW)
        self.assertLess(mobile.score.components["feature_match"], 8)
        self.assertEqual("inconclusive", mobile.recommendation)
        result = decide(ranked, [SourceReceipt("github", "ok", 1, returned=1)])
        self.assertEqual("inconclusive", result.recommendation)
        self.assertTrue(result.incomplete_reasons)

    def test_language_and_cross_platform_claim_do_not_prove_android_support(self):
        item = candidate()
        item.portability_signals = ["cross-platform"]
        score_candidate("Android launcher", item, now=NOW)
        self.assertEqual("unknown", item.requirement_checks[0].status)
        self.assertEqual("provisional", item.recommendation_status)
        self.assertIn("unverified", " ".join(item.required_checks))

    def test_positive_platform_declaration_does_not_turn_host_tests_into_target_verification(self):
        item = candidate()
        item.portability_signals = ["supports-android"]
        score_candidate("Android launcher", item, now=NOW)
        self.assertEqual("pass", item.requirement_checks[0].status)
        self.assertEqual("provisional", item.recommendation_status)
        self.assertTrue(any("target-environment" in text for text in item.required_checks))

    def test_runtime_mismatch_requires_explicit_evidence(self):
        item = candidate("web-scraper", "web scraper")
        item.language = "Java"
        score_candidate("web scraper using Python", item, now=NOW)
        self.assertEqual("unknown", item.requirement_checks[0].status)
        self.assertNotEqual("reject", item.recommendation)
        item.portability_signals = ["java-only"]
        score_candidate("web scraper using Python", item, now=NOW)
        self.assertEqual("fail", item.requirement_checks[0].status)
        self.assertEqual("reject", item.recommendation)

    def test_domain_language_does_not_imply_implementation_language(self):
        item = candidate("java-parser", "Java parser written in Python")
        item.portability_signals = ["python-only"]
        score_candidate("Java parser", item, now=NOW)
        self.assertEqual([], item.requirement_checks)
        self.assertNotEqual("reject", item.recommendation)

    def test_versions_and_unverified_requirements_keep_result_provisional(self):
        item = candidate("web-scraper", "web scraper")
        item.portability_signals = ["supports-python", "supports-windows"]
        score_candidate("web scraper for Windows using Python 3.11 offline", item, now=NOW)
        by_requirement = {check.requirement: check for check in item.requirement_checks}
        self.assertEqual("pass", by_requirement["Windows"].status)
        self.assertEqual("unknown", by_requirement["Python 3.11"].status)
        self.assertEqual("unknown", by_requirement["offline"].status)
        self.assertEqual("provisional", item.recommendation_status)

    def test_matching_package_ecosystem_is_scoped_positive_evidence(self):
        item = candidate("web-scraper", "web scraper")
        item.source = "pypi"
        score_candidate("web scraper using Python", item, now=NOW)
        self.assertEqual("pass", item.requirement_checks[0].status)
        self.assertTrue(any("package ecosystem" in value for value in item.requirement_checks[0].evidence))
        # Repository inspection still does not establish the package subtree.
        self.assertEqual("provisional", item.recommendation_status)

    def test_negated_only_declaration_is_not_mismatch_evidence(self):
        item = candidate(description="Android launcher, not Windows-only")
        score_candidate("Android launcher", item, now=NOW)
        self.assertEqual("unknown", item.requirement_checks[0].status)
        self.assertNotEqual("reject", item.recommendation)

    def test_platform_limited_examples_do_not_restrict_entire_artifact(self):
        item = candidate(description="Android launcher with Windows-only examples")
        score_candidate("Android launcher", item, now=NOW)
        self.assertEqual("unknown", item.requirement_checks[0].status)
        self.assertNotEqual("reject", item.recommendation)

    def test_conflicting_declarations_require_review(self):
        item = candidate()
        item.portability_signals = ["windows-only", "supports-android"]
        score_candidate("Android launcher", item, now=NOW)
        self.assertEqual("unknown", item.requirement_checks[0].status)
        self.assertIn("conflicting", item.requirement_checks[0].evidence[0])
        self.assertEqual("provisional", item.recommendation_status)

    def test_dependency_count_can_disprove_but_not_prove_dependency_free(self):
        item = candidate("web-scraper", "web scraper")
        score_candidate("dependency-free web scraper", item, now=NOW)
        self.assertEqual("unknown", item.requirement_checks[0].status)
        item.dependency_count = 3
        score_candidate("dependency-free web scraper", item, now=NOW)
        self.assertEqual("fail", item.requirement_checks[0].status)
        self.assertEqual("reject", item.recommendation)

    def test_cloud_requirement_conflict_has_explicit_evidence(self):
        item = candidate("web-scraper", "web scraper")
        item.reuse_signals = ["cloud-required"]
        score_candidate("web scraper with no cloud services", item, now=NOW)
        self.assertEqual("fail", item.requirement_checks[0].status)
        self.assertIn("cloud-required", " ".join(item.hard_blockers))

    def test_requirement_receipts_are_serializable_and_reset_when_query_changes(self):
        item = candidate()
        item.portability_signals = ["windows-only"]
        score_candidate("Android launcher", item, now=NOW)
        self.assertEqual("fail", item.to_dict()["requirement_checks"][0]["status"])
        score_candidate("launcher", item, now=NOW)
        self.assertEqual([], item.requirement_checks)
        self.assertFalse(any("requirement failed" in text for text in item.hard_blockers))


if __name__ == "__main__":
    unittest.main()
