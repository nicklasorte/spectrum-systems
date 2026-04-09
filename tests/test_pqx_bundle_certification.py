from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.runtime.pqx_sequence_runner import execute_sequence_run


def _slice_requests() -> list[dict]:
    return [
        {"slice_id": "PQX-QUEUE-01", "trace_id": "trace-01"},
        {"slice_id": "PQX-QUEUE-02", "trace_id": "trace-02"},
        {"slice_id": "PQX-QUEUE-03", "trace_id": "trace-03"},
    ]


def _success_executor(payload: dict) -> dict:
    return {
        "execution_status": "success",
        "queue_run_id": payload["queue_run_id"],
        "run_id": payload["run_id"],
        "trace_id": payload["trace_id"],
        "parent_execution_ref": payload["parent_execution_ref"],
        "slice_execution_record": f"{payload['slice_id']}.record.json",
        "done_certification_record": f"{payload['slice_id']}.cert.json",
        "pqx_slice_audit_bundle": f"{payload['slice_id']}.audit.json",
        "certification_complete": True,
        "audit_complete": True,
    }


def test_bundle_readiness_failure_blocks_execution(tmp_path: Path) -> None:
    state = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=tmp_path / "state.json",
        queue_run_id="queue-g4-001",
        run_id="run-g4-001",
        trace_id="trace-g4-001",
        execute_slice=_success_executor,
        review_results_by_slice={"PQX-QUEUE-02": {"review_id": "r2", "has_blocking_findings": True, "pending_fix_ids": ["fix-1"]}},
    )
    assert state["status"] == "blocked"
    assert state["bundle_readiness_decision"]["ready"] is False


def test_bundle_certification_failure_when_chain_not_certified(tmp_path: Path) -> None:
    state = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=tmp_path / "state.json",
        queue_run_id="queue-g4-002",
        run_id="run-g4-002",
        trace_id="trace-g4-002",
        execute_slice=_success_executor,
        review_results_by_slice={
            "PQX-QUEUE-02": {"review_id": "r2", "has_blocking_findings": False},
            "PQX-QUEUE-03": {"review_id": "r3", "overall_disposition": "rejected", "has_blocking_findings": True},
        },
    )
    assert state["status"] == "blocked"
    assert state["chain_certification_status"] == "blocked"
