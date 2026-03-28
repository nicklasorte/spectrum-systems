"""Tests for deterministic prompt queue retry policy and queue integration."""

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
    Priority,
    RetryQueueIntegrationError,
    RiskLevel,
    apply_retry_decision_to_queue,
    evaluate_retry_policy,
    validate_queue_state,
    validate_retry_decision_artifact,
    validate_work_item,
)
from spectrum_systems.modules.prompt_queue.queue_models import make_queue_state, make_work_item  # noqa: E402


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if self._values:
            return self._values.pop(0)
        return datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc)


def _failed_item(*, status: str = "executed_failure", retry_count: int = 0, retry_budget: int = 2) -> dict:
    item = make_work_item(
        work_item_id="wi-retry-1",
        prompt_id="prompt-retry-1",
        title="Retry item",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="feature/retry-policy",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        clock=FixedClock(["2026-03-22T00:00:00Z"]),
    )
    item["status"] = status
    item["retry_count"] = retry_count
    item["retry_budget"] = retry_budget
    return item


def _queue(item: dict | None = None) -> dict:
    return make_queue_state(
        queue_id="queue-retry",
        work_items=[item or _failed_item()],
        clock=FixedClock(["2026-03-22T00:00:01Z"]),
    )


def _retry_transition(*, source_decision_ref: str = "artifacts/prompt_queue/execution_results/wi-retry-1.execution.json") -> dict:
    artifact = load_example("prompt_queue_transition_decision")
    artifact["step_id"] = "step-001"
    artifact["source_decision_ref"] = source_decision_ref
    artifact["transition_action"] = "retry_allowed"
    artifact["transition_status"] = "allowed"
    artifact["reason_codes"] = ["block_errors_retry_allowed"]
    artifact["blocking_reasons"] = []
    artifact["derived_from_artifacts"] = [source_decision_ref]
    artifact["timestamp"] = "2026-03-22T00:00:59Z"
    artifact["trace_linkage"] = "queue-retry"
    return artifact


def test_retry_allowed_when_under_budget():
    queue = _queue(_failed_item(status="executed_failure", retry_count=0, retry_budget=2))
    queue["work_items"][0]["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-retry-1.execution.json"
    decision = evaluate_retry_policy(
        work_item=queue["work_items"][0],
        failure_reason_code="execution_failure_non_lineage_non_schema",
        source_queue_state_path="artifacts/prompt_queue/queue-retry.state.json",
        transition_decision_artifact=_retry_transition(),
        clock=FixedClock(["2026-03-22T00:01:00Z"]),
    )

    updated_queue, updated_item = apply_retry_decision_to_queue(
        queue_state=queue,
        work_item_id="wi-retry-1",
        retry_decision_artifact=decision,
        retry_decision_artifact_path="artifacts/prompt_queue/retry_decisions/wi-retry-1.retry_decision.json",
        clock=FixedClock(["2026-03-22T00:01:01Z"]),
    )

    assert decision["retry_status"] == "retry_allowed"
    assert updated_item["status"] == "runnable"
    assert updated_item["retry_count"] == 1
    validate_work_item(updated_item)
    validate_queue_state(updated_queue)


def test_retry_blocked_when_over_budget():
    queue = _queue(_failed_item(status="executed_failure", retry_count=2, retry_budget=2))
    queue["work_items"][0]["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-retry-1.execution.json"
    decision = evaluate_retry_policy(
        work_item=queue["work_items"][0],
        failure_reason_code="timeout",
        source_queue_state_path="artifacts/prompt_queue/queue-retry.state.json",
        transition_decision_artifact=_retry_transition(),
        clock=FixedClock(["2026-03-22T00:02:00Z"]),
    )

    updated_queue, updated_item = apply_retry_decision_to_queue(
        queue_state=queue,
        work_item_id="wi-retry-1",
        retry_decision_artifact=decision,
        retry_decision_artifact_path="artifacts/prompt_queue/retry_decisions/wi-retry-1.retry_decision.json",
        clock=FixedClock(["2026-03-22T00:02:01Z"]),
    )

    assert decision["retry_status"] == "retry_exhausted"
    assert decision["retry_action"] == "no_action"
    assert updated_item["status"] == "executed_failure"
    assert updated_item["retry_count"] == 2
    validate_work_item(updated_item)
    validate_queue_state(updated_queue)


def test_retry_blocked_for_non_retryable_failure():
    queue = _queue(_failed_item(status="executed_failure", retry_count=0, retry_budget=2))
    queue["work_items"][0]["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-retry-1.execution.json"
    decision = evaluate_retry_policy(
        work_item=queue["work_items"][0],
        failure_reason_code="lineage_mismatch",
        source_queue_state_path="artifacts/prompt_queue/queue-retry.state.json",
        transition_decision_artifact=_retry_transition(),
        clock=FixedClock(["2026-03-22T00:03:00Z"]),
    )

    assert decision["retry_status"] == "retry_blocked"
    assert decision["retry_action"] == "no_action"


def test_retry_does_not_apply_to_blocked_items():
    queue = _queue(_failed_item(status="blocked", retry_count=0, retry_budget=2))
    decision = evaluate_retry_policy(
        work_item=queue["work_items"][0],
        failure_reason_code="provider_transient_failure",
        source_queue_state_path="artifacts/prompt_queue/queue-retry.state.json",
        clock=FixedClock(["2026-03-22T00:04:00Z"]),
    )

    assert decision["retry_status"] == "retry_blocked"
    assert decision["retry_reason_code"] == "retry_blocked_work_item_blocked"


def test_retry_count_increments_only_when_retry_occurs():
    queue = _queue(_failed_item(status="review_provider_failed", retry_count=1, retry_budget=3))
    queue["work_items"][0]["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-retry-1.execution.json"
    decision = evaluate_retry_policy(
        work_item=queue["work_items"][0],
        failure_reason_code="provider_transient_failure",
        source_queue_state_path="artifacts/prompt_queue/queue-retry.state.json",
        transition_decision_artifact=_retry_transition(),
        clock=FixedClock(["2026-03-22T00:05:00Z"]),
    )

    updated_queue, updated_item = apply_retry_decision_to_queue(
        queue_state=queue,
        work_item_id="wi-retry-1",
        retry_decision_artifact=decision,
        retry_decision_artifact_path="artifacts/prompt_queue/retry_decisions/wi-retry-1.retry_decision.json",
        clock=FixedClock(["2026-03-22T00:05:01Z"]),
    )

    assert updated_item["status"] == "review_triggered"
    assert updated_item["retry_count"] == 2
    validate_work_item(updated_item)
    validate_queue_state(updated_queue)


def test_duplicate_retry_attempt_is_prevented_after_state_transition():
    queue = _queue(_failed_item(status="executed_failure", retry_count=0, retry_budget=2))
    queue["work_items"][0]["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-retry-1.execution.json"
    decision = evaluate_retry_policy(
        work_item=queue["work_items"][0],
        failure_reason_code="timeout",
        source_queue_state_path="artifacts/prompt_queue/queue-retry.state.json",
        transition_decision_artifact=_retry_transition(),
        clock=FixedClock(["2026-03-22T00:06:00Z"]),
    )
    updated_queue, _ = apply_retry_decision_to_queue(
        queue_state=queue,
        work_item_id="wi-retry-1",
        retry_decision_artifact=decision,
        retry_decision_artifact_path="artifacts/prompt_queue/retry_decisions/wi-retry-1.retry_decision.json",
        clock=FixedClock(["2026-03-22T00:06:01Z"]),
    )

    with pytest.raises(RetryQueueIntegrationError, match="current_status"):
        apply_retry_decision_to_queue(
            queue_state=updated_queue,
            work_item_id="wi-retry-1",
            retry_decision_artifact=decision,
            retry_decision_artifact_path="artifacts/prompt_queue/retry_decisions/wi-retry-1.retry_decision.json",
            clock=FixedClock(["2026-03-22T00:06:02Z"]),
        )


def test_retry_decision_artifact_validates_against_schema():
    validate_retry_decision_artifact(load_example("prompt_queue_retry_decision"))


def test_deterministic_queue_update_for_same_inputs():
    queue_a = _queue(_failed_item(status="review_invocation_failed", retry_count=0, retry_budget=2))
    queue_a["work_items"][0]["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-retry-1.execution.json"
    decision_a = evaluate_retry_policy(
        work_item=queue_a["work_items"][0],
        failure_reason_code="provider_transient_failure",
        source_queue_state_path="artifacts/prompt_queue/queue-retry.state.json",
        transition_decision_artifact=_retry_transition(),
        clock=FixedClock(["2026-03-22T00:07:00Z"]),
    )
    updated_queue_a, updated_item_a = apply_retry_decision_to_queue(
        queue_state=queue_a,
        work_item_id="wi-retry-1",
        retry_decision_artifact=decision_a,
        retry_decision_artifact_path="artifacts/prompt_queue/retry_decisions/wi-retry-1.retry_decision.json",
        clock=FixedClock(["2026-03-22T00:07:01Z"]),
    )

    queue_b = copy.deepcopy(_queue(_failed_item(status="review_invocation_failed", retry_count=0, retry_budget=2)))
    queue_b["work_items"][0]["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-retry-1.execution.json"
    decision_b = evaluate_retry_policy(
        work_item=queue_b["work_items"][0],
        failure_reason_code="provider_transient_failure",
        source_queue_state_path="artifacts/prompt_queue/queue-retry.state.json",
        transition_decision_artifact=_retry_transition(),
        clock=FixedClock(["2026-03-22T00:07:00Z"]),
    )
    updated_queue_b, updated_item_b = apply_retry_decision_to_queue(
        queue_state=queue_b,
        work_item_id="wi-retry-1",
        retry_decision_artifact=decision_b,
        retry_decision_artifact_path="artifacts/prompt_queue/retry_decisions/wi-retry-1.retry_decision.json",
        clock=FixedClock(["2026-03-22T00:07:01Z"]),
    )

    assert decision_a == decision_b
    assert updated_queue_a == updated_queue_b
    assert updated_item_a == updated_item_b


def test_retry_blocked_without_transition_eligibility_artifact():
    queue = _queue(_failed_item(status="executed_failure", retry_count=0, retry_budget=2))
    queue["work_items"][0]["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-retry-1.execution.json"
    decision = evaluate_retry_policy(
        work_item=queue["work_items"][0],
        failure_reason_code="timeout",
        source_queue_state_path="artifacts/prompt_queue/queue-retry.state.json",
        transition_decision_artifact=None,
        clock=FixedClock(["2026-03-22T00:08:00Z"]),
    )
    assert decision["retry_status"] == "retry_blocked"
    assert decision["retry_reason_code"] == "retry_blocked_transition_ineligible"


def test_conflicting_retry_artifact_path_fails_closed():
    queue = _queue(_failed_item(status="executed_failure", retry_count=0, retry_budget=2))
    queue["work_items"][0]["execution_result_artifact_path"] = "artifacts/prompt_queue/execution_results/wi-retry-1.execution.json"
    queue["work_items"][0]["retry_decision_artifact_path"] = "artifacts/prompt_queue/retry_decisions/original.json"
    decision = evaluate_retry_policy(
        work_item=queue["work_items"][0],
        failure_reason_code="timeout",
        source_queue_state_path="artifacts/prompt_queue/queue-retry.state.json",
        transition_decision_artifact=_retry_transition(),
        clock=FixedClock(["2026-03-22T00:09:00Z"]),
    )
    with pytest.raises(RetryQueueIntegrationError, match="Conflicting retry request"):
        apply_retry_decision_to_queue(
            queue_state=queue,
            work_item_id="wi-retry-1",
            retry_decision_artifact=decision,
            retry_decision_artifact_path="artifacts/prompt_queue/retry_decisions/new.json",
            clock=FixedClock(["2026-03-22T00:09:01Z"]),
        )
