from __future__ import annotations

import unittest
from datetime import datetime, timezone

from brief2ship.discovery import deduplicate_candidates
from brief2ship.discovery_models import (
    Candidate,
    DiscoveryConfig,
    InspectionResult,
    ScoreBreakdown,
    TestReceipt,
)
from brief2ship.discovery_scoring import (
    candidate_rank_key,
    rank_candidates,
    score_candidate,
)


class DiscoveryScoringTests(unittest.TestCase):
    def test_score_is_explainable_bounded_and_deterministic(self):
        candidate = Candidate(
            source="pypi",
            name="safe-web-scraper",
            url="https://pypi.org/project/safe-web-scraper/",
            repository_url="https://github.com/example/safe-web-scraper",
            description="Respectful web scraper with robots support",
            version="2.0.0",
            license="MIT",
            updated_at="2026-07-15T00:00:00Z",
            downloads=50_000,
            dependency_count=4,
            security_policy=True,
            vulnerabilities_checked=True,
            test_signals=["package tests"],
            portability_signals=["cross-platform"],
            reuse_signals=["package metadata", "documentation"],
            topics=["robots", "scraping"],
        )
        now = datetime(2026, 7, 30, tzinfo=timezone.utc)
        first = score_candidate("safe web scraper robots", candidate, now=now)
        second = score_candidate("safe web scraper robots", candidate, now=now)
        self.assertEqual(first, second)
        self.assertEqual(first.total, round(sum(first.components.values()), 2))
        self.assertEqual(set(first.components), {
            "feature_match", "maintenance_activity", "dependency_weight", "security_posture",
            "test_quality", "portability", "reuse_readiness", "adoption_health",
        })
        self.assertTrue(all(0 <= value for value in first.components.values()))
        self.assertGreater(first.coverage, 0.7)
        self.assertGreaterEqual(first.unknown_cost, 0)
        self.assertEqual(candidate.recommendation, "use-as-library")
        self.assertEqual(candidate.recommendation_status, "provisional")
        self.assertEqual(candidate.canonical_id, "pypi:safe-web-scraper@2.0.0")
        candidate.vulnerabilities_checked = False
        score_candidate("safe web scraper robots", candidate, now=now)
        self.assertNotEqual(candidate.recommendation, "use-as-library")
        self.assertTrue(any("OSV" in check for check in candidate.required_checks))

    def test_archived_unlicensed_candidate_is_not_recommended_for_fork(self):
        candidate = Candidate(
            source="github",
            name="old/tool",
            url="https://github.com/old/tool",
            description="tool",
            archived=True,
            stars=1_000_000,
            updated_at="2026-07-29T00:00:00Z",
        )
        breakdown = score_candidate("tool", candidate, now=datetime(2026, 7, 30, tzinfo=timezone.utc))
        self.assertEqual(breakdown.components["maintenance_activity"], 0)
        self.assertEqual(breakdown.components["security_posture"], 0)
        self.assertEqual(candidate.recommendation, "reject")
        self.assertEqual(candidate.recommendation_status, "blocked")
        self.assertIn("repository is archived", candidate.hard_blockers)

    def test_osv_finding_is_a_hard_reuse_blocker(self):
        candidate = Candidate(
            source="npm", name="matching-tool", version="1.0.0",
            url="https://npmjs.com/package/matching-tool",
            repository_url="https://github.com/owner/matching-tool",
            description="matching tool package", license="MIT",
            updated_at="2026-07-29T00:00:00Z", downloads=1_000_000,
            dependency_count=0, vulnerabilities_checked=True,
            vulnerabilities=["OSV-TEST-1"], test_signals=["tests"],
            portability_signals=["cross-platform"],
        )
        score_candidate("matching tool", candidate, now=datetime(2026, 7, 30, tzinfo=timezone.utc))
        self.assertEqual("reject", candidate.recommendation)
        self.assertEqual("blocked", candidate.recommendation_status)
        self.assertTrue(any("OSV" in blocker for blocker in candidate.hard_blockers))

    def test_reciprocal_license_requires_explicit_compatibility_review(self):
        candidate = Candidate(
            source="pypi", name="matching-tool", version="1.0.0",
            url="https://pypi.org/project/matching-tool/",
            repository_url="https://github.com/owner/matching-tool",
            description="matching tool", license="GPL-3.0-only",
            updated_at="2026-07-29T00:00:00Z", downloads=1_000_000,
            dependency_count=0, vulnerabilities_checked=True,
            test_signals=["tests"], portability_signals=["cross-platform"],
        )
        score_candidate("matching tool", candidate, now=datetime(2026, 7, 30, tzinfo=timezone.utc))
        self.assertEqual("reject", candidate.recommendation)
        self.assertEqual("blocked", candidate.recommendation_status)
        self.assertTrue(any("allowlist" in blocker for blocker in candidate.hard_blockers))

    def test_deprecated_and_gated_candidates_are_blocked(self):
        for candidate in (
            Candidate(
                source="npm", name="old-tool", version="1.0.0",
                url="https://npmjs.com/old-tool", description="old tool",
                license="MIT", deprecated=True, deprecation_reason="superseded",
                vulnerabilities_checked=True,
            ),
            Candidate(
                source="huggingface", name="owner/gated", version="abc",
                url="https://huggingface.co/owner/gated", description="gated model",
                license="apache-2.0", gated=True,
            ),
        ):
            score_candidate(candidate.name, candidate, now=datetime(2026, 7, 30, tzinfo=timezone.utc))
            self.assertEqual("reject", candidate.recommendation)
            self.assertEqual("blocked", candidate.recommendation_status)

    def test_dedup_prefers_package_identity_and_keeps_github_evidence(self):
        github = Candidate(
            source="github", name="owner/tool", url="https://github.com/owner/tool",
            repository_url="https://github.com/owner/tool", stars=900, license="MIT",
        )
        package = Candidate(
            source="pypi", name="tool", url="https://pypi.org/project/tool/",
            repository_url="https://github.com/owner/tool", version="1.2.3", dependency_count=3,
        )
        merged = deduplicate_candidates([github, package])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].source, "pypi")
        self.assertEqual(merged[0].stars, 900)
        self.assertIsNone(merged[0].license)
        self.assertEqual(merged[0].repository_evidence["license"], "MIT")
        self.assertIn("github:owner/tool", merged[0].aliases)

    def test_dedup_does_not_mutate_provider_candidates(self):
        first = Candidate(
            source="pypi",
            name="same",
            version="1.0.0",
            url="https://pypi.org/project/same/",
        )
        second = Candidate(
            source="pypi",
            name="same",
            version="1.0.0",
            url="https://pypi.org/project/same/",
            aliases=["second"],
        )

        merged = deduplicate_candidates([first, second])

        self.assertEqual([], first.aliases)
        self.assertEqual(["second"], second.aliases)
        self.assertIn("second", merged[0].aliases)

    def test_dedup_compares_activity_timestamps_chronologically(self):
        github = Candidate(
            source="github",
            name="owner/tool",
            url="https://github.com/owner/tool",
            repository_url="https://github.com/owner/tool",
            updated_at="2026-01-01T00:00:00Z",
        )
        package = Candidate(
            source="pypi",
            name="tool",
            version="1.0.0",
            url="https://pypi.org/project/tool/",
            repository_url="https://github.com/owner/tool",
            updated_at="2025-12-31T23:30:00-01:00",
        )

        merged = deduplicate_candidates([github, package])

        self.assertEqual("2025-12-31T23:30:00-01:00", merged[0].updated_at)

    def test_local_repository_with_remote_is_not_dropped_as_package_duplicate(self):
        candidate = Candidate(
            source="local",
            name="local/tool",
            url="file:///workspace/tool",
            local_path="/workspace/tool",
            repository_url="https://github.com/owner/tool",
        )

        merged = deduplicate_candidates([candidate])

        self.assertEqual(1, len(merged))
        self.assertEqual("local", merged[0].source)

    def test_config_requires_explicit_untrusted_test_gate(self):
        with self.assertRaisesRegex(ValueError, "allow-untrusted-tests"):
            DiscoveryConfig(inspect_top=1, test_top=1).validate()
        DiscoveryConfig(inspect_top=1, test_top=1, allow_untrusted_tests=True).validate()

    def test_local_source_requires_at_least_one_local_root(self):
        with self.assertRaisesRegex(ValueError, "local source requires"):
            DiscoveryConfig(sources=("local",)).validate()
        DiscoveryConfig(
            sources=("local",),
            local_roots=("/tmp",),
        ).validate()

    def test_distinct_packages_in_one_monorepo_remain_distinct(self):
        candidates = [
            Candidate(
                source="pypi", name="tool-python", version="1.0.0",
                url="https://pypi.org/project/tool-python/",
                repository_url="https://github.com/owner/monorepo",
            ),
            Candidate(
                source="npm", name="tool-js", version="2.0.0",
                url="https://npmjs.com/package/tool-js",
                repository_url="https://github.com/owner/monorepo",
            ),
            Candidate(
                source="github", name="owner/monorepo",
                url="https://github.com/owner/monorepo",
                repository_url="https://github.com/owner/monorepo", stars=100,
            ),
        ]
        merged = deduplicate_candidates(candidates)
        self.assertEqual(2, len(merged))
        self.assertEqual({"pypi", "npm"}, {candidate.source for candidate in merged})
        self.assertEqual({100}, {candidate.stars for candidate in merged})

    def test_ranking_uses_name_as_deterministic_tiebreak(self):
        candidates = [
            Candidate(source="github", name="z/tool", url="https://github.com/z/tool"),
            Candidate(source="github", name="a/tool", url="https://github.com/a/tool"),
        ]
        ranked = rank_candidates("unrelated query", candidates, now=datetime(2026, 7, 30, tzinfo=timezone.utc))
        self.assertEqual([candidate.name for candidate in ranked], ["a/tool", "z/tool"])

    def test_adoption_health_accounts_for_issue_ratio_and_contributors(self):
        healthy = Candidate(
            source="github",
            name="owner/healthy",
            url="https://github.com/owner/healthy",
            description="matching tool",
            license="MIT",
            stars=100,
            forks=20,
            watchers=10,
            contributors=12,
            open_issues=5,
            open_issues_exact=True,
        )
        noisy = Candidate(
            source="github",
            name="owner/noisy",
            url="https://github.com/owner/noisy",
            description="matching tool",
            license="MIT",
            stars=100,
            forks=1,
            watchers=0,
            contributors=1,
            open_issues=80,
            open_issues_exact=True,
        )

        healthy_score = score_candidate("matching tool", healthy)
        noisy_score = score_candidate("matching tool", noisy)

        self.assertGreater(
            healthy_score.components["adoption_health"],
            noisy_score.components["adoption_health"],
        )
        self.assertTrue(
            any(
                "contributors=12" in item
                for item in healthy_score.evidence["adoption_health"]
            )
        )
        self.assertTrue(
            any(
                "issue health penalty" in item
                for item in noisy_score.evidence["adoption_health"]
            )
        )

    def test_combined_github_issue_and_pr_count_is_not_penalized(self):
        candidate = Candidate(
            source="github",
            name="owner/active",
            url="https://github.com/owner/active",
            description="matching tool",
            license="MIT",
            stars=100,
            open_issues=80,
            open_issues_exact=False,
        )

        score = score_candidate("matching tool", candidate)

        self.assertFalse(
            any(
                "issue health penalty" in item
                for item in score.evidence["adoption_health"]
            )
        )
        self.assertTrue(
            any(
                "issues and pull requests combined=80" in item
                for item in score.evidence["adoption_health"]
            )
        )

    def test_exact_named_candidate_gets_identity_feature_bonus(self):
        candidate = Candidate(
            source="local",
            name="local/brief2ship",
            url="file:///workspace/brief2ship",
            local_path="/workspace/brief2ship",
            description="Brief2Ship",
            license="MIT",
        )

        score = score_candidate("brief2ship repository search", candidate)

        self.assertGreaterEqual(score.components["feature_match"], 8)

    def test_low_fit_candidate_uses_canonical_build_clean_disposition(self):
        candidate = Candidate(
            source="github",
            name="popular-but-unrelated",
            url="https://github.com/owner/popular-but-unrelated",
            repository_url="https://github.com/owner/popular-but-unrelated",
            description="A polished general purpose utility",
            license="MIT",
            updated_at="2026-07-29T00:00:00Z",
            stars=1_000_000,
        )

        score_candidate(
            "robots-aware package discovery",
            candidate,
            now=datetime(2026, 7, 30, tzinfo=timezone.utc),
        )

        self.assertEqual("build-clean", candidate.recommendation)

    def test_missing_license_rejects_even_when_total_is_low(self):
        candidate = Candidate(
            source="github",
            name="unlicensed",
            url="https://github.com/owner/unlicensed",
            repository_url="https://github.com/owner/unlicensed",
        )

        score_candidate(
            "unrelated package discovery",
            candidate,
            now=datetime(2026, 7, 30, tzinfo=timezone.utc),
        )

        self.assertLess(candidate.score.total if candidate.score else 100, 45)
        self.assertEqual("reject", candidate.recommendation)
        self.assertEqual("blocked", candidate.recommendation_status)

    def test_canonical_mit_body_is_recognized_without_approving_freeform_notice(self):
        raw_license = '''The MIT License (MIT)

Copyright (c) 2026 Example Authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.'''
        candidate = Candidate(
            source="github",
            name="owner/robots-discovery",
            url="https://github.com/owner/robots-discovery",
            repository_url="https://github.com/owner/robots-discovery",
            description="robots package discovery",
            license=raw_license,
            vulnerabilities_checked=True,
        )

        score_candidate("robots package discovery", candidate)

        self.assertEqual(raw_license, candidate.license)
        self.assertIsNone(candidate.normalized_license)
        self.assertEqual("MIT", candidate.license_body_match)
        self.assertTrue(candidate.license_review_required)
        self.assertTrue(any("license" in blocker for blocker in candidate.hard_blockers))

    def test_high_health_unrelated_utility_does_not_crowd_relevant_lead(self):
        candidates = [
            Candidate(
                source="github",
                name="authlib/jose",
                url="https://github.com/authlib/jose",
                repository_url="https://github.com/authlib/jose",
                description="A polished general purpose JOSE utility",
                license="MIT",
                updated_at="2026-07-29T00:00:00Z",
                stars=1_000_000,
                forks=20_000,
                watchers=5_000,
                contributors=500,
                dependency_count=0,
                security_policy=True,
                vulnerabilities_checked=True,
                test_signals=["tests"],
                portability_signals=["cross-platform"],
                reuse_signals=["docs", "examples", "package"],
                source_rank=1,
            ),
            Candidate(
                source="github",
                name="owner/robots-package-discovery",
                url="https://github.com/owner/robots-package-discovery",
                repository_url="https://github.com/owner/robots-package-discovery",
                description="robots-aware package discovery CLI",
                license="MIT",
                source_rank=20,
            ),
        ]

        ranked = rank_candidates(
            "Build a robots-aware package discovery CLI for Windows that runs locally with no cloud services",
            candidates,
            now=datetime(2026, 7, 30, tzinfo=timezone.utc),
        )

        self.assertEqual("owner/robots-package-discovery", ranked[0].name)
        self.assertIsNotNone(ranked[0].score)
        self.assertIsNotNone(ranked[1].score)
        assert ranked[0].score is not None
        assert ranked[1].score is not None
        self.assertGreaterEqual(ranked[0].score.components["feature_match"], 8)
        self.assertLess(ranked[1].score.components["feature_match"], 8)

    def test_unknown_evidence_reduces_decision_score_without_inflating_raw_total(self):
        candidate = Candidate(
            source="github",
            name="owner/robots-discovery",
            url="https://github.com/owner/robots-discovery",
            repository_url="https://github.com/owner/robots-discovery",
            description="robots package discovery",
            license="MIT",
            dependency_count=None,
        )

        score = score_candidate("robots package discovery", candidate)

        self.assertEqual(5.0, score.components["dependency_weight"])
        self.assertEqual(round(max(0.0, score.total - score.unknown_cost), 2), score.decision_score)
        self.assertLess(score.decision_score, score.total)

    def test_rank_key_prefers_ready_then_inspected_and_caps_same_source_rank(self):
        def tied(name: str, *, status: str, inspected: bool, source_rank: int) -> Candidate:
            candidate = Candidate(
                source="github",
                name=name,
                url=f"https://github.com/{name}",
                source_rank=source_rank,
                recommendation="selective-reuse",
                recommendation_status=status,
                score=ScoreBreakdown(
                    total=70.0,
                    components={"feature_match": 12.0},
                    evidence={},
                    coverage=0.8,
                    unknown_cost=4.0,
                    decision_score=66.0,
                ),
            )
            if inspected:
                candidate.inspection = InspectionResult(
                    repository_url=candidate.url,
                    status="inspected",
                )
            return candidate

        ready = tied("owner/ready", status="ready", inspected=True, source_rank=500)
        inspected = tied("owner/inspected", status="provisional", inspected=True, source_rank=500)
        provisional = tied("owner/provisional", status="provisional", inspected=False, source_rank=1)
        self.assertLess(candidate_rank_key(ready), candidate_rank_key(inspected))
        self.assertLess(candidate_rank_key(inspected), candidate_rank_key(provisional))

        capped_a = tied("owner/a", status="provisional", inspected=False, source_rank=21)
        capped_b = tied("owner/b", status="provisional", inspected=False, source_rank=10_000)
        self.assertEqual(candidate_rank_key(capped_a)[:-2], candidate_rank_key(capped_b)[:-2])

    def test_requested_constraints_remain_visible_until_verified(self):
        candidate = Candidate(
            source="github",
            name="owner/robots-discovery",
            url="https://github.com/owner/robots-discovery",
            repository_url="https://github.com/owner/robots-discovery",
            description="robots package discovery",
            license="MIT",
            vulnerabilities_checked=True,
            inspection=InspectionResult(
                repository_url="https://github.com/owner/robots-discovery",
                status="inspected",
                test_receipt=TestReceipt(status="passed"),
            ),
        )

        score_candidate(
            "Build robots package discovery for Windows, local operation, and no cloud services",
            candidate,
        )

        combined_checks = "\n".join(
            candidate.constraint_checks + candidate.required_checks
        ).casefold()
        self.assertIn("windows", combined_checks)
        self.assertIn("local", combined_checks)
        self.assertIn("cloud", combined_checks)
        self.assertEqual(len(candidate.required_checks), len(set(candidate.required_checks)))


if __name__ == "__main__":
    unittest.main()
