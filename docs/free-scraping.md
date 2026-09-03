# Free scraping

Brief2Ship v0.4 can collect small public-web source packs without API keys, subscriptions, hosted browsers, or paid scraping services.

This is a respectful evidence-acquisition tool, not an evasion framework.

## Install

Core, zero runtime dependencies:

```bash
python3 -m pip install .
brief2ship doctor
```

Optional local Trafilatura extraction:

```bash
python3 -m pip install '.[extract]'
brief2ship doctor
```

Trafilatura is Apache-2.0. It receives HTML inside the local process; Brief2Ship does not call a remote extraction service.

## Single page

JSON receipt to stdout:

```bash
brief2ship scrape https://example.com/article --extractor stdlib
```

Markdown artifact:

```bash
brief2ship scrape https://example.com/article \
  --format markdown \
  --output research/example-article.md
```

Text only:

```bash
brief2ship scrape https://example.com/article --format text
```

Extractor choices:

- `auto` — use Trafilatura when installed; otherwise deterministic stdlib extraction with a warning
- `stdlib` — dependency-free `HTMLParser` extraction
- `trafilatura` — require Trafilatura; fail honestly if unavailable

## Bounded crawl

```bash
brief2ship crawl https://example.com/docs \
  --output research/example-docs \
  --max-pages 5 \
  --max-depth 1
```

Output:

```text
research/example-docs/
├── manifest.json
└── pages/
    ├── 0001.json
    ├── 0001.md
    ├── 0002.json
    └── 0002.md
```

The crawl is breadth-first, same-origin, sequential, fragment-deduplicated, and robots-cached per origin.
`--max-pages` counts attempted URLs, including denied or failed pages, so failures cannot expand the request budget.
The output directory must be new or empty; Brief2Ship refuses to mix fresh receipts with stale crawl files.

## Defaults and hard caps

| Control | Default | Hard range |
|---|---:|---:|
| Total request timeout | 15 seconds | 0.1–120 seconds |
| Response size | 2,000,000 bytes | 1,024–20,000,000 bytes |
| Redirects | 5 | 0–10 |
| Minimum delay | 1 second | 0–60 seconds |
| Crawl pages | 5 | 1–20 |
| Crawl depth | 1 | 0–3 |

A robots.txt crawl delay overrides the configured delay when larger.

## robots.txt behavior

Before any page fetch, Brief2Ship requests the origin's `/robots.txt`.

- `200–299`: parse user-agent groups, `Allow`, `Disallow`, `*`, `$`, and `Crawl-delay`
- `404` or `410`: continue and record `robots.txt absent`
- `401` or `403`: deny
- other `4xx`, `5xx`, network error, oversized file, or malformed policy: fail closed
- the longest matching path rule wins; `Allow` wins equal-length ties
- user-agent groups match the crawler's exact case-insensitive product token
- percent-encoded unreserved octets are normalized before path comparison
- robots denial produces no page request

## Network safety

Default target validation:

- schemes restricted to `http` and `https`
- credentials in URLs rejected
- `localhost`, `.localhost`, and `.local` names rejected
- internationalized hosts are normalized to IDNA and Unicode paths/queries are percent-encoded before transport
- literal and DNS-resolved private, loopback, link-local, reserved, unspecified, and multicast addresses rejected
- DNS answers are revalidated immediately before connection and the socket is pinned to those exact addresses
- environment HTTP(S) proxies are ignored by the default transport so they cannot bypass target validation
- every redirect target resolved and checked again
- page redirects must remain same-origin; the target path is re-evaluated against the cached robots document before the redirect is followed
- compressed responses are not requested, keeping byte limits explicit
- content streamed only up to the configured cap
- one wall-clock deadline covers connection, redirects, and body streaming
- accepted page types: `text/html`, `application/xhtml+xml`, `text/plain`

`--allow-private` permits explicit local/owner-authorized targets for tests. It does not permit URL credentials, other schemes, robots bypass, oversized responses, unlimited redirects, concurrency, or unbounded crawls.

The default transport closes the DNS-rebinding window by connecting only to the revalidated address set while preserving the original hostname for HTTP `Host` and HTTPS certificate/SNI checks. Callers that inject a custom opener own equivalent DNS-pinning and proxy controls.

## Explicit non-features

v0.4 does not provide:

- browser or JavaScript rendering
- authentication or saved cookies
- CAPTCHA solving
- stealth/fingerprint spoofing
- proxy rotation
- rate-limit evasion
- cross-origin link expansion
- concurrent/distributed crawling
- PDF/image/media extraction
- personal-data harvesting

A JavaScript-only or anti-bot-blocked page is reported as a limitation. Do not weaken safety gates to force a result.
If a page redirects to another origin, scrape the final public URL explicitly so that origin's robots.txt is checked before its page is requested.

## Receipt schema

Markdown receipts place titles, warnings, provenance, and extracted text inside dynamically sized code fences. Terminal controls and bidirectional override controls are stripped so scraped text cannot become active Markdown, remote-image markup, or terminal escape output.

Single-page JSON fields:

```json
{
  "requested_url": "https://example.com/article",
  "final_url": "https://example.com/article",
  "fetched_at": "2026-07-30T00:00:00+00:00",
  "status_code": 200,
  "content_type": "text/html",
  "title": "Example",
  "text": "Extracted text",
  "links": [],
  "extractor": "stdlib",
  "bytes_read": 1234,
  "sha256": "raw-response-sha256",
  "robots_url": "https://example.com/robots.txt",
  "robots_allowed": true,
  "crawl_delay": 1.0,
  "warnings": []
}
```

The SHA-256 covers the fetched raw response body, not the normalized extracted text.
A crawl manifest's `attempted_count` equals successful pages plus recorded failures.

## Exit codes

- `0` — success
- `2` — CLI argument error
- `3` — blocked by network or robots policy
- `4` — fetch, extraction, output, or partial-crawl failure (the manifest is still written)

Errors go to stderr. Successful JSON written to stdout remains parseable.

## Responsible use

The operator remains responsible for site terms, copyright, privacy, database rights, and downstream reuse. Publicly reachable does not mean unrestricted. Keep source packs bounded, attributable, decision-relevant, and no more invasive than the brief requires.
