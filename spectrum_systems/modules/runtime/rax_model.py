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


def _is_semantically_sufficient_intent(intent: str) -> bool:
    normalized = " ".join(intent.lower().split())
    tokens = [piece for piece in normalized.replace("-", " ").split(" ") if piece]
    if len(tokens) < 4:
        return False

    generic_placeholders = {
        "todo",
        "tbd",
        "placeholder",
        "generic",
        "misc",
        "n/a",
        "none",
        "lorem",
        "ipsum",
        "asdf",
    }
    if normalized in generic_placeholders:
        return False
    if all(token in generic_placeholders for token in tokens):
        return False

    if len(set(tokens)) == 1:
        return False

    meaningful_tokens = [token for token in tokens if len(token) >= 4 and token not in generic_placeholders]
    return len(meaningful_tokens) >= 3


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

    raw_dependencies = [_require_non_empty_string(dep, "depends_on[]") for dep in depends_on_raw]
    normalized_dependencies = tuple(sorted(set(raw_dependencies)))
    if len(raw_dependencies) != len(normalized_dependencies):
        raise RAXModelError("depends_on normalization ambiguity: lossy dependency collapse detected")

    intent = _require_non_empty_string(payload["intent"], "intent")
    if not _is_semantically_sufficient_intent(intent):
        raise RAXModelError("intent semantic insufficiency: content is too weak or placeholder-like")

    return CanonicalRoadmapStep(
        roadmap_id=_require_non_empty_string(payload["roadmap_id"], "roadmap_id"),
        roadmap_group=_require_non_empty_string(payload["roadmap_group"], "roadmap_group"),
        step_id=_require_non_empty_string(payload["step_id"], "step_id"),
        owner=_require_non_empty_string(payload["owner"], "owner"),
        intent=intent,
        depends_on=normalized_dependencies,
        source_authority_ref=_require_non_empty_string(payload["source_authority_ref"], "source_authority_ref"),
        source_version=_require_non_empty_string(payload["source_version"], "source_version"),
        input_freshness_ref=_require_non_empty_string(payload["input_freshness_ref"], "input_freshness_ref"),
        input_provenance_ref=_require_non_empty_string(payload["input_provenance_ref"], "input_provenance_ref"),
    )
