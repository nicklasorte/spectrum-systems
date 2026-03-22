"""Schema validation and IO for prompt queue next-step action artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class NextStepActionArtifactValidationError(ValueError):
    """Raised when next-step action artifact validation fails."""


def validate_next_step_action_artifact(artifact: dict) -> None:
    schema = load_schema("prompt_queue_next_step_action")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: str(e.path))
    if errors:
        raise NextStepActionArtifactValidationError("; ".join(error.message for error in errors))


def default_next_step_action_path(work_item_id: str, queue_state_path: Path) -> Path:
    stem = queue_state_path.stem
    return queue_state_path.parent / "next_step_actions" / f"{stem}.{work_item_id}.next_step_action.json"


def write_next_step_action_artifact(artifact: dict, output_path: Path) -> Path:
    validate_next_step_action_artifact(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2)
    return output_path
