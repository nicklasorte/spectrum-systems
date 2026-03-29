from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.runtime.pqx_sequence_runner import execute_sequence_run, verify_two_slice_replay


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


def test_bundle_audit_is_synthesized(tmp_path: Path) -> None:
    state = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=tmp_path / "state.json",
        queue_run_id="queue-audit-001",
        run_id="run-audit-001",
        trace_id="trace-audit-001",
        execute_slice=_success_executor,
        review_results_by_slice={
            "PQX-QUEUE-02": {"review_id": "review-2", "has_blocking_findings": False},
            "PQX-QUEUE-03": {"review_id": "review-3", "has_blocking_findings": False, "overall_disposition": "approved"},
        },
    )
    assert state["bundle_audit_status"] == "synthesized"
    assert state["bundle_audit_ref"]


def test_replay_parity_across_chain(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    replay = tmp_path / "replay.json"
    output = tmp_path / "replay_record.json"

    kwargs = dict(
        slice_requests=_slice_requests(),
        queue_run_id="queue-audit-002",
        run_id="run-audit-002",
        trace_id="trace-audit-002",
        execute_slice=_success_executor,
        review_results_by_slice={
            "PQX-QUEUE-02": {"review_id": "review-2", "has_blocking_findings": False},
            "PQX-QUEUE-03": {"review_id": "review-3", "has_blocking_findings": False, "overall_disposition": "approved"},
        },
    )
    execute_sequence_run(state_path=baseline, **kwargs)
    execute_sequence_run(state_path=replay, **kwargs)

    record = verify_two_slice_replay(
        baseline_state_path=baseline,
        replay_state_path=replay,
        output_path=output,
        queue_run_id="queue-audit-002",
        run_id="run-audit-002",
        trace_id="trace-audit-002",
    )
    assert record["parity_status"] == "match"
