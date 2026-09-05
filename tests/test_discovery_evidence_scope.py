from __future__ import annotations

import unittest

from brief2ship.discovery import deduplicate_candidates
from brief2ship.discovery_inspection import RepositoryInspector
from brief2ship.discovery_models import Candidate, InspectionResult
from brief2ship.discovery_scoring import score_candidate


class EvidenceScopeTests(unittest.TestCase):
    def package(self):
        return Candidate("npm", "subpackage", "https://www.npmjs.com/package/subpackage",
                         repository_url="https://github.com/example/monorepo", version="1.0.0")

    def test_repository_merge_cannot_relabel_unknown_package_dependencies(self):
        package = self.package()
        repo = Candidate("github", "example/monorepo", "https://github.com/example/monorepo",
                         repository_url=package.repository_url, dependency_count=0,
                         stars=123, description="repository-wide capabilities")
        merged = deduplicate_candidates([package, repo])[0]
        self.assertIsNone(merged.dependency_count)
        self.assertEqual("", merged.description)
        self.assertEqual(123, merged.stars)
        self.assertEqual(0, merged.repository_evidence["dependency_count"])

    def test_repository_inspection_does_not_overwrite_package_dependencies(self):
        package = self.package()
        package.dependency_count = 3
        inspection = InspectionResult(repository_url=package.repository_url or "", status="inspected", dependency_count=70)
        package.inspection = inspection
        RepositoryInspector._apply_inspection_evidence(package, inspection)
        self.assertEqual(3, package.dependency_count)
        self.assertEqual(70, package.inspection.dependency_count)

    def test_package_scoring_cannot_promote_unknown_using_repository_count(self):
        package = self.package()
        package.inspection = InspectionResult(repository_url=package.repository_url or "", status="inspected", dependency_count=0)
        RepositoryInspector._apply_inspection_evidence(package, package.inspection)
        score = score_candidate("subpackage", package)
        self.assertIsNone(package.dependency_count)
        self.assertEqual(5, score.components["dependency_weight"])
        self.assertTrue(any("unknown" in line for line in score.evidence["dependency_weight"]))


if __name__ == "__main__":
    unittest.main()
