"""Deterministic, bounded query planning for discovery providers."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(
    r"@[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
    r"|[A-Za-z0-9_.+#-]+/[A-Za-z0-9_.+#-]+"
    r"|[A-Za-z0-9][A-Za-z0-9_.+#-]*"
)
_VERSION_RE = re.compile(r"\d+(?:\.\d+)*(?:\+)?$")

_LEADING_INSTRUCTION_WORDS = {
    "a",
    "an",
    "build",
    "create",
    "develop",
    "discover",
    "existing",
    "find",
    "help",
    "i",
    "implement",
    "looking",
    "make",
    "me",
    "need",
    "new",
    "please",
    "search",
    "the",
    "use",
    "want",
    "we",
}
_ARTIFACT_WORDS = {"app", "application", "library", "package", "project", "solution", "tool"}
_TRAILING_CONNECTORS = {"and", "for", "on", "or", "using", "with"}
_FOCUS_STOPWORDS = {
    "a",
    "an",
    "and",
    "app",
    "application",
    "code",
    "existing",
    "first",
    "for",
    "library",
    "new",
    "of",
    "or",
    "package",
    "project",
    "reuse",
    "solution",
    "support",
    "the",
    "tool",
    "using",
    "with",
}
_CONSTRAINT_TERMS = {
    "bounded",
    "browser-based",
    "cloud-free",
    "cross-platform",
    "dependency-free",
    "deterministic",
    "free",
    "local",
    "locally",
    "mobile-first",
    "no-cloud",
    "no-dependency",
    "offline",
    "open-source",
    "private-only",
    "public-only",
    "read-only",
    "robots-aware",
    "robots-compliant",
    "self-contained",
    "self-hosted",
    "zero-dependency",
}
_RUNTIME_TERMS = {
    ".net",
    "android",
    "c#",
    "c++",
    "deno",
    "go",
    "golang",
    "ios",
    "java",
    "javascript",
    "kotlin",
    "linux",
    "macos",
    "node",
    "node.js",
    "php",
    "python",
    "ruby",
    "rust",
    "swift",
    "typescript",
    "windows",
}
_NEGATED_RESOURCES = {
    "authentication",
    "cloud",
    "database",
    "dependencies",
    "dependency",
    "docker",
    "gpu",
    "internet",
    "network",
}
_RESOURCE_SUFFIXES = {"access", "service", "services"}


@dataclass(frozen=True)
class QueryPlan:
    original: str
    core_query: str
    constraints: tuple[str, ...]
    variants: tuple[str, ...]


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall(value)


def _is_constraint_term(value: str) -> bool:
    lowered = value.lower()
    if lowered in _CONSTRAINT_TERMS or lowered in _RUNTIME_TERMS:
        return True
    parts = lowered.split("/")
    return len(parts) > 1 and all(
        part in _CONSTRAINT_TERMS or part in _RUNTIME_TERMS for part in parts
    )


def _constraint_ranges(tokens: list[str]) -> list[tuple[int, int]]:
    """Return non-overlapping token ranges containing explicit constraints."""
    ranges: list[tuple[int, int]] = []
    index = 0
    while index < len(tokens):
        lowered = tokens[index].lower()
        next_lower = tokens[index + 1].lower() if index + 1 < len(tokens) else ""

        if lowered in _RUNTIME_TERMS and _VERSION_RE.fullmatch(next_lower):
            ranges.append((index, index + 2))
            index += 2
            continue
        if lowered in {"no", "without"} and next_lower in _NEGATED_RESOURCES:
            end = index + 2
            if end < len(tokens) and tokens[end].lower() in _RESOURCE_SUFFIXES:
                end += 1
            ranges.append((index, end))
            index = end
            continue
        if lowered in {"no", "without"} and next_lower == "paid":
            end = index + 2
            if end < len(tokens) and tokens[end].lower() in {"api", "apis", "service", "services"}:
                end += 1
                ranges.append((index, end))
                index = end
                continue
        if _is_constraint_term(tokens[index]):
            ranges.append((index, index + 1))
        index += 1
    return ranges


def _core_tokens(tokens: list[str], ranges: list[tuple[int, int]]) -> list[str]:
    constrained = {
        index
        for start, end in ranges
        for index in range(start, end)
    }
    # Remove only connectors introducing a recognized constraint, not the
    # connectors inside a task such as "PDF to Markdown" or "audio and video".
    introducers = {"for", "with", "on", "in", "using", "that", "runs", "run", "and", "or", "must", "be"}
    for start, _ in ranges:
        previous = start - 1
        while previous >= 0 and tokens[previous].lower() in introducers:
            constrained.add(previous)
            previous -= 1
    values = [token for index, token in enumerate(tokens) if index not in constrained]

    while values and values[0].lower() in _LEADING_INSTRUCTION_WORDS:
        values.pop(0)
    if (
        len(values) >= 2
        and values[0].lower() in _ARTIFACT_WORDS
        and values[1].lower() == "for"
    ):
        values = values[2:]
    while values and values[-1].lower() in _TRAILING_CONNECTORS:
        values.pop()
    return values


def _focused_variant(core_query: str) -> str:
    values = _tokens(core_query)
    focused = [value for value in values if value.lower() not in _FOCUS_STOPWORDS]
    if len(focused) < 2:
        return core_query
    return " ".join(focused)


def plan_query(query: str) -> QueryPlan:
    """Split a request into core intent, recorded constraints, and at most three queries.

    Variants only remove observed terms or combine observed constraints with the core;
    the planner does not invent synonyms or make semantic expansion claims.
    """
    tokens = _tokens(query)
    ranges = _constraint_ranges(tokens)
    constraints = tuple(" ".join(tokens[start:end]) for start, end in ranges)
    core_values = _core_tokens(tokens, ranges)
    normalized = " ".join(tokens)
    core_query = " ".join(core_values) or normalized or query

    variants: list[str] = []

    def add(value: str) -> None:
        if value and value not in variants and len(variants) < 3:
            variants.append(value)

    add(core_query)
    add(query)
    add(_focused_variant(core_query))
    if constraints:
        add(f"{constraints[-1]} {core_query}")

    return QueryPlan(
        original=query,
        core_query=core_query,
        constraints=constraints,
        variants=tuple(variants),
    )
