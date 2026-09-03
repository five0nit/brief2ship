"""Explainable deterministic scoring for code and package candidates."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from .discovery_models import Candidate, ScoreBreakdown

_COMPONENT_MAX = {
    "feature_match": 25.0,
    "maintenance_activity": 15.0,
    "dependency_weight": 10.0,
    "security_posture": 15.0,
    "test_quality": 10.0,
    "portability": 10.0,
    "reuse_readiness": 10.0,
    "adoption_health": 5.0,
}
_UNKNOWN_PENALTY = {
    "feature_match": 0.15,
    "maintenance_activity": 0.15,
    "dependency_weight": 0.10,
    "security_posture": 0.30,
    "test_quality": 0.20,
    "portability": 0.15,
    "reuse_readiness": 0.15,
    "adoption_health": 0.05,
}
_PERMISSIVE_LICENSES = {
    "apache-2.0",
    "apache 2.0",
    "mit",
    "bsd-2-clause",
    "bsd-3-clause",
    "isc",
    "unlicense",
    "0bsd",
    "mit license",
    "apache license 2.0",
}
_STOPWORDS = {"a", "an", "and", "for", "of", "or", "the", "to", "with"}


def tokenize(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower().replace("_", "-").replace(".", "-"))
        if len(token) > 1 and token not in _STOPWORDS
    }


def _permissive_license(value: str | None) -> bool:
    normalized = (value or "").strip().lower().replace("_", "-")
    if normalized in _PERMISSIVE_LICENSES:
        return True
    parts = [
        part.strip(" ()")
        for part in re.split(r"\s+(?:or|and)\s+|,", normalized)
        if part.strip(" ()")
    ]
    return bool(parts) and all(part in _PERMISSIVE_LICENSES for part in parts)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _feature_score(query: str, candidate: Candidate) -> tuple[float, list[str]]:
    query_tokens = tokenize(query)
    name_tokens = tokenize(candidate.name)
    description_tokens = tokenize(candidate.description)
    topic_tokens = tokenize(" ".join(candidate.topics))
    inspection_tokens = tokenize(
        " ".join(
            (candidate.inspection.manifest_files + candidate.inspection.feature_terms)
            if candidate.inspection
            else []
        )
    )
    if not query_tokens:
        return 0.0, ["query had no scoreable tokens"]
    name_overlap = len(query_tokens & name_tokens) / len(query_tokens)
    description_overlap = len(query_tokens & description_tokens) / len(query_tokens)
    topic_overlap = len(query_tokens & topic_tokens) / len(query_tokens)
    inspection_overlap = len(query_tokens & inspection_tokens) / len(query_tokens)
    phrase_bonus = 3.0 if query.lower() in f"{candidate.name} {candidate.description}".lower() else 0.0
    identity_tokens = tokenize(candidate.name.rsplit("/", 1)[-1])
    identity_bonus = (
        4.0
        if identity_tokens
        and identity_tokens <= query_tokens
        and sum(len(token) for token in identity_tokens) >= 6
        else 0.0
    )
    score = min(
        25.0,
        10 * name_overlap
        + 8 * description_overlap
        + 4 * topic_overlap
        + 3 * inspection_overlap
        + phrase_bonus
        + identity_bonus,
    )
    return score, [
        f"name token coverage={name_overlap:.2f}",
        f"description token coverage={description_overlap:.2f}",
        f"topic token coverage={topic_overlap:.2f}",
        f"exact phrase bonus={phrase_bonus:.0f}",
        f"candidate identity bonus={identity_bonus:.0f}",
    ]


def _maintenance_score(candidate: Candidate, now: datetime) -> tuple[float, list[str]]:
    if candidate.archived:
        return 0.0, ["repository is archived"]
    if candidate.deprecated or candidate.disabled:
        return 0.0, ["candidate is deprecated, yanked, or disabled"]
    observed = _parse_date(candidate.updated_at) or _parse_date(candidate.published_at)
    if observed is None:
        return 6.0, ["activity date unknown; neutral score"]
    days = max(0, (now - observed).days)
    if days <= 30:
        score = 15.0
    elif days <= 90:
        score = 13.0
    elif days <= 180:
        score = 11.0
    elif days <= 365:
        score = 8.0
    elif days <= 730:
        score = 5.0
    else:
        score = 2.0
    return score, [f"last activity {days} days ago"]


def _dependency_score(candidate: Candidate) -> tuple[float, list[str]]:
    count = candidate.dependency_count
    if count is None and candidate.inspection:
        count = candidate.inspection.dependency_count
    if count is None:
        return 5.0, ["dependency count unknown; neutral score"]
    if count == 0:
        score = 10.0
    elif count <= 5:
        score = 9.0
    elif count <= 15:
        score = 7.0
    elif count <= 30:
        score = 5.0
    elif count <= 75:
        score = 3.0
    else:
        score = 1.0
    return score, [f"declared dependencies={count}"]


def _security_score(candidate: Candidate) -> tuple[float, list[str]]:
    evidence: list[str] = []
    if candidate.vulnerabilities_checked:
        vulnerability_points = max(0.0, 8.0 - min(8.0, len(candidate.vulnerabilities) * 4.0))
        evidence.append(f"OSV findings={len(candidate.vulnerabilities)}")
    else:
        vulnerability_points = 3.0
        evidence.append("OSV status unknown; partial neutral score")
    license_value = (candidate.license or "").strip().lower()
    if _permissive_license(license_value):
        license_points = 4.0
        evidence.append(f"permissive license={candidate.license}")
    elif license_value:
        license_points = 2.0
        evidence.append(f"license requires review={candidate.license}")
    else:
        license_points = 0.0
        evidence.append("license missing")
    if candidate.security_policy is True:
        policy_points = 3.0
        evidence.append("security policy present")
    elif candidate.security_policy is False:
        policy_points = 0.0
        evidence.append("security policy absent")
    else:
        policy_points = 1.0
        evidence.append("security policy unknown")
    if candidate.archived:
        return 0.0, evidence + ["archived override"]
    return min(15.0, vulnerability_points + license_points + policy_points), evidence


def _test_score(candidate: Candidate) -> tuple[float, list[str]]:
    signals = set(candidate.test_signals)
    inspection = candidate.inspection
    score = 0.0
    evidence: list[str] = []
    if signals or (inspection and inspection.test_files):
        score += 4.0
        evidence.append("test files/signals present")
    if inspection and inspection.ci_files:
        score += 3.0
        evidence.append("CI workflow present")
    if inspection and inspection.test_command:
        score += 2.0
        evidence.append("test command detected")
    if inspection and inspection.test_receipt:
        if inspection.test_receipt.status == "passed":
            score += 1.0
            evidence.append("sandboxed tests passed")
        elif inspection.test_receipt.status == "failed":
            score = max(0.0, score - 2.0)
            evidence.append("sandboxed tests failed")
    if not evidence:
        return 3.0, ["test evidence unknown; partial neutral score"]
    return min(10.0, score), evidence


def _portability_score(candidate: Candidate) -> tuple[float, list[str]]:
    signals = {signal.lower() for signal in candidate.portability_signals}
    score = 6.0
    evidence = ["cross-platform status not disproven; neutral baseline"]
    if candidate.language and candidate.language.lower() in {"python", "javascript", "typescript", "rust", "go", "java"}:
        score += 2.0
        evidence.append(f"portable ecosystem={candidate.language}")
    if any("cross-platform" in signal or "os-independent" in signal for signal in signals):
        score += 2.0
        evidence.append("explicit cross-platform signal")
    if any("windows-only" in signal or "linux-only" in signal or "macos-only" in signal for signal in signals):
        score = min(score, 3.0)
        evidence.append("platform restriction detected")
    return min(10.0, score), evidence


def _reuse_score(candidate: Candidate) -> tuple[float, list[str]]:
    signals = {signal.lower() for signal in candidate.reuse_signals}
    inspection = candidate.inspection
    score = 2.0 if candidate.repository_url else 1.0
    evidence = ["repository link present" if candidate.repository_url else "repository link missing"]
    if candidate.description:
        score += 1.0
        evidence.append("description present")
    if candidate.license:
        score += 1.0
        evidence.append("license declared")
    if inspection:
        if inspection.docs_files:
            score += 2.0
            evidence.append("documentation present")
        if inspection.example_files:
            score += 1.0
            evidence.append("examples present")
        if inspection.manifest_files:
            score += 2.0
            evidence.append("package/build manifest present")
        if 0 < inspection.source_file_count <= 2_000:
            score += 1.0
            evidence.append("bounded source footprint")
    elif signals:
        score += min(3.0, float(len(signals)))
        evidence.append(f"registry reuse signals={len(signals)}")
    return min(10.0, score), evidence


def _adoption_score(candidate: Candidate) -> tuple[float, list[str]]:
    values = [
        value
        for value in (candidate.stars, candidate.downloads)
        if value is not None and value >= 0
    ]
    if not values:
        score = 1.5
        evidence = ["adoption data unknown; partial neutral score"]
    else:
        strongest = max(values)
        score = min(3.5, math.log10(strongest + 1) * 1.25)
        evidence = [f"strongest adoption signal={strongest}"]

    if candidate.forks is not None:
        score += min(0.75, math.log10(candidate.forks + 1) * 0.3)
        evidence.append(f"forks={candidate.forks}")
    if candidate.watchers is not None:
        score += min(0.5, math.log10(candidate.watchers + 1) * 0.25)
        evidence.append(f"watchers={candidate.watchers}")
    if candidate.contributors is not None:
        score += min(0.75, math.log10(candidate.contributors + 1) * 0.5)
        evidence.append(f"contributors={candidate.contributors}")

    if candidate.open_issues is not None:
        if candidate.open_issues_exact:
            issue_penalty = 0.0
            if candidate.stars is not None:
                ratio = candidate.open_issues / max(1, candidate.stars)
                if candidate.open_issues >= 50 and ratio >= 0.5:
                    issue_penalty = 1.5
                elif candidate.open_issues >= 20 and ratio >= 0.25:
                    issue_penalty = 0.75
            elif candidate.open_issues >= 100:
                issue_penalty = 0.75
            if issue_penalty:
                score -= issue_penalty
                evidence.append(
                    f"issue health penalty={issue_penalty:.2f}; open issues={candidate.open_issues}"
                )
            else:
                evidence.append(f"open issues={candidate.open_issues}")
        else:
            evidence.append(
                f"issues and pull requests combined={candidate.open_issues}; no issue penalty"
            )
    return min(5.0, max(0.0, score)), evidence


def recommend(candidate: Candidate) -> str:
    if candidate.score is None:
        return "unscored"
    total = candidate.score.total
    feature = candidate.score.components["feature_match"]
    security = candidate.score.components["security_posture"]
    license_missing = not bool((candidate.license or "").strip())
    license_incompatible = not license_missing and not _permissive_license(candidate.license)
    receipt = candidate.inspection.test_receipt if candidate.inspection else None
    if receipt and receipt.status in {"failed", "timeout", "oom", "signaled", "zero_tests"}:
        return "reject"
    if candidate.archived:
        return "reject"
    if candidate.deprecated or candidate.gated or candidate.disabled:
        return "reject"
    if license_missing or license_incompatible or candidate.vulnerabilities or security < 6:
        return "reject"
    if total < 45:
        return "build-clean"
    if (
        candidate.source in {"pypi", "npm", "crates"}
        and candidate.vulnerabilities_checked
        and total >= 72
        and feature >= 12
    ):
        return "use-as-library"
    if candidate.source == "github" and total >= 80 and feature >= 16:
        return "fork"
    if total >= 65 and feature >= 10:
        return "selective-reuse"
    if total >= 50 and feature >= 8:
        return "selective-reuse"
    return "build-clean"


def _score_coverage(candidate: Candidate) -> dict[str, float]:
    inspection_complete = bool(candidate.inspection and candidate.inspection.status == "inspected")
    inspection_dependency_known = bool(
        inspection_complete
        and candidate.inspection
        and candidate.inspection.dependency_count is not None
    )
    test_receipt = candidate.inspection.test_receipt if candidate.inspection else None
    security_coverage = (
        (0.60 if candidate.vulnerabilities_checked else 0.0)
        + (0.25 if candidate.license else 0.0)
        + (0.15 if candidate.security_policy is not None else 0.0)
    )
    return {
        "feature_match": 1.0 if inspection_complete else 0.65 if candidate.description or candidate.topics else 0.25,
        "maintenance_activity": 1.0 if candidate.updated_at or candidate.published_at else 0.0,
        "dependency_weight": 1.0 if candidate.dependency_count is not None or inspection_dependency_known else 0.0,
        "security_posture": security_coverage,
        "test_quality": 1.0 if inspection_complete else 0.35 if candidate.test_signals else 0.0,
        "portability": 1.0 if test_receipt and test_receipt.status == "passed" else 0.70 if candidate.portability_signals else 0.40 if candidate.language else 0.0,
        "reuse_readiness": 1.0 if inspection_complete else 0.60 if candidate.repository_url and candidate.license else 0.30 if candidate.repository_url else 0.0,
        "adoption_health": 1.0
        if any(
            value is not None
            for value in (
                candidate.stars,
                candidate.downloads,
                candidate.forks,
                candidate.watchers,
                candidate.contributors,
                candidate.open_issues,
            )
        )
        else 0.0,
    }


def _recommendation_receipt(candidate: Candidate) -> None:
    blockers: list[str] = []
    checks: list[str] = []
    if candidate.archived:
        blockers.append("repository is archived")
    if candidate.deprecated:
        blockers.append(candidate.deprecation_reason or "candidate is deprecated or yanked")
    if candidate.gated:
        blockers.append("artifact requires gated access")
    if candidate.disabled:
        blockers.append("artifact is disabled")
    if not candidate.license:
        blockers.append("license missing or ambiguous")
    elif not _permissive_license(candidate.license):
        blockers.append("license is outside the default permissive allowlist")
    if candidate.vulnerabilities:
        blockers.append("OSV findings require severity and remediation review")
    inspection = candidate.inspection
    receipt = inspection.test_receipt if inspection else None
    if receipt and receipt.status in {"failed", "timeout", "oom", "signaled", "zero_tests"}:
        blockers.append(f"sandboxed tests reported {receipt.status}")
    if not inspection or inspection.status != "inspected":
        checks.append("static repository inspection not completed")
    if not candidate.vulnerabilities_checked:
        checks.append("exact package-version OSV evidence unavailable")
    if not receipt or receipt.status != "passed":
        checks.append("authorized sandbox test pass unavailable")
    candidate.hard_blockers = blockers
    candidate.required_checks = checks
    if blockers:
        candidate.recommendation_status = "blocked"
    elif candidate.recommendation in {"use-as-library", "fork", "selective-reuse"}:
        candidate.recommendation_status = "ready" if not checks else "provisional"
    else:
        candidate.recommendation_status = "not-selected"


def _canonical_id(candidate: Candidate) -> str:
    if candidate.source in {"pypi", "npm", "crates"}:
        return f"{candidate.source}:{candidate.name.lower()}@{candidate.version or 'unknown'}"
    if candidate.source == "huggingface":
        return f"huggingface:{candidate.name.lower()}@{candidate.version or 'observed'}"
    commit = candidate.inspection.commit if candidate.inspection else None
    repository = (candidate.repository_url or candidate.url).lower().rstrip("/")
    return f"repo:{repository}@{commit or 'observed-unpinned'}"


def score_candidate(query: str, candidate: Candidate, *, now: datetime | None = None) -> ScoreBreakdown:
    current = now or datetime.now(timezone.utc)
    scorers = {
        "feature_match": lambda: _feature_score(query, candidate),
        "maintenance_activity": lambda: _maintenance_score(candidate, current),
        "dependency_weight": lambda: _dependency_score(candidate),
        "security_posture": lambda: _security_score(candidate),
        "test_quality": lambda: _test_score(candidate),
        "portability": lambda: _portability_score(candidate),
        "reuse_readiness": lambda: _reuse_score(candidate),
        "adoption_health": lambda: _adoption_score(candidate),
    }
    components: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}
    for name, scorer in scorers.items():
        value, notes = scorer()
        components[name] = round(min(_COMPONENT_MAX[name], max(0.0, value)), 2)
        evidence[name] = notes
    coverage_by_component = _score_coverage(candidate)
    coverage = sum(
        _COMPONENT_MAX[name] * coverage_by_component[name] for name in _COMPONENT_MAX
    ) / 100.0
    unknown_cost = sum(
        _COMPONENT_MAX[name] * _UNKNOWN_PENALTY[name] * (1.0 - coverage_by_component[name])
        for name in _COMPONENT_MAX
    )
    for name, value in coverage_by_component.items():
        evidence[name].append(f"evidence coverage={value:.2f}")
    breakdown = ScoreBreakdown(
        round(sum(components.values()), 2),
        components,
        evidence,
        coverage=round(coverage, 4),
        unknown_cost=round(unknown_cost, 2),
    )
    candidate.score = breakdown
    candidate.canonical_id = _canonical_id(candidate)
    candidate.recommendation = recommend(candidate)
    _recommendation_receipt(candidate)
    return breakdown


def rank_candidates(query: str, candidates: list[Candidate], *, now: datetime | None = None) -> list[Candidate]:
    for candidate in candidates:
        score_candidate(query, candidate, now=now)
    return sorted(
        candidates,
        key=lambda item: (
            -(item.score.total if item.score else 0),
            item.source,
            item.name.lower(),
        ),
    )
