"""Tests for deterministic prompt queue blocked-item recovery policy and integration."""

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
    BlockedRecoveryQueueIntegrationError,
    Priority,
    RiskLevel,
    apply_blocked_recovery_decision_to_queue,
    evaluate_blocked_recovery_policy,
    validate_blocked_recovery_decision_artifact,
    validate_queue_state,
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


def _blocked_item() -> dict:
    item = make_work_item(
        work_item_id="wi-blocked-1",
        prompt_id="prompt-blocked-1",
        title="Blocked item",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="feature/blocked-recovery",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        clock=FixedClock(["2026-03-22T00:00:00Z"]),
    )
    item["status"] = "blocked"
    return item


def _queue() -> dict:
    return make_queue_state(queue_id="queue-blocked", work_items=[_blocked_item()], clock=FixedClock(["2026-03-22T00:00:01Z"]))


def test_recoverable_blocked_item_returns_to_prior_state_safely():
    queue = _queue()
    decision = evaluate_blocked_recovery_policy(
        work_item=queue["work_items"][0],
        blocking_reason_code="blocked_transient_artifact_write_failure",
        source_blocking_artifact_path="artifacts/prompt_queue/review_invocation_results/wi-blocked-1.review_invocation_result.json",
        prior_state="review_triggered",
        source_queue_state_path="artifacts/prompt_queue/queue-blocked.state.json",
        clock=FixedClock(["2026-03-22T00:01:00Z"]),
    )

    updated_queue, updated_item = apply_blocked_recovery_decision_to_queue(
        queue_state=queue,
        work_item_id="wi-blocked-1",
        blocked_recovery_decision_artifact=decision,
        blocked_recovery_decision_artifact_path="artifacts/prompt_queue/blocked_recovery_decisions/wi-blocked-1.blocked_recovery.json",
        clock=FixedClock(["2026-03-22T00:01:01Z"]),
    )

    assert decision["recovery_status"] == "recoverable"
    assert decision["recovery_action"] == "return_to_prior_state"
    assert updated_item["status"] == "review_triggered"
    validate_work_item(updated_item)
    validate_queue_state(updated_queue)


def test_manual_review_required_stays_blocked_with_no_action():
    queue = _queue()
    decision = evaluate_blocked_recovery_policy(
        work_item=queue["work_items"][0],
        blocking_reason_code="blocked_lineage_mismatch",
        source_blocking_artifact_path="artifacts/prompt_queue/findings/wi-blocked-1.findings.json",
        prior_state="review_triggered",
        source_queue_state_path="artifacts/prompt_queue/queue-blocked.state.json",
        clock=FixedClock(["2026-03-22T00:02:00Z"]),
    )

    updated_queue, updated_item = apply_blocked_recovery_decision_to_queue(
        queue_state=queue,
        work_item_id="wi-blocked-1",
        blocked_recovery_decision_artifact=decision,
        blocked_recovery_decision_artifact_path="artifacts/prompt_queue/blocked_recovery_decisions/wi-blocked-1.blocked_recovery.json",
        clock=FixedClock(["2026-03-22T00:02:01Z"]),
    )

    assert decision["recovery_status"] == "manual_review_required"
    assert decision["recovery_action"] == "no_action"
    assert updated_item["status"] == "blocked"
    validate_work_item(updated_item)
    validate_queue_state(updated_queue)


def test_non_recoverable_item_stays_blocked_with_no_action():
    queue = _queue()
    decision = evaluate_blocked_recovery_policy(
        work_item=queue["work_items"][0],
        blocking_reason_code="blocked_missing_critical_lineage",
        source_blocking_artifact_path=None,
        prior_state=None,
        source_queue_state_path="artifacts/prompt_queue/queue-blocked.state.json",
        clock=FixedClock(["2026-03-22T00:03:00Z"]),
    )

    updated_queue, updated_item = apply_blocked_recovery_decision_to_queue(
        queue_state=queue,
        work_item_id="wi-blocked-1",
        blocked_recovery_decision_artifact=decision,
        blocked_recovery_decision_artifact_path="artifacts/prompt_queue/blocked_recovery_decisions/wi-blocked-1.blocked_recovery.json",
        clock=FixedClock(["2026-03-22T00:03:01Z"]),
    )

    assert decision["recovery_status"] == "non_recoverable"
    assert decision["recovery_action"] == "no_action"
    assert updated_item["status"] == "blocked"
    validate_work_item(updated_item)
    validate_queue_state(updated_queue)


def test_missing_blocking_lineage_fails_closed_for_recoverable_decision():
    queue = _queue()
    decision = evaluate_blocked_recovery_policy(
        work_item=queue["work_items"][0],
        blocking_reason_code="blocked_transient_artifact_write_failure",
        source_blocking_artifact_path=None,
        prior_state="review_triggered",
        source_queue_state_path="artifacts/prompt_queue/queue-blocked.state.json",
        clock=FixedClock(["2026-03-22T00:04:00Z"]),
    )

    with pytest.raises(BlockedRecoveryQueueIntegrationError):
        apply_blocked_recovery_decision_to_queue(
            queue_state=queue,
            work_item_id="wi-blocked-1",
            blocked_recovery_decision_artifact=decision,
            blocked_recovery_decision_artifact_path="artifacts/prompt_queue/blocked_recovery_decisions/wi-blocked-1.blocked_recovery.json",
        )


def test_unsupported_recovery_action_fails_closed():
    queue = _queue()
    decision = evaluate_blocked_recovery_policy(
        work_item=queue["work_items"][0],
        blocking_reason_code="blocked_transient_artifact_write_failure",
        source_blocking_artifact_path="artifacts/prompt_queue/review_invocation_results/wi-blocked-1.review_invocation_result.json",
        prior_state="review_triggered",
        source_queue_state_path="artifacts/prompt_queue/queue-blocked.state.json",
        clock=FixedClock(["2026-03-22T00:05:00Z"]),
    )
    decision["recovery_action"] = "return_to_runnable"

    with pytest.raises(BlockedRecoveryQueueIntegrationError):
        apply_blocked_recovery_decision_to_queue(
            queue_state=queue,
            work_item_id="wi-blocked-1",
            blocked_recovery_decision_artifact=decision,
            blocked_recovery_decision_artifact_path="artifacts/prompt_queue/blocked_recovery_decisions/wi-blocked-1.blocked_recovery.json",
        )


def test_malformed_blocked_work_item_fails_closed():
    malformed_work_item = {"work_item_id": "wi-bad", "status": "blocked"}
    with pytest.raises(Exception):
        evaluate_blocked_recovery_policy(
            work_item=malformed_work_item,
            blocking_reason_code="blocked_transient_artifact_write_failure",
            source_blocking_artifact_path="artifacts/prompt_queue/review_invocation_results/wi-bad.review_invocation_result.json",
            prior_state="review_triggered",
            source_queue_state_path="artifacts/prompt_queue/queue-blocked.state.json",
        )


def test_blocked_recovery_decision_example_validates_against_schema():
    validate_blocked_recovery_decision_artifact(load_example("prompt_queue_blocked_recovery_decision"))


def test_queue_updates_are_deterministic_and_schema_valid():
    queue_a = _queue()
    decision_a = evaluate_blocked_recovery_policy(
        work_item=queue_a["work_items"][0],
        blocking_reason_code="blocked_transient_artifact_update_failure",
        source_blocking_artifact_path="artifacts/prompt_queue/review_invocation_results/wi-blocked-1.review_invocation_result.json",
        prior_state="review_queued",
        source_queue_state_path="artifacts/prompt_queue/queue-blocked.state.json",
        clock=FixedClock(["2026-03-22T00:06:00Z"]),
    )
    updated_queue_a, updated_item_a = apply_blocked_recovery_decision_to_queue(
        queue_state=queue_a,
        work_item_id="wi-blocked-1",
        blocked_recovery_decision_artifact=decision_a,
        blocked_recovery_decision_artifact_path="artifacts/prompt_queue/blocked_recovery_decisions/wi-blocked-1.blocked_recovery.json",
        clock=FixedClock(["2026-03-22T00:06:01Z"]),
    )

    queue_b = copy.deepcopy(_queue())
    decision_b = evaluate_blocked_recovery_policy(
        work_item=queue_b["work_items"][0],
        blocking_reason_code="blocked_transient_artifact_update_failure",
        source_blocking_artifact_path="artifacts/prompt_queue/review_invocation_results/wi-blocked-1.review_invocation_result.json",
        prior_state="review_queued",
        source_queue_state_path="artifacts/prompt_queue/queue-blocked.state.json",
        clock=FixedClock(["2026-03-22T00:06:00Z"]),
    )
    updated_queue_b, updated_item_b = apply_blocked_recovery_decision_to_queue(
        queue_state=queue_b,
        work_item_id="wi-blocked-1",
        blocked_recovery_decision_artifact=decision_b,
        blocked_recovery_decision_artifact_path="artifacts/prompt_queue/blocked_recovery_decisions/wi-blocked-1.blocked_recovery.json",
        clock=FixedClock(["2026-03-22T00:06:01Z"]),
    )

    assert decision_a == decision_b
    assert updated_queue_a == updated_queue_b
    assert updated_item_a == updated_item_b
    validate_work_item(updated_item_a)
    validate_queue_state(updated_queue_a)


def test_duplicate_recovery_attempt_is_prevented_deterministically():
    queue = _queue()
    decision = evaluate_blocked_recovery_policy(
        work_item=queue["work_items"][0],
        blocking_reason_code="blocked_lineage_mismatch",
        source_blocking_artifact_path="artifacts/prompt_queue/findings/wi-blocked-1.findings.json",
        prior_state="review_triggered",
        source_queue_state_path="artifacts/prompt_queue/queue-blocked.state.json",
        clock=FixedClock(["2026-03-22T00:07:00Z"]),
    )
    updated_queue, _ = apply_blocked_recovery_decision_to_queue(
        queue_state=queue,
        work_item_id="wi-blocked-1",
        blocked_recovery_decision_artifact=decision,
        blocked_recovery_decision_artifact_path="artifacts/prompt_queue/blocked_recovery_decisions/wi-blocked-1.blocked_recovery.json",
        clock=FixedClock(["2026-03-22T00:07:01Z"]),
    )

    with pytest.raises(BlockedRecoveryQueueIntegrationError):
        apply_blocked_recovery_decision_to_queue(
            queue_state=updated_queue,
            work_item_id="wi-blocked-1",
            blocked_recovery_decision_artifact=decision,
            blocked_recovery_decision_artifact_path="artifacts/prompt_queue/blocked_recovery_decisions/wi-blocked-1.blocked_recovery.json",
            clock=FixedClock(["2026-03-22T00:07:02Z"]),
        )
