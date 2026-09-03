"""Respectful robots checks and bounded HTTP fetching."""

from __future__ import annotations

import hashlib
import http.client
import re
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from urllib.parse import urljoin, urlsplit, urlunsplit

from .errors import FetchError, PolicyError, RobotsDenied, RobotsUnavailable
from .models import FetchResult, RobotsPolicy, ScrapeConfig
from .safety import SocketTarget, origin, resolve_url_addresses, validate_url

_ROBOTS_MAX_BYTES = 256_000
_PAGE_CONTENT_TYPES = {"text/html", "application/xhtml+xml", "text/plain"}
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def _normalize_robots_value(value: str) -> str:
    """Normalize percent encodings as required for robots path comparison."""

    def replace(match: re.Match[str]) -> str:
        octet = int(match.group(1), 16)
        character = chr(octet)
        if character in _UNRESERVED:
            return character
        return f"%{octet:02X}"

    return re.sub(r"%([0-9A-Fa-f]{2})", replace, value)


def _robots_specificity(pattern: str) -> int:
    source = pattern.removesuffix("$").replace("*", "")
    octets = re.sub(r"%[0-9A-F]{2}", "x", source)
    return len(octets.encode("utf-8"))


def _robots_pattern_matches(pattern: str, target: str) -> bool:
    pattern = _normalize_robots_value(pattern)
    target = _normalize_robots_value(target)
    anchored = pattern.endswith("$")
    source = pattern[:-1] if anchored else pattern
    expression = "^" + re.escape(source).replace(r"\*", ".*")
    if anchored:
        expression += "$"
    return re.search(expression, target) is not None


def _parse_robots(text: str, user_agent: str, target_url: str) -> tuple[bool, float | None]:
    """Parse the small RFC 9309 subset required by the safe fetcher.

    Python's RobotFileParser uses first-match rule order; RFC 9309 requires
    the most specific matching path. This parser keeps the conservative,
    deterministic subset we need: user-agent groups, allow/disallow,
    wildcards, end anchors, and crawl-delay.
    """

    groups: list[dict[str, object]] = []
    agents: list[str] = []
    rules: list[tuple[bool, str]] = []
    delay: float | None = None

    def finish_group() -> None:
        nonlocal agents, rules, delay
        if agents:
            groups.append({"agents": agents, "rules": rules, "delay": delay})
        agents, rules, delay = [], [], None

    saw_directive = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if rules or delay is not None:
                finish_group()
            if value:
                agents.append(value.lower())
                saw_directive = True
        elif field in {"allow", "disallow"} and agents:
            if value:
                rules.append((field == "allow", value))
            saw_directive = True
        elif field == "crawl-delay" and agents:
            try:
                parsed = float(value)
            except ValueError:
                parsed = None
            if parsed is not None and 0 <= parsed <= 3600:
                delay = parsed
            saw_directive = True
    finish_group()

    if text.strip() and not groups and saw_directive:
        raise ValueError("robots directives had no valid user-agent group")
    if text.strip() and not groups and any(char.isalpha() for char in text):
        raise ValueError("robots.txt contained no valid user-agent group")

    product_token = user_agent.split(None, 1)[0].split("/", 1)[0].lower()
    candidates: list[tuple[int, dict[str, object]]] = []
    for group in groups:
        scores = [
            0 if token == "*" else len(token)
            for token in group["agents"]  # type: ignore[union-attr]
            if token == "*" or token == product_token
        ]
        if scores:
            candidates.append((max(scores), group))
    if not candidates:
        return True, None
    best_score = max(score for score, _ in candidates)
    selected = [group for score, group in candidates if score == best_score]

    parts = urlsplit(target_url)
    target = parts.path or "/"
    if parts.query:
        target += "?" + parts.query
    matches: list[tuple[int, bool]] = []
    delays: list[float] = []
    for group in selected:
        group_delay = group["delay"]
        if isinstance(group_delay, (int, float)):
            delays.append(float(group_delay))
        for allowed, pattern in group["rules"]:  # type: ignore[assignment]
            if _robots_pattern_matches(pattern, target):
                specificity = _robots_specificity(_normalize_robots_value(pattern))
                matches.append((specificity, allowed))
    allowed = True
    if matches:
        longest = max(length for length, _ in matches)
        allowed = any(rule_allowed for length, rule_allowed in matches if length == longest)
    return allowed, max(delays) if delays else None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _connect_resolved(
    targets: tuple[SocketTarget, ...],
    timeout: object,
    source_address: tuple[str, int] | None,
) -> socket.socket:
    deadline = (
        time.monotonic() + float(timeout)
        if isinstance(timeout, (int, float)) and timeout > 0
        else None
    )
    last_error: OSError | None = None
    for family, socktype, protocol, sockaddr in targets:
        connection = socket.socket(family, socktype, protocol)
        try:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("resolved-address connection timed out")
                connection.settimeout(remaining)
            elif timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:  # type: ignore[attr-defined]
                connection.settimeout(timeout)  # type: ignore[arg-type]
            if source_address:
                connection.bind(source_address)
            connection.connect(sockaddr)
            return connection
        except OSError as exc:
            last_error = exc
            connection.close()
    if last_error is not None:
        raise last_error
    raise OSError("no resolved socket target was available")


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, *, targets: tuple[SocketTarget, ...], **kwargs) -> None:
        super().__init__(host, **kwargs)
        self._pinned_targets = targets
        self._create_connection = self._create_pinned_connection

    def _create_pinned_connection(
        self,
        address: tuple[str, int],  # noqa: ARG002
        timeout: object = socket._GLOBAL_DEFAULT_TIMEOUT,  # type: ignore[attr-defined]
        source_address: tuple[str, int] | None = None,
    ) -> socket.socket:
        return _connect_resolved(self._pinned_targets, timeout, source_address)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, *, targets: tuple[SocketTarget, ...], **kwargs) -> None:
        super().__init__(host, **kwargs)
        self._pinned_targets = targets
        self._create_connection = self._create_pinned_connection

    def _create_pinned_connection(
        self,
        address: tuple[str, int],  # noqa: ARG002
        timeout: object = socket._GLOBAL_DEFAULT_TIMEOUT,  # type: ignore[attr-defined]
        source_address: tuple[str, int] | None = None,
    ) -> socket.socket:
        return _connect_resolved(self._pinned_targets, timeout, source_address)


class _PinnedHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, targets: tuple[SocketTarget, ...]) -> None:
        super().__init__()
        self.targets = targets

    def http_open(self, req):  # noqa: ANN001
        def connection(host: str, **kwargs) -> _PinnedHTTPConnection:
            return _PinnedHTTPConnection(host, targets=self.targets, **kwargs)

        return self.do_open(connection, req)


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, targets: tuple[SocketTarget, ...]) -> None:
        super().__init__()
        self.targets = targets

    def https_open(self, req):  # noqa: ANN001
        def connection(host: str, **kwargs) -> _PinnedHTTPSConnection:
            return _PinnedHTTPSConnection(host, targets=self.targets, **kwargs)

        return self.do_open(
            connection,
            req,
            context=getattr(self, "_context", None),
            check_hostname=getattr(self, "_check_hostname", None),
        )


def _pinned_opener(url: str, *, allow_private: bool) -> urllib.request.OpenerDirector:
    _, targets = resolve_url_addresses(url, allow_private=allow_private)
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _NoRedirect(),
        _PinnedHTTPHandler(targets),
        _PinnedHTTPSHandler(targets),
    )


@dataclass(frozen=True)
class _RawResponse:
    status_code: int
    final_url: str
    headers: Message
    body: bytes
    content_type: str
    charset: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RobotsDocument:
    robots_url: str
    status_code: int
    text: str
    warning: str | None = None


def _open_once(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    config: ScrapeConfig,
    timeout: float,
):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": config.user_agent,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
            "Accept-Encoding": "identity",
        },
        method="GET",
    )
    try:
        return opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        return exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FetchError(f"request failed for {url}: {exc}") from exc


def _read_limited(response, max_bytes: int, deadline: float) -> bytes:  # noqa: ANN001
    raw_length = response.headers.get("Content-Length")
    if raw_length:
        try:
            declared = int(raw_length)
        except ValueError:
            declared = None
        if declared is not None and declared > max_bytes:
            raise FetchError(f"response declares {declared} bytes; limit is {max_bytes}")
    chunks: list[bytes] = []
    total = 0
    reader = getattr(response, "read1", None) or response.read
    while total <= max_bytes:
        if time.monotonic() >= deadline:
            raise FetchError("request exceeded total timeout while reading response body")
        try:
            chunk = reader(min(65_536, max_bytes + 1 - total))
        except (TimeoutError, OSError) as exc:
            raise FetchError(f"response body read failed: {exc}") from exc
        if time.monotonic() >= deadline:
            raise FetchError("request exceeded total timeout while reading response body")
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    if total > max_bytes:
        raise FetchError(f"response exceeded byte limit of {max_bytes}")
    return b"".join(chunks)


def _header_metadata(headers: Message) -> tuple[str, str, tuple[str, ...]]:
    content_type = headers.get_content_type().lower() if headers else "application/octet-stream"
    charset = headers.get_content_charset() if headers else None
    warnings: list[str] = []
    if not charset:
        charset = "utf-8"
        warnings.append("response charset missing; decoded as utf-8 with replacement")
    return content_type, charset, tuple(warnings)


def _request_bytes(
    url: str,
    *,
    config: ScrapeConfig,
    max_bytes: int,
    opener: urllib.request.OpenerDirector | None = None,
    permit_error_status: bool = False,
    redirect_guard: Callable[[str, str], None] | None = None,
) -> _RawResponse:
    deadline = time.monotonic() + config.timeout
    current = validate_url(url, allow_private=config.allow_private)
    if time.monotonic() >= deadline:
        raise FetchError("request exceeded total timeout during URL validation")
    for redirect_count in range(config.max_redirects + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FetchError("request exceeded total timeout")
        active_opener = opener or _pinned_opener(
            current,
            allow_private=config.allow_private,
        )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FetchError("request exceeded total timeout during DNS validation")
        response = _open_once(
            active_opener,
            current,
            config=config,
            timeout=remaining,
        )
        try:
            raw_status = getattr(response, "status", None) or response.getcode()
            if raw_status is None:
                raise FetchError(f"response from {current} had no HTTP status")
            status = int(raw_status)
            if status in _REDIRECT_CODES:
                location = response.headers.get("Location")
                if not location:
                    raise FetchError(f"redirect response from {current} has no Location header")
                if redirect_count >= config.max_redirects:
                    raise FetchError(f"redirect limit exceeded ({config.max_redirects})")
                next_url = validate_url(urljoin(current, location), allow_private=config.allow_private)
                if redirect_guard is not None:
                    redirect_guard(current, next_url)
                current = next_url
                continue
            content_type, charset, warnings = _header_metadata(response.headers)
            if not 200 <= status < 300 and not permit_error_status:
                raise FetchError(f"HTTP {status} for {current}")
            body = _read_limited(response, max_bytes, deadline)
            final_url = validate_url(
                getattr(response, "url", None) or current,
                allow_private=config.allow_private,
            )
            return _RawResponse(
                status_code=status,
                final_url=final_url,
                headers=response.headers,
                body=body,
                content_type=content_type,
                charset=charset,
                warnings=warnings,
            )
        finally:
            response.close()
    raise FetchError(f"redirect limit exceeded ({config.max_redirects})")


def robots_url_for(url: str) -> str:
    parts = urlsplit(validate_url(url, allow_private=True))
    return urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))


def fetch_robots_document(
    url: str,
    *,
    config: ScrapeConfig,
    opener: urllib.request.OpenerDirector | None = None,
) -> RobotsDocument:
    target = validate_url(url, allow_private=config.allow_private)
    robots_url = validate_url(robots_url_for(target), allow_private=config.allow_private)
    try:
        response = _request_bytes(
            robots_url,
            config=config,
            max_bytes=min(config.max_bytes, _ROBOTS_MAX_BYTES),
            opener=opener,
            permit_error_status=True,
        )
    except FetchError as exc:
        raise RobotsUnavailable(f"robots.txt check failed closed: {exc}") from exc

    if response.status_code in {404, 410}:
        return RobotsDocument(robots_url, response.status_code, "", "robots.txt absent")
    if response.status_code in {401, 403}:
        raise RobotsDenied(f"robots.txt access denied with HTTP {response.status_code}")
    if not 200 <= response.status_code < 300:
        raise RobotsUnavailable(
            f"robots.txt returned HTTP {response.status_code}; refusing page fetch"
        )
    try:
        text = response.body.decode(response.charset, errors="replace")
        _parse_robots(text, config.user_agent, target)
    except Exception as exc:
        raise RobotsUnavailable(f"robots.txt could not be parsed safely: {exc}") from exc
    return RobotsDocument(robots_url, response.status_code, text)


def evaluate_robots(
    document: RobotsDocument,
    url: str,
    *,
    config: ScrapeConfig,
) -> RobotsPolicy:
    target = validate_url(url, allow_private=config.allow_private)
    try:
        allowed, delay = _parse_robots(document.text, config.user_agent, target)
    except Exception as exc:
        raise RobotsUnavailable(f"robots.txt could not be parsed safely: {exc}") from exc
    if not allowed:
        raise RobotsDenied(f"robots.txt disallows {target}")
    return RobotsPolicy(
        document.robots_url,
        True,
        float(delay) if delay is not None else None,
        document.status_code,
        document.warning,
        document.text,
    )


def check_robots(
    url: str,
    *,
    config: ScrapeConfig,
    opener: urllib.request.OpenerDirector | None = None,
) -> RobotsPolicy:
    document = fetch_robots_document(url, config=config, opener=opener)
    return evaluate_robots(document, url, config=config)


def fetch_page(
    url: str,
    *,
    config: ScrapeConfig,
    robots: RobotsPolicy | None = None,
    opener: urllib.request.OpenerDirector | None = None,
) -> FetchResult:
    config.validate()
    target = validate_url(url, allow_private=config.allow_private)
    policy = robots or check_robots(target, config=config, opener=opener)
    if not policy.allowed:
        raise RobotsDenied(f"robots.txt disallows {target}")

    def page_redirect_guard(current: str, next_url: str) -> None:
        if origin(current) != origin(next_url):
            raise PolicyError(
                "cross-origin page redirect blocked; scrape the final origin explicitly so its robots.txt is checked"
            )
        try:
            allowed, _ = _parse_robots(policy.rules_text, config.user_agent, next_url)
        except Exception as exc:
            raise RobotsUnavailable(f"robots.txt could not be re-evaluated for redirect: {exc}") from exc
        if not allowed:
            raise RobotsDenied(f"robots.txt disallows redirect target {next_url}")

    response = _request_bytes(
        target,
        config=config,
        max_bytes=config.max_bytes,
        opener=opener,
        redirect_guard=page_redirect_guard,
    )
    if response.content_type not in _PAGE_CONTENT_TYPES:
        raise FetchError(
            f"unsupported content type {response.content_type}; allowed: {', '.join(sorted(_PAGE_CONTENT_TYPES))}"
        )
    warnings = list(response.warnings)
    if policy.warning:
        warnings.append(policy.warning)
    return FetchResult(
        requested_url=target,
        final_url=response.final_url,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        status_code=response.status_code,
        content_type=response.content_type,
        charset=response.charset,
        body=response.body,
        bytes_read=len(response.body),
        sha256=hashlib.sha256(response.body).hexdigest(),
        robots=policy,
        warnings=tuple(warnings),
    )
