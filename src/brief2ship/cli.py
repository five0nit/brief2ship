"""Brief2Ship command-line interface."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

from . import __version__
from .crawl import crawl_site
from .discovery import discover as discover_candidates
from .discovery_models import DiscoveryConfig
from .discovery_render import render_discovery_summary, write_discovery
from .errors import Brief2ShipError, OutputError, PolicyError
from .models import ScrapeConfig
from .render import atomic_write, render_result, write_crawl
from .scrape import scrape_url


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (LookupError, OSError, ValueError):
            continue


def _bounded_float(minimum: float, maximum: float):
    def parse(value: str) -> float:
        try:
            number = float(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be a number") from exc
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"must be between {minimum} and {maximum}")
        return number

    return parse


def _bounded_int(minimum: int, maximum: int):
    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be an integer") from exc
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"must be between {minimum} and {maximum}")
        return number

    return parse


def _add_fetch_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=_bounded_float(0.1, 120), default=15.0)
    parser.add_argument("--max-bytes", type=_bounded_int(1_024, 20_000_000), default=2_000_000)
    parser.add_argument("--max-redirects", type=_bounded_int(0, 10), default=5)
    parser.add_argument("--delay", type=_bounded_float(0, 60), default=1.0)
    parser.add_argument("--extractor", choices=("auto", "stdlib", "trafilatura"), default="auto")
    parser.add_argument(
        "--allow-private",
        action="store_true",
        help="allow localhost/private targets for explicit owner-authorized testing",
    )


def _sources(value: str) -> tuple[str, ...]:
    selected = tuple(dict.fromkeys(part.strip().lower() for part in value.split(",") if part.strip()))
    allowed = {"local", "github", "pypi", "npm", "crates", "huggingface"}
    invalid = sorted(set(selected) - allowed)
    if not selected or invalid:
        detail = f"; invalid: {', '.join(invalid)}" if invalid else ""
        raise argparse.ArgumentTypeError(
            f"sources must contain local,github,pypi,npm,crates,huggingface{detail}"
        )
    return selected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="brief2ship",
        description="Repo-first discovery, safe public research, and brief-to-proof workflow tools.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser(
        "doctor",
        help="show local discovery, scraping, and sandbox capabilities",
    )
    doctor.set_defaults(handler=_run_doctor)

    scrape = commands.add_parser("scrape", help="extract one public HTTP/HTTPS page")
    scrape.add_argument("url")
    scrape.add_argument("--format", choices=("json", "markdown", "text"), default="json")
    scrape.add_argument("--output", type=Path)
    _add_fetch_options(scrape)
    scrape.set_defaults(handler=_run_scrape)

    crawl = commands.add_parser("crawl", help="crawl a bounded same-origin public site")
    crawl.add_argument("url")
    crawl.add_argument("--output", type=Path, required=True)
    crawl.add_argument("--max-pages", type=_bounded_int(1, 20), default=5)
    crawl.add_argument("--max-depth", type=_bounded_int(0, 3), default=1)
    _add_fetch_options(crawl)
    crawl.set_defaults(handler=_run_crawl)

    discover = commands.add_parser(
        "discover",
        help="search, inspect, score, and recommend existing code before building",
    )
    discover.add_argument("query")
    discover.add_argument("--output", type=Path, required=True)
    discover.add_argument("--summary", action="store_true", help="print a concise JSON decision and source-health summary instead of only the receipt path")
    discover.add_argument(
        "--sources",
        type=_sources,
        default=("github", "pypi", "npm", "crates", "huggingface"),
        help="comma-separated: local,github,pypi,npm,crates,huggingface",
    )
    discover.add_argument("--per-source", type=_bounded_int(1, 20), default=10)
    discover.add_argument("--limit", type=_bounded_int(1, 100), default=10)
    discover.add_argument(
        "--local",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help="search a bounded local workspace; repeatable and automatically enables source=local",
    )
    discover.add_argument("--inspect-top", type=_bounded_int(0, 5), default=0)
    discover.add_argument("--test-top", type=_bounded_int(0, 3), default=0)
    discover.add_argument("--timeout", type=_bounded_float(1, 30), default=20.0)
    discover.add_argument(
        "--total-timeout",
        type=_bounded_float(10, 600),
        default=180.0,
        help="overall network budget in seconds across all selected sources",
    )
    discover.add_argument("--refresh-cache", action="store_true")
    discover.add_argument(
        "--allow-untrusted-tests",
        action="store_true",
        help="permit explicit no-network Bubblewrap execution for --test-top candidates",
    )
    discover.set_defaults(handler=_run_discover)
    return parser


def _config(args: argparse.Namespace) -> ScrapeConfig:
    return ScrapeConfig(
        timeout=args.timeout,
        max_bytes=args.max_bytes,
        max_redirects=args.max_redirects,
        min_delay=args.delay,
        allow_private=args.allow_private,
        extractor=args.extractor,
    )


def _run_doctor(args: argparse.Namespace) -> int:  # noqa: ARG001
    payload = {
        "brief2ship_version": __version__,
        "python": sys.version.split()[0],
        "trafilatura_available": importlib.util.find_spec("trafilatura") is not None,
        "paid_api_required": False,
        "default_private_network_policy": "blocked",
        "robots_policy": "required/fail-closed",
        "crawl_policy": "same-origin/sequential/max-20-pages/max-depth-3",
        "discovery_sources": ["local", "github", "pypi", "npm", "crates", "huggingface"],
        "github_token_available": bool(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")),
        "untrusted_test_policy": "explicit/bubblewrap/no-network/no-unsafe-fallback",
        "bubblewrap_available": shutil.which("bwrap") is not None,
    }
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


def _run_scrape(args: argparse.Namespace) -> int:
    result = scrape_url(args.url, _config(args))
    rendered = render_result(result, args.format)
    if args.output:
        path = atomic_write(args.output, rendered)
        sys.stdout.write(f"{path}\n")
    else:
        sys.stdout.write(rendered)
    return 0


def _run_crawl(args: argparse.Namespace) -> int:
    result = crawl_site(
        args.url,
        config=_config(args),
        max_pages=args.max_pages,
        max_depth=args.max_depth,
    )
    path = write_crawl(result, args.output)
    sys.stdout.write(f"{path}\n")
    if not result.pages and result.failures and result.failures[0].error_type in {
        "PolicyError",
        "RobotsDenied",
        "RobotsUnavailable",
    }:
        return 3
    return 4 if result.failures or not result.pages else 0


def _run_discover(args: argparse.Namespace) -> int:
    local_roots = tuple(str(path.expanduser().resolve()) for path in args.local)
    sources = args.sources
    if local_roots and "local" not in sources:
        sources = ("local", *sources)
    config = DiscoveryConfig(
        sources=sources,
        local_roots=local_roots,
        per_source=args.per_source,
        limit=args.limit,
        timeout=args.timeout,
        total_timeout=args.total_timeout,
        inspect_top=args.inspect_top,
        test_top=args.test_top,
        allow_untrusted_tests=args.allow_untrusted_tests,
        refresh_cache=args.refresh_cache,
        github_token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"),
    )
    result = discover_candidates(args.query, config, output_dir=args.output)
    receipt = write_discovery(result, args.output.expanduser().resolve())
    if args.summary:
        sys.stdout.write(render_discovery_summary(result, args.output.expanduser().resolve()))
    else:
        sys.stdout.write(f"{receipt}\n")
    return 5 if result.decision_status == "inconclusive" or result.discovery_status != "complete" else 0


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except PolicyError as exc:
        print(f"blocked: {exc}", file=sys.stderr)
        return 3
    except (Brief2ShipError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except BrokenPipeError:
        return 0
    except OSError as exc:
        wrapped = OutputError(str(exc))
        print(f"error: {wrapped}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
