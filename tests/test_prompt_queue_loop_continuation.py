"""Tests for deterministic prompt queue loop continuation child spawn wiring."""

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
    LoopContinuationQueueIntegrationError,
    Priority,
    RiskLevel,
    WorkItemStatus,
    apply_loop_continuation_to_queue,
    run_loop_continuation,
    validate_loop_continuation,
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


def _work_item() -> dict:
    item = make_work_item(
        work_item_id="wi-loop-1",
        prompt_id="prompt-loop-1",
        title="Loop continuation candidate",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="feature/loop-continuation",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        clock=FixedClock(["2026-03-22T00:00:00Z"]),
    )
    item["status"] = WorkItemStatus.REPAIR_PROMPT_GENERATED.value
    item["findings_reentry_artifact_path"] = "artifacts/prompt_queue/findings_reentries/wi-loop-1.findings_reentry.json"
    item["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-loop-1.repair_prompt.json"
    item["loop_control_decision_artifact_path"] = "artifacts/prompt_queue/loop_control/wi-loop-1.loop_control_decision.json"
    return item


def _findings_reentry() -> dict:
    artifact = load_example("prompt_queue_findings_reentry")
    artifact["work_item_id"] = "wi-loop-1"
    artifact["parent_work_item_id"] = None
    artifact["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-loop-1.repair_prompt.json"
    artifact["reentry_status"] = "reentry_completed"
    artifact["reentry_reason_code"] = "reentry_completed_repair_prompt_generated"
    return artifact


def _repair_prompt() -> dict:
    artifact = load_example("prompt_queue_repair_prompt")
    artifact["work_item_id"] = "wi-loop-1"
    artifact["source_findings_artifact_path"] = "artifacts/prompt_queue/findings/wi-loop-1.findings.json"
    artifact["source_review_artifact_path"] = "artifacts/prompt_queue/reviews/wi-loop-1.review.md"
    artifact["review_decision"] = "FAIL"
    artifact["prompt_generation_status"] = "generated"
    return artifact


def _loop_control(action: str = "allow_reentry") -> dict:
    artifact = load_example("prompt_queue_loop_control_decision")
    artifact["work_item_id"] = "wi-loop-1"
    artifact["parent_work_item_id"] = None
    if action == "allow_reentry":
        artifact["loop_control_status"] = "within_budget"
        artifact["enforcement_action"] = "allow_reentry"
        artifact["reason_code"] = "within_budget_allow_reentry"
    else:
        artifact["loop_control_status"] = "limit_exceeded"
        artifact["enforcement_action"] = "block_reentry"
        artifact["reason_code"] = "limit_exceeded_block_reentry"
    return artifact


def test_valid_reentry_generated_repair_prompt_allowed_continuation_spawns_child():
    queue = make_queue_state(queue_id="queue-loop", work_items=[_work_item()], clock=FixedClock(["2026-03-22T00:00:01Z"]))

    result = run_loop_continuation(
        queue_state=queue,
        work_item=queue["work_items"][0],
        findings_reentry_artifact=_findings_reentry(),
        findings_reentry_artifact_path="artifacts/prompt_queue/findings_reentries/wi-loop-1.findings_reentry.json",
        repair_prompt_artifact=_repair_prompt(),
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-loop-1.repair_prompt.json",
        loop_control_decision_artifact=_loop_control("allow_reentry"),
        loop_control_decision_artifact_path="artifacts/prompt_queue/loop_control/wi-loop-1.loop_control_decision.json",
        source_queue_state_path="artifacts/prompt_queue/queue_state.json",
        clock=FixedClock(["2026-03-22T00:01:00Z", "2026-03-22T00:01:01Z", "2026-03-22T00:01:02Z", "2026-03-22T00:01:03Z"]),
    )

    assert result["loop_continuation_artifact"]["continuation_status"] == "child_spawned"
    assert result["spawned_child_work_item"]["work_item_id"] == "wi-loop-1.repair.1"

    updated_queue, updated_item = apply_loop_continuation_to_queue(
        queue_state=queue,
        work_item_id="wi-loop-1",
        loop_continuation_artifact=result["loop_continuation_artifact"],
        loop_continuation_artifact_path="artifacts/prompt_queue/loop_continuations/wi-loop-1.loop_continuation.json",
        updated_queue_state=result["updated_queue_state"],
        spawned_child_work_item=result["spawned_child_work_item"],
        clock=FixedClock(["2026-03-22T00:01:04Z", "2026-03-22T00:01:05Z"]),
    )

    assert updated_item["loop_continuation_artifact_path"]
    validate_work_item(updated_item)
    validate_queue_state(updated_queue)


def test_loop_control_blocked_returns_continuation_blocked_and_no_child():
    queue = make_queue_state(queue_id="queue-loop", work_items=[_work_item()], clock=FixedClock(["2026-03-22T00:00:01Z"]))
    result = run_loop_continuation(
        queue_state=queue,
        work_item=queue["work_items"][0],
        findings_reentry_artifact=_findings_reentry(),
        findings_reentry_artifact_path="artifacts/prompt_queue/findings_reentries/wi-loop-1.findings_reentry.json",
        repair_prompt_artifact=_repair_prompt(),
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-loop-1.repair_prompt.json",
        loop_control_decision_artifact=_loop_control("block_reentry"),
        loop_control_decision_artifact_path="artifacts/prompt_queue/loop_control/wi-loop-1.loop_control_decision.json",
        clock=FixedClock(["2026-03-22T00:01:00Z"]),
    )

    assert result["loop_continuation_artifact"]["continuation_status"] == "continuation_blocked"
    assert result["spawned_child_work_item"] is None


def test_duplicate_continuation_attempt_is_prevented():
    queue = make_queue_state(queue_id="queue-loop", work_items=[_work_item()], clock=FixedClock(["2026-03-22T00:00:01Z"]))
    existing_child = make_work_item(
        work_item_id="wi-loop-1.repair.1",
        prompt_id="prompt-loop-1:repair:1",
        title="Loop continuation candidate [repair 1]",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="feature/loop-continuation",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        parent_work_item_id="wi-loop-1",
        clock=FixedClock(["2026-03-22T00:00:02Z"]),
    )
    existing_child["spawned_from_repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-loop-1.repair_prompt.json"
    queue["work_items"].append(existing_child)

    result = run_loop_continuation(
        queue_state=queue,
        work_item=queue["work_items"][0],
        findings_reentry_artifact=_findings_reentry(),
        findings_reentry_artifact_path="artifacts/prompt_queue/findings_reentries/wi-loop-1.findings_reentry.json",
        repair_prompt_artifact=_repair_prompt(),
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-loop-1.repair_prompt.json",
        loop_control_decision_artifact=_loop_control("allow_reentry"),
        loop_control_decision_artifact_path="artifacts/prompt_queue/loop_control/wi-loop-1.loop_control_decision.json",
        clock=FixedClock(["2026-03-22T00:01:00Z"]),
    )

    assert result["loop_continuation_artifact"]["continuation_status"] == "continuation_blocked"
    assert result["loop_continuation_artifact"]["continuation_reason_code"] == "continuation_blocked_duplicate_spawn"


def test_missing_repair_prompt_artifact_fails_closed():
    queue = make_queue_state(queue_id="queue-loop", work_items=[_work_item()], clock=FixedClock(["2026-03-22T00:00:01Z"]))
    with pytest.raises(Exception):
        run_loop_continuation(
            queue_state=queue,
            work_item=queue["work_items"][0],
            findings_reentry_artifact=_findings_reentry(),
            findings_reentry_artifact_path="artifacts/prompt_queue/findings_reentries/wi-loop-1.findings_reentry.json",
            repair_prompt_artifact={},
            repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-loop-1.repair_prompt.json",
            loop_control_decision_artifact=_loop_control("allow_reentry"),
            loop_control_decision_artifact_path="artifacts/prompt_queue/loop_control/wi-loop-1.loop_control_decision.json",
        )


def test_missing_reentry_artifact_fails_closed():
    queue = make_queue_state(queue_id="queue-loop", work_items=[_work_item()], clock=FixedClock(["2026-03-22T00:00:01Z"]))
    with pytest.raises(Exception):
        run_loop_continuation(
            queue_state=queue,
            work_item=queue["work_items"][0],
            findings_reentry_artifact={},
            findings_reentry_artifact_path="artifacts/prompt_queue/findings_reentries/wi-loop-1.findings_reentry.json",
            repair_prompt_artifact=_repair_prompt(),
            repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-loop-1.repair_prompt.json",
            loop_control_decision_artifact=_loop_control("allow_reentry"),
            loop_control_decision_artifact_path="artifacts/prompt_queue/loop_control/wi-loop-1.loop_control_decision.json",
        )


def test_lineage_mismatch_between_reentry_and_repair_prompt_fails_closed():
    queue = make_queue_state(queue_id="queue-loop", work_items=[_work_item()], clock=FixedClock(["2026-03-22T00:00:01Z"]))
    bad_reentry = _findings_reentry()
    bad_reentry["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/other.repair_prompt.json"

    with pytest.raises(Exception):
        run_loop_continuation(
            queue_state=queue,
            work_item=queue["work_items"][0],
            findings_reentry_artifact=bad_reentry,
            findings_reentry_artifact_path="artifacts/prompt_queue/findings_reentries/wi-loop-1.findings_reentry.json",
            repair_prompt_artifact=_repair_prompt(),
            repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-loop-1.repair_prompt.json",
            loop_control_decision_artifact=_loop_control("allow_reentry"),
            loop_control_decision_artifact_path="artifacts/prompt_queue/loop_control/wi-loop-1.loop_control_decision.json",
        )


def test_child_creation_failure_returns_continuation_failed():
    queue = make_queue_state(queue_id="queue-loop", work_items=[_work_item()], clock=FixedClock(["2026-03-22T00:00:01Z"]))
    queue["work_items"][0]["status"] = WorkItemStatus.BLOCKED.value

    result = run_loop_continuation(
        queue_state=queue,
        work_item=queue["work_items"][0],
        findings_reentry_artifact=_findings_reentry(),
        findings_reentry_artifact_path="artifacts/prompt_queue/findings_reentries/wi-loop-1.findings_reentry.json",
        repair_prompt_artifact=_repair_prompt(),
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-loop-1.repair_prompt.json",
        loop_control_decision_artifact=_loop_control("allow_reentry"),
        loop_control_decision_artifact_path="artifacts/prompt_queue/loop_control/wi-loop-1.loop_control_decision.json",
        clock=FixedClock(["2026-03-22T00:01:00Z"]),
    )

    assert result["loop_continuation_artifact"]["continuation_status"] == "continuation_failed"


def test_continuation_example_validates_against_schema():
    validate_loop_continuation(load_example("prompt_queue_loop_continuation"))


def test_queue_work_item_updates_are_deterministic_and_schema_valid():
    queue = make_queue_state(queue_id="queue-loop", work_items=[_work_item()], clock=FixedClock(["2026-03-22T00:00:01Z"]))

    result_a = run_loop_continuation(
        queue_state=queue,
        work_item=queue["work_items"][0],
        findings_reentry_artifact=_findings_reentry(),
        findings_reentry_artifact_path="artifacts/prompt_queue/findings_reentries/wi-loop-1.findings_reentry.json",
        repair_prompt_artifact=_repair_prompt(),
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-loop-1.repair_prompt.json",
        loop_control_decision_artifact=_loop_control("allow_reentry"),
        loop_control_decision_artifact_path="artifacts/prompt_queue/loop_control/wi-loop-1.loop_control_decision.json",
        clock=FixedClock(["2026-03-22T00:01:00Z", "2026-03-22T00:01:01Z", "2026-03-22T00:01:02Z", "2026-03-22T00:01:03Z"]),
    )
    updated_queue_a, updated_item_a = apply_loop_continuation_to_queue(
        queue_state=queue,
        work_item_id="wi-loop-1",
        loop_continuation_artifact=result_a["loop_continuation_artifact"],
        loop_continuation_artifact_path="artifacts/prompt_queue/loop_continuations/wi-loop-1.loop_continuation.json",
        updated_queue_state=result_a["updated_queue_state"],
        spawned_child_work_item=result_a["spawned_child_work_item"],
        clock=FixedClock(["2026-03-22T00:01:04Z", "2026-03-22T00:01:05Z"]),
    )

    queue_copy = copy.deepcopy(queue)
    result_b = run_loop_continuation(
        queue_state=queue_copy,
        work_item=queue_copy["work_items"][0],
        findings_reentry_artifact=_findings_reentry(),
        findings_reentry_artifact_path="artifacts/prompt_queue/findings_reentries/wi-loop-1.findings_reentry.json",
        repair_prompt_artifact=_repair_prompt(),
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-loop-1.repair_prompt.json",
        loop_control_decision_artifact=_loop_control("allow_reentry"),
        loop_control_decision_artifact_path="artifacts/prompt_queue/loop_control/wi-loop-1.loop_control_decision.json",
        clock=FixedClock(["2026-03-22T00:01:00Z", "2026-03-22T00:01:01Z", "2026-03-22T00:01:02Z", "2026-03-22T00:01:03Z"]),
    )
    updated_queue_b, updated_item_b = apply_loop_continuation_to_queue(
        queue_state=queue_copy,
        work_item_id="wi-loop-1",
        loop_continuation_artifact=result_b["loop_continuation_artifact"],
        loop_continuation_artifact_path="artifacts/prompt_queue/loop_continuations/wi-loop-1.loop_continuation.json",
        updated_queue_state=result_b["updated_queue_state"],
        spawned_child_work_item=result_b["spawned_child_work_item"],
        clock=FixedClock(["2026-03-22T00:01:04Z", "2026-03-22T00:01:05Z"]),
    )

    assert updated_item_a == updated_item_b
    assert updated_queue_a == updated_queue_b
    validate_work_item(updated_item_a)
    validate_queue_state(updated_queue_a)


def test_continuation_failed_cannot_mutate_queue():
    queue = make_queue_state(queue_id="queue-loop", work_items=[_work_item()], clock=FixedClock(["2026-03-22T00:00:01Z"]))
    failed = load_example("prompt_queue_loop_continuation")
    failed["work_item_id"] = "wi-loop-1"
    failed["spawned_child_work_item_id"] = None
    failed["continuation_status"] = "continuation_failed"
    failed["continuation_reason_code"] = "continuation_failed_child_creation"

    with pytest.raises(LoopContinuationQueueIntegrationError):
        apply_loop_continuation_to_queue(
            queue_state=queue,
            work_item_id="wi-loop-1",
            loop_continuation_artifact=failed,
            loop_continuation_artifact_path="artifacts/prompt_queue/loop_continuations/wi-loop-1.loop_continuation.json",
            updated_queue_state=None,
            spawned_child_work_item=None,
        )
