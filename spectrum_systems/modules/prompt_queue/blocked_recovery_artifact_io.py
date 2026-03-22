"""Artifact IO boundary for prompt queue blocked-recovery decision artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class BlockedRecoveryArtifactValidationError(ValueError):
    """Raised when blocked-recovery artifact validation fails."""


class BlockedRecoveryArtifactIOError(ValueError):
    """Raised when blocked-recovery artifact writing fails."""


def validate_blocked_recovery_decision_artifact(artifact: dict) -> None:
    schema = load_schema("prompt_queue_blocked_recovery_decision")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: str(e.path))
    if errors:
        raise BlockedRecoveryArtifactValidationError("; ".join(error.message for error in errors))


def default_blocked_recovery_decision_path(*, work_item_id: str, root_dir: Path) -> Path:
    return root_dir / "artifacts" / "prompt_queue" / "blocked_recovery_decisions" / f"{work_item_id}.blocked_recovery.json"


def write_blocked_recovery_decision_artifact(*, artifact: dict, output_path: Path) -> Path:
    try:
        validate_blocked_recovery_decision_artifact(artifact)
    except BlockedRecoveryArtifactValidationError as exc:
        raise BlockedRecoveryArtifactIOError(str(exc)) from exc

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(artifact, handle, indent=2)
    except OSError as exc:
        raise BlockedRecoveryArtifactIOError(f"Failed to write blocked recovery decision artifact: {output_path}") from exc
    return output_path


def read_json_artifact(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
