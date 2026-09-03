"""URL normalization and default-deny network target policy."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import SplitResult, quote, urlsplit, urlunsplit

from .errors import PolicyError

Resolver = Callable[..., list[tuple]]
SocketTarget = tuple[int, int, int, tuple]
_ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_HOST_NAMES = {"localhost", "localhost.localdomain"}


def _effective_port(parts: SplitResult) -> int:
    try:
        if parts.port is not None:
            if parts.port < 1:
                raise PolicyError("URL port must be between 1 and 65535")
            return parts.port
    except ValueError as exc:
        raise PolicyError(f"invalid URL port: {exc}") from exc
    return 443 if parts.scheme.lower() == "https" else 80


def _is_safe_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError as exc:
        raise PolicyError(f"unparseable resolved address: {value}") from exc
    return bool(
        address.is_global
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_private
    )


def _host_is_locally_named(hostname: str) -> bool:
    host = hostname.rstrip(".").lower()
    return host in _BLOCKED_HOST_NAMES or host.endswith(".localhost") or host.endswith(".local")


def normalize_url(url: str) -> str:
    value = url.strip()
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise PolicyError(f"invalid URL: {exc}") from exc
    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise PolicyError("only http and https URLs are allowed")
    if not parts.hostname:
        raise PolicyError("URL must include a hostname")
    if parts.username is not None or parts.password is not None:
        raise PolicyError("credentials in URLs are not allowed")
    _effective_port(parts)
    hostname = parts.hostname.encode("idna").decode("ascii").lower()
    display_host = f"[{hostname}]" if ":" in hostname else hostname
    port = parts.port
    default_port = 443 if scheme == "https" else 80
    netloc = display_host if port in {None, default_port} else f"{display_host}:{port}"
    path = quote(parts.path or "/", safe="/:@-._~!$&'()*+,;=%")
    query = quote(parts.query, safe="/:?@-._~!$&'()*+,;=%")
    return urlunsplit((scheme, netloc, path, query, ""))


def validate_url(
    url: str,
    *,
    allow_private: bool = False,
    resolver: Resolver | None = None,
) -> str:
    active_resolver = resolver or socket.getaddrinfo
    normalized = normalize_url(url)
    parts = urlsplit(normalized)
    hostname = parts.hostname or ""
    if allow_private:
        return normalized
    if _host_is_locally_named(hostname):
        raise PolicyError(f"local hostname is blocked by default: {hostname}")
    try:
        literal = ipaddress.ip_address(hostname.split("%", 1)[0])
    except ValueError:
        literal = None
    if literal is not None:
        if not _is_safe_address(str(literal)):
            raise PolicyError(f"non-public address is blocked by default: {literal}")
        return normalized
    try:
        answers = active_resolver(
            hostname,
            _effective_port(parts),
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise PolicyError(f"DNS resolution failed for {hostname}: {exc}") from exc
    addresses = {
        str(answer[4][0])
        for answer in answers
        if answer and len(answer) >= 5
    }
    if not addresses:
        raise PolicyError(f"DNS resolution returned no addresses for {hostname}")
    unsafe = sorted(address for address in addresses if not _is_safe_address(address))
    if unsafe:
        raise PolicyError(f"hostname resolves to blocked address(es): {', '.join(unsafe)}")
    return normalized


def resolve_url_addresses(
    url: str,
    *,
    allow_private: bool = False,
    resolver: Resolver | None = None,
) -> tuple[str, tuple[SocketTarget, ...]]:
    """Resolve and revalidate the exact socket targets used by transport."""
    active_resolver = resolver or socket.getaddrinfo
    normalized = validate_url(
        url,
        allow_private=allow_private,
        resolver=active_resolver,
    )
    parts = urlsplit(normalized)
    hostname = parts.hostname or ""
    try:
        answers = active_resolver(
            hostname,
            _effective_port(parts),
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise PolicyError(f"DNS resolution failed for {hostname}: {exc}") from exc

    targets: list[SocketTarget] = []
    seen: set[SocketTarget] = set()
    for answer in answers:
        if not answer or len(answer) < 5:
            continue
        family, socktype, protocol, _, sockaddr = answer
        if not isinstance(sockaddr, tuple) or not sockaddr:
            continue
        address = str(sockaddr[0])
        if not allow_private and not _is_safe_address(address):
            raise PolicyError(f"hostname resolves to blocked address(es): {address}")
        target = (int(family), int(socktype), int(protocol), sockaddr)
        if target not in seen:
            seen.add(target)
            targets.append(target)
    if not targets:
        raise PolicyError(f"DNS resolution returned no socket targets for {hostname}")
    return normalized, tuple(targets)


def origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(normalize_url(url))
    return parts.scheme, parts.hostname or "", _effective_port(parts)


def same_origin(left: str, right: str) -> bool:
    return origin(left) == origin(right)
