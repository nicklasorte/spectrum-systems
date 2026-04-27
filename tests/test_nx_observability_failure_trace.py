"""NX-13..15: Observability 5-step failure trace + debuggability red team."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.observability.failure_trace import (
    CANONICAL_STAGES,
    OWNING_SYSTEM_BY_STAGE,
    build_failure_trace,
)


def _good_inputs() -> dict:
    return {
        "execution_record": {
            "artifact_id": "exec-1",
            "artifact_type": "pqx_slice_execution_record",
            "status": "ok",
        },
        "output_artifact": {
            "artifact_id": "out-1",
            "artifact_type": "eval_summary",
        },
        "eval_result": {
            "artifact_id": "eval-1",
            "artifact_type": "eval_slice_summary",
            "status": "healthy",
        },
        "control_decision": {
            "decision_id": "cde-1",
            "decision": "allow",
        },
        "enforcement_action": {
            "enforcement_id": "sel-1",
            "enforcement_action": "allow_execution",
        },
    }


def test_full_passing_trace_yields_ok() -> None:
    trace = build_failure_trace(trace_id="t1", **_good_inputs())
    assert trace["overall_status"] == "ok"
    assert trace["failed_stage"] is None
    assert len(trace["steps"]) == 5
    assert [step["stage"] for step in trace["steps"]] == list(CANONICAL_STAGES)


def test_failure_trace_produces_machine_and_human_output() -> None:
    inputs = _good_inputs()
    trace = build_failure_trace(trace_id="t1", **inputs)
    assert "human_readable" in trace
    assert "trace_id=t1" in trace["human_readable"]
    assert "execution" in trace["human_readable"]


# ---- NX-14: red team — every common failure must surface diagnostic fields ----


def test_red_team_missing_execution_record_fails_trace() -> None:
    inputs = _good_inputs()
    inputs["execution_record"] = None
    trace = build_failure_trace(trace_id="t1", **inputs)
    assert trace["overall_status"] == "failed"
    assert trace["failed_stage"] == "execution"
    assert trace["owning_system_for_failed_stage"] == "PQX"
    assert trace["primary_reason_code"] == "OBS_MISSING_EXECUTION_RECORD"
    assert trace["next_recommended_action"]


def test_red_team_missing_output_artifact_fails_trace() -> None:
    inputs = _good_inputs()
    inputs["output_artifact"] = None
    trace = build_failure_trace(trace_id="t1", **inputs)
    assert trace["failed_stage"] == "output"
    assert trace["primary_reason_code"] == "OBS_MISSING_OUTPUT_ARTIFACT"


def test_red_team_blocked_eval_summary_fails_trace() -> None:
    inputs = _good_inputs()
    inputs["eval_result"] = {
        "artifact_id": "eval-bad",
        "artifact_type": "eval_slice_summary",
        "status": "blocked",
        "block_reason": "missing_required_eval_result",
    }
    trace = build_failure_trace(trace_id="t1", **inputs)
    assert trace["failed_stage"] == "eval"
    assert trace["owning_system_for_failed_stage"] == "EVL"
    assert "remediate" in trace["next_recommended_action"]


def test_red_team_blocking_control_decision_fails_trace() -> None:
    inputs = _good_inputs()
    inputs["control_decision"] = {
        "decision_id": "cde-bad",
        "decision": "block",
        "reason_code": "required_eval_failed",
    }
    trace = build_failure_trace(trace_id="t1", **inputs)
    assert trace["failed_stage"] == "control"
    assert trace["primary_reason_code"] == "required_eval_failed"


def test_red_team_deny_enforcement_fails_trace() -> None:
    inputs = _good_inputs()
    inputs["enforcement_action"] = {
        "enforcement_id": "sel-bad",
        "enforcement_action": "deny_execution",
        "reason_code": "policy_mismatch",
    }
    trace = build_failure_trace(trace_id="t1", **inputs)
    assert trace["failed_stage"] == "enforcement"
    assert trace["owning_system_for_failed_stage"] == "SEL"


def test_red_team_first_failure_wins_for_blocking_attribution() -> None:
    """If multiple stages fail, attribution falls on the earliest stage."""
    trace = build_failure_trace(
        trace_id="t1",
        execution_record={
            "artifact_id": "exec-fail",
            "status": "error",
            "reason_code": "PQX_TIMEOUT",
        },
        output_artifact=None,
        eval_result={"status": "blocked", "block_reason": "missing_required_eval_result"},
        control_decision={"decision_id": "x", "decision": "block"},
        enforcement_action={"enforcement_action": "deny_execution"},
    )
    assert trace["failed_stage"] == "execution"
    assert trace["owning_system_for_failed_stage"] == "PQX"


def test_red_team_every_step_carries_required_diagnostic_fields() -> None:
    """For every step the trace must include stage, owning_system, status,
    reason_code (or null), artifact_id (or null), and a next-action when
    the step failed."""
    trace = build_failure_trace(
        trace_id="t1",
        execution_record=None,
        output_artifact=None,
        eval_result=None,
        control_decision=None,
        enforcement_action=None,
    )
    assert trace["overall_status"] == "failed"
    for step in trace["steps"]:
        assert "stage" in step
        assert "owning_system" in step
        assert "status" in step
        assert step["owning_system"] == OWNING_SYSTEM_BY_STAGE[step["stage"]]
        if step["status"] == "missing":
            assert step["reason_code"], "missing step must carry a reason_code"
            assert step["next_recommended_action"], "missing step must propose a next action"
