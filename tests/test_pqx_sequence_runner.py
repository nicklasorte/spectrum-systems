from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_sequence_runner import PQXSequenceRunnerError, execute_sequence_run


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
        return {"execution_status": "success"}

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
