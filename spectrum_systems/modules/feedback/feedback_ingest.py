"""
Feedback Ingestion — spectrum_systems/modules/feedback/feedback_ingest.py

Helpers for creating, validating, and attaching feedback records to artifacts.

Design principles
-----------------
- Feedback creation is the only place where a new ``HumanFeedbackRecord`` is
  instantiated from raw reviewer input.
- ``validate_feedback`` is a thin guard that delegates to the record's own
  schema validation.
- Attachment is declarative: the store index is updated but the artifact
  document itself is never mutated (feedback is additive only).

Public API
----------
create_feedback_from_review(artifact, reviewer_input) -> HumanFeedbackRecord
    Build and validate a new feedback record from raw reviewer input.

validate_feedback(record) -> list[str]
    Return schema validation errors (empty list = valid).

attach_feedback_to_artifact(artifact_id, feedback_id, store) -> None
    Register a feedback_id against an artifact_id in the store index.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from spectrum_systems.modules.feedback.human_feedback import (
    FeedbackStore,
    HumanFeedbackRecord,
)


def create_feedback_from_review(
    artifact: Dict[str, Any],
    reviewer_input: Dict[str, Any],
    store: Optional[FeedbackStore] = None,
) -> HumanFeedbackRecord:
    """Build and persist a new feedback record from raw reviewer input.

    Parameters
    ----------
    artifact:
        Dict containing at least ``artifact_id`` and ``artifact_type`` fields
        identifying the artifact under review.
    reviewer_input:
        Dict with all reviewer-supplied fields.  Required keys:

        - ``reviewer_id`` (str)
        - ``reviewer_role`` (str)
        - ``target_level`` (str): ``artifact`` | ``section`` | ``claim``
        - ``target_id`` (str)
        - ``action`` (str)
        - ``original_text`` (str)
        - ``rationale`` (str)
        - ``source_of_truth`` (str)
        - ``failure_type`` (str)
        - ``severity`` (str)
        - ``should_update`` (dict with ``golden_dataset``, ``prompts``,
          ``retrieval_memory`` booleans)

        Optional keys:

        - ``edited_text`` (str | None)
    store:
        ``FeedbackStore`` to persist the record.  A default store is created
        if not provided.

    Returns
    -------
    HumanFeedbackRecord
        Validated and persisted feedback record.

    Raises
    ------
    ValueError
        If required keys are missing or validation fails.
    KeyError
        If ``artifact`` is missing ``artifact_id`` or ``artifact_type``.
    """
    should_update = reviewer_input.get("should_update", {})

    record = HumanFeedbackRecord(
        artifact_id=artifact["artifact_id"],
        artifact_type=artifact["artifact_type"],
        target_level=reviewer_input["target_level"],
        target_id=reviewer_input["target_id"],
        reviewer_id=reviewer_input["reviewer_id"],
        reviewer_role=reviewer_input["reviewer_role"],
        action=reviewer_input["action"],
        original_text=reviewer_input["original_text"],
        edited_text=reviewer_input.get("edited_text"),
        rationale=reviewer_input["rationale"],
        source_of_truth=reviewer_input["source_of_truth"],
        failure_type=reviewer_input["failure_type"],
        severity=reviewer_input["severity"],
        golden_dataset=should_update.get("golden_dataset", False),
        prompts=should_update.get("prompts", False),
        retrieval_memory=should_update.get("retrieval_memory", False),
    )

    errors = validate_feedback(record)
    if errors:
        raise ValueError(
            f"Feedback record failed validation: {'; '.join(errors)}"
        )

    _store = store or FeedbackStore()
    _store.save_feedback(record)
    return record


def validate_feedback(record: HumanFeedbackRecord) -> List[str]:
    """Return schema validation errors for the given feedback record.

    Parameters
    ----------
    record:
        ``HumanFeedbackRecord`` to validate.

    Returns
    -------
    list[str]
        Validation error messages.  Empty list means the record is valid.
    """
    return record.validate_against_schema()


def attach_feedback_to_artifact(
    artifact_id: str,
    feedback_id: str,
    store: Optional[FeedbackStore] = None,
) -> None:
    """Register a feedback record against an artifact in the store index.

    This is a declarative link — no artifact document is mutated.

    Parameters
    ----------
    artifact_id:
        Target artifact identifier.
    feedback_id:
        Feedback record identifier.
    store:
        ``FeedbackStore`` instance.  A default store is used if not provided.
    """
    _store = store or FeedbackStore()
    # Load the feedback record to ensure it exists
    _store.load_feedback(feedback_id)
    # Update index (idempotent: duplicate links are ignored in _update_index)
    _store._update_index(artifact_id, feedback_id)  # noqa: SLF001
