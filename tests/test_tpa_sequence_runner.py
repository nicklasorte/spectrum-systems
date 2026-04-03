from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_sequence_runner import (
    PQXSequenceRunnerError,
    _deterministic_gate_selection,
    execute_sequence_run,
)


class FixedClock:
    def __init__(self, stamps: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in stamps]

    def __call__(self):
        if self._values:
            return self._values.pop(0)
        return datetime(2026, 4, 3, 0, 0, 0, tzinfo=timezone.utc)


def _tpa_slice_requests() -> list[dict]:
    return [
        {
            "slice_id": "AI-01-P",
            "trace_id": "trace-tpa-plan",
            "tpa_plan": {
                "artifact_kind": "plan",
                "files_touched": ["spectrum_systems/modules/runtime/pqx_sequence_runner.py"],
                "seams_reused": ["pqx_sequence_runner.execute_sequence_run"],
                "abstraction_intent": "reuse_existing",
                "constraints_acknowledged": {"build_small": True, "no_redesign": True},
            },
        },
        {"slice_id": "AI-01-B", "trace_id": "trace-tpa-build"},
        {"slice_id": "AI-01-S", "trace_id": "trace-tpa-simplify"},
        {"slice_id": "AI-01-G", "trace_id": "trace-tpa-gate"},
    ]


def _executor(payload: dict) -> dict:
    slice_id = payload["slice_id"]
    result = {
        "execution_status": "success",
        "slice_execution_record": f"records/{slice_id}.json",
        "done_certification_record": f"certs/{slice_id}.json",
        "pqx_slice_audit_bundle": f"audit/{slice_id}.json",
        "certification_complete": True,
        "audit_complete": True,
    }
    if slice_id.endswith("-B"):
        result["tpa_build"] = {
            "artifact_kind": "build",
            "files_touched": ["spectrum_systems/modules/runtime/pqx_sequence_runner.py"],
            "new_layers": 0,
            "unused_helpers": [],
            "unnecessary_indirection": [],
            "plan_scope_match": True,
            "abstraction_justifications": [],
        }
    elif slice_id.endswith("-S"):
        result["tpa_simplify"] = {
            "artifact_kind": "simplify",
            "source_build_artifact_id": f"tpa:{payload['run_id']}:AI-01-B",
            "actions": ["reduce_nesting", "rename_for_clarity"],
            "behavior_changed": False,
            "new_layers_introduced": 0,
        }
    elif slice_id.endswith("-G"):
        selected = _deterministic_gate_selection(
            run_id=payload["run_id"],
            step_id="AI-01",
            build_artifact_id=f"tpa:{payload['run_id']}:AI-01-B",
            simplify_artifact_id=f"tpa:{payload['run_id']}:AI-01-S",
        )
        result["tpa_gate"] = {
            "artifact_kind": "gate",
            "build_artifact_id": f"tpa:{payload['run_id']}:AI-01-B",
            "simplify_artifact_id": f"tpa:{payload['run_id']}:AI-01-S",
            "behavioral_equivalence": True,
            "contract_valid": True,
            "tests_valid": True,
            "selected_pass": selected,
            "selection_reason": "equivalence proven and deterministic control selected pass",
        }
    return result


def test_tpa_happy_path_emits_artifacts_and_deterministic_selection(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    first = execute_sequence_run(
        slice_requests=_tpa_slice_requests(),
        state_path=state_path,
        queue_run_id="queue-tpa-001",
        run_id="run-tpa-001",
        trace_id="trace-tpa-batch-001",
        execute_slice=_executor,
        clock=FixedClock([f"2026-04-03T00:00:{i:02d}Z" for i in range(1, 45)]),
    )
    second = execute_sequence_run(
        slice_requests=_tpa_slice_requests(),
        state_path=tmp_path / "state-second.json",
        queue_run_id="queue-tpa-001",
        run_id="run-tpa-001",
        trace_id="trace-tpa-batch-001",
        execute_slice=_executor,
        clock=FixedClock([f"2026-04-03T00:01:{i:02d}Z" for i in range(1, 45)]),
    )

    assert first["completed_slice_ids"] == ["AI-01-P", "AI-01-B", "AI-01-S", "AI-01-G"]
    assert first["tpa_artifacts"]["AI-01"]["plan"]["phase"] == "plan"
    assert first["tpa_artifacts"]["AI-01"]["build"]["phase"] == "build"
    assert first["tpa_artifacts"]["AI-01"]["simplify"]["phase"] == "simplify"
    assert first["tpa_artifacts"]["AI-01"]["gate"]["phase"] == "gate"
    assert (
        first["tpa_artifacts"]["AI-01"]["gate"]["artifact"]["selected_pass"]
        == second["tpa_artifacts"]["AI-01"]["gate"]["artifact"]["selected_pass"]
    )


def test_tpa_build_small_fails_on_unused_helpers(tmp_path: Path) -> None:
    def _bad_executor(payload: dict) -> dict:
        response = _executor(payload)
        if payload["slice_id"].endswith("-B"):
            response["tpa_build"]["unused_helpers"] = ["helper_that_is_not_used"]
        return response

    with pytest.raises(PQXSequenceRunnerError, match="unused_helpers"):
        execute_sequence_run(
            slice_requests=_tpa_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-tpa-002",
            run_id="run-tpa-002",
            trace_id="trace-tpa-batch-002",
            execute_slice=_bad_executor,
            clock=FixedClock([f"2026-04-03T00:10:{i:02d}Z" for i in range(1, 40)]),
        )


def test_tpa_gate_fails_on_nondeterministic_selection(tmp_path: Path) -> None:
    def _bad_gate_executor(payload: dict) -> dict:
        response = _executor(payload)
        if payload["slice_id"].endswith("-G"):
            expected = response["tpa_gate"]["selected_pass"]
            response["tpa_gate"]["selected_pass"] = "pass_1_build" if expected == "pass_2_simplify" else "pass_2_simplify"
        return response

    with pytest.raises(PQXSequenceRunnerError, match="deterministic control decision"):
        execute_sequence_run(
            slice_requests=_tpa_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-tpa-003",
            run_id="run-tpa-003",
            trace_id="trace-tpa-batch-003",
            execute_slice=_bad_gate_executor,
            clock=FixedClock([f"2026-04-03T00:20:{i:02d}Z" for i in range(1, 40)]),
        )
