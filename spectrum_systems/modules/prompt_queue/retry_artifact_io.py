"""Artifact IO boundary for prompt queue retry decision artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class RetryArtifactValidationError(ValueError):
    """Raised when retry artifact validation fails."""


class RetryArtifactIOError(ValueError):
    """Raised when retry artifact writing fails."""


def validate_retry_decision_artifact(artifact: dict) -> None:
    schema = load_schema("prompt_queue_retry_decision")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: str(e.path))
    if errors:
        raise RetryArtifactValidationError("; ".join(error.message for error in errors))


def default_retry_decision_path(*, work_item_id: str, root_dir: Path) -> Path:
    return root_dir / "artifacts" / "prompt_queue" / "retry_decisions" / f"{work_item_id}.retry_decision.json"


def write_retry_decision_artifact(*, artifact: dict, output_path: Path) -> Path:
    try:
        validate_retry_decision_artifact(artifact)
    except RetryArtifactValidationError as exc:
        raise RetryArtifactIOError(str(exc)) from exc

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(artifact, handle, indent=2)
    except OSError as exc:
        raise RetryArtifactIOError(f"Failed to write retry decision artifact: {output_path}") from exc
    return output_path


def read_json_artifact(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
