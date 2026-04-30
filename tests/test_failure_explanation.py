"""Tests for failure_explanation (CLX-ALL-01 Phase 5).

Covers:
- Valid block/freeze produces packet with required fields
- primary_reason is required
- outcome must be block or freeze
- stage inference from artifact_type
- suggested_repair auto-generated from stage
- attach_explanation_to_block_outcome convenience function
- Empty trace_id raises
- Invalid outcome raises
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.failure_explanation import (
    FailureExplanationError,
    attach_explanation_to_block_outcome,
    build_failure_explanation_packet,
)


def _valid_kwargs() -> dict:
    return {
        "trace_id": "trace-001",
        "outcome": "block",
        "primary_reason": "proof_presence_required_but_missing",
        "triggering_artifact_type": "proof_presence_enforcement_result",
        "triggering_artifact_id": "pper-abc123",
        "expected_behavior": "PR includes a valid loop_proof_bundle",
        "actual_behavior": "No proof artifact found for governed surfaces",
    }


def test_valid_block_produces_packet() -> None:
    packet = build_failure_explanation_packet(**_valid_kwargs())
    assert packet["artifact_type"] == "failure_explanation_packet"
    assert packet["outcome"] == "block"
    assert packet["primary_reason"] == "proof_presence_required_but_missing"
    assert packet["stage_of_failure"] == "GOV"


def test_valid_freeze_produces_packet() -> None:
    kwargs = _valid_kwargs()
    kwargs["outcome"] = "freeze"
    packet = build_failure_explanation_packet(**kwargs)
    assert packet["outcome"] == "freeze"


def test_required_fields_present() -> None:
    packet = build_failure_explanation_packet(**_valid_kwargs())
    required = [
        "artifact_type", "schema_version", "packet_id", "trace_id",
        "outcome", "primary_reason", "stage_of_failure",
        "triggering_artifact", "expected_behavior", "actual_behavior", "emitted_at",
    ]
    for key in required:
        assert key in packet, f"Missing: {key}"


def test_triggering_artifact_has_required_fields() -> None:
    packet = build_failure_explanation_packet(**_valid_kwargs())
    art = packet["triggering_artifact"]
    assert "artifact_type" in art
    assert "artifact_id" in art


def test_stage_inferred_from_artifact_type_closure_decision() -> None:
    kwargs = _valid_kwargs()
    kwargs["triggering_artifact_type"] = "closure_decision_artifact"
    kwargs["triggering_artifact_id"] = "cde-001"
    packet = build_failure_explanation_packet(**kwargs)
    assert packet["stage_of_failure"] == "CDE"


def test_stage_inferred_from_artifact_type_enforcement() -> None:
    kwargs = _valid_kwargs()
    kwargs["triggering_artifact_type"] = "enforcement_block_record"
    kwargs["triggering_artifact_id"] = "sel-001"
    packet = build_failure_explanation_packet(**kwargs)
    assert packet["stage_of_failure"] == "SEL"


def test_stage_inferred_from_artifact_type_eval() -> None:
    kwargs = _valid_kwargs()
    kwargs["triggering_artifact_type"] = "required_eval_coverage"
    kwargs["triggering_artifact_id"] = "evl-001"
    packet = build_failure_explanation_packet(**kwargs)
    assert packet["stage_of_failure"] == "EVL"


def test_unknown_artifact_type_maps_to_unknown_stage() -> None:
    kwargs = _valid_kwargs()
    kwargs["triggering_artifact_type"] = "completely_unknown_artifact"
    kwargs["triggering_artifact_id"] = "unk-001"
    packet = build_failure_explanation_packet(**kwargs)
    assert packet["stage_of_failure"] == "unknown"


def test_suggested_repair_auto_generated() -> None:
    packet = build_failure_explanation_packet(**_valid_kwargs())
    assert packet["suggested_repair"] is not None
    assert len(packet["suggested_repair"]) > 0


def test_explicit_stage_overrides_inference() -> None:
    kwargs = _valid_kwargs()
    kwargs["stage_of_failure"] = "FRE"
    packet = build_failure_explanation_packet(**kwargs)
    assert packet["stage_of_failure"] == "FRE"


def test_empty_trace_id_raises() -> None:
    import pytest
    kwargs = _valid_kwargs()
    kwargs["trace_id"] = ""
    with pytest.raises(FailureExplanationError, match="trace_id"):
        build_failure_explanation_packet(**kwargs)


def test_invalid_outcome_raises() -> None:
    import pytest
    kwargs = _valid_kwargs()
    kwargs["outcome"] = "allow"
    with pytest.raises(FailureExplanationError, match="outcome"):
        build_failure_explanation_packet(**kwargs)


def test_empty_primary_reason_raises() -> None:
    import pytest
    kwargs = _valid_kwargs()
    kwargs["primary_reason"] = ""
    with pytest.raises(FailureExplanationError, match="primary_reason"):
        build_failure_explanation_packet(**kwargs)


def test_attach_explanation_to_block_outcome() -> None:
    outcome = {
        "outcome_type": "block",
        "block_reason": "proof_missing",
        "triggering_artifact_type": "proof_presence_enforcement_result",
        "triggering_artifact_id": "pper-001",
    }
    packet = attach_explanation_to_block_outcome(block_outcome=outcome, trace_id="t")
    assert packet["artifact_type"] == "failure_explanation_packet"
    assert packet["outcome"] == "block"
    assert packet["primary_reason"] == "proof_missing"


def test_attach_non_dict_raises() -> None:
    import pytest
    with pytest.raises(FailureExplanationError):
        attach_explanation_to_block_outcome(block_outcome="not-a-dict", trace_id="t")


def test_ambiguity_note_stored_when_provided() -> None:
    kwargs = _valid_kwargs()
    kwargs["ambiguity_note"] = "Could be either GOV or FRE — review trace."
    packet = build_failure_explanation_packet(**kwargs)
    assert packet["ambiguity_note"] == "Could be either GOV or FRE — review trace."
