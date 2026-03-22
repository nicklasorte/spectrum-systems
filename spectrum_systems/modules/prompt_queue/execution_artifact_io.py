"""Schema validation and IO for prompt queue execution result artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ExecutionResultArtifactValidationError(ValueError):
    """Raised when execution result artifact validation fails."""


def validate_execution_result_artifact(artifact: dict) -> None:
    schema = load_schema("prompt_queue_execution_result")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: str(e.path))
    if errors:
        raise ExecutionResultArtifactValidationError("; ".join(error.message for error in errors))


def default_execution_result_path(work_item_id: str, queue_state_path: Path) -> Path:
    return queue_state_path.parent / "execution_results" / f"{work_item_id}.execution_result.json"


def write_execution_result_artifact(artifact: dict, output_path: Path) -> Path:
    validate_execution_result_artifact(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2)
    return output_path
