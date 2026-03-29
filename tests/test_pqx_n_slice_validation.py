from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.pqx_n_slice_validation import (
    PQXNSliceValidationError,
    build_n_slice_validation_record,
)


def _state(slice_ids: list[str]) -> dict:
    return {
        "requested_slice_ids": slice_ids,
        "completed_slice_ids": list(slice_ids),
        "execution_history": [{"slice_id": s} for s in slice_ids],
        "bundle_certification_status": "certified",
        "bundle_audit_status": "synthesized",
        "replay_verification": {"status": "verified"},
    }


def test_five_slice_happy_path_validates() -> None:
    record = build_n_slice_validation_record(
        validation_id="val-1",
        sequence_state=_state(["S1", "S2", "S3", "S4", "S5"]),
        run_id="run-1",
        trace_id="trace-1",
        created_at="2026-03-29T00:00:00Z",
    )
    assert record["status"] == "validated"


def test_longer_run_with_pause_resume_validates() -> None:
    state = _state(["S1", "S2", "S3", "S4", "S5", "S6", "S7"])
    state["replay_verification"] = {"status": "not_run"}
    record = build_n_slice_validation_record(
        validation_id="val-2",
        sequence_state=state,
        run_id="run-2",
        trace_id="trace-2",
        created_at="2026-03-29T00:00:00Z",
    )
    assert record["slice_count"] == 7


def test_validation_fails_on_missing_certification() -> None:
    state = _state(["S1", "S2", "S3", "S4", "S5"])
    state["bundle_certification_status"] = "pending"
    with pytest.raises(PQXNSliceValidationError, match="missing bundle certification"):
        build_n_slice_validation_record(
            validation_id="val-3",
            sequence_state=state,
            run_id="run-3",
            trace_id="trace-3",
            created_at="2026-03-29T00:00:00Z",
        )


def test_validation_fails_on_missing_audit() -> None:
    state = _state(["S1", "S2", "S3", "S4", "S5"])
    state["bundle_audit_status"] = "missing"
    with pytest.raises(PQXNSliceValidationError, match="missing bundle audit"):
        build_n_slice_validation_record(
            validation_id="val-4",
            sequence_state=state,
            run_id="run-4",
            trace_id="trace-4",
            created_at="2026-03-29T00:00:00Z",
        )


def test_validation_fails_on_hidden_drift_parity_mismatch() -> None:
    state = _state(["S1", "S2", "S3", "S4", "S5"])
    state["execution_history"] = [{"slice_id": "S1"}, {"slice_id": "S3"}, {"slice_id": "S2"}, {"slice_id": "S4"}, {"slice_id": "S5"}]
    with pytest.raises(PQXNSliceValidationError, match="deterministic advancement order mismatch"):
        build_n_slice_validation_record(
            validation_id="val-5",
            sequence_state=state,
            run_id="run-5",
            trace_id="trace-5",
            created_at="2026-03-29T00:00:00Z",
        )
