from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.review_handoff_disposition import (
    ReviewHandoffDispositionError,
    emit_review_handoff_disposition,
)


def test_review_handoff_disposition_contract_examples_validate() -> None:
    for artifact_type in ("review_operator_handoff_artifact", "review_handoff_disposition_artifact"):
        validate_artifact(load_example(artifact_type), artifact_type)


def test_fix_required_handoff_emits_schedule_follow_on_disposition(tmp_path) -> None:
    handoff = copy.deepcopy(load_example("review_operator_handoff_artifact"))
    handoff["post_cycle_verdict"] = "fix_required"
    handoff["handoff_reason"] = "post_cycle_fix_still_required"

    result = emit_review_handoff_disposition(handoff, output_dir=tmp_path)

    disposition = result["review_handoff_disposition_artifact"]
    assert disposition["disposition"] == "schedule_follow_on_cycle"
    assert disposition["reason_code"] == "unresolved_fix_required"
    assert disposition["scheduling_eligible"] is True
    assert disposition["provenance"]["execution_triggered"] is False
    assert disposition["provenance"]["rqx_cycle_reentry_triggered"] is False


def test_not_safe_to_merge_emits_escalation_disposition(tmp_path) -> None:
    handoff = copy.deepcopy(load_example("review_operator_handoff_artifact"))
    handoff["post_cycle_verdict"] = "not_safe_to_merge"
    handoff["handoff_reason"] = "post_cycle_not_safe_to_merge"

    result = emit_review_handoff_disposition(handoff, output_dir=tmp_path)
    disposition = result["review_handoff_disposition_artifact"]

    assert disposition["disposition"] == "escalate_to_owner"
    assert disposition["reason_code"] == "not_safe_to_merge"
    assert disposition["escalation_owner_ref"] == "CDE"
    assert disposition["scheduling_eligible"] is False


@pytest.mark.parametrize(
    ("handoff_reason", "expected_disposition", "expected_reason_code"),
    [
        ("tpa_blocked", "manual_review_required", "tpa_blocked"),
        ("checkpoint_required", "request_checkpoint_decision", "checkpoint_missing"),
        ("execution_failed", "hold_pending_input", "execution_failed"),
    ],
)
def test_blocked_outcomes_map_to_bounded_dispositions(
    tmp_path,
    handoff_reason: str,
    expected_disposition: str,
    expected_reason_code: str,
) -> None:
    handoff = copy.deepcopy(load_example("review_operator_handoff_artifact"))
    handoff["post_cycle_verdict"] = None
    handoff["handoff_reason"] = handoff_reason

    result = emit_review_handoff_disposition(handoff, output_dir=tmp_path)
    disposition = result["review_handoff_disposition_artifact"]

    assert disposition["disposition"] == expected_disposition
    assert disposition["reason_code"] == expected_reason_code
    validate_artifact(disposition, "review_handoff_disposition_artifact")


def test_disposition_emission_fails_closed_for_ambiguous_handoff(tmp_path) -> None:
    handoff = copy.deepcopy(load_example("review_operator_handoff_artifact"))
    handoff["handoff_reason"] = "review_incomplete"
    handoff["post_cycle_verdict"] = "safe_to_merge"

    with pytest.raises(ReviewHandoffDispositionError, match="ambiguous handoff disposition"):
        emit_review_handoff_disposition(handoff, output_dir=tmp_path)


def test_disposition_emits_once_per_handoff(tmp_path) -> None:
    handoff = copy.deepcopy(load_example("review_operator_handoff_artifact"))

    emit_review_handoff_disposition(handoff, output_dir=tmp_path)
    with pytest.raises(ReviewHandoffDispositionError, match="already exists"):
        emit_review_handoff_disposition(handoff, output_dir=tmp_path)


def test_disposition_artifact_does_not_become_execution_or_closure_authority(tmp_path) -> None:
    handoff = copy.deepcopy(load_example("review_operator_handoff_artifact"))
    result = emit_review_handoff_disposition(handoff, output_dir=tmp_path)
    disposition = result["review_handoff_disposition_artifact"]

    assert "pqx_execution" not in disposition
    assert "closure_decision" not in disposition
    assert disposition["provenance"]["execution_triggered"] is False
    assert disposition["provenance"]["closure_authority_transferred"] is False
