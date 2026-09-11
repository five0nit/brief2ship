from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from brief2ship.discovery import discover
from brief2ship.discovery_checkpoint import load_checkpoint, write_checkpoint
from brief2ship.discovery_models import (
    Candidate, DiscoveryConfig, InspectionResult, RequirementCheck,
    ScoreBreakdown, SourceReceipt, TestReceipt,
)


class CheckpointTests(unittest.TestCase):
    def _observation(self, source="github", *, status="ok"):
        candidates = [Candidate(
            source=source, name=f"{source}-scraper", url=f"https://example.invalid/{source}",
            description="web scraper", license="MIT",
        )] if status in {"ok", "partial"} else []
        receipt = SourceReceipt(source, status, 1, returned=len(candidates))
        if status in {"failed", "partial"}:
            receipt.error = "fixture provider unavailable"
        return candidates, receipt

    def _payload(self, root: Path):
        config = DiscoveryConfig(sources=("github",), per_source=1)
        path = write_checkpoint(root, "web scraper", config, {"github": self._observation()})
        return config, path, json.loads(path.read_text(encoding="utf-8"))

    def test_round_trip_preserves_metadata_but_discards_decision_authority(self):
        candidates, receipt = self._observation()
        candidate = candidates[0]
        candidate.inspection = InspectionResult(
            repository_url=candidate.url, status="inspected",
            test_receipt=TestReceipt(status="passed"),
        )
        candidate.score = ScoreBreakdown(total=100, components={}, evidence={})
        candidate.recommendation = "use-as-library"
        candidate.recommendation_status = "ready"
        candidate.required_checks = ["old check"]
        candidate.hard_blockers = ["old blocker"]
        candidate.constraint_checks = ["old constraint"]
        candidate.requirement_checks = [RequirementCheck("robots-aware", "pass", ["old"])]
        candidate.normalized_license = "MIT"
        candidate.license_body_match = "MIT"
        candidate.license_review_required = True
        candidate.canonical_id = "old decision identity"
        candidate.vulnerabilities_checked = True
        candidate.vulnerabilities = ["old-vulnerability"]
        candidate.vulnerability_evidence = [{"id": "old-vulnerability"}]
        candidate.repository_evidence = {"inspection": "old"}
        candidate.local_path = "/unrequested/local/project"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = DiscoveryConfig(sources=("github",), per_source=1)
            path = write_checkpoint(root, "web scraper", config, {"github": (candidates, receipt)})
            restored, timestamps = load_checkpoint(path, "web scraper", config)
        result = restored["github"][0][0]
        self.assertEqual("MIT", result.license)
        self.assertEqual(candidate.name, result.name)
        self.assertEqual("unscored", result.recommendation)
        self.assertEqual("unscored", result.recommendation_status)
        for field in ("inspection", "score", "canonical_id", "normalized_license", "license_body_match", "local_path"):
            self.assertIsNone(getattr(result, field), field)
        for field in ("required_checks", "hard_blockers", "constraint_checks", "requirement_checks", "vulnerabilities", "vulnerability_evidence"):
            self.assertEqual([], getattr(result, field), field)
        self.assertFalse(result.vulnerabilities_checked)
        self.assertFalse(result.license_review_required)
        self.assertEqual({}, result.repository_evidence)
        self.assertEqual({"github"}, set(timestamps))

    def test_malformed_types_sources_and_budgets_are_rejected(self):
        changes = (
            lambda value: value["scope"].update(per_source=True),
            lambda value: value["observations"]["github"]["receipt"].update(source="npm"),
            lambda value: value["observations"]["github"]["receipt"].update(requested=True),
            lambda value: value["observations"]["github"]["receipt"].update(requested=2),
            lambda value: value["observations"]["github"]["receipt"].update(returned=0),
            lambda value: value["observations"]["github"]["receipt"].update(status="ready"),
            lambda value: value["observations"]["github"]["candidates"][0].update(source="npm"),
            lambda value: value["observations"]["github"]["candidates"][0].update(stars="many"),
            lambda value: value["observations"]["github"]["candidates"][0].update(stars=True),
            lambda value: value["observations"]["github"]["candidates"][0].update(raw_relevance=float("nan")),
            lambda value: value["observations"]["github"]["candidates"][0].update(unsupported_field=True),
            lambda value: value["observations"]["github"]["candidates"][0].pop("source"),
            lambda value: value["observations"].update(unrequested={}),
        )
        for index, change in enumerate(changes):
            with self.subTest(case=index), tempfile.TemporaryDirectory() as temporary:
                config, path, payload = self._payload(Path(temporary))
                change(payload)
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_checkpoint(path, "web scraper", config)

    def test_changed_query_or_source_scope_requires_fresh_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, path, _ = self._payload(Path(temporary))
            for query, changed in (
                ("other query", config),
                ("web scraper", DiscoveryConfig(sources=("npm",), per_source=1)),
                ("web scraper", DiscoveryConfig(sources=("github",), per_source=2)),
            ):
                with self.subTest(query=query, sources=changed.sources, per_source=changed.per_source):
                    with self.assertRaisesRegex(ValueError, "same query, sources"):
                        load_checkpoint(path, query, changed)

    def test_expired_sources_refetch_without_discarding_fresh_sources(self):
        now = datetime.now(timezone.utc)
        stale = (now - timedelta(days=2)).isoformat()
        fresh = (now - timedelta(minutes=5)).isoformat()
        config = DiscoveryConfig(sources=("github", "npm"), per_source=1)
        with tempfile.TemporaryDirectory() as temporary:
            path = write_checkpoint(
                Path(temporary), "web scraper", config,
                {source: self._observation(source) for source in config.sources},
                source_observed_at={"github": stale, "npm": fresh},
            )
            restored, timestamps = load_checkpoint(path, "web scraper", config)
        self.assertEqual({"npm"}, set(restored))
        self.assertEqual({"npm": fresh}, timestamps)

    def test_future_or_timezone_free_source_timestamps_are_rejected(self):
        for timestamp in (
            (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "2026-09-11T00:00:00", 123,
        ):
            with self.subTest(timestamp=timestamp), tempfile.TemporaryDirectory() as temporary:
                config, path, payload = self._payload(Path(temporary))
                payload["observations"]["github"]["observed_at"] = timestamp
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_checkpoint(path, "web scraper", config)

    def test_repeated_retry_preserves_timestamp_and_one_reuse_warning(self):
        timestamp = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        config = DiscoveryConfig(sources=("github",), per_source=1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observations = {"github": self._observation()}
            timestamps = {"github": timestamp}
            for index in range(3):
                path = write_checkpoint(
                    root / str(index), "web scraper", config, observations,
                    source_observed_at=timestamps,
                )
                observations, timestamps = load_checkpoint(path, "web scraper", config)
                self.assertEqual({"github": timestamp}, timestamps)
                warnings = observations["github"][1].warnings
                self.assertEqual(1, len(warnings))
                self.assertIn(timestamp, warnings[0])

    def test_local_failed_and_partial_sources_are_refetched_but_empty_success_is_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = DiscoveryConfig(sources=("local", "github", "npm", "crates"), local_roots=(str(root),), per_source=1)
            path = write_checkpoint(root, "web scraper", config, {
                "local": self._observation("local"),
                "github": self._observation("github", status="failed"),
                "npm": self._observation("npm", status="partial"),
                "crates": self._observation("crates", status="empty"),
            })
            restored, _ = load_checkpoint(path, "web scraper", config)
        self.assertEqual({"crates"}, set(restored))
        self.assertEqual([], restored["crates"][0])

    def test_byte_depth_and_collection_limits_apply_to_untyped_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, path, payload = self._payload(Path(temporary))
            with patch("brief2ship.discovery_checkpoint.MAX_BYTES", 20):
                with self.assertRaisesRegex(ValueError, "10 MB"):
                    load_checkpoint(path, "web scraper", config)
            nested = {}
            for _ in range(40):
                nested = {"nested": nested}
            payload["observations"]["github"]["candidates"][0]["repository_evidence"] = nested
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "nested evidence budget"):
                load_checkpoint(path, "web scraper", config)
            payload["observations"]["github"]["candidates"][0]["repository_evidence"] = {"items": list(range(101))}
            path.write_text(json.dumps(payload), encoding="utf-8")
            with patch("brief2ship.discovery_checkpoint.MAX_COLLECTION_ITEMS", 100):
                with self.assertRaisesRegex(ValueError, "list exceeds"):
                    load_checkpoint(path, "web scraper", config)

    def test_resume_reuses_successes_retries_failure_and_rechecks_local_and_osv(self):
        github = Mock(return_value=self._observation("github"))
        npm = Mock(side_effect=[self._observation("npm", status="failed"), self._observation("npm")])
        local = Mock(side_effect=[self._observation("local"), self._observation("local")])
        osv = Mock(return_value=None)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = DiscoveryConfig(sources=("github", "npm", "local"), local_roots=(str(root),), per_source=1)
            with patch.dict("brief2ship.discovery.PROVIDERS", {"github": github, "npm": npm}), patch(
                "brief2ship.discovery.search_local", local,
            ), patch("brief2ship.discovery.enrich_osv", osv):
                first = discover("web scraper", config, output_dir=root / "first")
                second = discover("web scraper", config, output_dir=root / "second", resume_from=root / "first")
            self.assertEqual("partial", first.discovery_status)
            self.assertEqual("complete", second.discovery_status)
            self.assertEqual(1, github.call_count)
            self.assertEqual(2, npm.call_count)
            self.assertEqual(2, local.call_count)
            self.assertEqual(5, osv.call_count)
            before = json.loads((root / "first/checkpoint.json").read_text(encoding="utf-8"))
            after = json.loads((root / "second/checkpoint.json").read_text(encoding="utf-8"))
            self.assertEqual(before["observations"]["github"]["observed_at"], after["observations"]["github"]["observed_at"])
            self.assertNotEqual(before["observations"]["npm"]["observed_at"], after["observations"]["npm"]["observed_at"])


if __name__ == "__main__":
    unittest.main()
