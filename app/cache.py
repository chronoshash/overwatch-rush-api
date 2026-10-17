"""ETag helpers.

The dataset is immutable while the process runs, so an ETag can be derived
from (dataset version, updated_at, path, normalized query). That is a strong,
deterministic validator and avoids buffering response bodies in middleware.
"""

from __future__ import annotations

import hashlib
from urllib.parse import urlencode


def normalize_query(query_pairs: list[tuple[str, str]]) -> str:
    return urlencode(sorted(query_pairs))


def make_etag(
    data_version: str,
    updated_at_iso: str,
    path: str,
    query_pairs: list[tuple[str, str]],
) -> str:
    key = "|".join((data_version, updated_at_iso, path, normalize_query(query_pairs)))
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return f'"{digest}"'
