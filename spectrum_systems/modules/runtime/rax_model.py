"""Canonical RAX internal model for compact roadmap step intake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from spectrum_systems.contracts import validate_artifact


class RAXModelError(ValueError):
    """Raised when upstream input cannot form a canonical RAX model."""


@dataclass(frozen=True)
class CanonicalRoadmapStep:
    """Deterministic internal representation used by RAX translation and assurance."""

    roadmap_id: str
    roadmap_group: str
    step_id: str
    owner: str
    intent: str
    depends_on: tuple[str, ...]
    source_authority_ref: str
    source_version: str
    input_freshness_ref: str
    input_provenance_ref: str


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RAXModelError(f"{field_name} must be a non-empty string")
    return value.strip()


def load_compact_roadmap_step(payload: dict[str, Any]) -> CanonicalRoadmapStep:
    """Load and schema-validate a compact roadmap envelope before normalization."""
    validate_artifact(payload, "rax_upstream_input_envelope")
    return normalize_compact_roadmap_step(payload)


def normalize_compact_roadmap_step(payload: dict[str, Any]) -> CanonicalRoadmapStep:
    """Normalize upstream envelope into one deterministic canonical internal model."""
    required_fields = (
        "roadmap_id",
        "roadmap_group",
        "step_id",
        "owner",
        "intent",
        "depends_on",
        "source_authority_ref",
        "source_version",
        "input_freshness_ref",
        "input_provenance_ref",
    )
    for field in required_fields:
        if field not in payload:
            raise RAXModelError(f"missing required field: {field}")

    depends_on_raw = payload["depends_on"]
    if not isinstance(depends_on_raw, list):
        raise RAXModelError("depends_on must be a list")

    normalized_dependencies = tuple(sorted({_require_non_empty_string(dep, "depends_on[]") for dep in depends_on_raw}))

    return CanonicalRoadmapStep(
        roadmap_id=_require_non_empty_string(payload["roadmap_id"], "roadmap_id"),
        roadmap_group=_require_non_empty_string(payload["roadmap_group"], "roadmap_group"),
        step_id=_require_non_empty_string(payload["step_id"], "step_id"),
        owner=_require_non_empty_string(payload["owner"], "owner"),
        intent=_require_non_empty_string(payload["intent"], "intent"),
        depends_on=normalized_dependencies,
        source_authority_ref=_require_non_empty_string(payload["source_authority_ref"], "source_authority_ref"),
        source_version=_require_non_empty_string(payload["source_version"], "source_version"),
        input_freshness_ref=_require_non_empty_string(payload["input_freshness_ref"], "input_freshness_ref"),
        input_provenance_ref=_require_non_empty_string(payload["input_provenance_ref"], "input_provenance_ref"),
    )
