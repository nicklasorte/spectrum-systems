"""Pure entry validation and lineage re-validation for live review invocation."""

from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus
from spectrum_systems.modules.prompt_queue.review_invocation_guard import (
    DuplicateReviewInvocationError,
    assert_no_duplicate_review_invocation,
)


class ReviewInvocationEntryValidationError(ValueError):
    """Raised when invocation entry preconditions fail."""


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReviewInvocationEntryValidationError(f"Artifact is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewInvocationEntryValidationError(f"Artifact is not valid JSON: {path}") from exc


def validate_review_invocation_entry(*, work_item: dict, repo_root: Path) -> dict:
    """Validate strict invocation entry preconditions and return lineage context."""
    if work_item.get("status") != WorkItemStatus.REVIEW_TRIGGERED.value:
        raise ReviewInvocationEntryValidationError("Precondition failed: work item status must be 'review_triggered'.")

    review_trigger_artifact_path = work_item.get("review_trigger_artifact_path")
    if not review_trigger_artifact_path:
        raise ReviewInvocationEntryValidationError("Precondition failed: review_trigger_artifact_path must be non-null.")

    try:
        assert_no_duplicate_review_invocation(
            work_item=work_item,
            review_trigger_artifact_path=review_trigger_artifact_path,
        )
    except DuplicateReviewInvocationError as exc:
        raise ReviewInvocationEntryValidationError(str(exc)) from exc

    trigger_path = repo_root / review_trigger_artifact_path
    trigger_artifact = _read_json(trigger_path)

    if trigger_artifact.get("work_item_id") != work_item.get("work_item_id"):
        raise ReviewInvocationEntryValidationError("Precondition failed: trigger artifact work_item_id mismatch.")

    execution_result_artifact_path = trigger_artifact.get("execution_result_artifact_path")
    if not execution_result_artifact_path:
        raise ReviewInvocationEntryValidationError(
            "Precondition failed: trigger artifact execution_result_artifact_path must be non-null."
        )

    execution_path = repo_root / execution_result_artifact_path
    execution_result_artifact = _read_json(execution_path)

    if execution_result_artifact.get("work_item_id") != work_item.get("work_item_id"):
        raise ReviewInvocationEntryValidationError("Precondition failed: execution artifact work_item_id mismatch.")

    if work_item.get("review_invocation_result_artifact_path") is not None:
        raise ReviewInvocationEntryValidationError(
            "Precondition failed: review_invocation_result_artifact_path must be null before invocation."
        )

    return {
        "review_trigger_artifact": trigger_artifact,
        "review_trigger_artifact_path": review_trigger_artifact_path,
        "execution_result_artifact": execution_result_artifact,
        "execution_result_artifact_path": execution_result_artifact_path,
    }
