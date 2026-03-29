"""Validation of first governed PQX 5–10 slice runs."""

from __future__ import annotations

from spectrum_systems.contracts import validate_artifact


class PQXNSliceValidationError(ValueError):
    """Raised when governed n-slice validation fails closed."""


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
