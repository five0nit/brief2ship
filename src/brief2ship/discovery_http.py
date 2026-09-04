"""Bounded HTTP client for fixed public discovery APIs."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .errors import Brief2ShipError


class DiscoverySourceError(Brief2ShipError):
    """A discovery source failed without invalidating other sources."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


@dataclass(frozen=True)
class HttpPayload:
    status: int
    final_url: str
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DiscoverySourceError(f"source returned invalid JSON: {exc}") from exc


class DiscoveryHttpClient:
    def __init__(
        self,
        *,
        timeout: float = 20.0,
        total_timeout: float | None = None,
        github_token: str | None = None,
        user_agent: str = "Brief2ShipBot/0.6.2 (+https://github.com/five0nit/brief2ship)",
    ) -> None:
        self.timeout = timeout
        self._expires_at = time.monotonic() + total_timeout if total_timeout is not None else None
        self.github_token = github_token
        self.user_agent = user_agent
        self._opener = urllib.request.build_opener(_NoRedirect)
        self._last_request: dict[str, float] = {}
        self._pace_lock = threading.Lock()

    def _pace(self, url: str) -> None:
        host = (urlsplit(url).hostname or "").lower()
        interval = 1.0 if host == "crates.io" else 0.0
        if not interval:
            return
        with self._pace_lock:
            wait = interval - (time.monotonic() - self._last_request.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            self._last_request[host] = time.monotonic()

    def _headers(self, url: str, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"User-Agent": self.user_agent, "Accept-Encoding": "identity"}
        if urlsplit(url).hostname == "api.github.com" and self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
        if extra:
            headers.update(extra)
        if urlsplit(url).hostname != "api.github.com":
            for key in list(headers):
                if key.lower() == "authorization":
                    del headers[key]
        return headers

    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        json_body: Any | None = None,
        headers: dict[str, str] | None = None,
        max_bytes: int = 5_000_000,
        allowed_statuses: tuple[int, ...] = (200,),
    ) -> HttpPayload:
        data = None
        merged = self._headers(url, headers)
        if json_body is not None:
            data = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            merged["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=merged, method=method)
        self._pace(url)
        now = time.monotonic()
        remaining = self._expires_at - now if self._expires_at is not None else self.timeout
        if remaining <= 0:
            raise DiscoverySourceError("overall discovery network budget exhausted")
        request_timeout = min(self.timeout, remaining)
        deadline = now + request_timeout
        try:
            response = self._opener.open(request, timeout=request_timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DiscoverySourceError(f"request failed for {url}: {exc}") from exc
        try:
            raw_status = getattr(response, "status", None) or response.getcode()
            if raw_status is None:
                raise DiscoverySourceError(f"source returned no HTTP status for {url}")
            status = int(raw_status)
            if status not in allowed_statuses:
                raise DiscoverySourceError(f"HTTP {status} from {url}")
            raw_length = response.headers.get("Content-Length")
            if raw_length:
                try:
                    if int(raw_length) > max_bytes:
                        raise DiscoverySourceError(
                            f"source declared {raw_length} bytes; cap is {max_bytes}"
                        )
                except ValueError:
                    pass
            chunks: list[bytes] = []
            total = 0
            reader = getattr(response, "read1", None) or response.read
            while total <= max_bytes:
                if time.monotonic() >= deadline:
                    raise DiscoverySourceError(f"request exceeded total timeout for {url}")
                try:
                    chunk = reader(min(65_536, max_bytes + 1 - total))
                except (TimeoutError, OSError) as exc:
                    raise DiscoverySourceError(f"response read failed for {url}: {exc}") from exc
                if time.monotonic() >= deadline:
                    raise DiscoverySourceError(f"request exceeded total timeout for {url}")
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            if total > max_bytes:
                raise DiscoverySourceError(f"source exceeded byte cap of {max_bytes}")
            return HttpPayload(
                status=status,
                final_url=getattr(response, "url", None) or url,
                headers={key.lower(): value for key, value in response.headers.items()},
                body=b"".join(chunks),
            )
        finally:
            response.close()

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        max_bytes: int = 5_000_000,
    ) -> tuple[Any, HttpPayload]:
        payload = self.request(url, headers=headers, max_bytes=max_bytes)
        return payload.json(), payload

    def post_json(
        self,
        url: str,
        body: Any,
        *,
        max_bytes: int = 5_000_000,
    ) -> tuple[Any, HttpPayload]:
        payload = self.request(url, method="POST", json_body=body, max_bytes=max_bytes)
        return payload.json(), payload
