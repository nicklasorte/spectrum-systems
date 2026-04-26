"""Tests for rollback_signals.py — advisory revert/withhold_signal advisories to REL."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop.rollback_signals import (
    RollbackSignalError,
    RollbackSignalRequest,
    build_rollback_signal,
    emit_rollback_signal,
    has_withhold_signal,
    iter_rollback_signal_records,
)


def _evidence():
    return ({"kind": "snippet", "detail": "regression observed"},)


def test_build_revert_signal(store):
    record = build_rollback_signal(
        RollbackSignalRequest(
            subject_candidate_id="cand_a",
            previous_promoted_candidate_id="baseline_v1",
            recommended_action="revert",
            reason="regression_detected",
            evidence=_evidence(),
        )
    )
    assert record["recommended_action"] == "revert"
    assert record["reason"] == "regression_detected"
    assert record["advisory_only"] is True
    assert record["delegates_to"] == "REL"
    assert record["subject_candidate_id"] == "cand_a"
    assert record["previous_promoted_candidate_id"] == "baseline_v1"


def test_emit_withhold_signal_persists(store):
    record = emit_rollback_signal(
        RollbackSignalRequest(
            subject_candidate_id="cand_b",
            recommended_action="withhold_signal",
            reason="blocking_failure_detected",
            evidence=_evidence(),
        ),
        store=store,
    )
    assert has_withhold_signal(store, "cand_b")
    assert not has_withhold_signal(store, "cand_a")
    found = list(iter_rollback_signal_records(store, subject_candidate_id="cand_b"))
    assert len(found) == 1
    assert found[0]["artifact_id"] == record["artifact_id"]


def test_emit_rollback_signal_idempotent(store):
    req = RollbackSignalRequest(
        subject_candidate_id="cand_b",
        recommended_action="revert",
        reason="operator_request",
        evidence=_evidence(),
    )
    a = emit_rollback_signal(req, store=store)
    b = emit_rollback_signal(req, store=store)
    assert a["artifact_id"] == b["artifact_id"]


def test_invalid_action_rejected(store):
    with pytest.raises(RollbackSignalError, match="invalid_action"):
        build_rollback_signal(
            RollbackSignalRequest(
                subject_candidate_id="cand_x",
                recommended_action="advance",  # not a valid recommendation
                reason="operator_request",
                evidence=_evidence(),
            )
        )


def test_invalid_reason_rejected(store):
    with pytest.raises(RollbackSignalError, match="invalid_reason"):
        build_rollback_signal(
            RollbackSignalRequest(
                subject_candidate_id="cand_x",
                recommended_action="revert",
                reason="i_dont_like_it",
                evidence=_evidence(),
            )
        )


def test_self_referential_rejected(store):
    with pytest.raises(RollbackSignalError, match="invalid_self_reference"):
        build_rollback_signal(
            RollbackSignalRequest(
                subject_candidate_id="cand_x",
                previous_promoted_candidate_id="cand_x",
                recommended_action="revert",
                reason="operator_request",
                evidence=_evidence(),
            )
        )


def test_empty_evidence_rejected(store):
    with pytest.raises(RollbackSignalError, match="evidence_required"):
        build_rollback_signal(
            RollbackSignalRequest(
                subject_candidate_id="cand_x",
                recommended_action="revert",
                reason="operator_request",
                evidence=(),
            )
        )


def test_malformed_evidence_rejected(store):
    with pytest.raises(RollbackSignalError, match="invalid_evidence"):
        build_rollback_signal(
            RollbackSignalRequest(
                subject_candidate_id="cand_x",
                recommended_action="revert",
                reason="operator_request",
                evidence=({"kind": "", "detail": "x"},),
            )
        )


def test_release_block_signal_reason_value_accepted(store):
    """The release_block_signal reason replaces the prior promotion_gate_block."""
    record = build_rollback_signal(
        RollbackSignalRequest(
            subject_candidate_id="cand_y",
            recommended_action="withhold_signal",
            reason="release_block_signal",
            evidence=_evidence(),
        )
    )
    assert record["reason"] == "release_block_signal"
