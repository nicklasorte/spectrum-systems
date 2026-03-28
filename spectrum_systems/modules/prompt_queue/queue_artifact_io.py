"""Artifact validation and IO for governed prompt queue MVP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ArtifactValidationError(ValueError):
    """Raised when artifact validation fails."""


def validate_work_item(work_item: dict) -> None:
    _validate(work_item, "prompt_queue_work_item")


def validate_queue_state(queue_state: dict) -> None:
    _validate(queue_state, "prompt_queue_state")


def validate_review_attempt(review_attempt: dict) -> None:
    _validate(review_attempt, "prompt_queue_review_attempt")


def validate_review_invocation_result(review_invocation_result: dict) -> None:
    _validate(review_invocation_result, "prompt_queue_review_invocation_result")


def validate_review_parsing_handoff(review_parsing_handoff: dict) -> None:
    _validate(review_parsing_handoff, "prompt_queue_review_parsing_handoff")


def validate_findings_reentry(findings_reentry: dict) -> None:
    _validate(findings_reentry, "prompt_queue_findings_reentry")


def validate_repair_prompt_artifact(repair_prompt_artifact: dict) -> None:
    _validate(repair_prompt_artifact, "prompt_queue_repair_prompt")


def validate_loop_continuation(loop_continuation: dict) -> None:
    _validate(loop_continuation, "prompt_queue_loop_continuation")


def validate_observability_snapshot(observability_snapshot: dict) -> None:
    _validate(observability_snapshot, "prompt_queue_observability_snapshot")


def validate_resume_checkpoint(checkpoint: dict) -> None:
    _validate(checkpoint, "prompt_queue_resume_checkpoint")


def validate_replay_record(record: dict) -> None:
    _validate(record, "prompt_queue_replay_record")


def _validate(instance: Any, schema_name: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: str(e.path))
    if errors:
        raise ArtifactValidationError(
            "; ".join(error.message for error in errors)
        )


def read_json_artifact(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_artifact(artifact: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2)
    return output_path
