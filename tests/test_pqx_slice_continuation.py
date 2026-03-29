from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.pqx_sequence_runner import execute_sequence_run


class FixedClock:
    def __init__(self, stamps: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in stamps]

    def __call__(self):
        if self._values:
            return self._values.pop(0)
        return datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)


def _slice_requests() -> list[dict]:
    return [
        {"slice_id": "PQX-QUEUE-01", "trace_id": "trace-01"},
        {"slice_id": "PQX-QUEUE-02", "trace_id": "trace-02"},
    ]


def test_continuation_contract_example_validates() -> None:
    validate_artifact(load_example("pqx_slice_continuation_record"), "pqx_slice_continuation_record")


def test_valid_two_slice_continuation_persists_record(tmp_path: Path) -> None:
    def _executor(payload: dict) -> dict:
        suffix = payload["slice_id"].lower()
        return {
            "execution_status": "success",
            "slice_execution_record": f"{suffix}.pqx_slice_execution_record.json",
            "done_certification_record": f"{suffix}.done_certification_record.json",
            "pqx_slice_audit_bundle": f"{suffix}.pqx_slice_audit_bundle.json",
            "certification_complete": True,
            "audit_complete": True,
        }

    state = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=tmp_path / "state.json",
        queue_run_id="queue-run-cont-001",
        run_id="run-cont-001",
        trace_id="trace-cont-001",
        execute_slice=_executor,
        clock=FixedClock([f"2026-03-29T23:40:{i:02d}Z" for i in range(1, 30)]),
    )

    assert state["status"] == "completed"
    assert len(state["continuation_records"]) == 1
    continuation = state["continuation_records"][0]
    assert continuation["prior_step_id"] == "PQX-QUEUE-01"
    assert continuation["next_step_id"] == "PQX-QUEUE-02"
    assert continuation["continuation_decision"] == "allow"


def test_slice_2_blocked_when_prior_audit_missing(tmp_path: Path) -> None:
    def _executor(payload: dict) -> dict:
        if payload["slice_id"] == "PQX-QUEUE-01":
            return {
                "execution_status": "success",
                "slice_execution_record": "slice-1.pqx_slice_execution_record.json",
                "done_certification_record": "slice-1.done_certification_record.json",
                "pqx_slice_audit_bundle": None,
                "certification_complete": True,
                "audit_complete": False,
            }
        return {"execution_status": "success"}

    state = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=tmp_path / "state.json",
        queue_run_id="queue-run-audit-missing",
        run_id="run-audit-missing",
        trace_id="trace-audit-missing",
        execute_slice=_executor,
        clock=FixedClock([f"2026-03-29T23:50:{i:02d}Z" for i in range(1, 30)]),
    )

    assert state["status"] == "blocked"
    assert state["blocked_continuation_context"]["block_type"] == "PRIOR_SLICE_NOT_GOVERNED"


def test_malformed_continuation_record_blocks(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"

    def _executor(payload: dict) -> dict:
        suffix = payload["slice_id"].lower()
        return {
            "execution_status": "success",
            "slice_execution_record": f"{suffix}.pqx_slice_execution_record.json",
            "done_certification_record": f"{suffix}.done_certification_record.json",
            "pqx_slice_audit_bundle": f"{suffix}.pqx_slice_audit_bundle.json",
            "certification_complete": True,
            "audit_complete": True,
        }

    execute_sequence_run(
        slice_requests=_slice_requests()[:1],
        state_path=state_path,
        queue_run_id="queue-run-invalid-cont",
        run_id="run-invalid-cont",
        trace_id="trace-invalid-cont",
        execute_slice=_executor,
        clock=FixedClock([f"2026-03-29T23:52:{i:02d}Z" for i in range(1, 20)]),
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["requested_slice_ids"] = ["PQX-QUEUE-01", "PQX-QUEUE-02"]
    state["continuation_records"] = [{"artifact_id": "broken"}]
    state["status"] = "running"
    state["next_slice_ref"] = "PQX-QUEUE-02"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(Exception, match="invalid prompt_queue_sequence_run artifact"):
        execute_sequence_run(
            slice_requests=_slice_requests(),
            state_path=state_path,
            queue_run_id="queue-run-invalid-cont",
            run_id="run-invalid-cont",
            trace_id="trace-invalid-cont",
            execute_slice=_executor,
            resume=True,
            clock=FixedClock([f"2026-03-29T23:53:{i:02d}Z" for i in range(1, 20)]),
        )
