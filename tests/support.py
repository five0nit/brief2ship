"""HTTP fixtures for real local fetch/crawl integration tests."""

from __future__ import annotations

import contextlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@contextlib.contextmanager
def fixture_site(
    *,
    robots_status: int = 200,
    robots_body: str = "User-agent: *\nAllow: /\nDisallow: /blocked\nCrawl-delay: 1\n",
):
    class Handler(BaseHTTPRequestHandler):
        requests: list[str] = []

        def log_message(self, format, *args):  # noqa: A002, ANN001
            return

        def do_GET(self):  # noqa: N802
            type(self).requests.append(self.path)
            if self.path == "/robots.txt":
                self._send(robots_status, robots_body.encode(), "text/plain; charset=utf-8")
            elif self.path == "/article":
                body = b"""<!doctype html><html><head><title>Fixture Article</title><style>.x{}</style></head>
<body><nav>Discard navigation</nav><main><h1>Useful heading</h1><p>First useful paragraph &amp; proof.</p>
<ul><li>One item</li><li>Second item</li></ul><a href='/page2#part'>Page two</a>
<a href='https://example.org/external'>External</a><script>discard()</script></main></body></html>"""
                self._send(200, body, "text/html; charset=utf-8")
            elif self.path == "/page2":
                self._send(200, b"<html><title>Two</title><body><p>Second page text.</p><a href='/article'>Back</a></body></html>", "text/html")
            elif self.path == "/index-with-blocked":
                self._send(
                    200,
                    b"<html><title>Index</title><body><a href='/article'>Allowed</a><a href='/blocked'>Blocked</a></body></html>",
                    "text/html",
                )
            elif self.path == "/many":
                links = "".join(f"<a href='/missing-{index}'>Missing</a>" for index in range(10))
                self._send(200, f"<html><body>{links}</body></html>".encode(), "text/html")
            elif self.path == "/blocked":
                self._send(200, b"<html><body>must not fetch</body></html>", "text/html")
            elif self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/article")
                self.end_headers()
            elif self.path == "/redirect-blocked":
                self.send_response(302)
                self.send_header("Location", "/blocked")
                self.end_headers()
            elif self.path == "/redirect-cross-origin":
                self.send_response(302)
                self.send_header("Location", "https://example.org/")
                self.end_headers()
            elif self.path == "/not-modified":
                self.send_response(304)
                self.end_headers()
            elif self.path == "/large":
                self._send(200, b"x" * 4096, "text/plain", include_length=False)
            elif self.path == "/declared-large":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", "999999")
                self.end_headers()
            elif self.path == "/json":
                self._send(200, b'{"not":"html"}', "application/json")
            elif self.path == "/plain":
                self._send(200, b"plain evidence", "text/plain; charset=utf-8")
            else:
                self._send(404, b"missing", "text/plain")

        def _send(self, status: int, body: bytes, content_type: str, *, include_length: bool = True):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            if include_length:
                self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = str(server.server_address[0])
        port = int(server.server_address[1])
        yield f"http://{host}:{port}", Handler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
