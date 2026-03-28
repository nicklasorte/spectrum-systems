"""Schema validation and deterministic IO for prompt queue review findings artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class FindingsArtifactValidationError(ValueError):
    """Raised when findings artifact validation fails."""


def validate_findings_artifact(artifact: dict) -> None:
    if not isinstance(artifact, dict):
        raise FindingsArtifactValidationError("Findings artifact must be an object.")
    schema = load_schema("prompt_queue_review_findings")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: str(e.path))
    if errors:
        raise FindingsArtifactValidationError("; ".join(error.message for error in errors))


def write_findings_artifact(artifact: dict, output_path: Path) -> Path:
    validate_findings_artifact(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return output_path


def read_findings_artifact(path: Path) -> dict:
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FindingsArtifactValidationError(f"Unable to read findings artifact: {exc}") from exc

    validate_findings_artifact(artifact)
    return artifact


def read_json_artifact(path: Path) -> Any:
    artifact = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(artifact, dict):
        validate_findings_artifact(artifact)
    else:
        raise FindingsArtifactValidationError("Artifact payload must be an object.")
    return artifact
