"""Tests for deterministic prompt queue loop control policy and integration."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    LoopControlPolicyConfig,
    LoopControlPolicyError,
    LoopControlQueueIntegrationError,
    Priority,
    RiskLevel,
    WorkItemStatus,
    apply_loop_control_decision_to_queue,
    evaluate_loop_control_policy,
    make_queue_state,
    make_work_item,
    validate_loop_control_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.repair_child_queue_integration import (  # noqa: E402
    RepairChildQueueIntegrationError,
    spawn_repair_child_in_queue,
)


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if not self._values:
            return datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc)
        return self._values.pop(0)


def _make_item(*, work_item_id: str, generation_count: int, parent_work_item_id: str | None) -> dict:
    item = make_work_item(
        work_item_id=work_item_id,
        prompt_id=f"prompt-{work_item_id}",
        title=f"Item {work_item_id}",
        priority=Priority.MEDIUM,
        risk_level=RiskLevel.MEDIUM,
        repo="spectrum-systems",
        branch="feature/loop-control",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        parent_work_item_id=parent_work_item_id,
        clock=FixedClock(["2026-03-22T00:00:00Z"]),
    )
    item["status"] = WorkItemStatus.EXECUTED_FAILURE.value
    item["generation_count"] = generation_count
    item["repair_loop_generation"] = generation_count
    return item


def test_generation_zero_within_budget():
    item = _make_item(work_item_id="wi-root", generation_count=0, parent_work_item_id=None)
    decision = evaluate_loop_control_policy(
        work_item=item,
        parent_work_item=None,
        source_queue_state_path="artifacts/prompt_queue/state/queue.json",
        policy=LoopControlPolicyConfig(max_generation_allowed=2),
        clock=FixedClock(["2026-03-22T00:00:01Z"]),
    )
    assert decision["loop_control_status"] == "within_budget"
    assert decision["enforcement_action"] == "allow_reentry"


def test_generation_less_than_max_within_budget():
    parent = _make_item(work_item_id="wi-parent", generation_count=0, parent_work_item_id=None)
    child = _make_item(work_item_id="wi-child", generation_count=1, parent_work_item_id="wi-parent")
    decision = evaluate_loop_control_policy(
        work_item=child,
        parent_work_item=parent,
        source_queue_state_path="artifacts/prompt_queue/state/queue.json",
        policy=LoopControlPolicyConfig(max_generation_allowed=2),
        clock=FixedClock(["2026-03-22T00:00:01Z"]),
    )
    assert decision["loop_control_status"] == "within_budget"


def test_generation_equal_max_requires_review():
    parent = _make_item(work_item_id="wi-parent", generation_count=1, parent_work_item_id="wi-root")
    child = _make_item(work_item_id="wi-child", generation_count=2, parent_work_item_id="wi-parent")
    decision = evaluate_loop_control_policy(
        work_item=child,
        parent_work_item=parent,
        source_queue_state_path=None,
        policy=LoopControlPolicyConfig(max_generation_allowed=2),
        clock=FixedClock(["2026-03-22T00:00:01Z"]),
    )
    assert decision["loop_control_status"] == "limit_reached"
    assert decision["enforcement_action"] == "require_review"


def test_generation_above_max_blocks_reentry():
    parent = _make_item(work_item_id="wi-parent", generation_count=2, parent_work_item_id="wi-root")
    child = _make_item(work_item_id="wi-child", generation_count=3, parent_work_item_id="wi-parent")
    decision = evaluate_loop_control_policy(
        work_item=child,
        parent_work_item=parent,
        source_queue_state_path=None,
        policy=LoopControlPolicyConfig(max_generation_allowed=2),
        clock=FixedClock(["2026-03-22T00:00:01Z"]),
    )
    assert decision["loop_control_status"] == "limit_exceeded"
    assert decision["enforcement_action"] == "block_reentry"


def test_missing_generation_count_fails_closed():
    item = _make_item(work_item_id="wi-root", generation_count=0, parent_work_item_id=None)
    item.pop("generation_count")
    with pytest.raises(LoopControlPolicyError, match="generation_count"):
        evaluate_loop_control_policy(
            work_item=item,
            parent_work_item=None,
            source_queue_state_path=None,
        )


def test_missing_parent_when_generation_nonzero_fails_closed():
    item = _make_item(work_item_id="wi-child", generation_count=1, parent_work_item_id=None)
    with pytest.raises(LoopControlPolicyError, match="parent_work_item_id"):
        evaluate_loop_control_policy(
            work_item=item,
            parent_work_item=None,
            source_queue_state_path=None,
        )


def test_non_monotonic_generation_fails_closed():
    parent = _make_item(work_item_id="wi-parent", generation_count=0, parent_work_item_id=None)
    child = _make_item(work_item_id="wi-child", generation_count=3, parent_work_item_id="wi-parent")
    with pytest.raises(LoopControlPolicyError, match="Non-monotonic"):
        evaluate_loop_control_policy(
            work_item=child,
            parent_work_item=parent,
            source_queue_state_path=None,
        )


def test_invalid_lineage_parent_mismatch_fails_closed():
    parent = _make_item(work_item_id="wi-parent", generation_count=0, parent_work_item_id=None)
    child = _make_item(work_item_id="wi-child", generation_count=1, parent_work_item_id="different-parent")
    with pytest.raises(LoopControlPolicyError, match="Parent lineage mismatch"):
        evaluate_loop_control_policy(
            work_item=child,
            parent_work_item=parent,
            source_queue_state_path=None,
        )


def test_invalid_schema_artifact_rejected_by_validator():
    bad = {
        "loop_control_decision_artifact_id": "x",
        "work_item_id": "wi-1",
        "parent_work_item_id": None,
        "generation_count": 0,
        "max_generation_allowed": 2,
        "loop_control_status": "within_budget",
        "enforcement_action": "block_reentry",
        "reason_code": "limit_exceeded_block_reentry",
        "generated_at": "2026-03-22T00:00:01Z",
        "generator_version": "prompt_queue_loop_control_policy.v1",
    }
    with pytest.raises(Exception):
        validate_loop_control_decision_artifact(bad)


def test_deterministic_queue_updates_for_each_action():
    root = _make_item(work_item_id="wi-root", generation_count=0, parent_work_item_id=None)
    for status, expected_state in [
        ("within_budget", WorkItemStatus.REENTRY_ELIGIBLE.value),
        ("limit_reached", WorkItemStatus.REVIEW_REQUIRED.value),
        ("limit_exceeded", WorkItemStatus.BLOCKED.value),
    ]:
        queue = make_queue_state(
            queue_id="q-1",
            work_items=[dict(root)],
            clock=FixedClock(["2026-03-22T00:00:00Z"]),
        )
        decision = {
            "loop_control_decision_artifact_id": f"d-{status}",
            "work_item_id": "wi-root",
            "parent_work_item_id": None,
            "generation_count": 0,
            "max_generation_allowed": 2,
            "loop_control_status": status,
            "enforcement_action": {
                "within_budget": "allow_reentry",
                "limit_reached": "require_review",
                "limit_exceeded": "block_reentry",
            }[status],
            "reason_code": {
                "within_budget": "within_budget_allow_reentry",
                "limit_reached": "limit_reached_require_review",
                "limit_exceeded": "limit_exceeded_block_reentry",
            }[status],
            "generated_at": "2026-03-22T00:00:01Z",
            "generator_version": "prompt_queue_loop_control_policy.v1",
            "warnings": [],
        }
        queue["work_items"][0]["status"] = WorkItemStatus.EXECUTED_FAILURE.value
        updated_queue, updated_item = apply_loop_control_decision_to_queue(
            queue_state=queue,
            work_item_id="wi-root",
            loop_control_decision_artifact=decision,
            loop_control_decision_artifact_path=f"artifacts/prompt_queue/loop_control/{status}.json",
            clock=FixedClock(["2026-03-22T00:00:02Z", "2026-03-22T00:00:03Z"]),
        )
        assert updated_item["status"] == expected_state
        assert updated_queue["work_items"][0]["status"] == expected_state


def test_limit_exceeded_blocks_further_child_spawning():
    root = _make_item(work_item_id="wi-root", generation_count=2, parent_work_item_id="wi-grand")
    parent = _make_item(work_item_id="wi-parent", generation_count=3, parent_work_item_id="wi-root")
    parent["status"] = WorkItemStatus.EXECUTED_FAILURE.value
    parent["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json"
    queue = make_queue_state(queue_id="q-1", work_items=[root, parent], clock=FixedClock(["2026-03-22T00:00:00Z"]))
    decision = evaluate_loop_control_policy(
        work_item=parent,
        parent_work_item=root,
        source_queue_state_path=None,
        policy=LoopControlPolicyConfig(max_generation_allowed=2),
        clock=FixedClock(["2026-03-22T00:00:01Z"]),
    )

    blocked_queue, blocked_item = apply_loop_control_decision_to_queue(
        queue_state=queue,
        work_item_id="wi-parent",
        loop_control_decision_artifact=decision,
        loop_control_decision_artifact_path="artifacts/prompt_queue/loop_control/wi-parent.json",
        clock=FixedClock(["2026-03-22T00:00:02Z", "2026-03-22T00:00:03Z"]),
    )
    assert blocked_item["status"] == WorkItemStatus.BLOCKED.value

    with pytest.raises(RepairChildQueueIntegrationError):
        spawn_repair_child_in_queue(
            queue_state=blocked_queue,
            parent_work_item_id="wi-parent",
            repair_prompt_artifact={
                "repair_prompt_artifact_id": "rp-1",
                "work_item_id": "wi-parent",
                "source_findings_artifact_path": "artifacts/prompt_queue/findings/x.json",
                "source_review_artifact_path": "docs/reviews/x.md",
                "review_decision": "FAIL",
                "prompt_generation_status": "generated",
                "repair_prompt_markdown": "# fix",
                "generated_at": "2026-03-22T00:00:00Z",
                "generator_version": "prompt_queue_repair_prompt_generator.v1"
            },
            repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json",
            clock=FixedClock(["2026-03-22T00:00:10Z"]),
        )


def test_invalid_tuple_mapping_fails_closed_in_integration():
    root = _make_item(work_item_id="wi-root", generation_count=0, parent_work_item_id=None)
    queue = make_queue_state(queue_id="q-1", work_items=[root], clock=FixedClock(["2026-03-22T00:00:00Z"]))
    bad_decision = {
        "loop_control_decision_artifact_id": "d-1",
        "work_item_id": "wi-root",
        "parent_work_item_id": None,
        "generation_count": 0,
        "max_generation_allowed": 2,
        "loop_control_status": "within_budget",
        "enforcement_action": "require_review",
        "reason_code": "limit_reached_require_review",
        "generated_at": "2026-03-22T00:00:01Z",
        "generator_version": "prompt_queue_loop_control_policy.v1",
        "warnings": [],
    }

    with pytest.raises(LoopControlQueueIntegrationError):
        apply_loop_control_decision_to_queue(
            queue_state=queue,
            work_item_id="wi-root",
            loop_control_decision_artifact=bad_decision,
            loop_control_decision_artifact_path="artifacts/prompt_queue/loop_control/bad.json",
        )
