"""Bounded, typed checkpoints of provider observations for explicit retries.

Checkpoints are local evidence, not signed attestations. Retrying rechecks local
files, vulnerabilities, scores and inspections; it never restores a decision.
"""

from __future__ import annotations

import json
import math
import os
import stat
import types
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from .discovery_models import Candidate, DiscoveryConfig, SourceReceipt
from .render import atomic_write

SCHEMA = "brief2ship-source-checkpoint-v1"
MAX_BYTES = 10_000_000
MAX_AGE_SECONDS = 86_400
MAX_DEPTH = 32
MAX_NODES = 100_000
MAX_COLLECTION_ITEMS = 10_000
MAX_STRING_LENGTH = 2_000_000


def _validate_json_tree(value: Any) -> None:
    """Bound nested evidence dictionaries too, including fields typed as Any."""
    remaining = MAX_NODES
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        remaining -= 1
        if remaining < 0 or depth > MAX_DEPTH:
            raise ValueError("checkpoint exceeds the nested evidence budget")
        if isinstance(item, dict):
            if len(item) > MAX_COLLECTION_ITEMS or any(not isinstance(key, str) for key in item):
                raise ValueError("checkpoint contains an invalid evidence mapping")
            pending.extend((key, depth + 1) for key in item)
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            if len(item) > MAX_COLLECTION_ITEMS:
                raise ValueError("checkpoint evidence list exceeds its budget")
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            if len(item) > MAX_STRING_LENGTH:
                raise ValueError("checkpoint evidence text exceeds its budget")
        elif isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("checkpoint numbers must be finite")
        elif item is not None and type(item) not in (int, bool):
            raise ValueError("checkpoint contains non-JSON evidence")


def _read_bounded(path: Path) -> bytes:
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
        raise ValueError("checkpoint must be a regular file within the 10 MB limit")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        observed = os.fstat(stream.fileno())
        if not stat.S_ISREG(observed.st_mode) or (before.st_dev, before.st_ino) != (observed.st_dev, observed.st_ino):
            raise ValueError("checkpoint changed while being opened")
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("checkpoint exceeds the 10 MB limit")
    return raw


def _scope(query: str, config: DiscoveryConfig) -> dict[str, Any]:
    return {
        "query": query,
        "sources": list(config.sources),
        "local_roots": [str(Path(root).expanduser().resolve()) for root in config.local_roots],
        "per_source": config.per_source,
    }


def _timestamp_age(value: Any) -> float:
    if not isinstance(value, str):
        raise ValueError("checkpoint timestamp must be a string")
    observed = datetime.fromisoformat(value)
    if observed.tzinfo is None:
        raise ValueError("checkpoint timestamp must include a timezone")
    age = (datetime.now(timezone.utc) - observed).total_seconds()
    if age < -60:
        raise ValueError("checkpoint is future-dated; start a fresh discovery")
    return age


def write_checkpoint(
    directory: Path,
    query: str,
    config: DiscoveryConfig,
    observations: dict[str, tuple[list[Candidate], SourceReceipt]],
    *,
    observed_at: str | None = None,
    source_observed_at: dict[str, str] | None = None,
) -> Path:
    config.validate()
    saved_at = observed_at or datetime.now(timezone.utc).isoformat()
    observed_times = source_observed_at or {}
    payload = {
        "schema": SCHEMA,
        "observed_at": saved_at,
        "scope": _scope(query, config),
        "observations": {
            source: {
                "observed_at": observed_times.get(source, saved_at),
                "candidates": [asdict(item) for item in candidates],
                "receipt": asdict(receipt),
            }
            for source, (candidates, receipt) in observations.items()
        },
    }
    _validate_json_tree(payload)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(encoded.encode("utf-8")) > MAX_BYTES:
        raise ValueError("checkpoint exceeds the 10 MB limit")
    return atomic_write(directory / "checkpoint.json", encoded)


def _decode(annotation: Any, value: Any) -> Any:
    """Validate dataclass field types before cached metadata reaches scorers."""
    if annotation is Any:
        return value
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (Union, types.UnionType):
        for choice in args:
            try:
                return _decode(choice, value)
            except ValueError:
                continue
        raise ValueError("checkpoint field has an invalid type")
    if annotation is type(None):
        if value is None:
            return None
    elif origin is list and isinstance(value, list):
        return [_decode(args[0], item) for item in value]
    elif origin is dict and isinstance(value, dict):
        return {_decode(args[0], key): _decode(args[1], item) for key, item in value.items()}
    elif isinstance(annotation, type) and is_dataclass(annotation) and isinstance(value, dict):
        hints = get_type_hints(annotation)
        allowed = {item.name for item in fields(annotation)}
        if set(value) - allowed:
            raise ValueError("checkpoint contains unsupported fields")
        try:
            return annotation(**{key: _decode(hints[key], item) for key, item in value.items()})
        except TypeError as exc:
            raise ValueError("checkpoint is missing required fields") from exc
    elif annotation is float and type(value) in (int, float):
        try:
            number = float(value)
        except OverflowError as exc:
            raise ValueError("checkpoint number is outside the supported range") from exc
        if math.isfinite(number):
            return number
    elif annotation in (str, int, bool) and type(value) is annotation:
        return value
    raise ValueError("checkpoint field has an invalid type")


def load_checkpoint(
    path: Path, query: str, config: DiscoveryConfig,
) -> tuple[dict[str, tuple[list[Candidate], SourceReceipt]], dict[str, str]]:
    """Return reusable observations and their original per-source timestamps.

    Expired, failed, partial and local observations are omitted for refetching.
    """
    config.validate()
    checkpoint = path.expanduser().resolve()
    if checkpoint.is_dir():
        checkpoint /= "checkpoint.json"
    raw = _read_bounded(checkpoint)
    try:
        payload = json.loads(raw)
        _validate_json_tree(payload)
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
            raise ValueError("unsupported checkpoint schema")
        scope = payload.get("scope")
        if not isinstance(scope, dict) or type(scope.get("per_source")) is not int or scope != _scope(query, config):
            raise ValueError("resume requires the same query, sources, local roots and per-source limit")
        observed_at = payload["observed_at"]
        _timestamp_age(observed_at)
        raw_observations = payload["observations"]
        if not isinstance(raw_observations, dict) or set(raw_observations) - set(config.sources):
            raise ValueError("invalid checkpoint sources")
        observations = {}
        source_observed_at = {}
        for source, item in raw_observations.items():
            if not isinstance(item, dict) or not isinstance(item.get("candidates"), list):
                raise ValueError("invalid checkpoint observations")
            receipt = _decode(SourceReceipt, item["receipt"])
            if (
                receipt.source != source
                or receipt.requested != config.per_source
                or receipt.returned != len(item["candidates"])
                or len(item["candidates"]) > config.per_source
                or receipt.status not in {"ok", "empty", "partial", "failed"}
                or receipt.status == "empty" and receipt.returned != 0
            ):
                raise ValueError("checkpoint source or candidate budget mismatch")
            candidates = [_decode(Candidate, value) for value in item["candidates"]]
            if any(candidate.source != source for candidate in candidates):
                raise ValueError("checkpoint candidate source mismatch")
            source_timestamp = item.get("observed_at", observed_at)
            age = _timestamp_age(source_timestamp)
            if source == "local" or receipt.status not in {"ok", "empty"} or receipt.error or age > MAX_AGE_SECONDS:
                continue
            # Saved decisions and inspections must never grant authority on retry.
            for candidate in candidates:
                candidate.inspection = None
                candidate.score = None
                candidate.recommendation = "unscored"
                candidate.recommendation_status = "unscored"
                candidate.hard_blockers = []
                candidate.required_checks = []
                candidate.vulnerabilities_checked = False
                candidate.vulnerabilities = []
                candidate.vulnerability_evidence = []
                candidate.canonical_id = None
                candidate.normalized_license = None
                candidate.license_body_match = None
                candidate.license_review_required = False
                candidate.constraint_checks = []
                candidate.requirement_checks = []
                candidate.repository_evidence = {}
                candidate.local_path = None
            warning = f"reused local checkpoint observations from {source_timestamp}; metadata was not refetched"
            receipt.warnings = [value for value in receipt.warnings if not value.startswith("reused local checkpoint observations from ")]
            receipt.warnings.append(warning)
            observations[source] = (candidates, receipt)
            source_observed_at[source] = source_timestamp
        return observations, source_observed_at
    except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise ValueError("invalid discovery checkpoint") from exc
