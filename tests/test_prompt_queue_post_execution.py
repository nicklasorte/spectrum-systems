"""Tests for governed prompt queue post-execution policy and deterministic queue integration."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    PostExecutionPolicyConfig,
    PostExecutionQueueIntegrationError,
    Priority,
    RiskLevel,
    WorkItemStatus,
    apply_post_execution_decision_to_queue,
    evaluate_post_execution_policy,
    make_queue_state,
    make_work_item,
    validate_post_execution_decision_artifact,
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


def _executed_item(status: str = WorkItemStatus.EXECUTED_FAILURE.value, generation: int = 1) -> dict:
    item = make_work_item(
        work_item_id="wi-parent.repair.1",
        prompt_id="prompt-parent:repair:1",
        title="Repair child",
        priority=Priority.HIGH,
        risk_level=RiskLevel.MEDIUM,
        repo="spectrum-systems",
        branch="feature/post-execution",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        parent_work_item_id="wi-parent",
        clock=FixedClock(["2026-03-22T03:00:00Z"]),
    )
    item["status"] = status
    item["repair_loop_generation"] = generation
    item["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json"
    item["spawned_from_findings_artifact_path"] = "artifacts/prompt_queue/findings/wi-parent.findings.json"
    item["spawned_from_review_artifact_path"] = "docs/reviews/2026-03-22-parent-review.md"
    item["gating_decision_artifact_path"] = "artifacts/prompt_queue/gating/wi-parent.repair.1.execution_gating_decision.json"
    item["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-parent.repair.1.execution_result.json"
    return item


def _gating_artifact() -> dict:
    art = load_example("prompt_queue_execution_gating_decision")
    art["work_item_id"] = "wi-parent.repair.1"
    art["parent_work_item_id"] = "wi-parent"
    art["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json"
    art["decision_status"] = "runnable"
    art["decision_reason_code"] = "runnable_within_policy"
    art["approval_required"] = True
    art["approval_present"] = True
    return art


def _execution_result(status: str) -> dict:
    art = load_example("prompt_queue_execution_result")
    art["work_item_id"] = "wi-parent.repair.1"
    art["parent_work_item_id"] = "wi-parent"
    art["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json"
    art["gating_decision_artifact_path"] = "artifacts/prompt_queue/gating/wi-parent.repair.1.execution_gating_decision.json"
    art["execution_status"] = status
    if status == "failure":
        art["output_reference"] = None
        art["produced_artifact_refs"] = []
        art["error_summary"] = "Execution failed in deterministic post-execution test fixture."
    else:
        art["error_summary"] = None
    return art


def test_executed_success_transitions_to_complete():
    item = _executed_item(status=WorkItemStatus.EXECUTED_SUCCESS.value, generation=1)
    decision = evaluate_post_execution_policy(
        work_item=item,
        execution_result_artifact=_execution_result("success"),
        execution_result_artifact_path=item["execution_result_artifact_path"],
        gating_decision_artifact=_gating_artifact(),
        gating_decision_artifact_path=item["gating_decision_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T03:01:00Z"]),
    )
    assert decision["decision_status"] == "complete"
    assert decision["decision_reason_code"] == "complete_execution_success"


def test_executed_failure_below_max_generation_transitions_to_review_required():
    item = _executed_item(status=WorkItemStatus.EXECUTED_FAILURE.value, generation=1)
    decision = evaluate_post_execution_policy(
        work_item=item,
        execution_result_artifact=_execution_result("failure"),
        execution_result_artifact_path=item["execution_result_artifact_path"],
        gating_decision_artifact=_gating_artifact(),
        gating_decision_artifact_path=item["gating_decision_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        policy=PostExecutionPolicyConfig(max_generation_allowed=2),
        clock=FixedClock(["2026-03-22T03:01:00Z"]),
    )
    assert decision["decision_status"] == "review_required"
    assert decision["review_trigger_recommended"] is True


def test_executed_failure_at_max_generation_transitions_to_reentry_blocked():
    item = _executed_item(status=WorkItemStatus.EXECUTED_FAILURE.value, generation=2)
    decision = evaluate_post_execution_policy(
        work_item=item,
        execution_result_artifact=_execution_result("failure"),
        execution_result_artifact_path=item["execution_result_artifact_path"],
        gating_decision_artifact=_gating_artifact(),
        gating_decision_artifact_path=item["gating_decision_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        policy=PostExecutionPolicyConfig(max_generation_allowed=2),
        clock=FixedClock(["2026-03-22T03:01:00Z"]),
    )
    assert decision["decision_status"] == "reentry_blocked"
    assert decision["decision_reason_code"] == "reentry_blocked_generation_limit_reached"


def test_missing_execution_result_artifact_fails_closed():
    item = _executed_item(status=WorkItemStatus.EXECUTED_FAILURE.value, generation=1)
    malformed_execution = _execution_result("failure")
    malformed_execution.pop("execution_status")

    decision = evaluate_post_execution_policy(
        work_item=item,
        execution_result_artifact=malformed_execution,
        execution_result_artifact_path=item["execution_result_artifact_path"],
        gating_decision_artifact=_gating_artifact(),
        gating_decision_artifact_path=item["gating_decision_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T03:01:00Z"]),
    )
    assert decision["decision_status"] == "reentry_blocked"
    assert "execution result artifact failed schema validation" in decision["blocking_conditions"]


def test_invalid_gating_lineage_fails_closed():
    item = _executed_item(status=WorkItemStatus.EXECUTED_FAILURE.value, generation=1)
    gating = _gating_artifact()
    gating["work_item_id"] = "another-work-item"

    decision = evaluate_post_execution_policy(
        work_item=item,
        execution_result_artifact=_execution_result("failure"),
        execution_result_artifact_path=item["execution_result_artifact_path"],
        gating_decision_artifact=gating,
        gating_decision_artifact_path=item["gating_decision_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T03:01:00Z"]),
    )
    assert decision["decision_status"] == "reentry_blocked"
    assert decision["decision_reason_code"] == "reentry_blocked_invalid_lineage"


def test_malformed_executed_work_item_fails_closed():
    item = _executed_item(status=WorkItemStatus.EXECUTED_FAILURE.value, generation=1)
    item.pop("scope_paths")

    decision = evaluate_post_execution_policy(
        work_item=item,
        execution_result_artifact=_execution_result("failure"),
        execution_result_artifact_path="artifacts/prompt_queue/execution_results/wi-parent.repair.1.execution_result.json",
        gating_decision_artifact=_gating_artifact(),
        gating_decision_artifact_path="artifacts/prompt_queue/gating/wi-parent.repair.1.execution_gating_decision.json",
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T03:01:00Z"]),
    )
    assert decision["decision_status"] == "reentry_blocked"
    assert decision["decision_reason_code"] == "reentry_blocked_invalid_artifact"


def test_post_execution_decision_artifact_validates_against_schema():
    validate_post_execution_decision_artifact(load_example("prompt_queue_post_execution_decision"))


def test_queue_and_work_item_updates_are_deterministic_and_schema_valid():
    item = _executed_item(status=WorkItemStatus.EXECUTED_FAILURE.value, generation=1)
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T03:00:00Z"]))
    decision = evaluate_post_execution_policy(
        work_item=item,
        execution_result_artifact=_execution_result("failure"),
        execution_result_artifact_path=item["execution_result_artifact_path"],
        gating_decision_artifact=_gating_artifact(),
        gating_decision_artifact_path=item["gating_decision_artifact_path"],
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        policy=PostExecutionPolicyConfig(max_generation_allowed=2),
        clock=FixedClock(["2026-03-22T03:01:00Z"]),
    )

    updated_queue, updated_item = apply_post_execution_decision_to_queue(
        queue_state=queue,
        work_item_id=item["work_item_id"],
        post_execution_decision_artifact=decision,
        post_execution_decision_artifact_path="artifacts/prompt_queue/post_execution_decisions/queue-01.wi-parent.repair.1.post_execution_decision.json",
        clock=FixedClock(["2026-03-22T03:02:00Z", "2026-03-22T03:02:01Z", "2026-03-22T03:02:02Z"]),
    )

    assert updated_item["status"] == WorkItemStatus.REVIEW_REQUIRED.value
    assert updated_item["post_execution_decision_artifact_path"].endswith("post_execution_decision.json")
    validate_work_item(updated_item)
    validate_queue_state(updated_queue)


def test_illegal_state_transitions_fail_closed():
    item = _executed_item(status=WorkItemStatus.EXECUTING.value, generation=1)
    queue = make_queue_state(queue_id="queue-01", work_items=[item], clock=FixedClock(["2026-03-22T03:00:00Z"]))
    decision = evaluate_post_execution_policy(
        work_item=_executed_item(status=WorkItemStatus.EXECUTED_FAILURE.value, generation=1),
        execution_result_artifact=_execution_result("failure"),
        execution_result_artifact_path="artifacts/prompt_queue/execution_results/wi-parent.repair.1.execution_result.json",
        gating_decision_artifact=_gating_artifact(),
        gating_decision_artifact_path="artifacts/prompt_queue/gating/wi-parent.repair.1.execution_gating_decision.json",
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T03:01:00Z"]),
    )

    with pytest.raises(PostExecutionQueueIntegrationError, match="executed_success"):
        apply_post_execution_decision_to_queue(
            queue_state=queue,
            work_item_id=item["work_item_id"],
            post_execution_decision_artifact=decision,
            post_execution_decision_artifact_path="artifacts/prompt_queue/post_execution_decisions/queue-01.wi-parent.repair.1.post_execution_decision.json",
            clock=FixedClock(["2026-03-22T03:02:00Z"]),
        )
