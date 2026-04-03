"""Deterministic storage helper for governed ``roadmap_artifact`` artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


_REPO_SOURCE_REF_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[^#\s]+$")


class RoadmapArtifactStoreError(ValueError):
    """Raised when roadmap artifact payloads or storage operations fail closed."""


def _enforce_repo_trace_link(source_ref: Any) -> None:
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise RoadmapArtifactStoreError("roadmap_artifact.source_ref must be a non-empty string")

    trimmed = source_ref.strip()
    if _REPO_SOURCE_REF_PATTERN.match(trimmed):
        raise RoadmapArtifactStoreError(
            "roadmap_artifact.source_ref repo refs must include a trace link fragment (e.g., owner/repo@ref#trace:xyz)"
        )


def validate_roadmap_artifact(artifact: Dict[str, Any]) -> None:
    schema = load_schema("roadmap_artifact")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise RoadmapArtifactStoreError(f"roadmap_artifact failed schema validation: {details}")

    _enforce_repo_trace_link(artifact.get("source_ref"))


def write_roadmap_artifact(artifact: Dict[str, Any], output_path: Path) -> Path:
    validate_roadmap_artifact(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def read_roadmap_artifact(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RoadmapArtifactStoreError(f"roadmap_artifact artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RoadmapArtifactStoreError(f"roadmap_artifact artifact is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise RoadmapArtifactStoreError("roadmap_artifact artifact root must be a JSON object")
    validate_roadmap_artifact(payload)
    return payload


__all__ = [
    "RoadmapArtifactStoreError",
    "read_roadmap_artifact",
    "validate_roadmap_artifact",
    "write_roadmap_artifact",
]
