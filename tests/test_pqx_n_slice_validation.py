from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_n_slice_validation import (
    PQXNSliceValidationError,
    build_n_slice_validation_record,
)


_DEF_FALSIFICATION = {
    "artifact_type": "pqx_hard_gate_falsification_record",
    "overall_result": "pass",
}


def _state(slice_ids: list[str], falsification_ref: str) -> dict:
    return {
        "requested_slice_ids": slice_ids,
        "completed_slice_ids": list(slice_ids),
        "execution_history": [{"slice_id": s} for s in slice_ids],
        "bundle_certification_status": "certified",
        "bundle_audit_status": "synthesized",
        "hard_gate_falsification_ref": falsification_ref,
        "replay_verification": {"status": "verified"},
    }


def _write_falsification(tmp_path: Path, *, overall_result: str = "pass") -> str:
    payload = dict(_DEF_FALSIFICATION)
    payload["overall_result"] = overall_result
    path = tmp_path / "hard_gate_falsification.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_five_slice_happy_path_validates(tmp_path: Path) -> None:
    record = build_n_slice_validation_record(
        validation_id="val-1",
        sequence_state=_state(["S1", "S2", "S3", "S4", "S5"], _write_falsification(tmp_path)),
        run_id="run-1",
        trace_id="trace-1",
        created_at="2026-03-29T00:00:00Z",
    )
    assert record["status"] == "validated"


def test_longer_run_with_pause_resume_validates(tmp_path: Path) -> None:
    state = _state(["S1", "S2", "S3", "S4", "S5", "S6", "S7"], _write_falsification(tmp_path))
    state["replay_verification"] = {"status": "not_run"}
    record = build_n_slice_validation_record(
        validation_id="val-2",
        sequence_state=state,
        run_id="run-2",
        trace_id="trace-2",
        created_at="2026-03-29T00:00:00Z",
    )
    assert record["slice_count"] == 7


def test_validation_fails_on_missing_certification(tmp_path: Path) -> None:
    state = _state(["S1", "S2", "S3", "S4", "S5"], _write_falsification(tmp_path))
    state["bundle_certification_status"] = "pending"
    with pytest.raises(PQXNSliceValidationError, match="missing bundle certification"):
        build_n_slice_validation_record(
            validation_id="val-3",
            sequence_state=state,
            run_id="run-3",
            trace_id="trace-3",
            created_at="2026-03-29T00:00:00Z",
        )


def test_validation_fails_on_missing_hard_gate_falsification(tmp_path: Path) -> None:
    state = _state(["S1", "S2", "S3", "S4", "S5"], _write_falsification(tmp_path))
    state.pop("hard_gate_falsification_ref")
    with pytest.raises(PQXNSliceValidationError, match="missing hard-gate falsification evidence"):
        build_n_slice_validation_record(
            validation_id="val-4",
            sequence_state=state,
            run_id="run-4",
            trace_id="trace-4",
            created_at="2026-03-29T00:00:00Z",
        )


def test_validation_fails_on_failed_hard_gate_falsification(tmp_path: Path) -> None:
    state = _state(["S1", "S2", "S3", "S4", "S5"], _write_falsification(tmp_path, overall_result="fail"))
    with pytest.raises(PQXNSliceValidationError, match="hard-gate falsification did not pass"):
        build_n_slice_validation_record(
            validation_id="val-5",
            sequence_state=state,
            run_id="run-5",
            trace_id="trace-5",
            created_at="2026-03-29T00:00:00Z",
        )
