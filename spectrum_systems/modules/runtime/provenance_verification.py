"""Deterministic provenance identity verification helpers for runtime seams."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Tuple


class ProvenanceVerificationError(ValueError):
    """Raised when governed run/trace provenance identity checks fail."""


def _require_non_empty_string(value: Any, *, field_name: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProvenanceVerificationError(
            f"PROVENANCE_IDENTITY_INVALID: {label}.{field_name} must be a non-empty string"
        )
    return value.strip()


def extract_identity(payload: Dict[str, Any], *, label: str) -> Tuple[str, str]:
    """Return normalized ``(run_id, trace_id)`` from payload.

    The function does not mutate *payload*.
    """
    if not isinstance(payload, dict):
        raise ProvenanceVerificationError(f"PROVENANCE_IDENTITY_INVALID: {label} must be an object")

    run_id = _require_non_empty_string(payload.get("run_id"), field_name="run_id", label=label)
    trace_id = _require_non_empty_string(payload.get("trace_id"), field_name="trace_id", label=label)
    return run_id, trace_id


def validate_required_identity(payload: Dict[str, Any], *, label: str) -> None:
    """Fail closed when run_id/trace_id are missing or invalid."""
    extract_identity(payload, label=label)


def assert_inherited_trace_id(
    parent_payload: Dict[str, Any],
    child_payload: Dict[str, Any],
    *,
    parent_label: str,
    child_label: str,
    allow_trace_override: bool = False,
) -> None:
    """Enforce trace inheritance from parent to child unless explicitly allowed."""
    _, parent_trace = extract_identity(parent_payload, label=parent_label)
    _, child_trace = extract_identity(child_payload, label=child_label)
    if allow_trace_override:
        return
    if parent_trace != child_trace:
        raise ProvenanceVerificationError(
            "PROVENANCE_TRACE_MISMATCH: "
            f"{child_label}.trace_id={child_trace!r} does not match inherited "
            f"{parent_label}.trace_id={parent_trace!r}"
        )


def assert_linked_identity_consistency(
    upstream_payload: Dict[str, Any],
    linked_payload: Dict[str, Any],
    *,
    upstream_label: str,
    linked_label: str,
    require_same_run: bool = True,
    allow_cross_run_reference: bool = False,
    allow_trace_override: bool = False,
) -> None:
    """Verify linked artifact identity consistency for downstream seams."""
    upstream_run, upstream_trace = extract_identity(upstream_payload, label=upstream_label)
    linked_run, linked_trace = extract_identity(linked_payload, label=linked_label)

    if require_same_run and not allow_cross_run_reference and upstream_run != linked_run:
        raise ProvenanceVerificationError(
            "PROVENANCE_RUN_MISMATCH: "
            f"{linked_label}.run_id={linked_run!r} does not match "
            f"{upstream_label}.run_id={upstream_run!r}"
        )

    if not allow_trace_override and linked_trace != upstream_trace:
        raise ProvenanceVerificationError(
            "PROVENANCE_TRACE_MISMATCH: "
            f"{linked_label}.trace_id={linked_trace!r} does not match "
            f"{upstream_label}.trace_id={upstream_trace!r}"
        )


def assert_persisted_reload_identity(
    persisted_payload: Dict[str, Any],
    reloaded_payload: Dict[str, Any],
    *,
    persisted_label: str,
    reloaded_label: str,
) -> None:
    """Verify persisted and reloaded artifacts retain identical run/trace IDs."""
    before = deepcopy(persisted_payload)
    after = deepcopy(reloaded_payload)
    before_run, before_trace = extract_identity(before, label=persisted_label)
    after_run, after_trace = extract_identity(after, label=reloaded_label)

    if before_run != after_run or before_trace != after_trace:
        raise ProvenanceVerificationError(
            "PROVENANCE_RELOAD_IDENTITY_MISMATCH: "
            f"persisted=({before_run!r}, {before_trace!r}) reloaded=({after_run!r}, {after_trace!r})"
        )
