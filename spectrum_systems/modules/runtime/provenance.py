"""Canonical provenance builder/validator for Tier-1 governed emitters."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from jsonschema import Draft202012Validator, FormatChecker


class ProvenanceError(Exception):
    """Raised when canonical provenance is missing, partial, or malformed."""


_CANONICAL_PROVENANCE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "run_id",
        "trace_id",
        "span_id",
        "parent_span_id",
        "source_artifacts",
        "generator",
        "timestamp",
        "artifact",
    ],
    "properties": {
        "run_id": {"type": "string", "minLength": 1},
        "trace_id": {"type": "string", "minLength": 1},
        "span_id": {"type": "string", "minLength": 1},
        "parent_span_id": {"type": "string", "minLength": 1},
        "source_artifacts": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["artifact_type", "artifact_id"],
                "properties": {
                    "artifact_type": {"type": "string", "minLength": 1},
                    "artifact_id": {"type": "string", "minLength": 1},
                },
            },
        },
        "generator": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "version"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "version": {"type": "string", "minLength": 1},
            },
        },
        "timestamp": {"type": "string", "format": "date-time"},
        "artifact": {
            "type": "object",
            "additionalProperties": False,
            "required": ["artifact_type", "artifact_id", "schema_version"],
            "properties": {
                "artifact_type": {"type": "string", "minLength": 1},
                "artifact_id": {"type": "string", "minLength": 1},
                "schema_version": {"type": "string", "minLength": 1},
            },
        },
    },
}

_PLACEHOLDER_VALUES = {"unknown", "unknown-trace", "unknown-span", "unknown-run", "", "n/a", "none"}


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _reject_placeholder(field: str, value: str) -> None:
    if value.strip().lower() in _PLACEHOLDER_VALUES:
        raise ProvenanceError(f"canonical provenance field '{field}' cannot use placeholder value: {value!r}")


def _normalize_source_artifacts(source_artifacts: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in source_artifacts:
        if not isinstance(item, dict):
            raise ProvenanceError("source_artifacts entries must be objects")
        artifact_type = str(item.get("artifact_type") or "").strip()
        artifact_id = str(item.get("artifact_id") or "").strip()
        if not artifact_type or not artifact_id:
            raise ProvenanceError("source_artifacts entries must include artifact_type and artifact_id")
        _reject_placeholder("source_artifacts.artifact_type", artifact_type)
        _reject_placeholder("source_artifacts.artifact_id", artifact_id)
        normalized.append({"artifact_type": artifact_type, "artifact_id": artifact_id})
    if not normalized:
        raise ProvenanceError("source_artifacts must contain at least one entry")
    return normalized


def validate_canonical_provenance(provenance: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(_CANONICAL_PROVENANCE_SCHEMA, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(provenance), key=lambda err: list(err.path))
    messages = [f"{'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}" for err in errors]

    for field in ("run_id", "trace_id", "span_id", "parent_span_id"):
        value = provenance.get(field)
        if isinstance(value, str):
            if value.strip().lower() in _PLACEHOLDER_VALUES:
                messages.append(f"{field}: placeholder values are forbidden")

    generator = provenance.get("generator")
    if isinstance(generator, dict):
        for field in ("name", "version"):
            value = generator.get(field)
            if isinstance(value, str) and value.strip().lower() in _PLACEHOLDER_VALUES:
                messages.append(f"generator/{field}: placeholder values are forbidden")

    return messages


def assert_canonical_provenance(provenance: Dict[str, Any]) -> None:
    errors = validate_canonical_provenance(provenance)
    if errors:
        raise ProvenanceError("canonical provenance validation failed: " + "; ".join(errors))


def build_canonical_provenance(
    *,
    run_id: str,
    trace_id: str,
    span_id: str,
    parent_span_id: str,
    source_artifacts: Iterable[Dict[str, Any]],
    generator_name: str,
    generator_version: str,
    artifact_type: str,
    artifact_id: str,
    schema_version: str,
    timestamp: str | None = None,
) -> Dict[str, Any]:
    for field_name, field_value in (
        ("run_id", run_id),
        ("trace_id", trace_id),
        ("span_id", span_id),
        ("parent_span_id", parent_span_id),
        ("generator_name", generator_name),
        ("generator_version", generator_version),
        ("artifact_type", artifact_type),
        ("artifact_id", artifact_id),
        ("schema_version", schema_version),
    ):
        if not isinstance(field_value, str) or not field_value.strip():
            raise ProvenanceError(f"canonical provenance missing required field: {field_name}")
        _reject_placeholder(field_name, field_value)

    provenance = {
        "run_id": run_id.strip(),
        "trace_id": trace_id.strip(),
        "span_id": span_id.strip(),
        "parent_span_id": parent_span_id.strip(),
        "source_artifacts": _normalize_source_artifacts(source_artifacts),
        "generator": {
            "name": generator_name.strip(),
            "version": generator_version.strip(),
        },
        "timestamp": str(timestamp or _now_iso()),
        "artifact": {
            "artifact_type": artifact_type.strip(),
            "artifact_id": artifact_id.strip(),
            "schema_version": schema_version.strip(),
        },
    }
    assert_canonical_provenance(provenance)
    return provenance


def revalidate_mutated_artifact(
    artifact: Dict[str, Any],
    *,
    schema_validator: Any,
    artifact_label: str,
) -> Dict[str, Any]:
    mutated = deepcopy(artifact)
    provenance = mutated.get("provenance")
    if not isinstance(provenance, dict):
        raise ProvenanceError(f"{artifact_label} missing canonical provenance")
    assert_canonical_provenance(provenance)

    schema_errors = list(schema_validator(mutated))
    if schema_errors:
        raise ProvenanceError(f"{artifact_label} schema validation failed after mutation: {'; '.join(schema_errors)}")
    return mutated


__all__ = [
    "ProvenanceError",
    "assert_canonical_provenance",
    "build_canonical_provenance",
    "revalidate_mutated_artifact",
    "validate_canonical_provenance",
]
