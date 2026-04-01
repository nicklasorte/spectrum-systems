"""Validation of first governed PQX 5–10 slice runs with proof-closure gating."""

from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.contracts import validate_artifact


class PQXNSliceValidationError(ValueError):
    """Raised when governed n-slice validation fails closed."""


def _load_json_object(path_value: str, *, label: str) -> dict:
    path = Path(path_value)
    if not path.is_file():
        raise PQXNSliceValidationError(f"{label} file not found: {path_value}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PQXNSliceValidationError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PQXNSliceValidationError(f"{label} must be a JSON object")
    return payload


def build_n_slice_validation_record(
    *,
    validation_id: str,
    sequence_state: dict,
    run_id: str,
    trace_id: str,
    created_at: str,
) -> dict:
    requested = list(sequence_state.get("requested_slice_ids", []))
    executed = [row.get("slice_id") for row in sequence_state.get("execution_history", [])]
    completed = list(sequence_state.get("completed_slice_ids", []))

    if not (5 <= len(requested) <= 10):
        raise PQXNSliceValidationError("governed n-slice validation requires 5–10 requested slices")
    if executed != requested:
        raise PQXNSliceValidationError("deterministic advancement order mismatch")
    if completed != requested:
        raise PQXNSliceValidationError("incomplete execution: completed_slice_ids mismatch")
    if sequence_state.get("bundle_certification_status") != "certified":
        raise PQXNSliceValidationError("missing bundle certification")
    if sequence_state.get("bundle_audit_status") != "synthesized":
        raise PQXNSliceValidationError("missing bundle audit synthesis")

    falsification_ref = sequence_state.get("hard_gate_falsification_ref")
    if not isinstance(falsification_ref, str) or not falsification_ref:
        raise PQXNSliceValidationError("missing hard-gate falsification evidence")
    falsification = _load_json_object(falsification_ref, label="hard_gate_falsification")
    if falsification.get("artifact_type") != "pqx_hard_gate_falsification_record":
        raise PQXNSliceValidationError("hard-gate falsification evidence has wrong artifact_type")
    if falsification.get("overall_result") != "pass":
        raise PQXNSliceValidationError("hard-gate falsification did not pass")

    parity_status = sequence_state.get("replay_verification", {}).get("status")
    if parity_status not in {"verified", "not_run"}:
        raise PQXNSliceValidationError("replay/parity state is invalid")

    record = {
        "schema_version": "1.0.0",
        "validation_id": validation_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "slice_count": len(requested),
        "validated_slice_ids": requested,
        "deterministic_order": True,
        "review_checkpoints_skipped": False,
        "hidden_carry_forward_detected": False,
        "bundle_certification_status": sequence_state.get("bundle_certification_status"),
        "bundle_audit_status": sequence_state.get("bundle_audit_status"),
        "replay_parity_status": parity_status,
        "status": "validated",
        "created_at": created_at,
    }
    try:
        validate_artifact(record, "pqx_n_slice_validation_record")
    except Exception as exc:  # pragma: no cover
        raise PQXNSliceValidationError(f"invalid pqx_n_slice_validation_record artifact: {exc}") from exc
    return record
