"""Central fail-closed run/trace identity enforcement for runtime artifacts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class RequiredIdentityError(ValueError):
    """Raised when required run/trace identity is missing or invalid."""


def _normalize_identity(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RequiredIdentityError(f"{field_name} must be a non-empty string")
    return value.strip()


def ensure_required_ids(obj: dict, *, run_id: str, trace_id: str) -> dict:
    """Return a copy of *obj* with required run/trace identifiers injected.

    The input object is never mutated.
    """
    if not isinstance(obj, dict):
        raise RequiredIdentityError("obj must be a dict")

    normalized_run_id = _normalize_identity(run_id, field_name="run_id")
    normalized_trace_id = _normalize_identity(trace_id, field_name="trace_id")

    copied = deepcopy(obj)
    copied.setdefault("run_id", normalized_run_id)
    copied.setdefault("trace_id", normalized_trace_id)
    validate_required_ids(copied)
    return copied


def validate_required_ids(obj: dict) -> None:
    """Fail closed when required runtime identity fields are missing."""
    if not isinstance(obj, dict):
        raise RequiredIdentityError("obj must be a dict")

    missing = [
        field_name
        for field_name in ("run_id", "trace_id")
        if not isinstance(obj.get(field_name), str) or not str(obj.get(field_name)).strip()
    ]
    if missing:
        raise RequiredIdentityError(
            "artifact missing required identity fields: " + ", ".join(missing)
        )
