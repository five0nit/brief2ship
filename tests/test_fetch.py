import os
import socket
import time
import unittest
import urllib.request
from email.message import Message
from unittest.mock import patch

from brief2ship.errors import FetchError, PolicyError, RobotsDenied, RobotsUnavailable
from brief2ship.fetch import (
    _PinnedHTTPSConnection,
    _PinnedHTTPSHandler,
    _parse_robots,
    _pinned_opener,
    _request_bytes,
    check_robots,
    fetch_page,
)
from brief2ship.models import ScrapeConfig
from tests.support import fixture_site


class FakeResponse:
    def __init__(self, status, url, headers=None, body=b""):
        self.status = status
        self.url = url
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value
        self._body = body

    def getcode(self):
        return self.status

    def read(self, size=-1):
        return self._body if size < 0 else self._body[:size]

    def close(self):
        return None


class FakeRedirectOpener(urllib.request.OpenerDirector):
    def open(self, fullurl, data=None, timeout=None):  # noqa: ARG002
        url = fullurl.full_url if isinstance(fullurl, urllib.request.Request) else str(fullurl)
        return FakeResponse(
            302,
            url,
            {"Location": "http://127.0.0.1/private"},
        )


class SlowResponse(FakeResponse):
    def read1(self, size=-1):  # noqa: ARG002
        time.sleep(0.06)
        if not self._body:
            return b""
        chunk, self._body = self._body[:1], self._body[1:]
        return chunk


class SlowBodyOpener(urllib.request.OpenerDirector):
    def open(self, fullurl, data=None, timeout=None):  # noqa: ARG002
        url = fullurl.full_url if isinstance(fullurl, urllib.request.Request) else str(fullurl)
        return SlowResponse(
            200,
            url,
            {"Content-Type": "text/plain"},
            b"abcdefgh",
        )


class SlowEmptyBodyOpener(urllib.request.OpenerDirector):
    def open(self, fullurl, data=None, timeout=None):  # noqa: ARG002
        url = fullurl.full_url if isinstance(fullurl, urllib.request.Request) else str(fullurl)
        return SlowResponse(
            200,
            url,
            {"Content-Type": "text/plain"},
            b"",
        )


class FetchTests(unittest.TestCase):
    def config(self, **changes):
        values = {"allow_private": True, "extractor": "stdlib", **changes}
        return ScrapeConfig(**values)

    def test_fetch_checks_robots_and_hashes_body(self):
        with fixture_site() as (base, handler):
            result = fetch_page(f"{base}/article", config=self.config())
        self.assertEqual(200, result.status_code)
        self.assertEqual("text/html", result.content_type)
        self.assertEqual(64, len(result.sha256))
        self.assertEqual(1.0, result.robots.crawl_delay)
        self.assertEqual(["/robots.txt", "/article"], handler.requests)

    def test_robots_denial_prevents_page_fetch(self):
        with fixture_site() as (base, handler):
            with self.assertRaises(RobotsDenied):
                fetch_page(f"{base}/blocked", config=self.config())
        self.assertEqual(["/robots.txt"], handler.requests)

    def test_absent_robots_allows_with_warning(self):
        with fixture_site(robots_status=404, robots_body="missing") as (base, _):
            result = fetch_page(f"{base}/plain", config=self.config())
        self.assertIn("robots.txt absent", result.warnings)

    def test_robots_403_denies(self):
        with fixture_site(robots_status=403, robots_body="denied") as (base, _):
            with self.assertRaises(RobotsDenied):
                check_robots(f"{base}/article", config=self.config())

    def test_robots_5xx_fails_closed(self):
        with fixture_site(robots_status=503, robots_body="down") as (base, _):
            with self.assertRaises(RobotsUnavailable):
                check_robots(f"{base}/article", config=self.config())

    def test_unhandled_robots_3xx_fails_closed(self):
        with fixture_site(robots_status=304, robots_body="") as (base, _):
            with self.assertRaises(RobotsUnavailable):
                check_robots(f"{base}/article", config=self.config())

    def test_redirect_is_followed_with_limit(self):
        with fixture_site() as (base, _):
            result = fetch_page(f"{base}/redirect", config=self.config())
        self.assertEqual(f"{base}/article", result.final_url)

    def test_same_origin_redirect_target_is_rechecked_against_robots(self):
        with fixture_site() as (base, handler):
            with self.assertRaises(RobotsDenied):
                fetch_page(f"{base}/redirect-blocked", config=self.config())
        self.assertIn("/redirect-blocked", handler.requests)
        self.assertNotIn("/blocked", handler.requests)

    def test_cross_origin_page_redirect_is_blocked_before_target_fetch(self):
        with fixture_site() as (base, _):
            with self.assertRaisesRegex(PolicyError, "cross-origin"):
                fetch_page(f"{base}/redirect-cross-origin", config=self.config())

    def test_streaming_byte_cap_enforced(self):
        with fixture_site() as (base, _):
            with self.assertRaisesRegex(FetchError, "byte limit"):
                fetch_page(f"{base}/large", config=self.config(max_bytes=1024))

    def test_declared_byte_cap_enforced_before_body(self):
        with fixture_site() as (base, _):
            with self.assertRaisesRegex(FetchError, "declares"):
                fetch_page(f"{base}/declared-large", config=self.config(max_bytes=1024))

    def test_non_text_content_rejected(self):
        with fixture_site() as (base, _):
            with self.assertRaisesRegex(FetchError, "unsupported content type"):
                fetch_page(f"{base}/json", config=self.config())

    def test_unhandled_page_3xx_is_rejected(self):
        with fixture_site() as (base, _):
            with self.assertRaises(FetchError):
                fetch_page(f"{base}/not-modified", config=self.config())

    def test_robots_longest_path_rule_wins_regardless_of_order(self):
        policy = "User-agent: *\nAllow: /\nDisallow: /private\nAllow: /private/public\n"
        denied, _ = _parse_robots(policy, "Brief2ShipBot", "https://example.com/private/file")
        allowed, _ = _parse_robots(policy, "Brief2ShipBot", "https://example.com/private/public/file")
        self.assertFalse(denied)
        self.assertTrue(allowed)

    def test_robots_wildcard_end_anchor_and_specific_agent(self):
        policy = """User-agent: *
Disallow: /*.pdf$
User-agent: Brief2ShipBot
Allow: /
Disallow: /internal
"""
        allowed_pdf, _ = _parse_robots(policy, "OtherBot", "https://example.com/file.pdf")
        allowed_query, _ = _parse_robots(policy, "OtherBot", "https://example.com/file.pdf?view=1")
        allowed_specific, _ = _parse_robots(policy, "Brief2ShipBot/0.4", "https://example.com/file.pdf")
        self.assertFalse(allowed_pdf)
        self.assertTrue(allowed_query)
        self.assertTrue(allowed_specific)

    def test_robots_agent_match_uses_exact_product_token_not_substring(self):
        policy = "User-agent: Brief2Ship\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
        allowed, _ = _parse_robots(
            policy,
            "Brief2ShipBot/0.4 (+https://example.com)",
            "https://example.com/",
        )
        self.assertTrue(allowed)

    def test_robots_normalizes_percent_encoded_unreserved_octets(self):
        encoded_rule = "User-agent: *\nDisallow: /%70rivate\n"
        encoded_target = "User-agent: *\nDisallow: /private\n"
        allowed_rule, _ = _parse_robots(
            encoded_rule,
            "Brief2ShipBot/0.4",
            "https://example.com/private",
        )
        allowed_target, _ = _parse_robots(
            encoded_target,
            "Brief2ShipBot/0.4",
            "https://example.com/%70rivate",
        )
        self.assertFalse(allowed_rule)
        self.assertFalse(allowed_target)

    def test_malformed_robots_fails_closed(self):
        with fixture_site(robots_body="this is not a robots policy") as (base, _):
            with self.assertRaises(RobotsUnavailable):
                check_robots(f"{base}/article", config=self.config())

    def test_response_body_uses_total_wall_clock_timeout(self):
        started = time.monotonic()
        with self.assertRaisesRegex(FetchError, "total timeout"):
            _request_bytes(
                "https://93.184.216.34/",
                config=self.config(timeout=0.12),
                max_bytes=1024,
                opener=SlowBodyOpener(),
            )
        self.assertLess(time.monotonic() - started, 0.3)

    def test_empty_response_cannot_finish_after_wall_clock_deadline(self):
        with self.assertRaisesRegex(FetchError, "total timeout"):
            _request_bytes(
                "https://93.184.216.34/",
                config=self.config(timeout=0.05),
                max_bytes=1024,
                opener=SlowEmptyBodyOpener(),
            )

    def test_redirect_target_is_revalidated_against_private_network_policy(self):
        def selective_validator(url, *, allow_private=False):
            if url == "https://public.example/start":
                return url
            from brief2ship.safety import validate_url

            return validate_url(url, allow_private=allow_private)

        with patch("brief2ship.fetch.validate_url", side_effect=selective_validator):
            with self.assertRaisesRegex(PolicyError, "non-public"):
                _request_bytes(
                    "https://public.example/start",
                    config=ScrapeConfig(),
                    max_bytes=1024,
                    opener=FakeRedirectOpener(),
                )

    def test_default_transport_rechecks_dns_before_connecting(self):
        public_answer = [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("93.184.216.34", 80),
            )
        ]
        private_answer = [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("127.0.0.1", 80),
            )
        ]
        with patch(
            "brief2ship.safety.socket.getaddrinfo",
            side_effect=[public_answer, private_answer],
        ) as resolve, self.assertRaisesRegex(PolicyError, "blocked address"):
            _request_bytes(
                "http://rebind.example/article",
                config=ScrapeConfig(),
                max_bytes=1024,
            )

        self.assertEqual(2, resolve.call_count)

    def test_pinned_https_handler_only_forwards_portable_context(self):
        targets = (
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                ("93.184.216.34", 443),
            ),
        )
        handler = _PinnedHTTPSHandler(targets)
        request = urllib.request.Request("https://example.com/")
        sentinel = object()

        with patch.object(handler, "do_open", return_value=sentinel) as do_open:
            self.assertIs(sentinel, handler.https_open(request))

        self.assertEqual({"context"}, set(do_open.call_args.kwargs))
        context = do_open.call_args.kwargs["context"]
        self.assertTrue(context is None or context.check_hostname)
        connection = _PinnedHTTPSConnection(
            "example.com",
            targets=targets,
            context=context,
        )
        self.assertTrue(getattr(connection, "_context").check_hostname)

    def test_default_transport_ignores_environment_proxies(self):
        with patch.dict(
            os.environ,
            {
                "HTTP_PROXY": "http://127.0.0.1:9999",
                "HTTPS_PROXY": "http://127.0.0.1:9999",
                "NO_PROXY": "",
            },
        ), patch(
            "brief2ship.fetch.resolve_url_addresses",
            return_value=(
                "https://example.com/",
                (
                    (
                        socket.AF_INET,
                        socket.SOCK_STREAM,
                        socket.IPPROTO_TCP,
                        ("93.184.216.34", 443),
                    ),
                ),
            ),
        ):
            opener = _pinned_opener(
                "https://example.com/",
                allow_private=False,
            )

        proxy_handlers = [
            handler
            for handler in getattr(opener, "handlers", [])
            if isinstance(handler, urllib.request.ProxyHandler)
        ]
        self.assertEqual([], proxy_handlers)


if __name__ == "__main__":
    unittest.main()
