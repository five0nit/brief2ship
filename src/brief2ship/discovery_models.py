"""Typed contracts for multi-ecosystem code discovery."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ScoreBreakdown:
    total: float
    components: dict[str, float]
    evidence: dict[str, list[str]]
    coverage: float = 0.0
    unknown_cost: float = 0.0
    decision_score: float = 0.0


@dataclass
class TestReceipt:
    status: str
    command: list[str] = field(default_factory=list)
    exit_code: int | None = None
    duration_seconds: float | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    sandbox: str = "not-run"
    limitation: str | None = None


@dataclass
class InspectionResult:
    repository_url: str
    clone_path: str | None = None
    status: str = "not-run"
    commit: str | None = None
    license: str | None = None
    manifest_files: list[str] = field(default_factory=list)
    dependency_count: int | None = None
    test_files: list[str] = field(default_factory=list)
    ci_files: list[str] = field(default_factory=list)
    docs_files: list[str] = field(default_factory=list)
    example_files: list[str] = field(default_factory=list)
    source_file_count: int = 0
    languages: list[str] = field(default_factory=list)
    feature_terms: list[str] = field(default_factory=list)
    test_command: list[str] = field(default_factory=list)
    test_receipt: TestReceipt | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class Candidate:
    source: str
    name: str
    url: str
    description: str = ""
    repository_url: str | None = None
    local_path: str | None = None
    version: str | None = None
    license: str | None = None
    updated_at: str | None = None
    published_at: str | None = None
    downloads: int | None = None
    stars: int | None = None
    forks: int | None = None
    watchers: int | None = None
    contributors: int | None = None
    open_issues: int | None = None
    open_issues_exact: bool = False
    homepage: str | None = None
    repository_size_kb: int | None = None
    archived: bool = False
    deprecated: bool = False
    deprecation_reason: str | None = None
    gated: bool = False
    disabled: bool = False
    language: str | None = None
    topics: list[str] = field(default_factory=list)
    dependency_count: int | None = None
    security_policy: bool | None = None
    vulnerabilities_checked: bool = False
    vulnerabilities: list[str] = field(default_factory=list)
    vulnerability_evidence: list[dict[str, Any]] = field(default_factory=list)
    test_signals: list[str] = field(default_factory=list)
    portability_signals: list[str] = field(default_factory=list)
    reuse_signals: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    raw_relevance: float | None = None
    inspection: InspectionResult | None = None
    score: ScoreBreakdown | None = None
    recommendation: str = "unscored"
    recommendation_status: str = "unscored"
    hard_blockers: list[str] = field(default_factory=list)
    required_checks: list[str] = field(default_factory=list)
    canonical_id: str | None = None
    normalized_license: str | None = None
    source_rank: int | None = None
    constraint_checks: list[str] = field(default_factory=list)
    repository_evidence: dict[str, Any] = field(default_factory=dict)
    license_kind: str = "metadata"
    license_body_match: str | None = None
    license_review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceReceipt:
    source: str
    status: str
    requested: int
    returned: int = 0
    endpoints: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    rate_limit_remaining: int | None = None
    queries: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DiscoveryConfig:
    sources: tuple[str, ...] = ("github", "pypi", "npm", "crates", "huggingface")
    local_roots: tuple[str, ...] = ()
    per_source: int = 10
    limit: int = 10
    timeout: float = 20.0
    total_timeout: float = 180.0
    inspect_top: int = 0
    test_top: int = 0
    allow_untrusted_tests: bool = False
    refresh_cache: bool = False
    github_token: str | None = field(default=None, repr=False, compare=False)

    def validate(self) -> None:
        allowed = {"local", "github", "pypi", "npm", "crates", "huggingface"}
        if not self.sources or any(source not in allowed for source in self.sources):
            raise ValueError(f"sources must be selected from {', '.join(sorted(allowed))}")
        if "local" in self.sources and not self.local_roots:
            raise ValueError("local source requires at least one local root")
        if self.local_roots and "local" not in self.sources:
            raise ValueError("local roots require the local source")
        if len(self.local_roots) > 5:
            raise ValueError("local source accepts at most 5 roots")
        if not 1 <= self.per_source <= 20:
            raise ValueError("per_source must be between 1 and 20")
        if not 1 <= self.limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if not 1 <= self.timeout <= 30:
            raise ValueError("timeout must be between 1 and 30 seconds")
        if not 10 <= self.total_timeout <= 600:
            raise ValueError("total_timeout must be between 10 and 600 seconds")
        if not 0 <= self.inspect_top <= 5:
            raise ValueError("inspect_top must be between 0 and 5")
        if not 0 <= self.test_top <= 3:
            raise ValueError("test_top must be between 0 and 3")
        if self.test_top > self.inspect_top:
            raise ValueError("test_top cannot exceed inspect_top")
        if self.test_top and not self.allow_untrusted_tests:
            raise ValueError("test_top requires --allow-untrusted-tests")


@dataclass
class DiscoveryResult:
    query: str
    started_at: str
    completed_at: str
    config: dict[str, Any]
    candidates: list[Candidate]
    sources: list[SourceReceipt]
    overall_recommendation: str
    recommendation_reason: str
    limitations: list[str] = field(default_factory=list)
    schema_version: str = "brief2ship-discovery-v2"
    scoring_contract: str = "brief2ship-score-v2"
    sandbox_policy: str = "brief2ship-bwrap-v2"
    evaluated_candidates: list[Candidate] = field(default_factory=list)
    selected_candidate_id: str | None = None
    decision_status: str = "inconclusive"
    discovery_status: str = "incomplete"
    incomplete_reasons: list[str] = field(default_factory=list)
    query_plan: dict[str, Any] = field(default_factory=dict)
    inspection_decisions: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
