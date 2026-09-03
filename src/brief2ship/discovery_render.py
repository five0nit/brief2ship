"""Deterministic JSON and inert Markdown discovery receipts."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .discovery_models import Candidate, DiscoveryResult
from .render import atomic_write

_UNSAFE_CONTROLS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]"
)


def _safe(value: object) -> str:
    return _UNSAFE_CONTROLS.sub("", str(value)).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _code(value: object) -> str:
    text = _safe(value)
    runs = [len(match.group(0)) for match in re.finditer(r"`+", text)]
    fence = "`" * (max(runs, default=0) + 1)
    return f"{fence} {text} {fence}" if text.startswith(("`", " ")) or text.endswith(("`", " ")) else f"{fence}{text}{fence}"


def render_discovery_json(result: DiscoveryResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _score(candidate: Candidate, key: str) -> str:
    if not candidate.score:
        return "0.00"
    return f"{candidate.score.components.get(key, 0):.2f}"


def _observed_number(value: int | None) -> str:
    return str(value) if value is not None else "unknown"


def _issue_evidence(candidate: Candidate) -> str:
    if candidate.open_issues is None:
        return "unknown"
    suffix = "issue-only" if candidate.open_issues_exact else "issues+pull-requests"
    return f"{candidate.open_issues} ({suffix})"


def render_discovery_markdown(result: DiscoveryResult) -> str:
    lines = [
        "# Brief2Ship code-discovery receipt",
        "",
        "## Decision",
        "",
        f"- Overall: {_code(result.overall_recommendation)}",
        f"- Reason: {_code(result.recommendation_reason)}",
        f"- Query: {_code(result.query)}",
        f"- Started: {_code(result.started_at)}",
        f"- Completed: {_code(result.completed_at)}",
        "",
        "## Ranked candidates",
        "",
        "| # | Score | Coverage | Candidate | Source | Feature | Activity | Dependencies | Security | Tests | Portability | Reuse | Adoption | Recommendation | Status |",
        "|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for index, candidate in enumerate(result.candidates, 1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    f"{candidate.score.total if candidate.score else 0:.2f}",
                    f"{candidate.score.coverage if candidate.score else 0:.2f}",
                    _code(candidate.name),
                    _code(candidate.source),
                    _score(candidate, "feature_match"),
                    _score(candidate, "maintenance_activity"),
                    _score(candidate, "dependency_weight"),
                    _score(candidate, "security_posture"),
                    _score(candidate, "test_quality"),
                    _score(candidate, "portability"),
                    _score(candidate, "reuse_readiness"),
                    _score(candidate, "adoption_health"),
                    _code(candidate.recommendation),
                    _code(candidate.recommendation_status),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Candidate evidence", ""])
    for index, candidate in enumerate(result.candidates, 1):
        lines.extend(
            [
                f"### {index}. {_code(candidate.name)}",
                "",
                f"- URL: {_code(candidate.url)}",
                f"- Repository: {_code(candidate.repository_url or 'unknown')}",
                f"- Local path: {_code(candidate.local_path or 'not local')}",
                f"- Homepage/demo: {_code(candidate.homepage or 'unknown')}",
                f"- Version: {_code(candidate.version or 'unknown')}",
                f"- Canonical identity: {_code(candidate.canonical_id or 'unknown')}",
                f"- License: {_code(candidate.license or 'unknown')}",
                f"- Activity: {_code(candidate.updated_at or candidate.published_at or 'unknown')}",
                f"- Dependencies: {_code(candidate.dependency_count if candidate.dependency_count is not None else 'unknown')}",
                f"- Stars / forks / watchers: {_code(' / '.join((_observed_number(candidate.stars), _observed_number(candidate.forks), _observed_number(candidate.watchers))))}",
                f"- Contributors / open issues: {_code(' / '.join((_observed_number(candidate.contributors), _issue_evidence(candidate))))}",
                f"- Vulnerabilities: {_code(', '.join(candidate.vulnerabilities) if candidate.vulnerabilities else 'none observed' if candidate.vulnerabilities_checked else 'unknown')}",
                f"- Recommendation: {_code(candidate.recommendation)}",
                f"- Recommendation status: {_code(candidate.recommendation_status)}",
                f"- Hard blockers: {_code('; '.join(candidate.hard_blockers) or 'none')}",
                f"- Required checks: {_code('; '.join(candidate.required_checks) or 'none')}",
            ]
        )
        if candidate.inspection:
            lines.extend(
                [
                    f"- Inspection: {_code(candidate.inspection.status)}",
                    f"- Clone: {_code(candidate.inspection.clone_path or 'not cloned')}",
                    f"- Commit: {_code(candidate.inspection.commit or 'unknown')}",
                    f"- Manifests: {_code(', '.join(candidate.inspection.manifest_files) or 'none')}",
                    f"- Test files: `{len(candidate.inspection.test_files)}`",
                    f"- CI files: `{len(candidate.inspection.ci_files)}`",
                ]
            )
            if candidate.inspection.test_receipt:
                lines.extend(
                    [
                        f"- Sandboxed tests: {_code(candidate.inspection.test_receipt.status)}",
                        f"- Sandbox: {_code(candidate.inspection.test_receipt.sandbox)}",
                        f"- Exit: {_code(candidate.inspection.test_receipt.exit_code)}",
                    ]
                )
        if candidate.score:
            lines.extend(["", "Score evidence:", ""])
            for component, evidence in candidate.score.evidence.items():
                lines.append(f"- {_code(component)}: {_code('; '.join(evidence))}")
        lines.append("")
    lines.extend(["## Source receipts", ""])
    for source in result.sources:
        lines.append(
            f"- {_code(source.source)}: status={_code(source.status)}, returned={_code(source.returned)}, rate-limit-remaining={_code(source.rate_limit_remaining)}"
        )
        if source.error:
            lines.append(f"  - Error: {_code(source.error)}")
        for warning in source.warnings:
            lines.append(f"  - Warning: {_code(warning)}")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {_code(value)}" for value in result.limitations)
    return "\n".join(lines).rstrip() + "\n"


def write_discovery(result: DiscoveryResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(output_dir / "discovery.json", render_discovery_json(result))
    receipt = atomic_write(output_dir / "discovery.md", render_discovery_markdown(result))
    candidates_dir = output_dir / "candidates"
    candidates_dir.mkdir(exist_ok=True)
    for index, candidate in enumerate(result.candidates, 1):
        filename = re.sub(r"[^A-Za-z0-9_.-]+", "-", candidate.name).strip("-.")[:80] or "candidate"
        atomic_write(
            candidates_dir / f"{index:02d}-{filename}.json",
            json.dumps(candidate.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        )
    return receipt
