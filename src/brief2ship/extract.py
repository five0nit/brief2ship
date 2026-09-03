"""Local-only content extraction adapters."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from .errors import ExtractionError
from .models import ExtractedContent, FetchResult
from .safety import normalize_url

_SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas", "nav", "footer", "aside", "form"}
_BLOCK_TAGS = {
    "address",
    "article",
    "blockquote",
    "br",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "li",
    "main",
    "p",
    "pre",
    "section",
    "td",
    "th",
    "tr",
}
_UNSAFE_CONTROLS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]"
)


def _clean_lines(value: str) -> str:
    value = _UNSAFE_CONTROLS.sub("", value)
    lines: list[str] = []
    for raw in value.replace("\r", "\n").split("\n"):
        line = re.sub(r"[\t\f\v ]+", " ", raw).strip()
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return "\n\n".join(lines)


class _ReadableHTMLParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.skip_depth = 0
        self.in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if self.skip_depth:
            if lowered in _SKIP_TAGS:
                self.skip_depth += 1
            return
        if lowered in _SKIP_TAGS:
            self.skip_depth = 1
            return
        if lowered == "title":
            self.in_title = True
        if lowered in _BLOCK_TAGS:
            self.text_parts.append("\n")
        if lowered == "li":
            self.text_parts.append("• ")
        if lowered == "a":
            href = dict(attrs).get("href")
            if href:
                self._add_link(href)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _SKIP_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if self.skip_depth:
            if lowered in _SKIP_TAGS:
                self.skip_depth -= 1
            return
        if lowered == "title":
            self.in_title = False
        if lowered in _BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if self.in_title:
            self.title_parts.append(data)
        else:
            self.text_parts.append(data)

    def _add_link(self, href: str) -> None:
        if href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            return
        try:
            absolute = normalize_url(urljoin(self.base_url, href))
        except Exception:
            return
        if urlsplit(absolute).scheme in {"http", "https"} and absolute not in self.links:
            self.links.append(absolute)


def _stdlib_extract(html: str, base_url: str) -> ExtractedContent:
    parser = _ReadableHTMLParser(base_url)
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:
        raise ExtractionError(f"HTML parsing failed: {exc}") from exc
    text = _clean_lines("".join(parser.text_parts))
    title = re.sub(r"\s+", " ", "".join(parser.title_parts)).strip()
    if not text:
        raise ExtractionError("no readable text found")
    return ExtractedContent(
        title=title,
        text=text,
        links=tuple(parser.links),
        extractor="stdlib",
    )


def _trafilatura_extract(html: str, base_url: str) -> ExtractedContent:
    try:
        import trafilatura  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ExtractionError(
            "Trafilatura is not installed; use --extractor stdlib or install brief2ship[extract]"
        ) from exc
    baseline = _stdlib_extract(html, base_url)
    try:
        text = trafilatura.extract(
            html,
            url=base_url,
            output_format="txt",
            include_links=False,
            include_images=False,
            include_tables=True,
            no_fallback=False,
        )
    except Exception as exc:
        raise ExtractionError(f"Trafilatura extraction failed: {exc}") from exc
    cleaned = _clean_lines(text or "")
    if not cleaned:
        raise ExtractionError("Trafilatura returned no readable text")
    return ExtractedContent(
        title=baseline.title,
        text=cleaned,
        links=baseline.links,
        extractor="trafilatura",
    )


def extract_content(fetch: FetchResult, extractor: str = "auto") -> ExtractedContent:
    if extractor not in {"auto", "stdlib", "trafilatura"}:
        raise ExtractionError("extractor must be auto, stdlib, or trafilatura")
    try:
        text = fetch.body.decode(fetch.charset, errors="replace")
    except LookupError as exc:
        raise ExtractionError(f"unsupported response charset: {fetch.charset}") from exc
    if fetch.content_type == "text/plain":
        cleaned = _clean_lines(text)
        if not cleaned:
            raise ExtractionError("plain-text response was empty")
        return ExtractedContent("", cleaned, (), "plain-text")
    if extractor == "stdlib":
        return _stdlib_extract(text, fetch.final_url)
    if extractor == "trafilatura":
        return _trafilatura_extract(text, fetch.final_url)
    try:
        return _trafilatura_extract(text, fetch.final_url)
    except ExtractionError as exc:
        fallback = _stdlib_extract(text, fetch.final_url)
        return ExtractedContent(
            title=fallback.title,
            text=fallback.text,
            links=fallback.links,
            extractor=fallback.extractor,
            warnings=(f"optional Trafilatura unavailable or failed; used stdlib: {exc}",),
        )
