"""Compose safety, robots, fetch, extraction, and provenance."""

from __future__ import annotations

import urllib.request

from .extract import extract_content
from .fetch import RobotsDocument, evaluate_robots, fetch_page, fetch_robots_document
from .models import RobotsPolicy, ScrapeConfig, ScrapeResult
from .safety import origin, validate_url


class Scraper:
    def __init__(
        self,
        config: ScrapeConfig | None = None,
        *,
        opener: urllib.request.OpenerDirector | None = None,
    ) -> None:
        self.config = config or ScrapeConfig()
        self.config.validate()
        self.opener = opener
        self._robots: dict[tuple[str, str, int], RobotsDocument] = {}

    def robots_for(self, url: str) -> RobotsPolicy:
        target = validate_url(url, allow_private=self.config.allow_private)
        key = origin(target)
        if key not in self._robots:
            self._robots[key] = fetch_robots_document(
                target,
                config=self.config,
                opener=self.opener,
            )
        return evaluate_robots(self._robots[key], target, config=self.config)

    def scrape(self, url: str) -> ScrapeResult:
        target = validate_url(url, allow_private=self.config.allow_private)
        robots = self.robots_for(target)
        fetched = fetch_page(
            target,
            config=self.config,
            robots=robots,
            opener=self.opener,
        )
        extracted = extract_content(fetched, self.config.extractor)
        warnings = [*fetched.warnings, *extracted.warnings]
        return ScrapeResult(
            requested_url=fetched.requested_url,
            final_url=fetched.final_url,
            fetched_at=fetched.fetched_at,
            status_code=fetched.status_code,
            content_type=fetched.content_type,
            title=extracted.title,
            text=extracted.text,
            links=list(extracted.links),
            extractor=extracted.extractor,
            bytes_read=fetched.bytes_read,
            sha256=fetched.sha256,
            robots_url=robots.robots_url,
            robots_allowed=robots.allowed,
            crawl_delay=robots.crawl_delay,
            warnings=warnings,
        )


def scrape_url(url: str, config: ScrapeConfig | None = None) -> ScrapeResult:
    return Scraper(config).scrape(url)
