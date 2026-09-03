"""Small, same-origin, sequential crawl orchestration."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import urldefrag

from .errors import Brief2ShipError, PolicyError
from .models import CrawlFailure, CrawlResult, ScrapeConfig
from .safety import normalize_url, same_origin
from .scrape import Scraper

_MAX_PAGES_HARD = 20
_MAX_DEPTH_HARD = 3


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded_options(max_pages: int, max_depth: int) -> None:
    if not 1 <= max_pages <= _MAX_PAGES_HARD:
        raise PolicyError(f"max_pages must be between 1 and {_MAX_PAGES_HARD}")
    if not 0 <= max_depth <= _MAX_DEPTH_HARD:
        raise PolicyError(f"max_depth must be between 0 and {_MAX_DEPTH_HARD}")


def crawl_site(
    start_url: str,
    *,
    config: ScrapeConfig | None = None,
    max_pages: int = 5,
    max_depth: int = 1,
    sleep: Callable[[float], object] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    scraper: Scraper | None = None,
) -> CrawlResult:
    _bounded_options(max_pages, max_depth)
    active_config = config or ScrapeConfig()
    active_config.validate()
    worker = scraper or Scraper(active_config)
    start = normalize_url(start_url)
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    queued = {start}
    visited: set[str] = set()
    pages = []
    failures: list[CrawlFailure] = []
    started_at = _utc_now()
    last_request_at: float | None = None
    active_delay = active_config.min_delay
    attempts = 0

    while queue and attempts < max_pages:
        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        attempts += 1
        if last_request_at is not None:
            remaining = active_delay - (monotonic() - last_request_at)
            if remaining > 0:
                sleep(remaining)
        last_request_at = monotonic()
        try:
            page = worker.scrape(url)
            pages.append(page)
            if page.crawl_delay is not None:
                active_delay = max(active_delay, page.crawl_delay)
            if depth >= max_depth:
                continue
            for raw_link in page.links:
                normalized = normalize_url(urldefrag(raw_link)[0])
                if not same_origin(start, normalized):
                    continue
                if normalized not in queued and normalized not in visited:
                    queue.append((normalized, depth + 1))
                    queued.add(normalized)
        except Brief2ShipError as exc:
            failures.append(
                CrawlFailure(
                    url=url,
                    depth=depth,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )

    return CrawlResult(
        start_url=start,
        started_at=started_at,
        completed_at=_utc_now(),
        max_pages=max_pages,
        max_depth=max_depth,
        delay_seconds=active_delay,
        pages=pages,
        failures=failures,
    )
