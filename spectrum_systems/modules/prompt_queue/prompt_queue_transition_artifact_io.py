"""Schema validation and IO for unified prompt queue transition decision artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class PromptQueueTransitionArtifactValidationError(ValueError):
    """Raised when prompt queue transition decision artifact validation fails."""


def validate_prompt_queue_transition_decision_artifact(artifact: dict) -> None:
    schema = load_schema("prompt_queue_transition_decision")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: str(e.path))
    if errors:
        raise PromptQueueTransitionArtifactValidationError("; ".join(error.message for error in errors))


def write_prompt_queue_transition_decision_artifact(artifact: dict, output_path: Path) -> Path:
    validate_prompt_queue_transition_decision_artifact(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2)
    return output_path
