"""Deterministic scrape receipt rendering and atomic writes."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from .errors import OutputError
from .models import CrawlResult, ScrapeResult

_UNSAFE_CONTROLS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]"
)


def _safe_plain_text(value: str) -> str:
    return _UNSAFE_CONTROLS.sub("", value)


def _fenced_block(value: str, language: str = "text") -> str:
    safe = _safe_plain_text(value).rstrip()
    longest = max((len(run) for run in re.findall(r"`+", safe)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{language}\n{safe}\n{fence}"


def render_json(result: ScrapeResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_text(result: ScrapeResult) -> str:
    return _safe_plain_text(result.text).rstrip() + "\n"


def render_markdown(result: ScrapeResult) -> str:
    title = result.title or result.final_url
    provenance = {
        "Requested URL": result.requested_url,
        "Final URL": result.final_url,
        "Fetched": result.fetched_at,
        "HTTP status": result.status_code,
        "Content type": result.content_type,
        "Bytes": result.bytes_read,
        "SHA-256": result.sha256,
        "Extractor": result.extractor,
        "robots.txt": result.robots_url,
        "robots allowed": result.robots_allowed,
        "Crawl delay": result.crawl_delay,
    }
    warnings = "\n".join(f"- {item}" for item in result.warnings) or "- None"
    return (
        "# Brief2Ship scrape receipt\n\n"
        "## Title\n\n"
        f"{_fenced_block(title)}\n\n"
        "## Provenance\n\n"
        f"{_fenced_block(json.dumps(provenance, ensure_ascii=False, indent=2), 'json')}\n\n"
        "## Warnings\n\n"
        f"{_fenced_block(warnings)}\n\n"
        "## Extracted content\n\n"
        f"{_fenced_block(result.text)}\n"
    )


def render_result(result: ScrapeResult, output_format: str) -> str:
    if output_format == "json":
        return render_json(result)
    if output_format == "markdown":
        return render_markdown(result)
    if output_format == "text":
        return render_text(result)
    raise OutputError("format must be json, markdown, or text")


def atomic_write(path: str | Path, content: str) -> Path:
    target = Path(path).expanduser()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            text=True,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    except OSError as exc:
        raise OutputError(f"could not write {target}: {exc}") from exc
    return target.resolve()


def write_crawl(result: CrawlResult, output_dir: str | Path) -> Path:
    root = Path(output_dir).expanduser()
    pages_dir = root / "pages"
    try:
        if root.exists() and any(root.iterdir()):
            raise OutputError(f"crawl output directory must be empty: {root}")
        pages_dir.mkdir(parents=True, exist_ok=True)
    except OutputError:
        raise
    except OSError as exc:
        raise OutputError(f"could not create crawl output {root}: {exc}") from exc
    page_entries: list[dict[str, object]] = []
    for index, page in enumerate(result.pages, 1):
        stem = f"{index:04d}"
        json_path = atomic_write(pages_dir / f"{stem}.json", render_json(page))
        markdown_path = atomic_write(pages_dir / f"{stem}.md", render_markdown(page))
        page_entries.append(
            {
                "index": index,
                "requested_url": page.requested_url,
                "final_url": page.final_url,
                "sha256": page.sha256,
                "json": str(json_path.relative_to(root.resolve())),
                "markdown": str(markdown_path.relative_to(root.resolve())),
            }
        )
    manifest = result.to_dict()
    manifest["pages"] = page_entries
    manifest_path = atomic_write(
        root / "manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return manifest_path
