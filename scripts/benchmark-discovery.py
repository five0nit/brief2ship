#!/usr/bin/env python3
"""Deterministic synthetic task-quality regression gate; no provider requests."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brief2ship.discovery_decision import decide  # noqa: E402
from brief2ship.discovery_models import Candidate, InspectionResult, SourceReceipt  # noqa: E402
from brief2ship.discovery_scoring import rank_candidates  # noqa: E402
from brief2ship.render import atomic_write  # noqa: E402


def run_benchmark() -> dict:
    fixtures = json.loads((ROOT / "tests/fixtures/discovery-quality-v1.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(fixtures["clock"])
    rows = []
    for case in fixtures["cases"]:
        target = Candidate(
            source="github", name=case["expected"], url="https://github.com/" + case["expected"],
            repository_url="https://github.com/" + case["expected"], description=case["description"],
            license="MIT", updated_at=fixtures["clock"], dependency_count=2, language="Python",
        )
        unrelated = Candidate(
            source="github", name="fixture/aaa-unrelated", url="https://github.com/fixture/aaa-unrelated",
            description="Highly popular general purpose utility", repository_url="https://github.com/fixture/aaa-unrelated",
            license="MIT", updated_at=fixtures["clock"], stars=1_000_000, dependency_count=0,
            security_policy=True, vulnerabilities_checked=True, test_signals=["tests"],
            reuse_signals=["docs", "examples"], language="Python",
        )
        archived = Candidate(
            source="github", name="fixture/archived", url="https://github.com/fixture/archived",
            description=case["description"], license="MIT", archived=True, stars=1_000_000,
        )
        unlicensed = Candidate(
            source="github", name="fixture/unlicensed", url="https://github.com/fixture/unlicensed",
            description=case["description"], stars=1_000_000,
        )
        pool = [unrelated, archived, unlicensed, target]
        start = time.perf_counter()
        ranked = rank_candidates(case["query"], pool, now=now)
        elapsed_ms = (time.perf_counter() - start) * 1000
        before_inspection = decide(ranked, [SourceReceipt("github", "ok", 4, returned=4)])
        outage = decide(ranked, [SourceReceipt("github", "failed", 4, error="synthetic outage")])
        target.inspection = InspectionResult(repository_url=target.repository_url or "", status="inspected", commit="fixture")
        ranked_after = rank_candidates(case["query"], pool, now=now)
        after_inspection = decide(ranked_after, [SourceReceipt("github", "ok", 4, returned=4)])
        names = [item.name for item in ranked]
        checks = {
            "top1": names[0] == case["expected"],
            "top3": case["expected"] in names[:3],
            "no_false_clean_build": before_inspection.recommendation == "inconclusive" and outage.recommendation == "inconclusive",
            "inspected_reuse": after_inspection.selected_id == target.canonical_id and after_inspection.recommendation in {"selective-reuse", "fork", "use-as-library"},
            "no_blocked_top": not ranked[0].hard_blockers,
        }
        rows.append({"id": case["id"], "query": case["query"], "ranked": names,
                     "checks": checks, "passed": all(checks.values()), "ranking_ms": round(elapsed_ms, 3)})
    # These close-competitor and abstention cases are also synthetic. They
    # exercise decision semantics, not live retrieval recall or human accuracy.
    for case in fixtures.get("adversarial_cases", []):
        pool = []
        for values in case["candidates"]:
            url = "https://github.com/" + values["name"]
            pool.append(Candidate(
                source="github", url=url, repository_url=url, license="MIT",
                updated_at=fixtures["clock"], dependency_count=0,
                inspection=InspectionResult(
                    repository_url=url, status="inspected", commit="synthetic",
                    manifest_files=["pyproject.toml"], docs_files=["README.md"],
                ),
                **values,
            ))
        start = time.perf_counter()
        ranked = rank_candidates(case["query"], pool, now=now)
        elapsed_ms = (time.perf_counter() - start) * 1000
        outcome = decide(ranked, [SourceReceipt("github", "ok", len(pool), returned=len(pool))])
        selected = next((item for item in ranked if item.canonical_id == outcome.selected_id), None)
        blocked = sorted(item.name for item in ranked if item.hard_blockers)
        unknown = {check.requirement for item in ranked for check in item.requirement_checks if check.status == "unknown"}
        names = [item.name for item in ranked]
        checks = {
            "selected": (selected.name if selected else None) == case["expected_selected"],
            "decision_status": outcome.status == case["expected_status"],
            "blocked_candidates": blocked == sorted(case["expected_blocked"]),
            "unknown_requirements": set(case.get("expected_unknown", [])) <= unknown,
            "no_false_clean_build": outcome.recommendation != "build-clean",
            "no_blocked_top": not ranked[0].hard_blockers,
            "no_mismatched_selection": not selected or not any(check.status == "fail" for check in selected.requirement_checks),
        }
        if case.get("expected_top"):
            checks["top1"] = names[0] == case["expected_top"]
            checks["top3"] = case["expected_top"] in names[:3]
        rows.append({"id": case["id"], "query": case["query"], "ranked": names,
                     "decision_status": outcome.status, "checks": checks,
                     "passed": all(checks.values()), "ranking_ms": round(elapsed_ms, 3)})
    times = sorted(row["ranking_ms"] for row in rows)
    count = len(rows)
    return {
        "schema": "brief2ship-quality-report-v1", "scope": fixtures["provenance"],
        "case_count": count, "passed_count": sum(row["passed"] for row in rows),
        "ranking_case_count": sum("top1" in row["checks"] for row in rows),
        "adversarial_case_count": len(fixtures.get("adversarial_cases", [])),
        "top1_hits": sum(row["checks"].get("top1", False) for row in rows),
        "top3_hits": sum(row["checks"].get("top3", False) for row in rows),
        "false_clean_build_cases": sum(not row["checks"]["no_false_clean_build"] for row in rows),
        "blocked_top_cases": sum(not row["checks"]["no_blocked_top"] for row in rows),
        "ranking_median_ms": round(statistics.median(times), 3),
        "ranking_p95_ms": times[min(count - 1, max(0, (95 * count + 99) // 100 - 1))],
        "network_requests": 0, "candidate_executions": 0,
        "passed": bool(rows) and all(row["passed"] for row in rows), "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_benchmark()
    if args.output:
        atomic_write(args.output, json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, sort_keys=True))
    if not report["passed"]:
        print(json.dumps({"failed_cases": [row for row in report["cases"] if not row["passed"]]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
