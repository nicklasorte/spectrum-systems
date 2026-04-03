"""Tests for deterministic prompt queue automatic review triggering."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    Priority,
    ReviewTriggerQueueIntegrationError,
    RiskLevel,
    WorkItemStatus,
    apply_review_trigger_to_queue,
    evaluate_review_trigger_policy,
    make_queue_state,
    make_work_item,
    validate_queue_state,
    validate_review_trigger_artifact,
    validate_work_item,
)


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if not self._values:
            return datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc)
        return self._values.pop(0)


def _executed_item(status: str = WorkItemStatus.REVIEW_REQUIRED.value) -> dict:
    item = make_work_item(
        work_item_id="wi-parent.repair.1",
        prompt_id="prompt-parent:repair:1",
        title="Repair child",
        priority=Priority.HIGH,
        risk_level=RiskLevel.MEDIUM,
        repo="spectrum-systems",
        branch="feature/review-trigger",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        parent_work_item_id="wi-parent",
        clock=FixedClock(["2026-03-22T05:00:00Z"]),
    )
    item["status"] = status
    item["generation_count"] = 1
    item["repair_loop_generation"] = 1
    item["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-parent.repair.1.execution_result.json"
    item["post_execution_decision_artifact_path"] = (
        "artifacts/prompt_queue/post_execution_decisions/queue-01.wi-parent.repair.1.post_execution_decision.json"
    )
    item["loop_control_decision_artifact_path"] = (
        "artifacts/prompt_queue/loop_control/queue-01.wi-parent.repair.1.loop_control_decision.json"
    )
    return item


def _post_execution(status: str) -> dict:
    art = load_example("prompt_queue_post_execution_decision")
    art["work_item_id"] = "wi-parent.repair.1"
    art["parent_work_item_id"] = "wi-parent"
    art["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-parent.repair.1.execution_result.json"
    art["gating_decision_artifact_path"] = "artifacts/prompt_queue/gating/wi-parent.repair.1.execution_gating_decision.json"
    art["decision_status"] = status
    art["decision_reason_code"] = {
        "review_required": "review_required_execution_failure_within_generation_limit",
        "complete": "complete_execution_success",
        "reentry_blocked": "reentry_blocked_generation_limit_reached",
    }[status]
    return art


def _loop_control(action: str) -> dict:
    art = load_example("prompt_queue_loop_control_decision")
    art["work_item_id"] = "wi-parent.repair.1"
    art["parent_work_item_id"] = "wi-parent"
    art["generation_count"] = 1
    if action == "allow_reentry":
        art["loop_control_status"] = "within_budget"
        art["enforcement_action"] = "allow_reentry"
        art["reason_code"] = "within_budget_allow_reentry"
    elif action == "require_review":
        art["loop_control_status"] = "limit_reached"
        art["enforcement_action"] = "require_review"
        art["reason_code"] = "limit_reached_require_review"
    else:
        art["loop_control_status"] = "limit_exceeded"
        art["enforcement_action"] = "block_reentry"
        art["reason_code"] = "limit_exceeded_block_reentry"
    return art


def test_review_required_with_permitted_loop_control_triggers_and_spawns_review_item():
    item = _executed_item(status=WorkItemStatus.REVIEW_REQUIRED.value)
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T05:00:00Z"]))
    trigger = evaluate_review_trigger_policy(
        work_item=item,
        post_execution_decision_artifact=_post_execution("review_required"),
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        loop_control_decision_artifact=_loop_control("allow_reentry"),
        loop_control_decision_artifact_path=item["loop_control_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T05:01:00Z"]),
    )
    updated_queue, updated_item, child, final_trigger = apply_review_trigger_to_queue(
        queue_state=queue,
        work_item_id=item["work_item_id"],
        review_trigger_artifact=trigger,
        review_trigger_artifact_path="artifacts/prompt_queue/review_triggers/queue-01.wi-parent.repair.1.review_trigger.json",
        clock=FixedClock(["2026-03-22T05:02:00Z", "2026-03-22T05:02:01Z", "2026-03-22T05:02:02Z"]),
    )
    assert updated_item["status"] == WorkItemStatus.REVIEW_TRIGGERED.value
    assert child is not None
    assert child["status"] == WorkItemStatus.REVIEW_QUEUED.value
    assert child["work_item_id"] == "wi-parent.repair.1.review.1"
    assert final_trigger["spawned_review_work_item_id"] == child["work_item_id"]
    assert final_trigger["review_request"]["review_type"] == "failure"


def test_complete_maps_to_no_review_needed_without_child_creation():
    item = _executed_item(status=WorkItemStatus.COMPLETE.value)
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T05:00:00Z"]))
    trigger = evaluate_review_trigger_policy(
        work_item=item,
        post_execution_decision_artifact=_post_execution("complete"),
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        loop_control_decision_artifact=_loop_control("allow_reentry"),
        loop_control_decision_artifact_path=item["loop_control_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T05:01:00Z"]),
    )
    updated_queue, updated_item, child, _ = apply_review_trigger_to_queue(
        queue_state=queue,
        work_item_id=item["work_item_id"],
        review_trigger_artifact=trigger,
        review_trigger_artifact_path="artifacts/prompt_queue/review_triggers/queue-01.wi-parent.repair.1.review_trigger.json",
        clock=FixedClock(["2026-03-22T05:02:00Z", "2026-03-22T05:02:01Z"]),
    )
    assert updated_item["status"] == WorkItemStatus.COMPLETE.value
    assert child is None
    validate_queue_state(updated_queue)


def test_reentry_blocked_maps_to_blocked_no_trigger():
    item = _executed_item(status=WorkItemStatus.REENTRY_BLOCKED.value)
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T05:00:00Z"]))
    trigger = evaluate_review_trigger_policy(
        work_item=item,
        post_execution_decision_artifact=_post_execution("reentry_blocked"),
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        loop_control_decision_artifact=_loop_control("allow_reentry"),
        loop_control_decision_artifact_path=item["loop_control_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T05:01:00Z"]),
    )
    updated_queue, updated_item, child, _ = apply_review_trigger_to_queue(
        queue_state=queue,
        work_item_id=item["work_item_id"],
        review_trigger_artifact=trigger,
        review_trigger_artifact_path="artifacts/prompt_queue/review_triggers/queue-01.wi-parent.repair.1.review_trigger.json",
        clock=FixedClock(["2026-03-22T05:02:00Z", "2026-03-22T05:02:01Z"]),
    )
    assert updated_item["status"] == WorkItemStatus.BLOCKED.value
    assert child is None
    validate_queue_state(updated_queue)


def test_loop_control_block_forces_blocked_no_trigger():
    item = _executed_item(status=WorkItemStatus.REVIEW_REQUIRED.value)
    trigger = evaluate_review_trigger_policy(
        work_item=item,
        post_execution_decision_artifact=_post_execution("review_required"),
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        loop_control_decision_artifact=_loop_control("block_reentry"),
        loop_control_decision_artifact_path=item["loop_control_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
    )
    assert trigger["trigger_status"] == "blocked_no_trigger"
    assert trigger["trigger_reason_code"] == "blocked_loop_control_block_reentry"


def test_missing_or_invalid_decision_artifacts_fail_closed():
    item = _executed_item(status=WorkItemStatus.REVIEW_REQUIRED.value)
    bad = _post_execution("review_required")
    bad.pop("decision_status")
    trigger = evaluate_review_trigger_policy(
        work_item=item,
        post_execution_decision_artifact=bad,
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        loop_control_decision_artifact=_loop_control("allow_reentry"),
        loop_control_decision_artifact_path=item["loop_control_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
    )
    assert trigger["trigger_status"] == "blocked_no_trigger"
    assert trigger["trigger_reason_code"] == "blocked_invalid_artifact"


def test_duplicate_trigger_attempt_fails_closed():
    item = _executed_item(status=WorkItemStatus.REVIEW_REQUIRED.value)
    item["review_trigger_artifact_path"] = "artifacts/prompt_queue/review_triggers/existing.json"
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T05:00:00Z"]))
    trigger = evaluate_review_trigger_policy(
        work_item=item,
        post_execution_decision_artifact=_post_execution("review_required"),
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        loop_control_decision_artifact=_loop_control("allow_reentry"),
        loop_control_decision_artifact_path=item["loop_control_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
    )
    with pytest.raises(ReviewTriggerQueueIntegrationError, match="Duplicate trigger"):
        apply_review_trigger_to_queue(
            queue_state=queue,
            work_item_id=item["work_item_id"],
            review_trigger_artifact=trigger,
            review_trigger_artifact_path="artifacts/prompt_queue/review_triggers/queue-01.wi-parent.repair.1.review_trigger.json",
        )


def test_malformed_work_item_or_invalid_state_fails_closed():
    malformed = _executed_item(status=WorkItemStatus.QUEUED.value)
    malformed.pop("scope_paths")
    trigger = evaluate_review_trigger_policy(
        work_item=malformed,
        post_execution_decision_artifact=_post_execution("review_required"),
        post_execution_decision_artifact_path="artifacts/prompt_queue/post_execution_decisions/queue-01.wi-parent.repair.1.post_execution_decision.json",
        loop_control_decision_artifact=_loop_control("allow_reentry"),
        loop_control_decision_artifact_path="artifacts/prompt_queue/loop_control/queue-01.wi-parent.repair.1.loop_control_decision.json",
        execution_result_artifact_path="artifacts/prompt_queue/execution_results/wi-parent.repair.1.execution_result.json",
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
    )
    queue = make_queue_state(queue_id="queue-01", work_items=[_executed_item(status=WorkItemStatus.QUEUED.value)], clock=FixedClock(["2026-03-22T05:00:00Z"]))
    with pytest.raises(ReviewTriggerQueueIntegrationError, match="Invalid state"):
        apply_review_trigger_to_queue(
            queue_state=queue,
            work_item_id="wi-parent.repair.1",
            review_trigger_artifact=trigger,
            review_trigger_artifact_path="artifacts/prompt_queue/review_triggers/queue-01.wi-parent.repair.1.review_trigger.json",
        )


def test_review_trigger_artifact_validates_against_schema():
    validate_review_trigger_artifact(load_example("prompt_queue_review_trigger"))


def test_queue_and_work_item_updates_are_deterministic_and_schema_valid():
    item = _executed_item(status=WorkItemStatus.REVIEW_REQUIRED.value)
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T05:00:00Z"]))
    trigger = evaluate_review_trigger_policy(
        work_item=item,
        post_execution_decision_artifact=_post_execution("review_required"),
        post_execution_decision_artifact_path=item["post_execution_decision_artifact_path"],
        loop_control_decision_artifact=_loop_control("require_review"),
        loop_control_decision_artifact_path=item["loop_control_decision_artifact_path"],
        execution_result_artifact_path=item["execution_result_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue-01.state.json",
        clock=FixedClock(["2026-03-22T05:01:00Z"]),
    )
    updated_queue, updated_item, child, finalized = apply_review_trigger_to_queue(
        queue_state=queue,
        work_item_id=item["work_item_id"],
        review_trigger_artifact=trigger,
        review_trigger_artifact_path="artifacts/prompt_queue/review_triggers/queue-01.wi-parent.repair.1.review_trigger.json",
        clock=FixedClock(["2026-03-22T05:02:00Z", "2026-03-22T05:02:01Z", "2026-03-22T05:02:02Z"]),
    )
    assert updated_item["review_trigger_artifact_path"].endswith("review_trigger.json")
    assert child is not None
    assert finalized["spawned_review_work_item_id"] == child["work_item_id"]
    validate_work_item(updated_item)
    validate_work_item(child)
    validate_queue_state(updated_queue)
