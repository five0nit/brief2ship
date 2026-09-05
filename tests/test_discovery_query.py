from __future__ import annotations

import re
import unittest
from dataclasses import FrozenInstanceError, fields

from brief2ship.discovery_query import QueryPlan, plan_query


class QueryPlanTests(unittest.TestCase):
    def test_public_contract_is_frozen_and_exact(self):
        self.assertEqual(
            ["original", "core_query", "constraints", "variants"],
            [field.name for field in fields(QueryPlan)],
        )
        plan = plan_query("web scraper")
        with self.assertRaises(FrozenInstanceError):
            plan.core_query = "changed"  # type: ignore[misc]

    def test_local_robots_aware_scraper_keeps_domain_as_core_intent(self):
        query = "local robots-aware web scraper"

        plan = plan_query(query)

        self.assertEqual(query, plan.original)
        self.assertEqual("web scraper", plan.core_query)
        self.assertEqual(("local", "robots-aware"), plan.constraints)
        self.assertEqual(plan.core_query, plan.variants[0])
        self.assertIn(query, plan.variants)
        self.assertLessEqual(len(plan.variants), 3)

    def test_package_names_and_central_function_are_not_dropped(self):
        plan = plan_query(
            "Build a dependency-free PDF to Markdown converter using PyMuPDF"
        )
        manager = plan_query("Build a package manager for Python projects")

        self.assertEqual(("dependency-free",), plan.constraints)
        self.assertIn("PDF to Markdown converter", plan.core_query)
        self.assertIn("PyMuPDF", plan.core_query)
        self.assertIn("package manager", manager.core_query)

    def test_variants_are_deterministic_bounded_and_use_only_original_terms(self):
        query = "Please build a local deterministic web scraper with retry support"

        first = plan_query(query)
        second = plan_query(query)

        self.assertEqual(first, second)
        self.assertLessEqual(len(first.variants), 3)
        self.assertEqual(len(first.variants), len(set(first.variants)))
        self.assertIn(query, first.variants)
        original_terms = set(re.findall(r"[A-Za-z0-9_.+#@/-]+", query.lower()))
        for variant in first.variants:
            self.assertLessEqual(
                set(re.findall(r"[A-Za-z0-9_.+#@/-]+", variant.lower())),
                original_terms,
            )

    def test_original_is_retained_exactly_when_whitespace_is_normalized_for_core(self):
        query = "  Build   a web scraper  "

        plan = plan_query(query)

        self.assertEqual(query, plan.original)
        self.assertEqual("web scraper", plan.core_query)
        self.assertIn(query, plan.variants)


if __name__ == "__main__":
    unittest.main()
