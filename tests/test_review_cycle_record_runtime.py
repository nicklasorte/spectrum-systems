"""Runtime tests for review_cycle_record lifecycle behavior."""

from __future__ import annotations

import pytest
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.review_cycle_record import (
    ReviewCycleRecordError,
    advance_review_cycle,
    attach_fix_slice,
    attach_replay_result,
    attach_review_result,
    create_review_cycle,
    terminate_review_cycle,
)


def _create() -> dict:
    return create_review_cycle(
        parent_batch_id="REVIEW-FIX-LOOP-36-EXPLICIT",
        parent_umbrella_id="UMBRELLA-REVIEW-FIX-36",
        max_iterations=3,
        review_request_ref="review_request_artifact:rf-01-initial",
        lineage=["review_loop_entry:REVIEW-FIX-LOOP-36-EXPLICIT", "owner:RQX"],
        created_at="2026-04-11T00:00:00Z",
    )


def test_create_review_cycle_from_real_function_call() -> None:
    cycle = _create()
    assert cycle["artifact_type"] == "review_cycle_record"
    assert cycle["iteration_number"] == 1
    assert cycle["status"] == "active"
    assert cycle["termination_state"] == "open"


def test_iteration_increment_behavior() -> None:
    cycle = _create()
    cycle = advance_review_cycle(cycle, updated_at="2026-04-11T00:10:00Z")
    assert cycle["iteration_number"] == 2
    assert cycle["updated_at"] == "2026-04-11T00:10:00Z"


def test_attach_review_fix_replay_references() -> None:
    cycle = _create()
    cycle = attach_review_result(cycle, review_result_ref="review_result_artifact:r1")
    cycle = attach_fix_slice(cycle, fix_slice_ref="review_fix_slice_artifact:f1")
    cycle = attach_replay_result(cycle, replay_result_ref="replay_execution_record:p1")
    assert cycle["review_result_refs"] == ["review_result_artifact:r1"]
    assert cycle["fix_slice_refs"] == ["review_fix_slice_artifact:f1"]
    assert cycle["replay_result_refs"] == ["replay_execution_record:p1"]


def test_termination_behavior_blocks_future_mutation() -> None:
    cycle = _create()
    terminated = terminate_review_cycle(
        cycle,
        termination_state="completed",
        status="completed",
        updated_at="2026-04-11T00:20:00Z",
    )
    assert terminated["status"] == "completed"
    assert terminated["termination_state"] == "completed"

    with pytest.raises(ReviewCycleRecordError):
        advance_review_cycle(terminated)


def test_invalid_transitions_fail_closed() -> None:
    cycle = _create()
    cycle = advance_review_cycle(cycle)
    cycle = advance_review_cycle(cycle)
    with pytest.raises(ReviewCycleRecordError):
        advance_review_cycle(cycle)


def test_missing_required_fields_fail_validation() -> None:
    cycle = _create()
    cycle.pop("review_request_ref")
    with pytest.raises(ValidationError):
        validate_artifact(cycle, "review_cycle_record")
