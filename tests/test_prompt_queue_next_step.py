"""Tests for deterministic prompt queue next-step orchestration."""

from __future__ import annotations

import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    NextStepOrchestrationError,
    NextStepQueueIntegrationError,
    Priority,
    RiskLevel,
    WorkItemStatus,
    apply_next_step_action_to_queue,
    determine_next_step_action,
    make_queue_state,
    make_work_item,
    validate_next_step_action_artifact,
    validate_queue_state,
    validate_work_item,
)


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if not self._values:
            return datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc)
        return self._values.pop(0)


def _executed_item(status: str = WorkItemStatus.EXECUTED_FAILURE.value) -> dict:
    item = make_work_item(
        work_item_id="wi-parent.repair.1",
        prompt_id="prompt-parent:repair:1",
        title="Repair child",
        priority=Priority.HIGH,
        risk_level=RiskLevel.MEDIUM,
        repo="spectrum-systems",
        branch="feature/next-step",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        parent_work_item_id="wi-parent",
        clock=FixedClock(["2026-03-22T04:00:00Z"]),
    )
    item["status"] = status
    item["repair_loop_generation"] = 1
    item["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json"
    item["spawned_from_findings_artifact_path"] = "artifacts/prompt_queue/findings/wi-parent.findings.json"
    item["spawned_from_review_artifact_path"] = "docs/reviews/2026-03-22-parent-review.md"
    item["gating_decision_artifact_path"] = "artifacts/prompt_queue/gating/wi-parent.repair.1.execution_gating_decision.json"
    item["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-parent.repair.1.execution_result.json"
    item["post_execution_decision_artifact_path"] = "artifacts/prompt_queue/post_execution_decisions/queue-01.wi-parent.repair.1.post_execution_decision.json"
    return item


def _post_execution_decision(decision_status: str) -> dict:
    art = load_example("prompt_queue_post_execution_decision")
    art["work_item_id"] = "wi-parent.repair.1"
    art["parent_work_item_id"] = "wi-parent"
    art["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-parent.repair.1.execution_result.json"
    art["gating_decision_artifact_path"] = "artifacts/prompt_queue/gating/wi-parent.repair.1.execution_gating_decision.json"
    art["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json"
    art["decision_status"] = decision_status
    art["decision_reason_code"] = {
        "complete": "complete_execution_success",
        "review_required": "review_required_execution_failure_within_generation_limit",
        "reentry_eligible": "review_required_execution_failure_within_generation_limit",
        "reentry_blocked": "reentry_blocked_generation_limit_reached",
    }[decision_status]
    art["execution_status"] = "success" if decision_status == "complete" else "failure"
    art["generated_at"] = "2026-03-22T04:01:00Z"
    return art


def test_complete_maps_to_marked_complete_without_child_spawn():
    item = _executed_item(status=WorkItemStatus.EXECUTED_SUCCESS.value)
    decision = _post_execution_decision("complete")
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T04:00:00Z"]))

    action = determine_next_step_action(
        work_item=item,
        post_execution_decision_artifact=decision,
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T04:02:00Z", "2026-03-22T04:02:01Z"]),
    )

    updated_queue, updated_item, spawned_child, updated_action = apply_next_step_action_to_queue(
        queue_state=queue,
        work_item_id=item["work_item_id"],
        next_step_action_artifact=action,
        next_step_action_artifact_path="artifacts/prompt_queue/next_step_actions/queue-01.wi-parent.repair.1.next_step_action.json",
        clock=FixedClock(["2026-03-22T04:03:00Z", "2026-03-22T04:03:01Z", "2026-03-22T04:03:02Z"]),
    )

    assert updated_action["action_status"] == "marked_complete"
    assert updated_item["status"] == WorkItemStatus.COMPLETE.value
    assert spawned_child is None
    validate_work_item(updated_item)
    validate_queue_state(updated_queue)


def test_review_required_maps_to_spawn_review_and_creates_child():
    item = _executed_item()
    decision = _post_execution_decision("review_required")
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T04:00:00Z"]))

    action = determine_next_step_action(
        work_item=item,
        post_execution_decision_artifact=decision,
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T04:02:00Z", "2026-03-22T04:02:01Z"]),
    )

    updated_queue, updated_item, spawned_child, updated_action = apply_next_step_action_to_queue(
        queue_state=queue,
        work_item_id=item["work_item_id"],
        next_step_action_artifact=action,
        next_step_action_artifact_path="artifacts/prompt_queue/next_step_actions/queue-01.wi-parent.repair.1.next_step_action.json",
        clock=FixedClock(["2026-03-22T04:03:00Z", "2026-03-22T04:03:01Z", "2026-03-22T04:03:02Z"]),
    )

    assert updated_item["status"] == WorkItemStatus.REVIEW_REQUIRED.value
    assert spawned_child is not None
    assert spawned_child["work_item_id"] == "wi-parent.repair.1.review.1"
    assert updated_action["spawned_work_item_id"] == spawned_child["work_item_id"]
    assert spawned_child["post_execution_decision_artifact_path"] == item["post_execution_decision_artifact_path"]
    validate_work_item(spawned_child)
    validate_queue_state(updated_queue)


def test_reentry_eligible_maps_to_spawn_reentry_child_and_creates_child():
    item = _executed_item()
    decision = _post_execution_decision("reentry_eligible")
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T04:00:00Z"]))

    action = determine_next_step_action(
        work_item=item,
        post_execution_decision_artifact=decision,
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T04:02:00Z", "2026-03-22T04:02:01Z"]),
    )

    updated_queue, updated_item, spawned_child, updated_action = apply_next_step_action_to_queue(
        queue_state=queue,
        work_item_id=item["work_item_id"],
        next_step_action_artifact=action,
        next_step_action_artifact_path="artifacts/prompt_queue/next_step_actions/queue-01.wi-parent.repair.1.next_step_action.json",
        clock=FixedClock(["2026-03-22T04:03:00Z", "2026-03-22T04:03:01Z", "2026-03-22T04:03:02Z"]),
    )

    assert updated_item["status"] == WorkItemStatus.REENTRY_ELIGIBLE.value
    assert spawned_child is not None
    assert spawned_child["work_item_id"] == "wi-parent.repair.1.reentry.1"
    assert updated_action["spawned_work_item_id"] == spawned_child["work_item_id"]


def test_reentry_blocked_maps_to_blocked_no_action():
    item = _executed_item()
    decision = _post_execution_decision("reentry_blocked")
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T04:00:00Z"]))

    action = determine_next_step_action(
        work_item=item,
        post_execution_decision_artifact=decision,
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T04:02:00Z", "2026-03-22T04:02:01Z"]),
    )
    updated_queue, updated_item, spawned_child, updated_action = apply_next_step_action_to_queue(
        queue_state=queue,
        work_item_id=item["work_item_id"],
        next_step_action_artifact=action,
        next_step_action_artifact_path="artifacts/prompt_queue/next_step_actions/queue-01.wi-parent.repair.1.next_step_action.json",
        clock=FixedClock(["2026-03-22T04:03:00Z", "2026-03-22T04:03:01Z", "2026-03-22T04:03:02Z"]),
    )

    assert updated_action["action_status"] == "blocked_no_action"
    assert updated_item["status"] == WorkItemStatus.REENTRY_BLOCKED.value
    assert spawned_child is None
    validate_queue_state(updated_queue)


def test_missing_or_invalid_post_execution_decision_fails_closed():
    item = _executed_item()
    bad_decision = _post_execution_decision("review_required")
    bad_decision.pop("decision_status")

    with pytest.raises(NextStepOrchestrationError, match="Malformed post-execution decision artifact"):
        determine_next_step_action(
            work_item=item,
            post_execution_decision_artifact=bad_decision,
            post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
            execution_result_artifact_path=item["execution_result_artifact_path"],
            source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        )


def test_duplicate_spawn_attempt_fails_closed():
    item = _executed_item()
    decision = _post_execution_decision("review_required")
    existing_child = make_work_item(
        work_item_id="wi-parent.repair.1.review.1",
        prompt_id="prompt-parent:repair:1:review:1",
        title="Repair child [review 1]",
        priority=Priority.HIGH,
        risk_level=RiskLevel.MEDIUM,
        repo="spectrum-systems",
        branch="feature/next-step",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        parent_work_item_id="wi-parent.repair.1",
        clock=FixedClock(["2026-03-22T04:00:30Z"]),
    )
    queue = make_queue_state(
        queue_id="queue-01",
        work_items=[item, existing_child],
        clock=FixedClock(["2026-03-22T04:00:00Z"]),
    )
    action = determine_next_step_action(
        work_item=item,
        post_execution_decision_artifact=decision,
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T04:02:00Z", "2026-03-22T04:02:01Z"]),
    )

    with pytest.raises(NextStepQueueIntegrationError, match="Duplicate spawn detected"):
        apply_next_step_action_to_queue(
            queue_state=queue,
            work_item_id=item["work_item_id"],
            next_step_action_artifact=action,
            next_step_action_artifact_path="artifacts/prompt_queue/next_step_actions/queue-01.wi-parent.repair.1.next_step_action.json",
            clock=FixedClock(["2026-03-22T04:03:00Z", "2026-03-22T04:03:01Z", "2026-03-22T04:03:02Z"]),
        )


def test_malformed_work_item_or_invalid_state_fails_closed():
    malformed = _executed_item()
    malformed.pop("scope_paths")

    with pytest.raises(NextStepOrchestrationError, match="Malformed work item"):
        determine_next_step_action(
            work_item=malformed,
            post_execution_decision_artifact=_post_execution_decision("review_required"),
            post_execution_decision_artifact_path="artifacts/prompt_queue/post_execution_decisions/queue-01.wi-parent.repair.1.post_execution_decision.json",
            execution_result_artifact_path="artifacts/prompt_queue/execution_results/wi-parent.repair.1.execution_result.json",
            source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        )


def test_next_step_action_artifact_validates_against_schema():
    validate_next_step_action_artifact(load_example("prompt_queue_next_step_action"))


def test_queue_and_work_item_updates_are_deterministic_and_schema_valid():
    item = _executed_item()
    decision = _post_execution_decision("review_required")
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T04:00:00Z"]))

    action = determine_next_step_action(
        work_item=item,
        post_execution_decision_artifact=decision,
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T04:02:00Z", "2026-03-22T04:02:01Z"]),
    )

    updated_queue, updated_item, spawned_child, updated_action = apply_next_step_action_to_queue(
        queue_state=queue,
        work_item_id=item["work_item_id"],
        next_step_action_artifact=action,
        next_step_action_artifact_path="artifacts/prompt_queue/next_step_actions/queue-01.wi-parent.repair.1.next_step_action.json",
        clock=FixedClock(["2026-03-22T04:03:00Z", "2026-03-22T04:03:01Z", "2026-03-22T04:03:02Z"]),
    )

    assert updated_item["next_step_action_artifact_path"].endswith("next_step_action.json")
    assert spawned_child is not None
    assert updated_action["spawned_work_item_id"] == spawned_child["work_item_id"]
    validate_work_item(updated_item)
    validate_work_item(spawned_child)
    validate_queue_state(updated_queue)


def _assert_integration_fails_closed_without_mutation(
    *,
    queue_state: dict,
    item: dict,
    action: dict,
    expected_error: str | None = None,
) -> None:
    queue_before = copy.deepcopy(queue_state)
    if expected_error is None:
        with pytest.raises(NextStepQueueIntegrationError):
            apply_next_step_action_to_queue(
                queue_state=queue_state,
                work_item_id=item["work_item_id"],
                next_step_action_artifact=action,
                next_step_action_artifact_path="artifacts/prompt_queue/next_step_actions/queue-01.wi-parent.repair.1.next_step_action.json",
                clock=FixedClock(["2026-03-22T04:03:00Z", "2026-03-22T04:03:01Z", "2026-03-22T04:03:02Z"]),
            )
    else:
        with pytest.raises(NextStepQueueIntegrationError, match=expected_error):
            apply_next_step_action_to_queue(
                queue_state=queue_state,
                work_item_id=item["work_item_id"],
                next_step_action_artifact=action,
                next_step_action_artifact_path="artifacts/prompt_queue/next_step_actions/queue-01.wi-parent.repair.1.next_step_action.json",
                clock=FixedClock(["2026-03-22T04:03:00Z", "2026-03-22T04:03:01Z", "2026-03-22T04:03:02Z"]),
            )
    assert queue_state == queue_before
    assert len(queue_state["work_items"]) == len(queue_before["work_items"]) == 1
    assert queue_state["work_items"][0]["child_work_item_ids"] == []
    assert queue_state["work_items"][0]["next_step_action_artifact_path"] is None


def test_integration_rejects_complete_with_spawn_review_tuple_mismatch():
    item = _executed_item(status=WorkItemStatus.EXECUTED_SUCCESS.value)
    decision = _post_execution_decision("complete")
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T04:00:00Z"]))
    action = determine_next_step_action(
        work_item=item,
        post_execution_decision_artifact=decision,
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T04:02:00Z", "2026-03-22T04:02:01Z"]),
    )
    action["action_status"] = "spawn_review"
    action["action_reason_code"] = "spawn_review_from_post_execution_review_required"

    _assert_integration_fails_closed_without_mutation(
        queue_state=queue,
        item=item,
        action=action,
    )


def test_integration_rejects_review_required_with_marked_complete_tuple_mismatch():
    item = _executed_item()
    decision = _post_execution_decision("review_required")
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T04:00:00Z"]))
    action = determine_next_step_action(
        work_item=item,
        post_execution_decision_artifact=decision,
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T04:02:00Z", "2026-03-22T04:02:01Z"]),
    )
    action["action_status"] = "marked_complete"
    action["action_reason_code"] = "marked_complete_from_post_execution_complete"

    _assert_integration_fails_closed_without_mutation(
        queue_state=queue,
        item=item,
        action=action,
    )


def test_integration_rejects_reentry_blocked_with_non_blocked_reason_code():
    item = _executed_item()
    decision = _post_execution_decision("reentry_blocked")
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T04:00:00Z"]))
    action = determine_next_step_action(
        work_item=item,
        post_execution_decision_artifact=decision,
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T04:02:00Z", "2026-03-22T04:02:01Z"]),
    )
    action["action_reason_code"] = "spawn_review_from_post_execution_review_required"

    _assert_integration_fails_closed_without_mutation(
        queue_state=queue,
        item=item,
        action=action,
    )


def test_integration_rejects_mismatched_reason_code_for_valid_decision_action_pair():
    item = _executed_item()
    decision = _post_execution_decision("review_required")
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T04:00:00Z"]))
    action = determine_next_step_action(
        work_item=item,
        post_execution_decision_artifact=decision,
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T04:02:00Z", "2026-03-22T04:02:01Z"]),
    )
    action["action_reason_code"] = "spawn_reentry_child_from_post_execution_reentry_eligible"

    _assert_integration_fails_closed_without_mutation(
        queue_state=queue,
        item=item,
        action=action,
    )
