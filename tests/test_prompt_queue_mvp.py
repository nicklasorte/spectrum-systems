"""Tests for governed prompt queue MVP (state, fallback orchestration, artifacts)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    IllegalTransitionError,
    Priority,
    ProviderResult,
    RiskLevel,
    WorkItemStatus,
    make_queue_state,
    make_work_item,
    run_review_with_fallback,
    transition_work_item,
    validate_queue_state,
    validate_review_attempt,
    validate_work_item,
    write_artifact,
)


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if not self._values:
            return datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc)
        return self._values.pop(0)


def _base_item(clock=None):
    if clock is None:
        clock = FixedClock(["2026-03-22T00:00:00Z"])
    return make_work_item(
        work_item_id="wi-100",
        prompt_id="prompt-100",
        title="Queue MVP",
        priority=Priority.HIGH,
        risk_level=RiskLevel.MEDIUM,
        repo="spectrum-systems",
        branch="feature/gpq",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        clock=clock,
    )


def test_valid_work_item_schema():
    validate_work_item(load_example("prompt_queue_work_item"))


def test_valid_queue_state_schema():
    validate_queue_state(load_example("prompt_queue_state"))


def test_valid_review_attempt_schema():
    validate_review_attempt(load_example("prompt_queue_review_attempt"))


def test_legal_state_transitions():
    item = _base_item(clock=FixedClock(["2026-03-22T00:00:00Z", "2026-03-22T00:00:01Z"]))
    review_queued = transition_work_item(item, WorkItemStatus.REVIEW_QUEUED.value, clock=FixedClock(["2026-03-22T00:00:01Z"]))
    running = transition_work_item(review_queued, WorkItemStatus.REVIEW_RUNNING.value, clock=FixedClock(["2026-03-22T00:00:02Z"]))
    done = transition_work_item(running, WorkItemStatus.REVIEW_COMPLETE.value, clock=FixedClock(["2026-03-22T00:00:03Z"]))
    assert done["status"] == WorkItemStatus.REVIEW_COMPLETE.value


def test_illegal_state_transitions_fail_closed():
    item = _base_item()
    with pytest.raises(IllegalTransitionError):
        transition_work_item(item, WorkItemStatus.REVIEW_COMPLETE.value, clock=FixedClock(["2026-03-22T00:00:01Z"]))


def test_claude_success_path():
    item = _base_item(clock=FixedClock(["2026-03-22T00:00:00Z"]))
    clock = FixedClock([
        "2026-03-22T00:00:01Z",
        "2026-03-22T00:00:02Z",
        "2026-03-22T00:00:03Z",
        "2026-03-22T00:00:04Z",
        "2026-03-22T00:00:05Z",
    ])
    updated, attempts = run_review_with_fallback(
        item,
        run_claude=lambda _wi: ProviderResult(success=True, review_artifact_path="artifacts/prompt_queue/claude.json"),
        run_codex=lambda _wi: ProviderResult(success=True),
        clock=clock,
    )
    assert updated["status"] == WorkItemStatus.REVIEW_COMPLETE.value
    assert updated["review_provider_actual"] == "claude"
    assert len(attempts) == 1


def test_claude_usage_limit_fallback_to_codex_success():
    item = _base_item(clock=FixedClock(["2026-03-22T00:00:00Z"]))
    updated, attempts = run_review_with_fallback(
        item,
        run_claude=lambda _wi: ProviderResult(success=False, failure_reason="usage_limit", error_message="limit"),
        run_codex=lambda _wi: ProviderResult(success=True, review_artifact_path="artifacts/prompt_queue/codex.json"),
        clock=FixedClock([
            "2026-03-22T00:00:01Z",
            "2026-03-22T00:00:02Z",
            "2026-03-22T00:00:03Z",
            "2026-03-22T00:00:04Z",
            "2026-03-22T00:00:05Z",
            "2026-03-22T00:00:06Z",
            "2026-03-22T00:00:07Z",
        ]),
    )
    assert updated["status"] == WorkItemStatus.REVIEW_COMPLETE.value
    assert updated["review_provider_actual"] == "codex"
    assert updated["review_fallback_used"] is True
    assert updated["review_fallback_reason"] == "usage_limit"
    assert len(attempts) == 2


def test_claude_failure_and_codex_failure_blocks_item():
    item = _base_item(clock=FixedClock(["2026-03-22T00:00:00Z"]))
    updated, attempts = run_review_with_fallback(
        item,
        run_claude=lambda _wi: ProviderResult(success=False, failure_reason="timeout", error_message="timeout"),
        run_codex=lambda _wi: ProviderResult(success=False, failure_reason="provider_unavailable", error_message="down"),
        clock=FixedClock([
            "2026-03-22T00:00:01Z",
            "2026-03-22T00:00:02Z",
            "2026-03-22T00:00:03Z",
            "2026-03-22T00:00:04Z",
            "2026-03-22T00:00:05Z",
            "2026-03-22T00:00:06Z",
            "2026-03-22T00:00:07Z",
        ]),
    )
    assert updated["status"] == WorkItemStatus.BLOCKED.value
    assert updated["review_fallback_used"] is True
    assert len(attempts) == 2
    assert attempts[0]["error_message"] == "timeout"
    assert attempts[1]["provider_used"] == "codex"


def test_provider_metadata_recorded_correctly():
    item = _base_item(clock=FixedClock(["2026-03-22T00:00:00Z"]))
    updated, attempts = run_review_with_fallback(
        item,
        run_claude=lambda _wi: ProviderResult(success=False, failure_reason="rate_limited", error_message="429"),
        run_codex=lambda _wi: ProviderResult(success=True, review_artifact_path="artifacts/prompt_queue/codex.json"),
        clock=FixedClock([
            "2026-03-22T00:00:01Z",
            "2026-03-22T00:00:02Z",
            "2026-03-22T00:00:03Z",
            "2026-03-22T00:00:04Z",
            "2026-03-22T00:00:05Z",
            "2026-03-22T00:00:06Z",
            "2026-03-22T00:00:07Z",
        ]),
    )
    assert updated["review_fallback_reason"] == "rate_limited"
    assert attempts[0]["provider_requested"] == "claude"
    assert attempts[1]["fallback_used"] is True


def test_timestamps_update_deterministically():
    item = _base_item(clock=FixedClock(["2026-03-22T00:00:00Z"]))
    moved = transition_work_item(item, WorkItemStatus.REVIEW_QUEUED.value, clock=FixedClock(["2026-03-22T00:00:30Z"]))
    assert item["updated_at"] == "2026-03-22T00:00:00Z"
    assert moved["updated_at"] == "2026-03-22T00:00:30Z"


def test_emitted_artifacts_validate_against_schema(tmp_path: Path):
    item = _base_item(clock=FixedClock(["2026-03-22T00:00:00Z"]))
    queue = make_queue_state(queue_id="queue-100", work_items=[item], clock=FixedClock(["2026-03-22T00:00:00Z"]))
    updated, attempts = run_review_with_fallback(
        item,
        run_claude=lambda _wi: ProviderResult(success=True, review_artifact_path="artifacts/prompt_queue/claude.json"),
        run_codex=lambda _wi: ProviderResult(success=True),
        clock=FixedClock([
            "2026-03-22T00:00:01Z",
            "2026-03-22T00:00:02Z",
            "2026-03-22T00:00:03Z",
            "2026-03-22T00:00:04Z",
            "2026-03-22T00:00:05Z",
        ]),
    )
    queue["work_items"] = [updated]

    validate_work_item(updated)
    validate_queue_state(queue)
    for attempt in attempts:
        validate_review_attempt(attempt)

    item_path = write_artifact(updated, tmp_path / "item.json")
    queue_path = write_artifact(queue, tmp_path / "queue.json")
    attempt_path = write_artifact(attempts[0], tmp_path / "attempt.json")

    for path in (item_path, queue_path, attempt_path):
        assert path.exists()
        json.loads(path.read_text(encoding="utf-8"))


def test_findings_parsed_to_repair_prompt_generated_transition():
    item = _base_item(clock=FixedClock(["2026-03-22T00:00:00Z"]))
    review_complete = transition_work_item(item, WorkItemStatus.REVIEW_QUEUED.value, clock=FixedClock(["2026-03-22T00:00:01Z"]))
    review_complete = transition_work_item(review_complete, WorkItemStatus.REVIEW_RUNNING.value, clock=FixedClock(["2026-03-22T00:00:02Z"]))
    review_complete = transition_work_item(review_complete, WorkItemStatus.REVIEW_COMPLETE.value, clock=FixedClock(["2026-03-22T00:00:03Z"]))
    findings_parsed = transition_work_item(review_complete, WorkItemStatus.FINDINGS_PARSED.value, clock=FixedClock(["2026-03-22T00:00:04Z"]))
    repair_generated = transition_work_item(findings_parsed, WorkItemStatus.REPAIR_PROMPT_GENERATED.value, clock=FixedClock(["2026-03-22T00:00:05Z"]))
    assert repair_generated["status"] == WorkItemStatus.REPAIR_PROMPT_GENERATED.value
