"""Free public discovery providers for code and package ecosystems."""

from __future__ import annotations

import gzip
import json
import math
import os
import re
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from .discovery_http import DiscoveryHttpClient, DiscoverySourceError
from .discovery_models import Candidate, SourceReceipt
from .discovery_scoring import tokenize

_GITHUB_API = "https://api.github.com"
_PYPI_SIMPLE = "https://pypi.org/simple/"
_OSV_API = "https://api.osv.dev/v1/query"
_GITHUB_FOCUS_STOPWORDS = {
    "and",
    "app",
    "application",
    "build",
    "building",
    "code",
    "ecosystem",
    "existing",
    "first",
    "for",
    "greenfield",
    "library",
    "multi",
    "new",
    "of",
    "or",
    "package",
    "reuse",
    "solution",
    "support",
    "the",
    "tool",
    "tools",
    "with",
}


def _rate_limit_remaining(headers: dict[str, str]) -> int | None:
    direct = headers.get("x-ratelimit-remaining")
    if direct and direct.isdigit():
        return int(direct)
    standard = headers.get("ratelimit") or ""
    match = re.search(r"(?:^|;)r=(\d+)(?:;|$)", standard.replace('"', ""))
    return int(match.group(1)) if match else None


_CACHE_MAX_AGE = 7 * 24 * 60 * 60


class _SimpleNamesParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside = False
        self.names: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: ARG002
        if tag.lower() == "a":
            self._inside = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a":
            self._inside = False

    def handle_data(self, data: str) -> None:
        if self._inside:
            value = data.strip()
            if value:
                self.names.append(value)


def canonical_repository_url(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().replace("git+https://", "https://").replace("git://", "https://")
    if cleaned.startswith("github:"):
        cleaned = "https://github.com/" + cleaned.split(":", 1)[1]
    if cleaned.startswith("git@github.com:"):
        cleaned = "https://github.com/" + cleaned.split(":", 1)[1]
    try:
        parts = urlsplit(cleaned)
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return None
    if parts.username is not None or parts.password is not None:
        return None
    host = parts.hostname.lower()
    if host not in {"github.com", "www.github.com"}:
        try:
            port = parts.port
        except ValueError:
            return None
        display_host = f"[{host}]" if ":" in host else host
        default_port = 443 if parts.scheme == "https" else 80
        netloc = display_host if port in {None, default_port} else f"{display_host}:{port}"
        path = parts.path.rstrip("/").removesuffix(".git")
        return urlunsplit((parts.scheme, netloc, path or "/", "", ""))
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) < 2:
        return None
    owner, repo = segments[0], segments[1].removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        return None
    return urlunsplit(("https", "github.com", f"/{owner}/{repo}", "", ""))


def _repository_from_mapping(mapping: Any) -> str | None:
    if isinstance(mapping, str):
        return canonical_repository_url(mapping)
    if isinstance(mapping, dict):
        return canonical_repository_url(str(mapping.get("url") or ""))
    return None


def _github_candidate(item: dict[str, Any]) -> Candidate:
    license_data = item.get("license") or {}
    return Candidate(
        source="github",
        name=str(item.get("full_name") or item.get("name") or "unknown"),
        url=str(item.get("html_url") or ""),
        repository_url=canonical_repository_url(item.get("html_url")),
        description=str(item.get("description") or ""),
        homepage=str(item.get("homepage") or "") or None,
        license=str(license_data.get("spdx_id") or "") or None,
        updated_at=item.get("pushed_at") or item.get("updated_at"),
        published_at=item.get("created_at"),
        stars=int(item.get("stargazers_count") or 0),
        forks=int(item.get("forks_count") or 0),
        open_issues=int(item.get("open_issues_count") or 0),
        repository_size_kb=int(item.get("size") or 0),
        archived=bool(item.get("archived")),
        language=item.get("language"),
        topics=[str(value) for value in item.get("topics") or []],
        raw_relevance=float(item.get("score") or 0),
        aliases=[str(item.get("id"))] if item.get("id") is not None else [],
    )


def _github_focus_query(query: str) -> str:
    """Reduce long prose to one bounded, deterministic GitHub fallback."""
    tokens: list[str] = []
    for value in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.+#-]*", query.lower()):
        for token in re.findall(r"[a-z0-9][a-z0-9_.+#]*", value.replace("-", " ")):
            if len(token) < 2 or token in _GITHUB_FOCUS_STOPWORDS or token in tokens:
                continue
            tokens.append(token)
    if len(tokens) < 2:
        return query
    return " ".join(tokens[:3])


def search_github(
    query: str,
    limit: int,
    client: DiscoveryHttpClient,
) -> tuple[list[Candidate], SourceReceipt]:
    endpoint = f"{_GITHUB_API}/search/repositories?{urlencode({'q': query, 'per_page': limit, 'page': 1})}"
    receipt = SourceReceipt("github", "ok", limit, endpoints=[endpoint])
    try:
        data, payload = client.get_json(
            endpoint,
            headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        )
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise DiscoverySourceError("GitHub response had no repository items")
        remaining_values = [_rate_limit_remaining(payload.headers)]
        focused_query = _github_focus_query(query)
        if not data["items"] and focused_query != query:
            focused_endpoint = f"{_GITHUB_API}/search/repositories?{urlencode({'q': focused_query, 'per_page': limit, 'page': 1})}"
            focused_data, focused_payload = client.get_json(
                focused_endpoint,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            if not isinstance(focused_data, dict) or not isinstance(
                focused_data.get("items"),
                list,
            ):
                raise DiscoverySourceError(
                    "GitHub focused fallback had no repository items"
                )
            data = focused_data
            payload = focused_payload
            receipt.endpoints.append(focused_endpoint)
            receipt.warnings.append(
                f"original query returned no results; used focused fallback: {focused_query}"
            )
            remaining_values.append(_rate_limit_remaining(payload.headers))
        public_items = [
            item for item in data["items"]
            if isinstance(item, dict) and not item.get("private")
        ]
        private_count = len(data["items"]) - len(public_items)
        candidates = [_github_candidate(item) for item in public_items]
        observed_remaining = [value for value in remaining_values if value is not None]
        receipt.rate_limit_remaining = min(observed_remaining) if observed_remaining else None
        receipt.returned = len(candidates)
        if payload.headers.get("x-ratelimit-limit") == "10":
            receipt.warnings.append("unauthenticated GitHub rate limit is low; set GH_TOKEN or GITHUB_TOKEN")
        if private_count:
            receipt.warnings.append(f"filtered {private_count} private GitHub result(s)")
        return candidates, receipt
    except DiscoverySourceError as exc:
        receipt.status = "failed"
        receipt.error = str(exc)
        return [], receipt


def _load_pypi_names(
    client: DiscoveryHttpClient,
    cache_dir: Path,
    refresh: bool,
    warnings: list[str],
) -> list[str]:
    cache = cache_dir / "pypi-simple-names.json.gz"
    if cache.is_file() and not refresh and time.time() - cache.stat().st_mtime <= _CACHE_MAX_AGE:
        try:
            with gzip.open(cache, "rt", encoding="utf-8") as handle:
                values = json.load(handle)
            if isinstance(values, list):
                return [str(value) for value in values]
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"PyPI name cache unreadable; refreshing: {exc}")
    payload = client.request(
        _PYPI_SIMPLE,
        headers={"Accept": "application/vnd.pypi.simple.v1+html"},
        max_bytes=50_000_000,
    )
    parser = _SimpleNamesParser()
    try:
        parser.feed(payload.body.decode("utf-8"))
        parser.close()
    except (UnicodeDecodeError, ValueError) as exc:
        raise DiscoverySourceError(f"PyPI Simple index could not be parsed: {exc}") from exc
    if not parser.names:
        raise DiscoverySourceError("PyPI Simple index contained no package names")
    temporary: str | None = None
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".pypi-names.", suffix=".tmp", dir=cache_dir)
        os.close(descriptor)
        with gzip.open(temporary, "wt", encoding="utf-8") as handle:
            json.dump(parser.names, handle, ensure_ascii=False, separators=(",", ":"))
        os.replace(temporary, cache)
        temporary = None
    except OSError as exc:
        warnings.append(f"PyPI cache write skipped: {exc}")
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass
    return parser.names


def _name_fit(query: str, name: str) -> tuple[int, int, str]:
    query_tokens = tokenize(query)
    name_tokens = tokenize(name.replace("-", " "))
    overlap = len(query_tokens & name_tokens)
    all_match = int(bool(query_tokens) and query_tokens <= name_tokens)
    return all_match, overlap, name.lower()


def _pypi_repository(info: dict[str, Any]) -> str | None:
    project_urls = info.get("project_urls") or {}
    if isinstance(project_urls, dict):
        prioritized = sorted(
            project_urls.items(),
            key=lambda item: (0 if any(word in str(item[0]).lower() for word in ("source", "repository", "github")) else 1, str(item[0])),
        )
        for _, value in prioritized:
            repository = canonical_repository_url(str(value))
            if repository:
                return repository
    return canonical_repository_url(info.get("home_page"))


def _pypi_runtime_dependency_count(requires: object) -> int | None:
    if not isinstance(requires, list):
        return None
    return sum(
        1
        for value in requires
        if isinstance(value, str) and "extra ==" not in value.lower()
    )


def search_pypi(
    query: str,
    limit: int,
    client: DiscoveryHttpClient,
    *,
    cache_dir: Path,
    refresh: bool = False,
) -> tuple[list[Candidate], SourceReceipt]:
    receipt = SourceReceipt("pypi", "ok", limit, endpoints=[_PYPI_SIMPLE])
    try:
        names = _load_pypi_names(client, cache_dir, refresh, receipt.warnings)
        matched_names: list[tuple[tuple[int, int, str], str]] = []
        for name in names:
            fit = _name_fit(query, name)
            if fit[1] > 0:
                matched_names.append((fit, name))
        ranked_names = [
            name
            for _, name in sorted(
                matched_names,
                key=lambda item: (-item[0][0], -item[0][1], item[0][2]),
            )
        ]
        candidates: list[Candidate] = []
        for name in ranked_names[: max(limit * 3, limit)]:
            endpoint = f"https://pypi.org/pypi/{quote(name, safe='')}/json"
            try:
                data, _ = client.get_json(endpoint, max_bytes=3_000_000)
            except DiscoverySourceError as exc:
                receipt.warnings.append(f"{name}: {exc}")
                continue
            if not isinstance(data, dict) or not isinstance(data.get("info"), dict):
                continue
            info = data["info"]
            requires = info.get("requires_dist") or []
            releases = data.get("releases") or {}
            version = str(info.get("version") or "") or None
            upload_time = None
            if version and isinstance(releases, dict):
                files = releases.get(version) or []
                if files and isinstance(files[0], dict):
                    upload_time = files[0].get("upload_time_iso_8601")
            candidates.append(
                Candidate(
                    source="pypi",
                    name=str(info.get("name") or name),
                    url=str(info.get("package_url") or f"https://pypi.org/project/{name}/"),
                    repository_url=_pypi_repository(info),
                    description=str(info.get("summary") or ""),
                    version=version,
                    license=str(info.get("license_expression") or info.get("license") or "") or None,
                    updated_at=upload_time,
                    published_at=upload_time,
                    language="Python",
                    topics=[str(value) for value in info.get("keywords") or []] if isinstance(info.get("keywords"), list) else str(info.get("keywords") or "").split(),
                    dependency_count=_pypi_runtime_dependency_count(requires),
                    reuse_signals=["package metadata", "installable package"],
                )
            )
            receipt.endpoints.append(endpoint)
            if len(candidates) >= limit:
                break
        receipt.returned = len(candidates)
        if not candidates:
            receipt.status = "failed"
            receipt.error = "PyPI name search produced no inspectable candidates"
        return candidates, receipt
    except DiscoverySourceError as exc:
        receipt.status = "failed"
        receipt.error = str(exc)
        return [], receipt


def search_npm(query: str, limit: int, client: DiscoveryHttpClient) -> tuple[list[Candidate], SourceReceipt]:
    endpoint = f"https://registry.npmjs.org/-/v1/search?{urlencode({'text': query, 'size': limit})}"
    receipt = SourceReceipt("npm", "ok", limit, endpoints=[endpoint])
    try:
        data, _ = client.get_json(endpoint)
        objects = data.get("objects") if isinstance(data, dict) else None
        if not isinstance(objects, list):
            raise DiscoverySourceError("npm response had no objects")
        candidates: list[Candidate] = []
        for entry in objects:
            package = entry.get("package") if isinstance(entry, dict) else None
            if not isinstance(package, dict):
                continue
            name = str(package.get("name") or "")
            detail_url = f"https://registry.npmjs.org/{quote(name, safe='')}"
            detail: dict[str, Any] = {}
            try:
                detail_data, _ = client.get_json(detail_url, max_bytes=8_000_000)
                if isinstance(detail_data, dict):
                    detail = detail_data
                receipt.endpoints.append(detail_url)
            except DiscoverySourceError as exc:
                receipt.warnings.append(f"{name}: {exc}")
            version = str(package.get("version") or "") or None
            version_data = (detail.get("versions") or {}).get(version, {}) if version else {}
            dependencies = version_data.get("dependencies") or {}
            dev_dependencies = version_data.get("devDependencies") or {}
            scripts = version_data.get("scripts") or {}
            deprecation_reason = str(version_data.get("deprecated") or detail.get("deprecated") or "")
            links = package.get("links") or {}
            repository = _repository_from_mapping(version_data.get("repository")) or canonical_repository_url(links.get("repository"))
            score_data = entry.get("score") or {}
            candidates.append(
                Candidate(
                    source="npm",
                    name=name,
                    url=str(links.get("npm") or f"https://www.npmjs.com/package/{name}"),
                    repository_url=repository,
                    description=str(package.get("description") or ""),
                    version=version,
                    license=str(version_data.get("license") or detail.get("license") or "") or None,
                    updated_at=package.get("date"),
                    downloads=int(((entry.get("downloads") or {}).get("monthly") or (entry.get("downloads") or {}).get("weekly") or 0)) if isinstance(entry.get("downloads") or {}, dict) else None,
                    language="JavaScript",
                    dependency_count=len(dependencies) if isinstance(dependencies, dict) else None,
                    test_signals=(
                        ["npm test script", f"development dependencies={len(dev_dependencies)}"]
                        if isinstance(scripts, dict) and scripts.get("test") and isinstance(dev_dependencies, dict)
                        else []
                    ),
                    deprecated=bool(deprecation_reason),
                    deprecation_reason=deprecation_reason or None,
                    raw_relevance=float(score_data.get("final") or 0),
                    reuse_signals=["package metadata", "installable package"],
                )
            )
        receipt.returned = len(candidates)
        return candidates, receipt
    except DiscoverySourceError as exc:
        receipt.status = "failed"
        receipt.error = str(exc)
        return [], receipt


def search_crates(query: str, limit: int, client: DiscoveryHttpClient) -> tuple[list[Candidate], SourceReceipt]:
    endpoint = f"https://crates.io/api/v1/crates?{urlencode({'q': query, 'sort': 'relevance', 'per_page': limit, 'page': 1})}"
    receipt = SourceReceipt("crates", "ok", limit, endpoints=[endpoint])
    try:
        data, _ = client.get_json(endpoint)
        crates = data.get("crates") if isinstance(data, dict) else None
        if not isinstance(crates, list):
            raise DiscoverySourceError("crates.io response had no crates")
        candidates: list[Candidate] = []
        for item in crates:
            if not isinstance(item, dict):
                continue
            name = str(item.get("id") or item.get("name") or "")
            version = str(item.get("max_stable_version") or item.get("newest_version") or "") or None
            dependency_count = None
            if version:
                dependency_url = f"https://crates.io/api/v1/crates/{quote(name, safe='')}/{quote(version, safe='')}/dependencies"
                try:
                    dependency_data, _ = client.get_json(dependency_url)
                    dependencies = dependency_data.get("dependencies") if isinstance(dependency_data, dict) else None
                    dependency_count = (
                        sum(
                            1
                            for dependency in dependencies
                            if isinstance(dependency, dict)
                            and dependency.get("kind") in {None, "normal"}
                            and not dependency.get("optional")
                        )
                        if isinstance(dependencies, list)
                        else None
                    )
                    receipt.endpoints.append(dependency_url)
                except DiscoverySourceError as exc:
                    receipt.warnings.append(f"{name}: {exc}")
            candidates.append(
                Candidate(
                    source="crates",
                    name=name,
                    url=f"https://crates.io/crates/{name}",
                    repository_url=canonical_repository_url(item.get("repository")),
                    description=str(item.get("description") or ""),
                    version=version,
                    license=str(item.get("license") or "") or None,
                    updated_at=item.get("updated_at"),
                    published_at=item.get("created_at"),
                    downloads=int(item.get("downloads") or 0),
                    language="Rust",
                    dependency_count=dependency_count,
                    deprecated=bool(item.get("yanked")),
                    deprecation_reason="crate is yanked" if item.get("yanked") else None,
                    reuse_signals=["crate metadata", "installable package"],
                )
            )
        receipt.returned = len(candidates)
        return candidates, receipt
    except DiscoverySourceError as exc:
        receipt.status = "failed"
        receipt.error = str(exc)
        return [], receipt


def _hf_license(item: dict[str, Any]) -> str | None:
    card = item.get("cardData") or {}
    if isinstance(card, dict) and card.get("license"):
        return str(card["license"])
    for tag in item.get("tags") or []:
        if str(tag).startswith("license:"):
            return str(tag).split(":", 1)[1]
    return None


def search_huggingface(query: str, limit: int, client: DiscoveryHttpClient) -> tuple[list[Candidate], SourceReceipt]:
    receipt = SourceReceipt("huggingface", "ok", limit)
    candidates_by_kind: list[list[Candidate]] = []
    per_kind = max(1, math.ceil(limit / 3))
    for kind, plural in (("model", "models"), ("dataset", "datasets"), ("space", "spaces")):
        kind_candidates: list[Candidate] = []
        endpoint = f"https://huggingface.co/api/{plural}?{urlencode({'search': query, 'limit': per_kind, 'full': 'true'})}"
        receipt.endpoints.append(endpoint)
        try:
            data, payload = client.get_json(endpoint, max_bytes=8_000_000)
        except DiscoverySourceError as exc:
            receipt.warnings.append(f"{kind}: {exc}")
            candidates_by_kind.append(kind_candidates)
            continue
        remaining = _rate_limit_remaining(payload.headers)
        if remaining is not None:
            receipt.rate_limit_remaining = (
                remaining
                if receipt.rate_limit_remaining is None
                else min(receipt.rate_limit_remaining, remaining)
            )
        if not isinstance(data, list):
            receipt.warnings.append(f"{kind}: response was not a list")
            candidates_by_kind.append(kind_candidates)
            continue
        for position, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            if item.get("private"):
                receipt.warnings.append(f"{kind}: filtered private result")
                continue
            identifier = str(item.get("id") or "")
            tags = [str(value) for value in item.get("tags") or []]
            kind_candidates.append(
                Candidate(
                    source="huggingface",
                    name=identifier,
                    url=f"https://huggingface.co/{'datasets/' if kind == 'dataset' else 'spaces/' if kind == 'space' else ''}{identifier}",
                    repository_url=None,
                    description=str((item.get("cardData") or {}).get("summary") or item.get("pipeline_tag") or ""),
                    license=_hf_license(item),
                    updated_at=item.get("lastModified") or item.get("last_modified"),
                    downloads=int(item.get("downloads") or 0),
                    stars=int(item.get("likes") or 0),
                    language=str(item.get("library_name") or "") or None,
                    topics=tags + [kind],
                    reuse_signals=[f"Hugging Face {kind}", "downloadable artifact"],
                    aliases=[f"huggingface:{kind}"],
                    raw_relevance=round(1.0 / (position + 1), 6),
                    gated=item.get("gated") not in {None, False, "false"},
                    disabled=bool(item.get("disabled")),
                )
            )
        candidates_by_kind.append(kind_candidates)
    candidates = [
        group[index]
        for index in range(per_kind)
        for group in candidates_by_kind
        if index < len(group)
    ][:limit]
    receipt.returned = len(candidates)
    if not candidates and receipt.warnings:
        receipt.status = "failed"
        receipt.error = "all Hugging Face endpoints failed"
    return candidates, receipt


def enrich_osv(candidate: Candidate, client: DiscoveryHttpClient) -> str | None:
    ecosystem_map = {"pypi": "PyPI", "npm": "npm", "crates": "crates.io"}
    ecosystem = ecosystem_map.get(candidate.source)
    if not ecosystem or not candidate.version:
        return "OSV does not have an exact package-version query for this candidate"
    body = {"package": {"ecosystem": ecosystem, "name": candidate.name}, "version": candidate.version}
    try:
        data, _ = client.post_json(_OSV_API, body)
    except DiscoverySourceError as exc:
        return str(exc)
    if not isinstance(data, dict):
        return "OSV response was not an object"
    vulnerabilities = data.get("vulns")
    if vulnerabilities is not None and not isinstance(vulnerabilities, list):
        return "OSV vulnerabilities field was not a list"
    candidate.vulnerabilities_checked = True
    candidate.vulnerabilities = sorted(
        str(item.get("id")) for item in (vulnerabilities or []) if isinstance(item, dict) and item.get("id")
    )
    candidate.vulnerability_evidence = sorted(
        (
            {
                "id": str(item.get("id")),
                "summary": str(item.get("summary") or ""),
                "modified": item.get("modified"),
                "aliases": sorted(str(value) for value in item.get("aliases") or []),
                "severity": item.get("severity") or [],
                "database_specific_severity": (
                    item.get("database_specific") or {}
                ).get("severity")
                if isinstance(item.get("database_specific") or {}, dict)
                else None,
            }
            for item in (vulnerabilities or [])
            if isinstance(item, dict) and item.get("id")
        ),
        key=lambda item: item["id"],
    )
    return None


PROVIDERS = {
    "github": search_github,
    "npm": search_npm,
    "crates": search_crates,
    "huggingface": search_huggingface,
}
