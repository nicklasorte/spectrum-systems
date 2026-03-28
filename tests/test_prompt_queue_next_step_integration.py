"""Tests for transition-based next-step integrations with no queue advancement side effects."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    LoopControlQueueIntegrationError,
    NextStepQueueIntegrationError,
    PostExecutionQueueIntegrationError,
    Priority,
    RiskLevel,
    emit_loop_control_transition_receipt,
    emit_next_step_transition_receipt,
    emit_post_execution_transition_receipt,
    make_queue_state,
    make_work_item,
)


def _queue_state() -> dict:
    item = make_work_item(
        work_item_id="wi-001",
        prompt_id="prompt-001",
        title="queue test",
        priority=Priority.MEDIUM,
        risk_level=RiskLevel.MEDIUM,
        repo="spectrum-systems",
        branch="feature/queue-04",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
    )
    return make_queue_state(queue_id="queue-001", work_items=[item])


def _transition(action: str, status: str = "allowed") -> dict:
    return {
        "transition_decision_id": "transition-decision-step-001-20260328T120001Z",
        "step_id": "step-001",
        "queue_id": "queue-001",
        "trace_linkage": "trace-001",
        "source_decision_ref": "step-decision-step-001-20260328T115959Z",
        "transition_action": action,
        "transition_status": status,
        "reason_codes": ["allow_clean_findings_continue"] if status == "allowed" else ["block_invalid_report_fail_closed"],
        "blocking_reasons": [] if status == "allowed" else ["conflicting_signals"],
        "derived_from_artifacts": ["execres-wi-001-attempt-1"],
        "timestamp": "2026-03-28T12:00:01Z",
    }


def test_next_step_integration_emits_receipt_and_does_not_mutate_queue():
    queue = _queue_state()
    original = copy.deepcopy(queue)
    receipt = emit_next_step_transition_receipt(
        queue_state=queue,
        transition_decision_artifact=_transition("continue"),
        transition_decision_artifact_path="artifacts/prompt_queue/transition/step-001.json",
    )
    assert receipt["queue_mutation_performed"] is False
    assert queue == original


def test_post_execution_integration_emits_receipt_and_does_not_mutate_queue():
    queue = _queue_state()
    original = copy.deepcopy(queue)
    receipt = emit_post_execution_transition_receipt(
        queue_state=queue,
        transition_decision_artifact=_transition("request_review"),
        transition_decision_artifact_path="artifacts/prompt_queue/transition/step-001.json",
    )
    assert receipt["queue_mutation_performed"] is False
    assert queue == original


def test_loop_control_integration_emits_receipt_for_retry_allowed_only():
    queue = _queue_state()
    receipt = emit_loop_control_transition_receipt(
        queue_state=queue,
        transition_decision_artifact=_transition("retry_allowed"),
        transition_decision_artifact_path="artifacts/prompt_queue/transition/step-001.json",
    )
    assert receipt["transition_action"] == "retry_allowed"


def test_loop_control_integration_fails_closed_on_non_loop_action():
    queue = _queue_state()
    with pytest.raises(LoopControlQueueIntegrationError, match="not loop-control eligible"):
        emit_loop_control_transition_receipt(
            queue_state=queue,
            transition_decision_artifact=_transition("continue"),
            transition_decision_artifact_path="artifacts/prompt_queue/transition/step-001.json",
        )


def test_next_step_integration_fails_closed_on_ambiguous_block_status():
    queue = _queue_state()
    with pytest.raises(NextStepQueueIntegrationError):
        emit_next_step_transition_receipt(
            queue_state=queue,
            transition_decision_artifact=_transition("block", "allowed"),
            transition_decision_artifact_path="artifacts/prompt_queue/transition/step-001.json",
        )


def test_post_execution_integration_fails_closed_on_invalid_transition_artifact():
    queue = _queue_state()
    bad = _transition("continue")
    bad.pop("source_decision_ref")
    with pytest.raises(PostExecutionQueueIntegrationError):
        emit_post_execution_transition_receipt(
            queue_state=queue,
            transition_decision_artifact=bad,
            transition_decision_artifact_path="artifacts/prompt_queue/transition/step-001.json",
        )
