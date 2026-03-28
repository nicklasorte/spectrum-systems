"""Schema validation and IO for prompt queue execution result artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ExecutionResultArtifactValidationError(ValueError):
    """Raised when execution result artifact validation fails."""


def validate_execution_result_artifact(artifact: dict) -> None:
    if not isinstance(artifact, dict):
        raise ExecutionResultArtifactValidationError("Execution result artifact must be an object.")

    schema = load_schema("prompt_queue_execution_result")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: str(e.path))
    if errors:
        raise ExecutionResultArtifactValidationError("; ".join(error.message for error in errors))

    produced_refs = artifact.get("produced_artifact_refs")
    if isinstance(produced_refs, list):
        if produced_refs != sorted(produced_refs):
            raise ExecutionResultArtifactValidationError("produced_artifact_refs must be deterministic and sorted.")
        if len(set(produced_refs)) != len(produced_refs):
            raise ExecutionResultArtifactValidationError("produced_artifact_refs must not contain duplicates.")


def default_execution_result_path(work_item_id: str, queue_state_path: Path) -> Path:
    return queue_state_path.parent / "execution_results" / f"{work_item_id}.execution_result.json"


def read_execution_result_artifact(path: Path) -> dict:
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ExecutionResultArtifactValidationError(f"Unable to read execution result artifact: {exc}") from exc
    validate_execution_result_artifact(artifact)
    return artifact


def write_execution_result_artifact(artifact: dict, output_path: Path) -> Path:
    validate_execution_result_artifact(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return output_path
