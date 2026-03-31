"""Cycle manifest schema + semantic validator."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.orchestration.sequence_transition_policy import SEQUENCE_STATES


class CycleManifestError(ValueError):
    """Raised when cycle manifest fails schema or semantic validation."""


def _parse_timestamp(value: Any, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise CycleManifestError(f"{field_name} must be a non-empty RFC3339 string or null")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CycleManifestError(f"{field_name} is not a valid ISO timestamp") from exc


def validate_cycle_manifest(manifest: dict) -> None:
    """Validate cycle_manifest contract and semantic invariants."""
    schema = load_schema("cycle_manifest")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(manifest), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise CycleManifestError(f"cycle_manifest schema validation failed: {details}")

    if manifest.get("current_state") == "blocked" and not manifest.get("blocking_issues"):
        raise CycleManifestError("blocked state requires non-empty blocking_issues")

    eligible_step_ids_snapshot = manifest.get("eligible_step_ids_snapshot")
    if not isinstance(eligible_step_ids_snapshot, list):
        raise CycleManifestError("eligible_step_ids_snapshot must be a list")

    selected_step_id = manifest.get("selected_step_id")
    if isinstance(selected_step_id, str) and selected_step_id not in eligible_step_ids_snapshot:
        raise CycleManifestError("selected_step_id must be present in eligible_step_ids_snapshot")

    decision_blocked = manifest.get("decision_blocked")
    if decision_blocked is True and not manifest.get("blocking_issues"):
        raise CycleManifestError("decision_blocked=true requires non-empty blocking_issues")

    started_at = _parse_timestamp(manifest.get("execution_started_at"), field_name="execution_started_at")
    completed_at = _parse_timestamp(manifest.get("execution_completed_at"), field_name="execution_completed_at")
    updated_at = _parse_timestamp(manifest.get("updated_at"), field_name="updated_at")

    if started_at and completed_at and completed_at < started_at:
        raise CycleManifestError("execution_completed_at must be >= execution_started_at")
    if completed_at and updated_at and updated_at < completed_at:
        raise CycleManifestError("updated_at must be >= execution_completed_at")

    state = manifest.get("current_state")
    if manifest.get("sequence_mode") == "three_slice" and state in SEQUENCE_STATES:
        trace_id = manifest.get("sequence_trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            raise CycleManifestError("sequence state requires non-empty sequence_trace_id")
        lineage = manifest.get("sequence_lineage")
        if not isinstance(lineage, list) or not lineage:
            raise CycleManifestError("sequence state requires non-empty sequence_lineage")
        history = manifest.get("sequence_transition_history")
        if not isinstance(history, list):
            raise CycleManifestError("sequence_transition_history must be a list")
        for idx, entry in enumerate(history):
            if not isinstance(entry, dict):
                raise CycleManifestError(f"sequence_transition_history[{idx}] must be an object")
            from_state = entry.get("from_state")
            to_state = entry.get("to_state")
            if from_state not in SEQUENCE_STATES or to_state not in SEQUENCE_STATES:
                raise CycleManifestError("sequence_transition_history includes unknown state")
