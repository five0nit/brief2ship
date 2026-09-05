"""Run-level decisions: incomplete searches never authorize a clean build."""

from __future__ import annotations

from dataclasses import dataclass, field

from .discovery_models import Candidate, SourceReceipt

_REUSE = {"use-as-library", "fork", "selective-reuse"}


@dataclass
class DecisionOutcome:
    recommendation: str = "inconclusive"
    status: str = "inconclusive"
    discovery_status: str = "incomplete"
    reason: str = "discovery evidence is incomplete"
    selected_id: str | None = None
    incomplete_reasons: list[str] = field(default_factory=list)


def decide(candidates: list[Candidate], sources: list[SourceReceipt]) -> DecisionOutcome:
    """Decide across all evaluated candidates, never the display-only shortlist.

    A static inspection can establish a provisional reuse lead, not a runtime
    verification. Complete negative inspections can justify build-clean within
    the bounded search. Empty/failed searches establish neither outcome.
    """
    outcome = DecisionOutcome()
    failed = [source for source in sources if source.status != "ok" or source.error]
    if not sources or failed:
        outcome.discovery_status = "partial" if any(
            source.status in {"ok", "partial"} for source in sources
        ) else "failed"
        outcome.incomplete_reasons = [
            f"{source.source}: {source.error or source.status}" for source in failed
        ] or ["no source receipts available"]
        outcome.reason = "source collection incomplete; reuse/build decision deferred"
        return outcome

    outcome.discovery_status = "complete"
    if not candidates:
        outcome.reason = "no candidates found; absence of results is not proof that reuse is unsuitable"
        outcome.incomplete_reasons = ["broaden or revise the query before deciding to build clean"]
        return outcome

    reusable = [candidate for candidate in candidates if (
        candidate.recommendation in _REUSE
        and candidate.recommendation_status in {"ready", "provisional"}
        and candidate.inspection is not None
        and candidate.inspection.status == "inspected"
    )]
    if reusable:
        selected = next((item for item in reusable if item.recommendation_status == "ready"), reusable[0])
        outcome.recommendation = selected.recommendation
        outcome.status = "complete" if selected.recommendation_status == "ready" else "provisional"
        outcome.selected_id = selected.canonical_id
        outcome.reason = (
            f"candidate {selected.name} selected with {outcome.status} evidence; "
            "static inspection completed"
        )
        return outcome

    missing = [candidate for candidate in candidates if (
        candidate.inspection is None
        or candidate.inspection.status != "inspected"
        or not candidate.normalized_license
        or not candidate.score
        or (candidate.score.components.get("feature_match", 0) >= 8 and not (
            candidate.archived or candidate.deprecated or candidate.disabled or candidate.gated
            or candidate.vulnerabilities or (candidate.inspection.test_receipt and
                candidate.inspection.test_receipt.status in {"failed", "timeout", "oom", "signaled", "zero_tests"})
        ))
    )]
    if missing:
        outcome.incomplete_reasons = [
            f"{item.name}: static inspection, license or supported negative evidence incomplete" for item in missing
        ]
        outcome.reason = "no inspected reusable candidate; remaining evidence is insufficient for build-clean"
        return outcome

    outcome.recommendation = "build-clean"
    outcome.status = "complete"
    outcome.reason = "all evaluated candidates inspected; none cleared reuse gates within this bounded search"
    return outcome
