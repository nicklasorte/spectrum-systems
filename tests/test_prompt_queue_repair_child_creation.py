"""Tests for governed prompt queue child repair work-item creation and queue integration."""

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
    RepairChildQueueIntegrationError,
    RiskLevel,
    WorkItemStatus,
    make_queue_state,
    make_work_item,
    spawn_repair_child_in_queue,
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


def _parent() -> dict:
    item = make_work_item(
        work_item_id="wi-parent",
        prompt_id="prompt-parent",
        title="Parent work item",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="feature/repair-child",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        clock=FixedClock(["2026-03-22T00:00:00Z"]),
    )
    item["status"] = WorkItemStatus.REPAIR_PROMPT_GENERATED.value
    item["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json"
    return item


def _repair_prompt() -> dict:
    artifact = load_example("prompt_queue_repair_prompt")
    artifact["work_item_id"] = "wi-parent"
    artifact["review_decision"] = "FAIL"
    artifact["prompt_generation_status"] = "generated"
    artifact["source_findings_artifact_path"] = "artifacts/prompt_queue/findings/wi-parent.findings.json"
    artifact["source_review_artifact_path"] = "docs/reviews/2026-03-22-parent-review.md"
    return artifact


def test_valid_repair_prompt_spawns_child_successfully():
    parent = _parent()
    queue = make_queue_state(queue_id="queue-01", work_items=[parent], clock=FixedClock(["2026-03-22T00:00:00Z"]))

    updated_queue, updated_parent, child = spawn_repair_child_in_queue(
        queue_state=queue,
        parent_work_item_id="wi-parent",
        repair_prompt_artifact=_repair_prompt(),
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json",
        clock=FixedClock(["2026-03-22T00:00:10Z", "2026-03-22T00:00:11Z", "2026-03-22T00:00:12Z"]),
    )

    assert child["work_item_id"] == "wi-parent.repair.1"
    assert child["status"] == WorkItemStatus.QUEUED.value
    assert child["parent_work_item_id"] == "wi-parent"
    assert updated_parent["status"] == WorkItemStatus.REPAIR_CHILD_CREATED.value
    assert updated_parent["child_work_item_ids"] == ["wi-parent.repair.1"]
    assert len(updated_queue["work_items"]) == 2


def test_child_contains_explicit_lineage_fields():
    parent = _parent()
    queue = make_queue_state(queue_id="queue-01", work_items=[parent], clock=FixedClock(["2026-03-22T00:00:00Z"]))
    path = "artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json"

    _, _, child = spawn_repair_child_in_queue(
        queue_state=queue,
        parent_work_item_id="wi-parent",
        repair_prompt_artifact=_repair_prompt(),
        repair_prompt_artifact_path=path,
        clock=FixedClock(["2026-03-22T00:00:10Z", "2026-03-22T00:00:11Z", "2026-03-22T00:00:12Z"]),
    )

    assert child["spawned_from_repair_prompt_artifact_path"] == path
    assert child["spawned_from_findings_artifact_path"] == "artifacts/prompt_queue/findings/wi-parent.findings.json"
    assert child["spawned_from_review_artifact_path"] == "docs/reviews/2026-03-22-parent-review.md"
    assert child["repair_loop_generation"] == 1


def test_duplicate_spawn_attempt_fails_closed():
    parent = _parent()
    path = "artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json"
    first_child = make_work_item(
        work_item_id="wi-parent.repair.1",
        prompt_id="prompt-parent:repair:1",
        title="Parent work item [repair 1]",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="feature/repair-child",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        parent_work_item_id="wi-parent",
        clock=FixedClock(["2026-03-22T00:00:09Z"]),
    )
    first_child["spawned_from_repair_prompt_artifact_path"] = path
    queue = make_queue_state(queue_id="queue-01", work_items=[parent, first_child], clock=FixedClock(["2026-03-22T00:00:00Z"]))

    with pytest.raises(RepairChildQueueIntegrationError, match="Duplicate child spawn"):
        spawn_repair_child_in_queue(
            queue_state=queue,
            parent_work_item_id="wi-parent",
            repair_prompt_artifact=_repair_prompt(),
            repair_prompt_artifact_path=path,
            clock=FixedClock(["2026-03-22T00:00:10Z"]),
        )


def test_missing_repair_prompt_path_fails_closed():
    parent = _parent()
    queue = make_queue_state(queue_id="queue-01", work_items=[parent], clock=FixedClock(["2026-03-22T00:00:00Z"]))
    with pytest.raises(RepairChildQueueIntegrationError, match="repair_prompt_artifact_path is required"):
        spawn_repair_child_in_queue(
            queue_state=queue,
            parent_work_item_id="wi-parent",
            repair_prompt_artifact=_repair_prompt(),
            repair_prompt_artifact_path="",
            clock=FixedClock(["2026-03-22T00:00:10Z"]),
        )


def test_pass_derived_repair_prompt_artifact_cannot_spawn_child():
    parent = _parent()
    queue = make_queue_state(queue_id="queue-01", work_items=[parent], clock=FixedClock(["2026-03-22T00:00:00Z"]))
    artifact = _repair_prompt()
    artifact["review_decision"] = "PASS"

    with pytest.raises(RepairChildQueueIntegrationError, match="Malformed repair prompt artifact"):
        spawn_repair_child_in_queue(
            queue_state=queue,
            parent_work_item_id="wi-parent",
            repair_prompt_artifact=artifact,
            repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json",
            clock=FixedClock(["2026-03-22T00:00:10Z"]),
        )


def test_malformed_repair_prompt_artifact_fails_closed():
    parent = _parent()
    queue = make_queue_state(queue_id="queue-01", work_items=[parent], clock=FixedClock(["2026-03-22T00:00:00Z"]))
    artifact = _repair_prompt()
    artifact.pop("prompt_generation_status")

    with pytest.raises(RepairChildQueueIntegrationError):
        spawn_repair_child_in_queue(
            queue_state=queue,
            parent_work_item_id="wi-parent",
            repair_prompt_artifact=artifact,
            repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json",
            clock=FixedClock(["2026-03-22T00:00:10Z"]),
        )


def test_parent_and_queue_are_updated_and_schema_validated_after_spawn():
    parent = _parent()
    queue = make_queue_state(queue_id="queue-01", work_items=[parent], clock=FixedClock(["2026-03-22T00:00:00Z"]))

    updated_queue, updated_parent, child = spawn_repair_child_in_queue(
        queue_state=queue,
        parent_work_item_id="wi-parent",
        repair_prompt_artifact=_repair_prompt(),
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-parent.repair_prompt.json",
        clock=FixedClock(["2026-03-22T00:00:10Z", "2026-03-22T00:00:11Z", "2026-03-22T00:00:12Z"]),
    )

    assert updated_parent["work_item_id"] == "wi-parent"
    assert child["status"] == WorkItemStatus.QUEUED.value
    validate_work_item(updated_parent)
    validate_work_item(child)
    validate_queue_state(updated_queue)
