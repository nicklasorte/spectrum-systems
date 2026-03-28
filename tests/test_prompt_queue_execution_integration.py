"""Integration tests for normalized queue-step execution adapter boundary."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    ExecutionQueueIntegrationError,
    Priority,
    RiskLevel,
    WorkItemStatus,
    make_queue_state,
    make_work_item,
    run_queue_step_execution_adapter,
    transition_to_executing,
)


def _queue_and_step() -> tuple[dict, dict, dict]:
    item = make_work_item(
        work_item_id="wi-q2-int-1",
        prompt_id="prompt-q2-int-1",
        title="adapter",
        priority=Priority.MEDIUM,
        risk_level=RiskLevel.MEDIUM,
        repo="spectrum-systems",
        branch="main",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
    )
    item["status"] = WorkItemStatus.RUNNABLE.value
    item["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-q2-int.repair_prompt.json"
    item["spawned_from_findings_artifact_path"] = "artifacts/prompt_queue/findings/wi-q2-int.findings.json"
    item["spawned_from_review_artifact_path"] = "docs/reviews/2026-03-28-q2-int.md"
    item["gating_decision_artifact_path"] = "artifacts/prompt_queue/gating/wi-q2-int.execution_gating_decision.json"

    queue_state = make_queue_state(queue_id="queue-q2-int", work_items=[item])
    step = {"step_id": "step-001", "work_item_id": "wi-q2-int-1", "execution_mode": "simulated"}

    gating = load_example("prompt_queue_execution_gating_decision")
    gating["work_item_id"] = "wi-q2-int-1"
    gating["decision_status"] = "runnable"
    gating["decision_reason_code"] = "runnable_within_policy"
    return queue_state, step, gating


def test_integration_uses_normalized_adapter_without_state_transition():
    queue_state, step, gating = _queue_and_step()
    result = run_queue_step_execution_adapter(
        queue_state=queue_state,
        step=step,
        input_refs={"gating_decision_artifact": gating, "source_queue_state_path": "artifacts/prompt_queue/queue_state.json"},
    )
    assert result["queue_id"] == "queue-q2-int"
    assert queue_state["work_items"][0]["status"] == WorkItemStatus.RUNNABLE.value


def test_adapter_failure_does_not_advance_queue_logic():
    queue_state, step, gating = _queue_and_step()
    with pytest.raises(ExecutionQueueIntegrationError):
        run_queue_step_execution_adapter(
            queue_state=queue_state,
            step=step,
            input_refs={"gating_decision_artifact": gating, "unexpected": "x"},
        )


def test_existing_transition_seam_still_required_for_state_changes():
    queue_state, _, _ = _queue_and_step()
    queue_executing, _ = transition_to_executing(queue_state=queue_state, work_item_id="wi-q2-int-1")
    assert queue_executing["work_items"][0]["status"] == WorkItemStatus.EXECUTING.value
