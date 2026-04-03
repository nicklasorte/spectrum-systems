from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example, load_schema  # noqa: E402
import spectrum_systems.modules.runtime.roadmap_execution_loop_validator as loop_validator  # noqa: E402
from spectrum_systems.modules.runtime.roadmap_execution_loop_validator import validate_single_batch_execution_loop  # noqa: E402


def _roadmap() -> dict:
    artifact = copy.deepcopy(load_example("roadmap_artifact"))
    for batch in artifact["batches"]:
        if batch["batch_id"] == "BATCH-H":
            batch["status"] = "completed"
    artifact["current_batch_id"] = "BATCH-I"
    return artifact


def _selection_signals(*, include_required: bool = True) -> dict:
    signals = ["roadmap_authority_resolved"]
    if include_required:
        signals.append("executor_ingestion_valid")
    return {
        "signals": signals,
        "hard_gates": {"BATCH-G": "pass"},
        "control_loop": {"eval_present": True, "trace_present": True, "schema_valid": True},
    }


def _authorization_signals(*, allow: bool = True) -> dict:
    return {
        "trace_id": "trace-rdx-005-test",
        "required_signals_satisfied": allow,
        "hard_gate_state": "pass",
        "certification_state": "complete",
        "review_state": "complete",
        "eval_state": "complete",
        "replay_consistency": "match",
        "control_freeze_condition": False,
        "control_block_condition": not allow,
        "warning_states": [],
    }


def _pqx_success(**_: dict) -> dict:
    return {
        "status": "completed",
        "blocked_reason": None,
        "batch_result": {"status": "completed"},
        "execution_history": [
            {
                "execution_ref": "exec:queue-batch-i:RDX-005:1",
                "slice_execution_record_ref": "runs/pqx/RDX-005.pqx_slice_execution_record.json",
                "certification_ref": "runs/pqx/RDX-005.done_certification_record.json",
                "audit_bundle_ref": "runs/pqx/RDX-005.pqx_slice_audit_bundle.json",
            }
        ],
    }


def _pqx_blocked(**_: dict) -> dict:
    return {
        "status": "blocked",
        "blocked_reason": "pqx blocked execution",
        "batch_result": {"status": "blocked"},
        "execution_history": [],
    }


def test_positive_end_to_end_loop_passes_and_emits_progress(tmp_path: Path) -> None:
    result = validate_single_batch_execution_loop(
        _roadmap(),
        _selection_signals(),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        evaluated_at="2026-04-03T19:00:00Z",
        executed_at="2026-04-03T19:01:00Z",
        validated_at="2026-04-03T19:02:00Z",
        pqx_execute_fn=_pqx_success,
    )

    loop = result["loop_validation"]
    assert loop["loop_status"] == "passed"
    assert loop["execution_occurred"] is True
    assert loop["selected_batch_id"] == "BATCH-I"
    assert loop["selected_batch_status"] == "completed"
    assert loop["reason_codes"] == ["LOOP_VALIDATION_PASSED"]
    assert result["progress_update"]["execution_status"] == "succeeded"


def test_authorization_denied_path_has_no_execution_or_progress(tmp_path: Path) -> None:
    result = validate_single_batch_execution_loop(
        _roadmap(),
        _selection_signals(),
        _authorization_signals(allow=False),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        evaluated_at="2026-04-03T19:00:00Z",
        validated_at="2026-04-03T19:02:00Z",
    )

    loop = result["loop_validation"]
    assert loop["loop_status"] == "passed"
    assert loop["execution_occurred"] is False
    assert loop["control_decision"] == "block"
    assert loop["progress_update_id"] is None
    assert loop["reason_codes"] == ["LOOP_VALIDATION_DENIED_PATH"]
    assert result["progress_update"] is None


def test_blocked_execution_path_is_valid_governed_outcome(tmp_path: Path) -> None:
    result = validate_single_batch_execution_loop(
        _roadmap(),
        _selection_signals(),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        evaluated_at="2026-04-03T19:00:00Z",
        executed_at="2026-04-03T19:01:00Z",
        validated_at="2026-04-03T19:02:00Z",
        pqx_execute_fn=_pqx_blocked,
    )

    loop = result["loop_validation"]
    assert loop["loop_status"] == "passed"
    assert loop["execution_occurred"] is True
    assert loop["selected_batch_status"] == "blocked"
    assert result["progress_update"]["new_batch_status"] == "blocked"


def test_stage_mismatch_fails_closed(tmp_path: Path, monkeypatch) -> None:
    original_authorize = loop_validator.authorize_selected_batch

    def _mismatch_authorize(*args, **kwargs):
        payload = original_authorize(*args, **kwargs)
        payload["selected_batch_id"] = "BATCH-J"
        return payload

    monkeypatch.setattr(loop_validator, "authorize_selected_batch", _mismatch_authorize)
    result = validate_single_batch_execution_loop(
        _roadmap(),
        _selection_signals(),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        evaluated_at="2026-04-03T19:00:00Z",
        executed_at="2026-04-03T19:01:00Z",
        validated_at="2026-04-03T19:02:00Z",
        source_refs={"selection_result": "x", "authorization_result": "y"},
        pqx_execute_fn=_pqx_success,
    )
    loop = result["loop_validation"]
    assert loop["loop_status"] == "failed_closed"
    assert "SELECTION_AUTHORIZATION_MISMATCH" in loop["reason_codes"]


def test_replay_chain_missing_required_artifact_fails_closed(tmp_path: Path) -> None:
    result = validate_single_batch_execution_loop(
        _roadmap(),
        _selection_signals(),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        evaluated_at="2026-04-03T19:00:00Z",
        executed_at="2026-04-03T19:01:00Z",
        validated_at="2026-04-03T19:02:00Z",
        source_refs={"pqx_result": ""},
        pqx_execute_fn=_pqx_success,
    )
    loop = result["loop_validation"]
    assert loop["replay_ready"] is False
    assert loop["loop_status"] == "failed_closed"
    assert "REPLAY_CHAIN_INCOMPLETE" in loop["reason_codes"]


def test_determinism_same_inputs_identical_loop_artifact(tmp_path: Path) -> None:
    kwargs = {
        "roadmap_artifact": _roadmap(),
        "selection_signals": _selection_signals(),
        "authorization_signals": _authorization_signals(),
        "pqx_state_path": tmp_path / "pqx" / "state.json",
        "pqx_runs_root": tmp_path / "pqx",
        "evaluated_at": "2026-04-03T19:00:00Z",
        "executed_at": "2026-04-03T19:01:00Z",
        "validated_at": "2026-04-03T19:02:00Z",
        "pqx_execute_fn": _pqx_success,
    }
    first = validate_single_batch_execution_loop(**kwargs)
    second = validate_single_batch_execution_loop(**kwargs)
    assert first["loop_validation"] == second["loop_validation"]


def test_single_batch_guarantee_rejects_multi_batch_status_mutation(tmp_path: Path, monkeypatch) -> None:
    original_execute = loop_validator.execute_authorized_batch

    def _execute_with_chain(*args, **kwargs):
        payload = original_execute(*args, **kwargs)
        for batch in payload["roadmap"]["batches"]:
            if batch["batch_id"] == "BATCH-J":
                batch["status"] = "running"
        return payload

    monkeypatch.setattr(loop_validator, "execute_authorized_batch", _execute_with_chain)

    result = validate_single_batch_execution_loop(
        _roadmap(),
        _selection_signals(),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        evaluated_at="2026-04-03T19:00:00Z",
        executed_at="2026-04-03T19:01:00Z",
        validated_at="2026-04-03T19:02:00Z",
        pqx_execute_fn=_pqx_success,
    )

    loop = result["loop_validation"]
    assert loop["loop_status"] == "failed_closed"
    assert "MULTI_BATCH_EXECUTION_DETECTED" in loop["reason_codes"]


def test_contract_example_and_generated_payload_validate(tmp_path: Path) -> None:
    schema = load_schema("roadmap_execution_loop_validation")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        load_example("roadmap_execution_loop_validation")
    )

    generated = validate_single_batch_execution_loop(
        _roadmap(),
        _selection_signals(),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        evaluated_at="2026-04-03T19:00:00Z",
        executed_at="2026-04-03T19:01:00Z",
        validated_at="2026-04-03T19:02:00Z",
        pqx_execute_fn=_pqx_success,
    )["loop_validation"]
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(generated)
    assert json.loads(json.dumps(generated, sort_keys=True)) == generated
