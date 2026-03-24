"""Shared helpers for canonical governed artifact envelope construction."""

from __future__ import annotations

from typing import Any


class ArtifactEnvelopeError(ValueError):
    """Raised when envelope inputs are invalid."""


def normalize_trace_refs(*, primary: str, related: list[str] | None = None) -> dict[str, Any]:
    primary_ref = str(primary).strip()
    if not primary_ref:
        raise ArtifactEnvelopeError("trace_refs.primary must be a non-empty string")

    normalized_related = sorted(
        {
            str(item).strip()
            for item in (related or [])
            if isinstance(item, str) and str(item).strip() and str(item).strip() != primary_ref
        }
    )
    return {
        "primary": primary_ref,
        "related": normalized_related,
    }


def validate_trace_refs(trace_refs: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(trace_refs, dict):
        raise ArtifactEnvelopeError("trace_refs must be an object")

    allowed = {"primary", "related"}
    unknown = sorted(set(trace_refs.keys()) - allowed)
    if unknown:
        raise ArtifactEnvelopeError(f"trace_refs contains unsupported keys: {unknown}")

    primary = trace_refs.get("primary")
    related = trace_refs.get("related", [])
    if not isinstance(related, list):
        raise ArtifactEnvelopeError("trace_refs.related must be an array")

    return normalize_trace_refs(primary=str(primary or ""), related=[str(item) for item in related])


def build_artifact_envelope(
    *,
    artifact_id: str,
    timestamp: str,
    schema_version: str,
    primary_trace_ref: str,
    related_trace_refs: list[str] | None = None,
) -> dict[str, Any]:
    artifact_id_value = str(artifact_id).strip()
    if not artifact_id_value:
        raise ArtifactEnvelopeError("id must be a non-empty string")

    timestamp_value = str(timestamp).strip()
    if not timestamp_value:
        raise ArtifactEnvelopeError("timestamp must be a non-empty string")

    schema_version_value = str(schema_version).strip()
    if not schema_version_value:
        raise ArtifactEnvelopeError("schema_version must be a non-empty string")

    return {
        "id": artifact_id_value,
        "timestamp": timestamp_value,
        "schema_version": schema_version_value,
        "trace_refs": normalize_trace_refs(primary=primary_trace_ref, related=related_trace_refs),
    }
