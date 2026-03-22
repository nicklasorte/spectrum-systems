"""Tests for governed prompt queue execution gating policy and queue integration."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    ExecutionGatingPolicyConfig,
    ExecutionGatingQueueIntegrationError,
    Priority,
    RiskLevel,
    WorkItemStatus,
    apply_execution_gating_decision_to_queue,
    evaluate_execution_gating_policy,
    make_queue_state,
    make_work_item,
    validate_execution_gating_decision_artifact,
)


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if not self._values:
            return datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc)
        return self._values.pop(0)


def _child_work_item(*, risk: RiskLevel | str = RiskLevel.MEDIUM, generation: int = 1) -> dict:
    child = make_work_item(
        work_item_id="wi-parent.repair.1",
        prompt_id="prompt-parent:repair:1",
        title="Parent repair child",
        priority=Priority.HIGH,
        risk_level=risk,
        repo="spectrum-systems",
        branch="feature/gating",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        parent_work_item_id="wi-parent",
        clock=FixedClock(["2026-03-22T01:00:00Z"]),
    )
    child["status"] = WorkItemStatus.REPAIR_CHILD_CREATED.value
    child["spawned_from_repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json"
    child["spawned_from_findings_artifact_path"] = "artifacts/prompt_queue/findings/wi-parent.findings.json"
    child["spawned_from_review_artifact_path"] = "docs/reviews/2026-03-22-parent-review.md"
    child["repair_loop_generation"] = generation
    return child


def _repair_prompt_artifact() -> dict:
    artifact = load_example("prompt_queue_repair_prompt")
    artifact["work_item_id"] = "wi-parent"
    artifact["review_decision"] = "FAIL"
    artifact["prompt_generation_status"] = "generated"
    artifact["source_findings_artifact_path"] = "artifacts/prompt_queue/findings/wi-parent.findings.json"
    artifact["source_review_artifact_path"] = "docs/reviews/2026-03-22-parent-review.md"
    return artifact


def _queue_with_child(child: dict) -> dict:
    return make_queue_state(queue_id="queue-01", work_items=[child], clock=FixedClock(["2026-03-22T01:00:00Z"]))


def test_low_risk_child_within_generation_limit_becomes_runnable():
    child = _child_work_item(risk=RiskLevel.LOW, generation=1)
    decision = evaluate_execution_gating_policy(
        work_item=child,
        repair_prompt_artifact=_repair_prompt_artifact(),
        repair_prompt_artifact_path=child["spawned_from_repair_prompt_artifact_path"],
        approval_present=False,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T01:00:01Z"]),
    )
    assert decision["decision_status"] == "runnable"
    assert decision["approval_required"] is False


def test_high_risk_child_without_approval_becomes_approval_required():
    child = _child_work_item(risk=RiskLevel.HIGH, generation=1)
    decision = evaluate_execution_gating_policy(
        work_item=child,
        repair_prompt_artifact=_repair_prompt_artifact(),
        repair_prompt_artifact_path=child["spawned_from_repair_prompt_artifact_path"],
        approval_present=False,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T01:00:01Z"]),
    )
    assert decision["decision_status"] == "approval_required"
    assert decision["decision_reason_code"] == "approval_required_high_risk"


def test_high_risk_child_with_approval_becomes_runnable():
    child = _child_work_item(risk=RiskLevel.HIGH, generation=1)
    decision = evaluate_execution_gating_policy(
        work_item=child,
        repair_prompt_artifact=_repair_prompt_artifact(),
        repair_prompt_artifact_path=child["spawned_from_repair_prompt_artifact_path"],
        approval_present=True,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T01:00:01Z"]),
    )
    assert decision["decision_status"] == "runnable"
    assert decision["approval_required"] is True


def test_child_exceeding_max_generation_becomes_blocked():
    child = _child_work_item(risk=RiskLevel.MEDIUM, generation=3)
    decision = evaluate_execution_gating_policy(
        work_item=child,
        repair_prompt_artifact=_repair_prompt_artifact(),
        repair_prompt_artifact_path=child["spawned_from_repair_prompt_artifact_path"],
        approval_present=False,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        policy=ExecutionGatingPolicyConfig(max_generation_allowed=2),
        clock=FixedClock(["2026-03-22T01:00:01Z"]),
    )
    assert decision["decision_status"] == "blocked"
    assert decision["decision_reason_code"] == "blocked_generation_limit_exceeded"


def test_missing_lineage_fails_closed_as_blocked():
    child = _child_work_item(risk=RiskLevel.LOW, generation=1)
    child["parent_work_item_id"] = None
    decision = evaluate_execution_gating_policy(
        work_item=child,
        repair_prompt_artifact=_repair_prompt_artifact(),
        repair_prompt_artifact_path=child["spawned_from_repair_prompt_artifact_path"],
        approval_present=False,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T01:00:01Z"]),
    )
    assert decision["decision_status"] == "blocked"
    assert decision["decision_reason_code"] == "blocked_invalid_lineage"


def test_malformed_child_work_item_fails_closed():
    child = _child_work_item(risk=RiskLevel.LOW, generation=1)
    child.pop("scope_paths")
    decision = evaluate_execution_gating_policy(
        work_item=child,
        repair_prompt_artifact=_repair_prompt_artifact(),
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json",
        approval_present=False,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T01:00:01Z"]),
    )
    assert decision["decision_status"] == "blocked"
    assert decision["decision_reason_code"] == "blocked_invalid_work_item"


def test_gating_decision_artifact_validates_against_schema():
    validate_execution_gating_decision_artifact(load_example("prompt_queue_execution_gating_decision"))


def test_queue_work_item_update_occurs_correctly_after_gating_decision():
    child = _child_work_item(risk=RiskLevel.LOW, generation=1)
    queue = _queue_with_child(child)
    decision = evaluate_execution_gating_policy(
        work_item=child,
        repair_prompt_artifact=_repair_prompt_artifact(),
        repair_prompt_artifact_path=child["spawned_from_repair_prompt_artifact_path"],
        approval_present=False,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T01:00:01Z"]),
    )

    updated_queue, updated_item = apply_execution_gating_decision_to_queue(
        queue_state=queue,
        work_item_id=child["work_item_id"],
        gating_decision_artifact=decision,
        gating_decision_artifact_path="artifacts/prompt_queue/gating/wi-parent.repair.1.execution_gating_decision.json",
        clock=FixedClock(["2026-03-22T01:00:02Z", "2026-03-22T01:00:03Z", "2026-03-22T01:00:04Z", "2026-03-22T01:00:05Z"]),
    )

    assert updated_item["status"] == WorkItemStatus.RUNNABLE.value
    assert updated_item["gating_decision_artifact_path"].endswith("execution_gating_decision.json")
    assert updated_queue["work_items"][0]["status"] == WorkItemStatus.RUNNABLE.value


def test_illegal_or_inconsistent_state_transition_fails_closed():
    child = _child_work_item(risk=RiskLevel.LOW, generation=1)
    child["status"] = WorkItemStatus.QUEUED.value
    queue = _queue_with_child(child)
    decision = evaluate_execution_gating_policy(
        work_item=_child_work_item(risk=RiskLevel.LOW, generation=1),
        repair_prompt_artifact=_repair_prompt_artifact(),
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json",
        approval_present=False,
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T01:00:01Z"]),
    )

    with pytest.raises(ExecutionGatingQueueIntegrationError, match="repair_child_created"):
        apply_execution_gating_decision_to_queue(
            queue_state=queue,
            work_item_id=child["work_item_id"],
            gating_decision_artifact=decision,
            gating_decision_artifact_path="artifacts/prompt_queue/gating/wi-parent.repair.1.execution_gating_decision.json",
            clock=FixedClock(["2026-03-22T01:00:02Z"]),
        )
