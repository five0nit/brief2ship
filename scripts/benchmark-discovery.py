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

from brief2ship.discovery_decision import decide
from brief2ship.discovery_models import Candidate, InspectionResult, SourceReceipt
from brief2ship.discovery_scoring import rank_candidates
from brief2ship.render import atomic_write


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
    times = sorted(row["ranking_ms"] for row in rows)
    count = len(rows)
    return {
        "schema": "brief2ship-quality-report-v1", "scope": fixtures["provenance"],
        "case_count": count, "passed_count": sum(row["passed"] for row in rows),
        "top1_hits": sum(row["checks"]["top1"] for row in rows),
        "top3_hits": sum(row["checks"]["top3"] for row in rows),
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
