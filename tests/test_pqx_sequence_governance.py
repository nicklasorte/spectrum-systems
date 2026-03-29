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


def test_three_slice_success_with_required_reviews(tmp_path: Path) -> None:
    state = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=tmp_path / "state.json",
        queue_run_id="queue-g3-001",
        run_id="run-g3-001",
        trace_id="trace-g3-001",
        execute_slice=_success_executor,
        review_results_by_slice={
            "PQX-QUEUE-02": {"review_id": "review-2", "has_blocking_findings": False},
            "PQX-QUEUE-03": {"review_id": "review-3", "has_blocking_findings": False, "overall_disposition": "approved"},
        },
    )
    assert state["status"] == "completed"
    assert state["chain_certification_status"] == "certified"
    assert state["bundle_certification_status"] == "certified"
    assert state["bundle_audit_status"] == "synthesized"


def test_review_blocking_fails_closed(tmp_path: Path) -> None:
    state = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=tmp_path / "state.json",
        queue_run_id="queue-g3-002",
        run_id="run-g3-002",
        trace_id="trace-g3-002",
        execute_slice=_success_executor,
        review_results_by_slice={"PQX-QUEUE-02": {"review_id": "review-2", "has_blocking_findings": True, "pending_fix_ids": ["fx-1"]}},
    )
    assert state["status"] == "blocked"
    assert "slice 2 review" in state["blocked_reason"]


def test_budget_exceeded_freezes_sequence(tmp_path: Path) -> None:
    def _always_fail(payload: dict) -> dict:
        return {
            "execution_status": "failed",
            "queue_run_id": payload["queue_run_id"],
            "run_id": payload["run_id"],
            "trace_id": payload["trace_id"],
            "parent_execution_ref": payload["parent_execution_ref"],
            "error": "boom",
        }

    state = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=tmp_path / "state.json",
        queue_run_id="queue-g3-003",
        run_id="run-g3-003",
        trace_id="trace-g3-003",
        execute_slice=_always_fail,
        sequence_budget_thresholds={"max_failed_slices": 0, "max_cumulative_severity": 0},
    )
    assert state["status"] == "blocked"
    assert state["sequence_budget_status"] == "exceeded_budget"
