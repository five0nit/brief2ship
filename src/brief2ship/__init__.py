"""Brief2Ship public package."""

__version__ = "0.7.0"

from .discovery import discover
from .discovery_models import Candidate, DiscoveryConfig, DiscoveryResult
from .models import ScrapeConfig, ScrapeResult
from .scrape import Scraper, scrape_url

__all__ = [
    "Candidate",
    "DiscoveryConfig",
    "DiscoveryResult",
    "ScrapeConfig",
    "ScrapeResult",
    "Scraper",
    "discover",
    "scrape_url",
    "__version__",
]
