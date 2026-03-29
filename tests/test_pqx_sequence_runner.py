from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_sequence_runner import (
    PQXSequenceRunnerError,
    execute_bundle_sequence_run,
    execute_sequence_run,
    verify_two_slice_replay,
)


class FixedClock:
    def __init__(self, stamps: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in stamps]

    def __call__(self):
        if self._values:
            return self._values.pop(0)
        return datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)


def _slice_requests() -> list[dict]:
    return [
        {"slice_id": "PQX-QUEUE-01", "trace_id": "trace-01"},
        {"slice_id": "PQX-QUEUE-02", "trace_id": "trace-02"},
        {"slice_id": "PQX-QUEUE-03", "trace_id": "trace-03"},
    ]


def test_happy_path_runs_three_slices_in_order_and_persists(tmp_path: Path) -> None:
    state_path = tmp_path / "sequence.json"
    checkpoints: list[dict] = []

    def _executor(payload: dict) -> dict:
        checkpoints.append(json.loads(state_path.read_text(encoding="utf-8")))
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

    state = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=state_path,
        queue_run_id="queue-run-001",
        run_id="run-001",
        trace_id="trace-batch-001",
        execute_slice=_executor,
        clock=FixedClock([f"2026-03-29T12:00:0{i}Z" for i in range(1, 15)]),
    )

    assert state["status"] == "completed"
    assert state["completed_slice_ids"] == ["PQX-QUEUE-01", "PQX-QUEUE-02", "PQX-QUEUE-03"]
    assert [row["slice_id"] for row in state["execution_history"]] == ["PQX-QUEUE-01", "PQX-QUEUE-02", "PQX-QUEUE-03"]
    assert len(checkpoints) == 3
    assert checkpoints[0]["completed_slice_ids"] == []
    assert checkpoints[1]["completed_slice_ids"] == ["PQX-QUEUE-01"]


def test_resume_after_interruption_continues_without_rerun(tmp_path: Path) -> None:
    state_path = tmp_path / "sequence.json"
    calls: list[str] = []

    def _executor(payload: dict) -> dict:
        calls.append(payload["slice_id"])
        return {
            "execution_status": "success",
            "slice_execution_record": f"{payload['slice_id']}.record.json",
            "done_certification_record": f"{payload['slice_id']}.cert.json",
            "pqx_slice_audit_bundle": f"{payload['slice_id']}.audit.json",
            "certification_complete": True,
            "audit_complete": True,
        }

    execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=state_path,
        queue_run_id="queue-run-001",
        run_id="run-001",
        trace_id="trace-batch-001",
        execute_slice=_executor,
        max_slices=1,
        clock=FixedClock([f"2026-03-29T12:10:0{i}Z" for i in range(1, 8)]),
    )
    resumed = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=state_path,
        queue_run_id="queue-run-001",
        run_id="run-001",
        trace_id="trace-batch-001",
        execute_slice=_executor,
        resume=True,
        clock=FixedClock([f"2026-03-29T12:11:0{i}Z" for i in range(1, 12)]),
    )

    assert calls == ["PQX-QUEUE-01", "PQX-QUEUE-02", "PQX-QUEUE-03"]
    assert resumed["status"] == "completed"


def test_missing_required_identity_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(PQXSequenceRunnerError, match="run_id is required"):
        execute_sequence_run(
            slice_requests=_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-run-001",
            run_id="",
            trace_id="trace-batch-001",
        )


def test_parent_child_continuity_mismatch_fails_closed(tmp_path: Path) -> None:
    def _executor(_: dict) -> dict:
        return {"execution_status": "success", "parent_execution_ref": "tampered-parent"}

    with pytest.raises(PQXSequenceRunnerError, match="parent_execution_ref changed"):
        execute_sequence_run(
            slice_requests=_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-run-001",
            run_id="run-001",
            trace_id="trace-batch-001",
            execute_slice=_executor,
            max_slices=2,
        )


def test_persisted_reload_mismatch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = "spectrum_systems.modules.runtime.pqx_sequence_runner._persist_and_reload_exact"

    def _tampered(state: dict, state_path: Path) -> dict:
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
        loaded["run_id"] = "tampered"
        return loaded

    monkeypatch.setattr(target, _tampered)
    with pytest.raises(PQXSequenceRunnerError, match="stable batch run_id"):
        execute_sequence_run(
            slice_requests=_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-run-001",
            run_id="run-001",
            trace_id="trace-batch-001",
        )


def test_bad_transition_state_fails_closed(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=state_path,
        queue_run_id="queue-run-001",
        run_id="run-001",
        trace_id="trace-batch-001",
        max_slices=1,
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["completed_slice_ids"] = ["PQX-QUEUE-03"]
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    with pytest.raises(PQXSequenceRunnerError, match="completed_slice_ids mismatch"):
        execute_sequence_run(
            slice_requests=_slice_requests(),
            state_path=state_path,
            queue_run_id="queue-run-001",
            run_id="run-001",
            trace_id="trace-batch-001",
            resume=True,
        )


def test_sequence_runner_does_not_require_roadmap_path_rebinding(tmp_path: Path) -> None:
    state = execute_sequence_run(
        slice_requests=_slice_requests()[:1],
        state_path=tmp_path / "state.json",
        queue_run_id="queue-run-bridge-001",
        run_id="run-bridge-001",
        trace_id="trace-bridge-001",
        clock=FixedClock(["2026-03-29T14:00:01Z", "2026-03-29T14:00:02Z", "2026-03-29T14:00:03Z", "2026-03-29T14:00:04Z"]),
    )
    assert state["status"] == "completed"


def test_sequence_runner_persists_bundle_state_when_configured(tmp_path: Path) -> None:
    bundle_state_path = tmp_path / "bundle_state.json"
    execute_sequence_run(
        slice_requests=_slice_requests()[:2],
        state_path=tmp_path / "state.json",
        queue_run_id="queue-run-b4-001",
        run_id="run-b4-001",
        trace_id="trace-b4-001",
        bundle_state_path=bundle_state_path,
        bundle_id="BUNDLE-03",
        clock=FixedClock([f"2026-03-29T15:00:0{i}Z" for i in range(1, 12)]),
    )

    bundle_state = json.loads(bundle_state_path.read_text(encoding="utf-8"))
    assert bundle_state["completed_step_ids"] == ["PQX-QUEUE-01", "PQX-QUEUE-02"]
    assert bundle_state["completed_bundle_ids"] == ["BUNDLE-03"]


def test_sequence_runner_bundle_state_blocks_out_of_order_progression(tmp_path: Path) -> None:
    with pytest.raises(PQXSequenceRunnerError, match="step_id not declared in bundle plan"):
        execute_sequence_run(
            slice_requests=_slice_requests()[:1],
            state_path=tmp_path / "state.json",
            queue_run_id="queue-run-b4-003",
            run_id="run-b4-003",
            trace_id="trace-b4-003",
            bundle_state_path=tmp_path / "bundle_state.json",
            bundle_plan=[{"bundle_id": "BUNDLE-01", "step_ids": ["B3-01"], "depends_on": []}],
            clock=FixedClock(["2026-03-29T16:01:01Z", "2026-03-29T16:01:02Z", "2026-03-29T16:01:03Z", "2026-03-29T16:01:04Z"]),
        )




def test_sequence_runner_bundle_invocation_path_is_additive(tmp_path: Path) -> None:
    plan_path = tmp_path / "execution_bundles.md"
    plan_path.write_text(
        "\n".join(
            [
                "# Test",
                "## EXECUTABLE BUNDLE TABLE",
                "| Bundle ID | Ordered Step IDs | Depends On |",
                "| --- | --- | --- |",
                "| BUNDLE-TSEQ | AI-01 | - |",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = execute_bundle_sequence_run(
        bundle_id="BUNDLE-TSEQ",
        bundle_state_path=tmp_path / "bundle_state.json",
        output_dir=tmp_path / "out",
        run_id="run-tseq-001",
        queue_run_id="queue-tseq-001",
        trace_id="trace-tseq-001",
        bundle_plan_path=plan_path,
        execute_step=lambda _: {"execution_status": "success"},
        clock=FixedClock([f"2026-03-29T21:00:0{i}Z" for i in range(1, 12)]),
    )

    assert result["status"] == "completed"


def test_sequence_runner_default_executor_routes_to_canonical_slice_runner(tmp_path: Path) -> None:
    state = execute_sequence_run(
        slice_requests=_slice_requests()[:1],
        state_path=tmp_path / "state.json",
        queue_run_id="queue-run-default-001",
        run_id="run-default-001",
        trace_id="trace-default-001",
        clock=FixedClock(["2026-03-29T22:30:01Z", "2026-03-29T22:30:02Z", "2026-03-29T22:30:03Z", "2026-03-29T22:30:04Z", "2026-03-29T22:30:05Z", "2026-03-29T22:30:06Z"]),
    )
    assert state["status"] == "completed"
    assert state["completed_slice_ids"] == ["PQX-QUEUE-01"]


def test_slice_2_blocked_when_prior_certification_missing(tmp_path: Path) -> None:
    def _executor(payload: dict) -> dict:
        if payload["slice_id"] == "PQX-QUEUE-01":
            return {
                "execution_status": "success",
                "slice_execution_record": "record-1.json",
                "done_certification_record": None,
                "pqx_slice_audit_bundle": "audit-1.json",
                "certification_complete": False,
                "audit_complete": True,
            }
        return {"execution_status": "success"}

    state = execute_sequence_run(
        slice_requests=_slice_requests()[:2],
        state_path=tmp_path / "state.json",
        queue_run_id="queue-run-cert-block",
        run_id="run-cert-block",
        trace_id="trace-cert-block",
        execute_slice=_executor,
        clock=FixedClock([f"2026-03-29T23:10:{i:02d}Z" for i in range(1, 20)]),
    )
    assert state["status"] == "blocked"
    assert state["blocked_continuation_context"]["block_type"] == "PRIOR_SLICE_NOT_GOVERNED"


def test_slice_2_blocked_on_continuation_state_mismatch(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"

    def _executor(_: dict) -> dict:
        return {
            "execution_status": "success",
            "slice_execution_record": "record-1.json",
            "done_certification_record": "cert-1.json",
            "pqx_slice_audit_bundle": "audit-1.json",
            "certification_complete": True,
            "audit_complete": True,
        }

    execute_sequence_run(
        slice_requests=_slice_requests()[:1],
        state_path=state_path,
        queue_run_id="queue-run-mismatch",
        run_id="run-mismatch",
        trace_id="trace-mismatch",
        execute_slice=_executor,
        clock=FixedClock([f"2026-03-29T23:20:{i:02d}Z" for i in range(1, 20)]),
    )
    tampered = json.loads(state_path.read_text(encoding="utf-8"))
    tampered["requested_slice_ids"] = ["PQX-QUEUE-01", "PQX-QUEUE-02"]
    tampered["failed_slice_ids"] = []
    tampered["next_slice_ref"] = "PQX-QUEUE-02"
    tampered["status"] = "running"
    tampered["continuation_records"] = [
        {
            "artifact_id": "cont:bad",
            "prior_step_id": "PQX-QUEUE-01",
            "next_step_id": "PQX-QUEUE-02",
            "prior_run_id": "bad-run",
            "prior_trace_id": "trace-01",
            "prior_slice_execution_record_ref": "x",
            "prior_certification_ref": "y",
            "prior_audit_bundle_ref": "z",
            "continuation_status": "ready",
            "continuation_decision": "allow",
            "continuation_reasons": ["tampered"],
            "created_at": "2026-03-29T23:20:59Z",
        }
    ]
    state_path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

    blocked = execute_sequence_run(
        slice_requests=_slice_requests()[:2],
        state_path=state_path,
        queue_run_id="queue-run-mismatch",
        run_id="run-mismatch",
        trace_id="trace-mismatch",
        execute_slice=_executor,
        resume=True,
        clock=FixedClock([f"2026-03-29T23:21:{i:02d}Z" for i in range(1, 20)]),
    )
    assert blocked["status"] == "blocked"
    assert blocked["blocked_continuation_context"]["block_type"] == "CONTINUATION_STATE_MISMATCH"


def test_two_slice_replay_verification_pass_and_fail_closed(tmp_path: Path) -> None:
    state_1 = tmp_path / "baseline.json"
    state_2 = tmp_path / "replay.json"

    def _executor(_: dict) -> dict:
        return {
            "execution_status": "success",
            "slice_execution_record": "record.json",
            "done_certification_record": "cert.json",
            "pqx_slice_audit_bundle": "audit.json",
            "certification_complete": True,
            "audit_complete": True,
        }

    execute_sequence_run(
        slice_requests=_slice_requests()[:2],
        state_path=state_1,
        queue_run_id="queue-run-rp-1",
        run_id="run-rp-1",
        trace_id="trace-rp-1",
        execute_slice=_executor,
        clock=FixedClock([f"2026-03-29T23:30:{i:02d}Z" for i in range(1, 24)]),
    )
    execute_sequence_run(
        slice_requests=_slice_requests()[:2],
        state_path=state_2,
        queue_run_id="queue-run-rp-1",
        run_id="run-rp-1",
        trace_id="trace-rp-1",
        execute_slice=_executor,
        clock=FixedClock([f"2026-03-29T23:31:{i:02d}Z" for i in range(1, 24)]),
    )

    record = verify_two_slice_replay(
        baseline_state_path=state_1,
        replay_state_path=state_2,
        output_path=tmp_path / "replay_record.json",
        queue_run_id="queue-run-rp-1",
        run_id="run-rp-1",
        trace_id="trace-rp-1",
        clock=FixedClock(["2026-03-29T23:32:01Z"]),
    )
    assert record["parity_status"] == "match"

    tampered = json.loads(state_2.read_text(encoding="utf-8"))
    tampered["execution_history"][1]["audit_complete"] = False
    state_2.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(PQXSequenceRunnerError, match="failed closed"):
        verify_two_slice_replay(
            baseline_state_path=state_1,
            replay_state_path=state_2,
            output_path=tmp_path / "replay_record_mismatch.json",
            queue_run_id="queue-run-rp-1",
            run_id="run-rp-1",
            trace_id="trace-rp-1",
            clock=FixedClock(["2026-03-29T23:32:02Z"]),
        )
