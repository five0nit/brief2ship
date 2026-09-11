"""Synthetic regression fixtures for query-to-decision requirement authority."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from brief2ship.discovery_decision import decide
from brief2ship.discovery_models import Candidate, InspectionResult, SourceReceipt
from brief2ship.discovery_query import plan_query
from brief2ship.discovery_scoring import rank_candidates

NOW = datetime(2026, 9, 11, tzinfo=timezone.utc)


def inspected_candidate(name: str, description: str, *signals: str) -> Candidate:
    """Provide static fixture evidence; no candidate code or tests are executed."""
    url = f"https://github.com/fixture/{name}"
    return Candidate(
        source="github", name=f"fixture/{name}", url=url, repository_url=url,
        description=description, license="MIT", updated_at=NOW.isoformat(),
        dependency_count=0, security_policy=True, vulnerabilities_checked=True,
        stars=10_000, language="Python", portability_signals=list(signals),
        inspection=InspectionResult(
            repository_url=url, status="inspected", commit="synthetic-fixture",
            manifest_files=["pyproject.toml"], test_files=["tests/test_parser.py"],
            ci_files=[".github/workflows/tests.yml"], docs_files=["README.md"],
            source_file_count=20,
        ),
    )


def decision_for(query: str, item: Candidate):
    ranked = rank_candidates(query, [item], now=NOW)
    return decide(ranked, [SourceReceipt("github", "ok", 1, returned=1)])


class RequirementHardeningTests(unittest.TestCase):
    def test_negation_and_optionality_do_not_create_mandatory_platforms(self):
        for query in (
            "launcher not for Android",
            "launcher for Windows with optional Android support",
            "launcher for Windows without Android support",
            "launcher for Windows, Android support is not required",
            "launcher for Windows, preferably Android too",
            "launcher for Windows, Android would be nice",
        ):
            with self.subTest(query=query):
                item = inspected_candidate("launcher", "Windows-only launcher")
                result = decision_for(query, item)
                self.assertNotEqual("build-clean", result.recommendation)
                self.assertEqual([], item.hard_blockers)
                self.assertEqual({"unknown"}, {check.status for check in item.requirement_checks})
                self.assertIn(result.status, {"provisional", "inconclusive"})

    def test_alternative_platforms_never_authorize_false_build_clean(self):
        for query in (
            "launcher for Android or Windows",
            "launcher for either Android or Windows",
            "launcher for Android, iOS or Windows",
            "Android launcher or Windows launcher",
            "launcher for Android and/or Windows",
        ):
            for platform in ("android", "windows"):
                with self.subTest(query=query, platform=platform):
                    item = inspected_candidate("launcher", "launcher", f"{platform}-only")
                    result = decision_for(query, item)
                    self.assertNotEqual("build-clean", result.recommendation)
                    self.assertEqual([], item.hard_blockers)
                    self.assertTrue(item.requirement_checks)
                    self.assertEqual({"unknown"}, {check.status for check in item.requirement_checks})
                    self.assertEqual("provisional", result.status)
                    self.assertEqual(item.canonical_id, result.selected_id)
                    self.assertTrue(any("unverified" in check for check in item.required_checks))

    def test_unsupported_disjunction_is_not_silently_dropped_or_split(self):
        query = "launcher for Android or a desktop operating system"
        plan = plan_query(query)
        self.assertEqual((query,), plan.constraints)
        self.assertEqual(query, plan.core_query)
        self.assertIn(query, plan.variants)
        item = inspected_candidate("launcher", query, "windows-only")
        result = decision_for(query, item)
        self.assertEqual("unknown", item.requirement_checks[0].status)
        self.assertEqual("provisional", result.status)
        self.assertNotEqual("build-clean", result.recommendation)

    def test_unsupported_compound_does_not_claim_compatibility(self):
        item = inspected_candidate("launcher", "launcher for Android or Windows", "linux-only")
        result = decision_for("launcher for Android or Windows", item)
        self.assertEqual({"unknown"}, {check.status for check in item.requirement_checks})
        self.assertEqual("provisional", result.status)
        self.assertNotEqual("build-clean", result.recommendation)

    def test_for_language_preserves_domain_without_implementation_requirement(self):
        for query in ("parser for Java", "parser for Java 17", "package manager for Python projects"):
            with self.subTest(query=query):
                item = inspected_candidate("parser", query, "python-only")
                result = decision_for(query, item)
                self.assertNotEqual("build-clean", result.recommendation)
                self.assertEqual([], item.requirement_checks)
                self.assertEqual([], item.hard_blockers)
                self.assertEqual(item.canonical_id, result.selected_id)
                plan = plan_query(query)
                self.assertEqual((), plan.constraints)
                self.assertEqual(query, plan.core_query)

    def test_domain_language_and_explicit_implementation_remain_distinct(self):
        query = "parser for Java written in Python"
        item = inspected_candidate("parser", query, "python-only")
        result = decision_for(query, item)
        self.assertEqual(("Python",), plan_query(query).constraints)
        self.assertIn("parser for Java", plan_query(query).core_query)
        self.assertEqual([("Python", "pass")], [
            (check.requirement, check.status) for check in item.requirement_checks
        ])
        self.assertEqual(item.canonical_id, result.selected_id)
        self.assertEqual("provisional", result.status)

    def test_explicit_implementation_cues_still_authorize_negative_decisions(self):
        for cue in ("written in", "implemented in", "using"):
            with self.subTest(cue=cue):
                query = f"parser {cue} Java"
                item = inspected_candidate("parser", "parser for Java written in Python", "python-only")
                result = decision_for(query, item)
                self.assertEqual([("Java", "fail")], [
                    (check.requirement, check.status) for check in item.requirement_checks
                ])
                self.assertEqual("reject", item.recommendation)
                self.assertEqual("build-clean", result.recommendation)
                self.assertEqual("complete", result.status)

    def test_single_platform_requirement_still_authorizes_negative_decision(self):
        item = inspected_candidate("launcher", "Windows-only launcher")
        result = decision_for("launcher for Android", item)
        self.assertEqual([("Android", "fail")], [
            (check.requirement, check.status) for check in item.requirement_checks
        ])
        self.assertEqual("build-clean", result.recommendation)
        self.assertEqual("complete", result.status)

    def test_platform_conjunction_is_not_weakened_to_alternatives(self):
        item = inspected_candidate("launcher", "launcher", "windows-only")
        result = decision_for("launcher for Android and Windows", item)
        self.assertEqual([("Android", "fail"), ("Windows", "pass")], [
            (check.requirement, check.status) for check in item.requirement_checks
        ])
        self.assertEqual("build-clean", result.recommendation)
        self.assertEqual("complete", result.status)

    def test_positive_platform_declaration_still_requires_target_verification(self):
        item = inspected_candidate("launcher", "launcher", "supports-android")
        result = decision_for("launcher for Android", item)
        self.assertEqual("pass", item.requirement_checks[0].status)
        self.assertEqual(item.canonical_id, result.selected_id)
        self.assertEqual("provisional", result.status)
        self.assertTrue(any("target-environment" in check for check in item.required_checks))

    def test_resource_requirement_remains_authoritative(self):
        item = inspected_candidate("launcher", "launcher", "cloud-required")
        result = decision_for("offline launcher", item)
        self.assertEqual("fail", item.requirement_checks[0].status)
        self.assertEqual("build-clean", result.recommendation)
        self.assertEqual("complete", result.status)


if __name__ == "__main__":
    unittest.main()
