from __future__ import annotations

from test_prompt_queue_review_trigger import (  # noqa: F401
    _executed_item,
    _loop_control,
    _post_execution,
    FixedClock,
)

from spectrum_systems.modules.prompt_queue.review_trigger_policy import evaluate_review_trigger_policy
from spectrum_systems.modules.prompt_queue import WorkItemStatus


def test_sensitive_scope_triggers_surgical_review_type() -> None:
    item = _executed_item(status=WorkItemStatus.REVIEW_REQUIRED.value)
    item["scope_paths"] = ["spectrum_systems/modules/runtime/evaluation_control.py"]
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
    assert trigger["review_request"]["review_type"] == "surgical"


def test_hard_gate_event_triggers_hard_gate_type() -> None:
    item = _executed_item(status=WorkItemStatus.REVIEW_REQUIRED.value)
    item["title"] = "major capability promotion hard gate"
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
    assert trigger["review_request"]["review_type"] == "hard_gate"


def test_reentry_blocked_is_blocked_fail_closed() -> None:
    item = _executed_item(status=WorkItemStatus.REENTRY_BLOCKED.value)
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
    assert trigger["trigger_status"] == "blocked_no_trigger"
    assert trigger["trigger_reason_code"] == "blocked_post_execution_reentry_blocked"
