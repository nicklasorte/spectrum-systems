"""Deterministic artifact construction helpers for HOP.

Every HOP artifact carries:
- ``artifact_id`` (deterministic, prefix-bound)
- ``artifact_type`` (canonical const)
- ``schema_ref`` (relative path under ``contracts/schemas/``)
- ``schema_version`` (semver)
- ``trace`` (primary + related)
- ``content_hash`` (sha256 over the canonical JSON of all fields except
  ``content_hash`` and ``artifact_id``)

The hash is computed over canonical JSON (sorted keys, no whitespace) so the
same logical payload always produces the same hash, regardless of insertion
order or formatting.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

CONTENT_HASH_SENTINEL = "sha256:" + "0" * 64

_HASH_EXCLUDED_FIELDS = ("content_hash", "artifact_id")


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_content_hash(payload: Mapping[str, Any]) -> str:
    """Compute the canonical sha256 content hash for an artifact payload.

    ``artifact_id`` and ``content_hash`` are excluded from the hashed surface
    so a stable hash can be derived before the id is assigned (the id is
    derived from the hash).
    """
    snapshot = {k: v for k, v in payload.items() if k not in _HASH_EXCLUDED_FIELDS}
    digest = hashlib.sha256(canonical_json(snapshot).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def short_hash(content_hash: str, length: int = 16) -> str:
    if not content_hash.startswith("sha256:"):
        raise ValueError(f"hop_artifact_invalid_content_hash:{content_hash}")
    return content_hash.split(":", 1)[1][:length]


def derive_artifact_id(prefix: str, content_hash: str) -> str:
    return f"{prefix}{short_hash(content_hash)}"


def finalize_artifact(payload: dict[str, Any], *, id_prefix: str) -> dict[str, Any]:
    """Compute the content hash and artifact id, returning a finalized payload.

    The function expects the caller to have provided every field except
    ``content_hash`` and ``artifact_id``. It mutates and returns ``payload``.
    """
    payload["content_hash"] = compute_content_hash(payload)
    payload["artifact_id"] = derive_artifact_id(id_prefix, payload["content_hash"])
    return payload


def make_trace(*, primary: str, related: list[str] | tuple[str, ...] = ()) -> dict[str, Any]:
    seen: set[str] = set()
    related_unique: list[str] = []
    for item in related:
        if item in seen:
            continue
        seen.add(item)
        related_unique.append(item)
    return {"primary": primary, "related": sorted(related_unique)}
