"""
hash_utils — spectrum_systems/modules/runtime/hash_utils.py

Canonical content hashing for governed artifacts.

Policy (H01B-3):
- Excludes content_hash (self-reference — would be circular)
- Excludes trace (routing metadata, not artifact content)
- Excludes created_at (operational timestamp, not artifact content)
- Uses sorted-key JSON with no whitespace for determinism
- Same payload always produces the same hash regardless of field insertion order,
  trace context, or creation timestamp.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

_EXCLUDED_FIELDS = frozenset([
    "content_hash",
    "trace",
    "created_at",
])


def compute_content_hash(artifact_payload: Dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash of artifact payload fields.

    Excludes: content_hash (self-reference), trace (metadata), created_at (timestamp).
    Returns 'sha256:<hex>'.

    Canonicalization rules:
    - Keys sorted lexicographically at all nesting levels (via sort_keys=True)
    - No whitespace (separators=(",", ":"))
    - ASCII-safe encoding (ensure_ascii=True)
    """
    hashable = {k: v for k, v in artifact_payload.items() if k not in _EXCLUDED_FIELDS}
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


__all__ = ["compute_content_hash"]
