from __future__ import annotations

import unittest

from brief2ship.discovery_licenses import normalize_license, license_body_match


MIT_BODY = '''Permission is hereby granted, free of charge, to any person obtaining a copy
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


class DiscoveryLicenseTests(unittest.TestCase):
    def test_exact_permissive_aliases_are_canonicalized(self):
        expected = {
            "MIT": "MIT",
            "MIT License": "MIT",
            "Apache-2.0": "Apache-2.0",
            "Apache License 2.0": "Apache-2.0",
            "BSD-2-Clause": "BSD-2-Clause",
            "BSD-3-Clause": "BSD-3-Clause",
            "ISC": "ISC",
            "Unlicense": "Unlicense",
            "0BSD": "0BSD",
        }

        for raw, canonical in expected.items():
            with self.subTest(raw=raw):
                self.assertEqual(canonical, normalize_license(raw))

    def test_canonical_mit_body_allows_titles_but_not_freeform_notices(self):
        variants = (
            MIT_BODY,
            f"MIT License\n\n{MIT_BODY}",
            f"The MIT License (MIT)\r\n\r\n{MIT_BODY}",
        )

        for raw in variants:
            with self.subTest(raw=raw[:40]):
                self.assertEqual("MIT", normalize_license(raw))

    def test_freeform_notices_are_recognized_but_never_authorize_reuse(self):
        from brief2ship.discovery_scoring import rank_candidates
        from brief2ship.discovery_models import Candidate, InspectionResult, SourceReceipt
        from brief2ship.discovery_decision import decide
        for notice in (
            "Copyright (c) 2026 Example Authors",
            "Copyright © 2018-2026 Example, Inc.",
            "Copyright 2026 Example Corp Commercial exploitation forbidden",
            "Copyright 2026 Must Have Software Pty Ltd",
        ):
            with self.subTest(notice=notice):
                raw = f"MIT License\n{notice}\n\n{MIT_BODY}"
                self.assertIsNone(normalize_license(raw))
                self.assertEqual("MIT", license_body_match(raw))
                item = Candidate("local", "web-scraper", "file:///fixture", description="web scraper", license=raw,
                                 license_kind="file", dependency_count=0, test_signals=["unit tests", "continuous integration"])
                item.inspection = InspectionResult(repository_url=item.url, status="inspected")
                rank_candidates("web scraper", [item])
                self.assertTrue(item.license_review_required)
                self.assertIsNone(item.normalized_license)
                self.assertEqual("MIT", item.license_body_match)
                self.assertEqual("inconclusive", decide([item], [SourceReceipt("local", "ok", requested=1)]).recommendation)

    def test_truncated_or_modified_mit_body_is_rejected(self):
        variants = (
            MIT_BODY[:-20],
            f"MIT License\nCopyright (c) 2026 Authors. Non-commercial use only.\n\n{MIT_BODY}",
            f"{MIT_BODY}\n\nUse is prohibited for commercial purposes.",
            MIT_BODY.replace("without restriction", "only for non-commercial use"),
        )

        for raw in variants:
            with self.subTest(raw=raw[-60:]):
                self.assertIsNone(normalize_license(raw))

    def test_license_substrings_and_restrictive_expressions_are_not_accepted(self):
        for raw in (
            "MIT with Commons Clause",
            "MIT OR GPL-3.0-only",
            "Custom MIT-style license",
            "The software includes MIT-licensed components",
            "GPL-3.0-only",
            "",
        ):
            with self.subTest(raw=raw):
                self.assertIsNone(normalize_license(raw))

    def test_none_is_unknown(self):
        self.assertIsNone(normalize_license(None))


if __name__ == "__main__":
    unittest.main()
