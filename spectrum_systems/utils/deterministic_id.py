"""Canonical deterministic ID utilities for governance artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    """Serialize payload deterministically for stable identity hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def deterministic_id(
    *,
    prefix: str,
    payload: Any,
    namespace: str | None = None,
    digest_length: int = 16,
) -> str:
    """Build a deterministic ID from canonical structured payload."""
    canonical_payload = canonical_json(payload)
    seed = f"{namespace}::{canonical_payload}" if namespace else canonical_payload
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:digest_length]
    return f"{prefix}-{digest}"
