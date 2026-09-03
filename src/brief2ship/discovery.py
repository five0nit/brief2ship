"""Orchestration for multi-source code and package discovery."""

from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .discovery_http import DiscoveryHttpClient
from .discovery_inspection import RepositoryInspector
from .discovery_local import search_local
from .discovery_models import Candidate, DiscoveryConfig, DiscoveryResult, SourceReceipt
from .discovery_providers import PROVIDERS, enrich_osv, search_pypi
from .discovery_scoring import rank_candidates
from .errors import OutputError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _latest_timestamp(*values: str | None) -> str | None:
    available = [value for value in values if value]
    parsed: list[tuple[datetime, str]] = []
    for value in available:
        try:
            observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        parsed.append((observed.astimezone(timezone.utc), value))
    if parsed:
        return max(parsed, key=lambda item: item[0])[1]
    return max(available, default=None)


def prepare_output_directory(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.exists():
        if not resolved.is_dir():
            raise OutputError(f"discovery output is not a directory: {resolved}")
        if any(resolved.iterdir()):
            raise OutputError(f"discovery output directory must be empty: {resolved}")
    else:
        resolved.mkdir(parents=True)
    return resolved


def _merge_candidate(existing: Candidate, incoming: Candidate) -> Candidate:
    package_sources = {"pypi", "npm", "crates"}
    if incoming.source in package_sources and existing.source not in package_sources:
        primary, secondary = incoming, existing
    else:
        primary, secondary = existing, incoming
    primary.aliases = sorted(
        set(primary.aliases + secondary.aliases + [f"{secondary.source}:{secondary.name}", secondary.url])
    )
    if len(secondary.description) > len(primary.description):
        primary.description = secondary.description
    primary.repository_url = primary.repository_url or secondary.repository_url
    primary.local_path = primary.local_path or secondary.local_path
    primary.version = primary.version or secondary.version
    primary.license = primary.license or secondary.license
    primary.updated_at = _latest_timestamp(primary.updated_at, secondary.updated_at)
    primary.published_at = primary.published_at or secondary.published_at
    for field_name in (
        "downloads",
        "stars",
        "forks",
        "watchers",
        "contributors",
        "repository_size_kb",
    ):
        values = [value for value in (getattr(primary, field_name), getattr(secondary, field_name)) if value is not None]
        if values:
            setattr(primary, field_name, max(values))
    if secondary.open_issues_exact and not primary.open_issues_exact:
        primary.open_issues = secondary.open_issues
    elif primary.open_issues is None:
        primary.open_issues = secondary.open_issues
    elif primary.open_issues_exact and secondary.open_issues_exact:
        primary.open_issues = max(
            value
            for value in (primary.open_issues, secondary.open_issues)
            if value is not None
        )
    primary.open_issues_exact = primary.open_issues_exact or secondary.open_issues_exact
    primary.archived = primary.archived or secondary.archived
    primary.deprecated = primary.deprecated or secondary.deprecated
    primary.deprecation_reason = primary.deprecation_reason or secondary.deprecation_reason
    primary.gated = primary.gated or secondary.gated
    primary.disabled = primary.disabled or secondary.disabled
    primary.language = primary.language or secondary.language
    primary.homepage = primary.homepage or secondary.homepage
    primary.topics = sorted(set(primary.topics + secondary.topics))
    if primary.dependency_count is None:
        primary.dependency_count = secondary.dependency_count
    if primary.security_policy is None:
        primary.security_policy = secondary.security_policy
    primary.vulnerabilities_checked = (
        primary.vulnerabilities_checked or secondary.vulnerabilities_checked
    )
    primary.vulnerabilities = sorted(
        set(primary.vulnerabilities + secondary.vulnerabilities)
    )
    vulnerability_evidence = {
        str(value.get("id") or index): value
        for index, value in enumerate(
            primary.vulnerability_evidence + secondary.vulnerability_evidence
        )
    }
    primary.vulnerability_evidence = [
        vulnerability_evidence[key] for key in sorted(vulnerability_evidence)
    ]
    primary.test_signals = sorted(set(primary.test_signals + secondary.test_signals))
    primary.portability_signals = sorted(set(primary.portability_signals + secondary.portability_signals))
    primary.reuse_signals = sorted(set(primary.reuse_signals + secondary.reuse_signals))
    return primary


def deduplicate_candidates(candidates: list[Candidate]) -> list[Candidate]:
    merged: dict[str, Candidate] = {}
    order: list[str] = []
    for candidate in candidates:
        if candidate.source == "local" and not candidate.repository_url:
            key = f"local:{(candidate.local_path or candidate.url).lower()}"
        elif candidate.source in {"pypi", "npm", "crates", "huggingface"}:
            key = f"package:{candidate.source}:{candidate.name.lower()}@{candidate.version or 'observed'}"
        elif candidate.repository_url:
            key = f"repo:{candidate.repository_url.lower().rstrip('/')}"
        else:
            key = f"source:{candidate.source}:{candidate.name.lower()}"
        if key in merged:
            merged[key] = _merge_candidate(merged[key], candidate)
        else:
            merged[key] = deepcopy(candidate)
            order.append(key)
    values = [merged[key] for key in order]
    repository_evidence_by_repo = {
        candidate.repository_url.lower().rstrip("/"): candidate
        for candidate in values
        if candidate.source in {"github", "local"} and candidate.repository_url
    }
    package_repositories = {
        candidate.repository_url.lower().rstrip("/")
        for candidate in values
        if candidate.source in {"pypi", "npm", "crates"}
        and candidate.repository_url
    }
    output: list[Candidate] = []
    for candidate in values:
        repository_key = candidate.repository_url.lower().rstrip("/") if candidate.repository_url else None
        if candidate.source in {"github", "local"} and repository_key in package_repositories:
            continue
        if candidate.source not in {"github", "local"} and repository_key in repository_evidence_by_repo:
            candidate = _merge_candidate(
                candidate,
                deepcopy(repository_evidence_by_repo[repository_key]),
            )
        output.append(candidate)
    return output


def _inspection_priority(candidate: Candidate) -> tuple[float, float, str, str]:
    """Prefer direct query fit when choosing scarce inspection slots."""
    feature_match = (
        candidate.score.components.get("feature_match", 0.0)
        if candidate.score
        else 0.0
    )
    total = candidate.score.total if candidate.score else 0.0
    return (-feature_match, -total, candidate.source, candidate.name.lower())


def discover(
    query: str,
    config: DiscoveryConfig,
    *,
    output_dir: Path,
    cache_dir: Path | None = None,
    client: DiscoveryHttpClient | None = None,
) -> DiscoveryResult:
    config.validate()
    normalized_query = " ".join(query.split())
    if not 2 <= len(normalized_query) <= 300:
        raise ValueError("query must contain between 2 and 300 non-whitespace characters")
    destination = prepare_output_directory(output_dir)
    started_at = _now()
    http = client or DiscoveryHttpClient(
        timeout=config.timeout,
        total_timeout=config.total_timeout,
        github_token=config.github_token,
    )
    cache = cache_dir or Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "brief2ship"
    candidates: list[Candidate] = []
    receipts: list[SourceReceipt] = []
    for source in config.sources:
        try:
            if source == "local":
                found, receipt = search_local(
                    normalized_query,
                    config.local_roots,
                    limit=config.per_source,
                    timeout_seconds=config.total_timeout,
                )
            elif source == "pypi":
                found, receipt = search_pypi(
                    normalized_query,
                    config.per_source,
                    http,
                    cache_dir=cache,
                    refresh=config.refresh_cache,
                )
            else:
                found, receipt = PROVIDERS[source](normalized_query, config.per_source, http)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            found = []
            receipt = SourceReceipt(source, "failed", config.per_source, error=f"invalid source response: {exc}")
        candidates.extend(found)
        receipts.append(receipt)
    candidates = deduplicate_candidates(candidates)
    limitations = [
        "scores compare observed public metadata; missing evidence remains explicit",
        "registry popularity is supporting evidence, not proof of implementation quality",
        "JavaScript client challenges are not bypassed; PyPI uses its official Simple index",
        "repository tests never execute unless both test_top and allow_untrusted_tests are set",
        "local workspace discovery is read-only and bounded; receipts may contain local paths",
    ]
    for candidate in candidates:
        warning = enrich_osv(candidate, http)
        if warning and candidate.source in {"pypi", "npm", "crates"}:
            limitations.append(f"OSV {candidate.source}:{candidate.name}: {warning}")
    ranked = rank_candidates(normalized_query, candidates)
    if config.inspect_top:
        inspector = RepositoryInspector(http, destination / "worktrees")
        shortlist = sorted(ranked, key=_inspection_priority)[: config.inspect_top]
        for index, candidate in enumerate(shortlist):
            candidate.inspection = inspector.inspect(candidate, run_tests=index < config.test_top)
        ranked = rank_candidates(normalized_query, ranked)
    ranked = ranked[: config.limit]
    if ranked:
        top = ranked[0]
        reusable = next(
            (
                candidate
                for candidate in ranked
                if candidate.recommendation in {"use-as-library", "fork", "selective-reuse"}
                and candidate.recommendation_status in {"ready", "provisional"}
            ),
            None,
        )
        if reusable:
            overall = reusable.recommendation
            reason = f"candidate {reusable.name} scored {reusable.score.total if reusable.score else 0:.2f}/100 with {reusable.recommendation_status} evidence"
        else:
            overall = "build-clean"
            reason = f"no candidate cleared reuse gates; top score was {top.score.total if top.score else 0:.2f}/100 ({top.recommendation})"
    else:
        overall = "build-clean"
        reason = "no candidates were returned by the selected sources"
    config_receipt = {
        "sources": list(config.sources),
        "local_roots": [
            str(Path(value).expanduser().resolve()) for value in config.local_roots
        ],
        "per_source": config.per_source,
        "limit": config.limit,
        "timeout": config.timeout,
        "total_timeout": config.total_timeout,
        "inspect_top": config.inspect_top,
        "test_top": config.test_top,
        "allow_untrusted_tests": config.allow_untrusted_tests,
        "refresh_cache": config.refresh_cache,
        "github_token_used": bool(config.github_token),
    }
    return DiscoveryResult(
        query=normalized_query,
        started_at=started_at,
        completed_at=_now(),
        config=config_receipt,
        candidates=ranked,
        sources=receipts,
        overall_recommendation=overall,
        recommendation_reason=reason,
        limitations=sorted(set(limitations)),
    )
