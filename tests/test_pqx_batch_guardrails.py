from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_sequence_runner import (
    PQXSequenceRunnerError,
    execute_sequence_run,
    verify_two_slice_replay,
)


class FixedClock:
    def __init__(self, stamps: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in stamps]

    def __call__(self):
        if self._values:
            return self._values.pop(0)
        return datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)


def _slice_requests() -> list[dict]:
    return [
        {"slice_id": "AI-01", "trace_id": "trace-1"},
        {"slice_id": "AI-02", "trace_id": "trace-2"},
    ]


def test_pqx_sequence_runner_private_helpers_are_exercised_structurally() -> None:
    module_path = Path("spectrum_systems/modules/runtime/pqx_sequence_runner.py")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    private_helpers = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_")
    ]
    referenced_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }
    unreferenced = [name for name in private_helpers if name not in referenced_names]
    assert not unreferenced, f"unused helper abstractions require explicit justification: {unreferenced}"


def test_sequential_run_is_stateless_when_resume_is_false(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"

    def _executor(payload: dict) -> dict:
        return {
            "execution_status": "success",
            "slice_execution_record": f"{payload['run_id']}/{payload['slice_id']}.record.json",
            "done_certification_record": f"{payload['run_id']}/{payload['slice_id']}.cert.json",
            "pqx_slice_audit_bundle": f"{payload['run_id']}/{payload['slice_id']}.audit.json",
            "certification_complete": True,
            "audit_complete": True,
        }

    first = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=state_path,
        queue_run_id="queue-stateless-001",
        run_id="run-stateless-001",
        trace_id="trace-stateless-001",
        execute_slice=_executor,
        clock=FixedClock([f"2026-04-01T00:00:{i:02d}Z" for i in range(1, 30)]),
    )
    second = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=state_path,
        queue_run_id="queue-stateless-002",
        run_id="run-stateless-002",
        trace_id="trace-stateless-002",
        execute_slice=_executor,
        resume=False,
        clock=FixedClock([f"2026-04-01T00:01:{i:02d}Z" for i in range(1, 30)]),
    )

    assert first["run_id"] == "run-stateless-001"
    assert second["run_id"] == "run-stateless-002"
    assert all(row["run_id"] == "run-stateless-002" for row in second["execution_history"])


def test_replay_mismatch_summary_uses_structured_fields_not_text(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    replay = tmp_path / "replay.json"

    execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=baseline,
        queue_run_id="queue-diag-001",
        run_id="run-diag-001",
        trace_id="trace-diag-001",
        execute_slice=lambda payload: {
            "execution_status": "success",
            "slice_execution_record": f"safe/{payload['slice_id']}.record.json",
            "done_certification_record": f"safe/{payload['slice_id']}.cert.json",
            "pqx_slice_audit_bundle": f"safe/{payload['slice_id']}.audit.json",
            "certification_complete": True,
            "audit_complete": True,
        },
        clock=FixedClock([f"2026-04-01T00:02:{i:02d}Z" for i in range(1, 30)]),
    )
    execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=replay,
        queue_run_id="queue-diag-001",
        run_id="run-diag-001",
        trace_id="trace-diag-001",
        execute_slice=lambda payload: {
            "execution_status": "success",
            "slice_execution_record": f"review-keyword/{payload['slice_id']}.record.json",
            "done_certification_record": f"blocked-keyword/{payload['slice_id']}.cert.json",
            "pqx_slice_audit_bundle": f"path-substring/{payload['slice_id']}.audit.json",
            "certification_complete": True,
            "audit_complete": True,
        },
        clock=FixedClock([f"2026-04-01T00:03:{i:02d}Z" for i in range(1, 30)]),
    )

    tampered = json.loads(replay.read_text(encoding="utf-8"))
    tampered["termination_reason"] = "STOPPED_FAILED"
    replay.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(PQXSequenceRunnerError) as exc_info:
        verify_two_slice_replay(
            baseline_state_path=baseline,
            replay_state_path=replay,
            output_path=tmp_path / "replay_record.json",
            queue_run_id="queue-diag-001",
            run_id="run-diag-001",
            trace_id="trace-diag-001",
            clock=FixedClock(["2026-04-01T00:04:01Z"]),
        )
    message = str(exc_info.value)
    assert "termination_reason_mismatch" in message
    assert "review-keyword" not in message
    assert "blocked-keyword" not in message


def test_impacted_module_guardrail_suite_exists() -> None:
    required = [
        Path("tests/test_pqx_sequence_runner.py"),
        Path("tests/test_replay_engine.py"),
        Path("tests/test_prompt_queue_audit_bundle.py"),
        Path("tests/test_pqx_bundle_certification.py"),
    ]
    missing = [str(path) for path in required if not path.exists()]
    assert not missing, f"impacted-module coverage files missing: {missing}"
