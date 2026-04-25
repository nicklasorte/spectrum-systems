"""Tests for rollback.py — advisory revert / quarantine artifacts."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop.rollback import (
    RollbackError,
    RollbackRequest,
    build_rollback_record,
    emit_rollback,
    is_quarantined,
    list_rollbacks,
)


def _evidence():
    return ({"kind": "snippet", "detail": "regression observed"},)


def test_build_revert_record(store):
    record = build_rollback_record(
        RollbackRequest(
            subject_candidate_id="cand_a",
            previous_promoted_candidate_id="baseline_v1",
            action="revert",
            reason="regression_detected",
            evidence=_evidence(),
        )
    )
    assert record["action"] == "revert"
    assert record["reason"] == "regression_detected"
    assert record["advisory_only"] is True
    assert record["subject_candidate_id"] == "cand_a"
    assert record["previous_promoted_candidate_id"] == "baseline_v1"


def test_emit_quarantine_persists_record(store):
    record = emit_rollback(
        RollbackRequest(
            subject_candidate_id="cand_b",
            action="quarantine",
            reason="blocking_failure_detected",
            evidence=_evidence(),
        ),
        store=store,
    )
    assert is_quarantined(store, "cand_b")
    assert not is_quarantined(store, "cand_a")
    found = list(list_rollbacks(store, subject_candidate_id="cand_b"))
    assert len(found) == 1
    assert found[0]["artifact_id"] == record["artifact_id"]


def test_emit_rollback_idempotent(store):
    req = RollbackRequest(
        subject_candidate_id="cand_b",
        action="revert",
        reason="operator_request",
        evidence=_evidence(),
    )
    a = emit_rollback(req, store=store)
    b = emit_rollback(req, store=store)
    assert a["artifact_id"] == b["artifact_id"]


def test_invalid_action_rejected(store):
    with pytest.raises(RollbackError, match="invalid_action"):
        build_rollback_record(
            RollbackRequest(
                subject_candidate_id="cand_x",
                action="promote",  # not a valid action
                reason="operator_request",
                evidence=_evidence(),
            )
        )


def test_invalid_reason_rejected(store):
    with pytest.raises(RollbackError, match="invalid_reason"):
        build_rollback_record(
            RollbackRequest(
                subject_candidate_id="cand_x",
                action="revert",
                reason="i_dont_like_it",
                evidence=_evidence(),
            )
        )


def test_self_referential_rejected(store):
    with pytest.raises(RollbackError, match="invalid_self_reference"):
        build_rollback_record(
            RollbackRequest(
                subject_candidate_id="cand_x",
                previous_promoted_candidate_id="cand_x",
                action="revert",
                reason="operator_request",
                evidence=_evidence(),
            )
        )


def test_empty_evidence_rejected(store):
    with pytest.raises(RollbackError, match="evidence_required"):
        build_rollback_record(
            RollbackRequest(
                subject_candidate_id="cand_x",
                action="revert",
                reason="operator_request",
                evidence=(),
            )
        )


def test_malformed_evidence_rejected(store):
    with pytest.raises(RollbackError, match="invalid_evidence"):
        build_rollback_record(
            RollbackRequest(
                subject_candidate_id="cand_x",
                action="revert",
                reason="operator_request",
                evidence=({"kind": "", "detail": "x"},),
            )
        )
