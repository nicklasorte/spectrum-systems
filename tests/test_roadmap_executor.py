from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example, load_schema  # noqa: E402
from spectrum_systems.modules.runtime.roadmap_authorizer import authorize_selected_batch  # noqa: E402
from spectrum_systems.modules.runtime.roadmap_executor import (  # noqa: E402
    RoadmapExecutorError,
    execute_authorized_batch,
    read_roadmap_progress_update,
    update_roadmap_after_execution,
    validate_roadmap_progress_update,
    write_roadmap_progress_update,
)
from spectrum_systems.modules.runtime.roadmap_selector import build_roadmap_selection_result  # noqa: E402


def _roadmap() -> dict:
    artifact = copy.deepcopy(load_example("roadmap_artifact"))
    for batch in artifact["batches"]:
        if batch["batch_id"] == "BATCH-H":
            batch["status"] = "completed"
    artifact["current_batch_id"] = "BATCH-I"
    return artifact


def _selection() -> dict:
    signals = {
        "signals": ["roadmap_authority_resolved", "executor_ingestion_valid"],
        "hard_gates": {"BATCH-G": "pass"},
        "control_loop": {"eval_present": True, "trace_present": True, "schema_valid": True},
    }
    return build_roadmap_selection_result(_roadmap(), signals, evaluated_at="2026-04-03T13:00:00Z")


def _auth(*, decision: str = "allow") -> dict:
    signals = {
        "trace_id": "trace-rdx-004-test",
        "required_signals_satisfied": True,
        "hard_gate_state": "pass",
        "certification_state": "complete",
        "review_state": "complete",
        "eval_state": "complete",
        "replay_consistency": "match",
        "control_freeze_condition": False,
        "control_block_condition": False,
        "warning_states": [],
        "source_refs": [
            "contracts/examples/roadmap_artifact.json",
            "contracts/examples/roadmap_selection_result.json",
        ],
    }
    if decision == "warn":
        signals["warning_states"] = ["minor-latency"]
    if decision == "block":
        signals["control_block_condition"] = True
    return authorize_selected_batch(_roadmap(), _selection(), signals, evaluated_at="2026-04-03T13:30:00Z")


def _pqx_success(_: dict) -> dict:
    return {
        "status": "completed",
        "blocked_reason": None,
        "batch_result": {"status": "completed"},
        "execution_history": [
            {
                "execution_ref": "exec:queue-batch-i:RDX-002:1",
                "slice_execution_record_ref": "runs/pqx/RDX-002.pqx_slice_execution_record.json",
                "certification_ref": "runs/pqx/RDX-002.done_certification_record.json",
                "audit_bundle_ref": "runs/pqx/RDX-002.pqx_slice_audit_bundle.json",
            }
        ],
    }


def _pqx_blocked(_: dict) -> dict:
    return {
        "status": "blocked",
        "blocked_reason": "pqx gate blocked",
        "batch_result": {"status": "blocked"},
        "execution_history": [],
    }


def test_positive_path_executes_once_updates_completed_and_emits_artifact(tmp_path: Path) -> None:
    calls: list[dict] = []

    def _execute(**kwargs: dict) -> dict:
        calls.append(kwargs)
        return _pqx_success({})

    result = execute_authorized_batch(
        _roadmap(),
        _selection(),
        _auth(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        executed_at="2026-04-03T16:00:00Z",
        pqx_execute_fn=_execute,
    )

    assert len(calls) == 1
    assert calls[0]["slice_requests"] == [{"slice_id": "RDX-002", "trace_id": "trace-rdx-004-test"}]
    assert result["pqx_called"] is True
    assert result["roadmap"]["batches"][8]["status"] == "completed"
    assert result["progress_update"]["execution_status"] == "succeeded"
    assert result["progress_update"]["stop_reason"] is None
    assert result["progress_update"]["new_batch_status"] == "completed"
    assert result["progress_update"]["next_candidate_batch_id"] == "BATCH-J"


def test_blocked_authorization_does_not_call_pqx_or_mutate_roadmap(tmp_path: Path) -> None:
    roadmap = _roadmap()
    before = copy.deepcopy(roadmap)
    calls: list[dict] = []

    def _execute(**kwargs: dict) -> dict:
        calls.append(kwargs)
        return _pqx_success({})

    result = execute_authorized_batch(
        roadmap,
        _selection(),
        _auth(decision="block"),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        executed_at="2026-04-03T16:00:00Z",
        pqx_execute_fn=_execute,
    )

    assert calls == []
    assert result["pqx_called"] is False
    assert result["roadmap"] == before
    assert result["progress_update"]["execution_status"] == "not_executed"
    assert result["progress_update"]["stop_reason"] == "authorization_block"
    assert result["progress_update"]["reason_codes"] == ["AUTHORIZATION_DENIED_EXECUTION"]


def test_execution_failure_blocks_selected_batch_only(tmp_path: Path) -> None:
    roadmap = _roadmap()
    result = execute_authorized_batch(
        roadmap,
        _selection(),
        _auth(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        executed_at="2026-04-03T16:00:00Z",
        pqx_execute_fn=lambda **_: _pqx_blocked({}),
    )

    statuses = {batch["batch_id"]: batch["status"] for batch in result["roadmap"]["batches"]}
    assert statuses["BATCH-I"] == "blocked"
    assert statuses["BATCH-J"] == "not_started"
    assert result["progress_update"]["execution_status"] == "blocked"
    assert result["progress_update"]["stop_reason"] == "execution_blocked"
    assert "pqx gate blocked" in result["progress_update"]["blocking_conditions"]


def test_boundary_fail_closed_cases(tmp_path: Path) -> None:
    with pytest.raises(RoadmapExecutorError, match="must match"):
        bad_auth = _auth()
        bad_auth["selected_batch_id"] = "BATCH-J"
        execute_authorized_batch(
            _roadmap(),
            _selection(),
            bad_auth,
            pqx_state_path=tmp_path / "pqx" / "state.json",
            pqx_runs_root=tmp_path / "pqx",
            pqx_execute_fn=lambda **_: _pqx_success({}),
        )

    with pytest.raises(RoadmapExecutorError, match="roadmap_artifact failed schema validation"):
        bad_roadmap = _roadmap()
        bad_roadmap.pop("roadmap_id")
        execute_authorized_batch(
            bad_roadmap,
            _selection(),
            _auth(),
            pqx_state_path=tmp_path / "pqx" / "state.json",
            pqx_runs_root=tmp_path / "pqx",
            pqx_execute_fn=lambda **_: _pqx_success({}),
        )

    with pytest.raises(RoadmapExecutorError, match="roadmap_execution_authorization failed schema validation"):
        bad_auth = _auth()
        bad_auth["trace_id"] = "bad-trace"
        execute_authorized_batch(
            _roadmap(),
            _selection(),
            bad_auth,
            pqx_state_path=tmp_path / "pqx" / "state.json",
            pqx_runs_root=tmp_path / "pqx",
            pqx_execute_fn=lambda **_: _pqx_success({}),
        )

    with pytest.raises(RoadmapExecutorError, match="must not be terminal"):
        roadmap = _roadmap()
        for batch in roadmap["batches"]:
            if batch["batch_id"] == "BATCH-I":
                batch["status"] = "completed"
        execute_authorized_batch(
            roadmap,
            _selection(),
            _auth(),
            pqx_state_path=tmp_path / "pqx" / "state.json",
            pqx_runs_root=tmp_path / "pqx",
            pqx_execute_fn=lambda **_: _pqx_success({}),
        )


def test_determinism_same_inputs_identical_progress_artifact(tmp_path: Path) -> None:
    kwargs = {
        "roadmap_artifact": _roadmap(),
        "roadmap_selection_result": _selection(),
        "roadmap_execution_authorization": _auth(),
        "pqx_state_path": tmp_path / "pqx" / "state.json",
        "pqx_runs_root": tmp_path / "pqx",
        "executed_at": "2026-04-03T16:00:00Z",
        "pqx_execute_fn": lambda **_: _pqx_success({}),
    }
    first = execute_authorized_batch(**kwargs)
    second = execute_authorized_batch(**kwargs)
    assert first["progress_update"] == second["progress_update"]


def test_non_multi_batch_guarantee_single_pqx_call_no_chain(tmp_path: Path) -> None:
    calls: list[dict] = []

    def _execute(**kwargs: dict) -> dict:
        calls.append(kwargs)
        return _pqx_success({})

    result = execute_authorized_batch(
        _roadmap(),
        _selection(),
        _auth(decision="warn"),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        executed_at="2026-04-03T16:00:00Z",
        pqx_execute_fn=_execute,
    )
    assert len(calls) == 1
    assert result["roadmap"]["batches"][9]["status"] == "not_started"


def test_progress_update_contract_example_and_storage_round_trip(tmp_path: Path) -> None:
    example = load_example("roadmap_progress_update")
    schema = load_schema("roadmap_progress_update")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(example)

    payload = execute_authorized_batch(
        _roadmap(),
        _selection(),
        _auth(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        executed_at="2026-04-03T16:00:00Z",
        pqx_execute_fn=lambda **_: _pqx_success({}),
    )["progress_update"]
    validate_roadmap_progress_update(payload)

    out = write_roadmap_progress_update(payload, tmp_path / "roadmap_progress_update.json")
    loaded = read_roadmap_progress_update(out)
    assert loaded == payload
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_update_roadmap_after_execution_fail_closed_on_illegal_transition() -> None:
    roadmap = _roadmap()
    for batch in roadmap["batches"]:
        if batch["batch_id"] == "BATCH-I":
            batch["status"] = "completed"
    with pytest.raises(RoadmapExecutorError, match="must not be terminal"):
        update_roadmap_after_execution(roadmap, selected_batch_id="BATCH-I", execution_status="succeeded")
