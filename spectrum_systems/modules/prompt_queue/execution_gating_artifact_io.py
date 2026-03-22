"""Schema validation and IO for prompt queue execution gating decision artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ExecutionGatingArtifactValidationError(ValueError):
    """Raised when execution gating decision artifact validation fails."""


def validate_execution_gating_decision_artifact(artifact: dict) -> None:
    schema = load_schema("prompt_queue_execution_gating_decision")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: str(e.path))
    if errors:
        raise ExecutionGatingArtifactValidationError("; ".join(error.message for error in errors))


def write_execution_gating_decision_artifact(artifact: dict, output_path: Path) -> Path:
    validate_execution_gating_decision_artifact(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2)
    return output_path


def read_json_artifact(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
