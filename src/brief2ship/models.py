"""Stable data contracts for free scraping and crawl receipts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


DEFAULT_USER_AGENT = "Brief2ShipBot/0.7.0 (+https://github.com/five0nit/brief2ship)"


@dataclass(frozen=True)
class ScrapeConfig:
    timeout: float = 15.0
    max_bytes: int = 2_000_000
    max_redirects: int = 5
    user_agent: str = DEFAULT_USER_AGENT
    min_delay: float = 1.0
    allow_private: bool = False
    extractor: str = "auto"

    def validate(self) -> None:
        if not 0.1 <= self.timeout <= 120:
            raise ValueError("timeout must be between 0.1 and 120 seconds")
        if not 1_024 <= self.max_bytes <= 20_000_000:
            raise ValueError("max_bytes must be between 1024 and 20000000")
        if not 0 <= self.max_redirects <= 10:
            raise ValueError("max_redirects must be between 0 and 10")
        if not 0 <= self.min_delay <= 60:
            raise ValueError("min_delay must be between 0 and 60 seconds")
        if self.extractor not in {"auto", "stdlib", "trafilatura"}:
            raise ValueError("extractor must be auto, stdlib, or trafilatura")


@dataclass(frozen=True)
class RobotsPolicy:
    robots_url: str
    allowed: bool
    crawl_delay: float | None
    status_code: int
    warning: str | None = None
    rules_text: str = field(default="", repr=False, compare=False)


@dataclass(frozen=True)
class FetchResult:
    requested_url: str
    final_url: str
    fetched_at: str
    status_code: int
    content_type: str
    charset: str
    body: bytes
    bytes_read: int
    sha256: str
    robots: RobotsPolicy
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtractedContent:
    title: str
    text: str
    links: tuple[str, ...]
    extractor: str
    warnings: tuple[str, ...] = ()


@dataclass
class ScrapeResult:
    requested_url: str
    final_url: str
    fetched_at: str
    status_code: int
    content_type: str
    title: str
    text: str
    links: list[str]
    extractor: str
    bytes_read: int
    sha256: str
    robots_url: str
    robots_allowed: bool
    crawl_delay: float | None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CrawlFailure:
    url: str
    depth: int
    error_type: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CrawlResult:
    start_url: str
    started_at: str
    completed_at: str
    max_pages: int
    max_depth: int
    delay_seconds: float
    pages: list[ScrapeResult]
    failures: list[CrawlFailure]

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_url": self.start_url,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "max_pages": self.max_pages,
            "max_depth": self.max_depth,
            "delay_seconds": self.delay_seconds,
            "attempted_count": len(self.pages) + len(self.failures),
            "page_count": len(self.pages),
            "failure_count": len(self.failures),
            "pages": [page.to_dict() for page in self.pages],
            "failures": [failure.to_dict() for failure in self.failures],
        }
