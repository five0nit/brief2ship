from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from brief2ship.discovery_inspection import RepositoryInspector, inspect_tree
from brief2ship.discovery_local import search_local
from brief2ship.discovery_models import Candidate
from brief2ship.discovery_scoring import score_candidate


class LicenseSourceTests(unittest.TestCase):
    def test_inspection_preserves_modified_file_and_overrides_metadata_claim(self):
        raw = "MIT License\n\nCommercial use is prohibited.\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "LICENSE").write_bytes(raw.encode("utf-8"))
            inspection = inspect_tree(root, root.as_uri())
            item = Candidate("github", "example/web-scraper", "https://github.com/example/web-scraper", license="MIT")
            item.inspection = inspection
            RepositoryInspector._apply_inspection_evidence(item, inspection)
            score_candidate("web scraper", item)
        self.assertEqual(raw, inspection.license)
        self.assertEqual(raw, item.license)
        self.assertIsNone(item.normalized_license)
        self.assertEqual("reject", item.recommendation)

    def test_local_title_only_license_file_is_not_a_canonical_grant(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "web-scraper"
            root.mkdir()
            (root / "pyproject.toml").write_text('[project]\nname="web-scraper"\nversion="1.0"\n', encoding="utf-8")
            (root / "LICENSE").write_text("MIT License\n", encoding="utf-8")
            candidates, _ = search_local("web scraper", (str(root),), limit=3)
            self.assertEqual(1, len(candidates))
            score_candidate("web scraper", candidates[0])
            self.assertIsNone(candidates[0].normalized_license)
            self.assertEqual("reject", candidates[0].recommendation)


if __name__ == "__main__":
    unittest.main()
