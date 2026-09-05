"""Strict, dependency-free normalization for reusable license evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

# These are exact metadata aliases for the existing permissive allowlist.  The
# lookup is case-insensitive, but it never treats a license name as a substring
# of a larger expression or custom license.
_LICENSE_ALIASES = {
    "0bsd": "0BSD",
    "apache license 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "isc": "ISC",
    "mit": "MIT",
    "mit license": "MIT",
    "the unlicense": "Unlicense",
    "unlicense": "Unlicense",
}
_PERMISSIVE_LICENSES = frozenset(_LICENSE_ALIASES.values())

_MIT_BODY = '''Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.'''
_MIT_BODY_START = "Permission is hereby granted, free of charge,"
_MIT_TITLES = frozenset({"mit", "mit license", "the mit license", "the mit license (mit)"})



def _collapse_whitespace(value: str) -> str:
    """Ignore wrapping and line-ending differences, but not wording changes."""

    return " ".join(value.split())


def _is_permitted_mit_prefix(prefix: str) -> bool:
    """Exact titles only; free-form notices cannot confer decision authority."""

    lines = [line.strip() for line in prefix.splitlines() if line.strip()]
    return all(line.casefold() in _MIT_TITLES for line in lines)


def license_body_match(value: str | None) -> str | None:
    """Recognize a complete MIT body, NEVER approval of surrounding text.

    Arbitrary holder names and arbitrary conditions are both natural language.
    A name-shape regex or vocabulary denylist cannot distinguish them reliably.
    This diagnostic match is deliberately separate from normalize_license.
    """
    if not value:
        return None
    start = value.find(_MIT_BODY_START)
    if start >= 0 and _collapse_whitespace(value[start:]) == _collapse_whitespace(_MIT_BODY):
        return "MIT"
    return None


def normalize_license(value: str | None, *, metadata: bool = True) -> str | None:
    """Return a canonical permissive SPDX identifier for exact evidence.

    Full MIT text is recognized only when the complete canonical grant,
    inclusion condition, warranty disclaimer, and liability disclaimer are
    present with no appended terms. Only exact title prefixes and whitespace
    variations are authoritative. Free-form copyright notices still receive a
    license_body_match, but need review; never silently erase arbitrary prose.
    Unknown, compound, truncated, and modified text remains unnormalized.
    """

    if value is None:
        return None
    stripped = value.strip().lstrip("\ufeff")
    if not stripped:
        return None

    alias = _LICENSE_ALIASES.get(_collapse_whitespace(stripped).casefold())
    if alias is not None and metadata:
        return alias

    body_offset = stripped.find(_MIT_BODY_START)
    if body_offset < 0:
        return None
    prefix = stripped[:body_offset]
    body = stripped[body_offset:]
    if not _is_permitted_mit_prefix(prefix):
        return None
    if _collapse_whitespace(body) != _collapse_whitespace(_MIT_BODY):
        return None
    return "MIT"


def is_permissive_license(normalized_license: str | None) -> bool:
    """Return whether already-normalized evidence is on the reuse allowlist."""

    return normalized_license in _PERMISSIVE_LICENSES


def read_license_evidence(root: Path, reader: Callable[[Path], str]) -> str | None:
    """Retain bounded, symlink-safe file evidence without guessing SPDX."""
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md"):
        text = reader(root / name)
        if text:
            return text
    return None
