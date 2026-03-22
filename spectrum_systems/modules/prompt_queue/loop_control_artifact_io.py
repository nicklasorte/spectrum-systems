"""Schema validation and IO for prompt queue loop control decision artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class LoopControlArtifactValidationError(ValueError):
    """Raised when loop control decision artifact validation fails."""


def validate_loop_control_decision_artifact(artifact: dict) -> None:
    schema = load_schema("prompt_queue_loop_control_decision")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: str(e.path))
    if errors:
        raise LoopControlArtifactValidationError("; ".join(error.message for error in errors))


def default_loop_control_decision_path(work_item_id: str) -> Path:
    return Path("artifacts/prompt_queue/loop_control") / f"{work_item_id}.loop_control_decision.json"


def write_loop_control_decision_artifact(artifact: dict, output_path: Path) -> Path:
    validate_loop_control_decision_artifact(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2)
    return output_path


def read_json_artifact(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
