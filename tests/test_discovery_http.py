from __future__ import annotations

import threading
import time
import unittest
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from brief2ship.discovery_http import DiscoveryHttpClient, DiscoverySourceError


class RedirectHandler(BaseHTTPRequestHandler):
    target_requests = 0

    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/target")
            self.end_headers()
            return
        type(self).target_requests += 1
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format, *args):  # noqa: A002, ARG002
        return


class SlowEmptyResponse:
    status = 200
    url = "https://example.com/payload"
    headers = Message()

    def getcode(self):
        return self.status

    def read1(self, size=-1):  # noqa: ARG002
        time.sleep(0.08)
        return b""

    def close(self):
        return None


class SlowEmptyOpener:
    def open(self, fullurl, data=None, timeout=None):  # noqa: ARG002
        return SlowEmptyResponse()


class DiscoveryHttpTests(unittest.TestCase):
    def test_redirects_are_rejected_not_followed(self):
        RedirectHandler.target_requests = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/redirect"
            with self.assertRaisesRegex(DiscoverySourceError, "HTTP 302"):
                DiscoveryHttpClient(timeout=2).request(url)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(RedirectHandler.target_requests, 0)

    def test_github_token_is_scoped_to_api_host(self):
        client = DiscoveryHttpClient(github_token="secret-test-token")
        self.assertIn("Authorization", client._headers("https://api.github.com/search/repositories"))
        self.assertNotIn("Authorization", client._headers("https://github.com/owner/repo"))
        self.assertNotIn("Authorization", client._headers("https://example.com/"))
        self.assertNotIn(
            "authorization",
            client._headers("https://example.com/", {"authorization": "Bearer injected"}),
        )

    def test_overall_network_budget_fails_closed_before_request(self):
        client = DiscoveryHttpClient(timeout=2, total_timeout=10)
        client._expires_at = 0.0
        with self.assertRaisesRegex(DiscoverySourceError, "budget exhausted"):
            client.request("https://example.com/payload")

    def test_empty_response_cannot_finish_after_request_deadline(self):
        client = DiscoveryHttpClient(timeout=0.05)
        client._opener = SlowEmptyOpener()  # type: ignore[assignment]
        with self.assertRaisesRegex(DiscoverySourceError, "total timeout"):
            client.request("https://example.com/payload")

    def test_crates_requests_are_paced_without_delaying_other_hosts(self):
        client = DiscoveryHttpClient()
        client._last_request["crates.io"] = 100.0
        with patch("brief2ship.discovery_http.time.monotonic", return_value=100.25), patch(
            "brief2ship.discovery_http.time.sleep"
        ) as sleep:
            client._pace("https://crates.io/api/v1/crates")
            sleep.assert_called_once_with(0.75)
        with patch("brief2ship.discovery_http.time.sleep") as sleep:
            client._pace("https://registry.npmjs.org/-/v1/search")
            sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
