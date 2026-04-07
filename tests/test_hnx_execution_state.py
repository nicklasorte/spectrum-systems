from __future__ import annotations

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.hnx_execution_state import (
    apply_resume,
    create_async_wait,
    create_checkpoint,
    evaluate_long_running_policy,
    validate_handoff,
    validate_resume,
)


def _stage_contract(execution_mode: str = "continuous") -> dict:
    return {
        "contract_id": "stage-contract-1",
        "execution_mode": execution_mode,
        "resume_policy": {
            "allowed": True,
            "validation_required": True,
            "max_resume_age_minutes": 60,
        },
        "async_policy": {
            "allowed": True,
            "max_wait_minutes": 30,
            "timeout_behavior": "freeze",
        },
        "compaction_policy": {
            "allowed": True,
            "trigger": "context_size",
            "strategy": "summarize",
        },
    }


def _checkpoint() -> dict:
    return {
        "artifact_type": "checkpoint_record",
        "checkpoint_id": "cp-1",
        "state_snapshot": {
            "required_inputs": ["a"],
            "observed_outputs": ["b"],
            "eval_refs": ["eval-1"],
            "control_refs": ["ctrl-1"],
            "pending_actions": ["pending"],
        },
    }


def test_checkpoint_creation_is_deterministic() -> None:
    kwargs = {
        "checkpoint_id": "cp-1",
        "workflow_id": "wf-1",
        "stage_contract_id": "stage-contract-1",
        "stage_name": "promoted",
        "stage_sequence": 2,
        "execution_mode": "continuous",
        "state_snapshot": {
            "required_inputs": ["a"],
            "observed_outputs": ["b"],
            "eval_refs": ["eval-1"],
            "control_refs": ["ctrl-1"],
            "pending_actions": ["pending"],
        },
        "execution_context": {"iteration_count": 1, "elapsed_time_minutes": 10, "cost_accumulated_usd": 0.2},
        "created_at": "2026-04-07T00:00:00Z",
        "trace": {"trace_id": "trace-1", "agent_run_id": "run-1"},
        "provenance": {"created_by": "spectrum-systems", "source": "test", "version": "1.0.0"},
    }
    first = create_checkpoint(**kwargs)
    second = create_checkpoint(**kwargs)
    assert first == second


def test_resume_validation_expired_fails() -> None:
    result = validate_resume(
        checkpoint_record=_checkpoint(),
        resume_policy=_stage_contract()["resume_policy"],
        checkpoint_age_minutes=120,
        has_validation_evidence=True,
    )
    assert result["allowed"] is False
    assert "RESUME_AGE_EXCEEDED" in result["policy_failures"]


def test_resume_apply_requires_validated_resume() -> None:
    blocked = apply_resume(resume_validation={"allowed": False}, checkpoint_record=_checkpoint())
    assert blocked["applied"] is False

    allowed = apply_resume(resume_validation={"allowed": True}, checkpoint_record=_checkpoint())
    assert allowed["applied"] is True
    assert allowed["state_snapshot"]["required_inputs"] == ["a"]


def test_handoff_validation_fails_for_reset_mode_when_missing() -> None:
    result = validate_handoff(handoff_artifact=None, stage_contract=_stage_contract(execution_mode="reset_with_handoff"))
    assert result["allowed"] is False
    assert "HANDOFF_REQUIRED" in result["validation_failures"]


def test_async_wait_creation_obeys_policy() -> None:
    stage_contract = _stage_contract()
    created = create_async_wait(
        checkpoint_id="cp-1",
        wait_id="wait-1",
        wait_condition="dependency_ready",
        trigger_type="dependency",
        created_at="2026-04-07T00:00:00Z",
        trace={"trace_id": "trace-1", "agent_run_id": "run-1"},
        async_policy=stage_contract["async_policy"],
    )
    assert created["result"]["allowed"] is True
    assert created["artifact"]["artifact_type"] == "async_wait_record"

    stage_contract["async_policy"]["allowed"] = False
    blocked = create_async_wait(
        checkpoint_id="cp-1",
        wait_id="wait-1",
        wait_condition="dependency_ready",
        trigger_type="dependency",
        created_at="2026-04-07T00:00:00Z",
        trace={"trace_id": "trace-1", "agent_run_id": "run-1"},
        async_policy=stage_contract["async_policy"],
    )
    assert blocked["result"]["allowed"] is False


def test_long_running_policy_timeout_obeys_contract_behavior() -> None:
    stage_contract = _stage_contract()
    freeze = evaluate_long_running_policy(
        stage_contract=stage_contract,
        checkpoint_record=_checkpoint(),
        handoff_artifact=None,
        request_resume=False,
        checkpoint_age_minutes=0,
        has_resume_validation_evidence=False,
        request_async_wait=True,
        wait_elapsed_minutes=45,
    )
    assert freeze["recommended_state"] == "freeze"

    stage_contract["async_policy"]["timeout_behavior"] = "block"
    blocked = evaluate_long_running_policy(
        stage_contract=stage_contract,
        checkpoint_record=_checkpoint(),
        handoff_artifact=None,
        request_resume=False,
        checkpoint_age_minutes=0,
        has_resume_validation_evidence=False,
        request_async_wait=True,
        wait_elapsed_minutes=45,
    )
    assert blocked["recommended_state"] == "block"


def test_hnx_schemas_validate_and_fail_closed() -> None:
    checkpoint_schema = Draft202012Validator(load_schema("checkpoint_record"))
    valid_checkpoint = {
        "artifact_type": "checkpoint_record",
        "schema_version": "1.0.0",
        "checkpoint_id": "cp-1",
        "workflow_id": "wf-1",
        "stage_contract_id": "stage-contract-1",
        "stage_name": "promoted",
        "stage_sequence": 6,
        "execution_mode": "continuous",
        "state_snapshot": {
            "required_inputs": ["a"],
            "observed_outputs": ["b"],
            "eval_refs": ["eval-1"],
            "control_refs": ["ctrl-1"],
            "pending_actions": ["pending"],
        },
        "execution_context": {"iteration_count": 1, "elapsed_time_minutes": 1, "cost_accumulated_usd": 0.01},
        "created_at": "2026-04-07T00:00:00Z",
        "trace": {"trace_id": "trace-1", "agent_run_id": "run-1"},
        "content_hash": "0" * 64,
        "provenance": {"created_by": "spectrum-systems", "source": "test", "version": "1.0.0"},
    }
    checkpoint_schema.validate(valid_checkpoint)
    invalid_checkpoint = dict(valid_checkpoint)
    invalid_checkpoint.pop("state_snapshot")
    assert list(checkpoint_schema.iter_errors(invalid_checkpoint))

    resume_schema = Draft202012Validator(load_schema("resume_record"))
    valid_resume = {
        "artifact_type": "resume_record",
        "schema_version": "1.0.0",
        "resume_id": "resume-1",
        "checkpoint_id": "cp-1",
        "resume_reason": "operator_requested",
        "resumed_at": "2026-04-07T00:00:00Z",
        "validation_result": {"status": "valid", "reason_codes": ["OK"]},
        "trace": {"trace_id": "trace-1", "agent_run_id": "run-1"},
    }
    resume_schema.validate(valid_resume)

    handoff_schema = Draft202012Validator(load_schema("handoff_artifact"))
    invalid_handoff = {
        "artifact_type": "handoff_artifact",
        "schema_version": "1.0.0",
        "handoff_id": "h-1",
        "from_stage": "a",
        "to_stage": "b",
        "stage_contract_id": "stage-contract-1",
        "required_state": ["ctx"],
        "state_snapshot_ref": "artifacts/state.json",
        "created_at": "2026-04-07T00:00:00Z",
        "trace": {"trace_id": "trace-1", "agent_run_id": "run-1"},
    }
    assert list(handoff_schema.iter_errors(invalid_handoff))
