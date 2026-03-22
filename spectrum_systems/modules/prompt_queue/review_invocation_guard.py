"""Fail-closed helper primitives for review invocation duplicate prevention."""

from __future__ import annotations


class DuplicateReviewInvocationError(ValueError):
    """Raised when an invocation would duplicate an already persisted invocation result."""


def has_duplicate_review_invocation_result(*, work_item: dict, review_trigger_artifact_path: str) -> bool:
    """Return True when persisted invocation result linkage already exists for current trigger lineage."""
    persisted_result_path = work_item.get("review_invocation_result_artifact_path")
    persisted_trigger_path = work_item.get("review_trigger_artifact_path")
    return bool(persisted_result_path and persisted_trigger_path == review_trigger_artifact_path)


def assert_no_duplicate_review_invocation(*, work_item: dict, review_trigger_artifact_path: str) -> None:
    """Raise when duplicate invocation lineage is detected."""
    if has_duplicate_review_invocation_result(
        work_item=work_item,
        review_trigger_artifact_path=review_trigger_artifact_path,
    ):
        raise DuplicateReviewInvocationError(
            "Duplicate review invocation blocked: review_invocation_result_artifact_path already exists for trigger lineage."
        )
