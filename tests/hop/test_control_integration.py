"""Tests for control_integration.py — harness -> external owners bridge."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop.control_integration import (
    ControlAdvisoryRequest,
    ControlIntegrationError,
    build_control_advisory,
    emit_control_advisory,
    list_advisories,
)
from spectrum_systems.modules.hop.evaluator import evaluate_candidate
from spectrum_systems.modules.hop.promotion_readiness import (
    ReadinessSignalInputs,
    evaluate_and_persist,
)
from tests.hop.conftest import make_baseline_candidate


@pytest.fixture()
def populated_store(eval_set, heldout_eval_set, store):
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    search = evaluate_candidate(
        candidate_payload=candidate, eval_set=eval_set, store=store
    )
    heldout = evaluate_candidate(
        candidate_payload=candidate, eval_set=heldout_eval_set, store=store
    )
    signal = evaluate_and_persist(
        inputs=ReadinessSignalInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search["score"],
            heldout_score=heldout["score"],
        ),
        store=store,
    )
    return candidate, signal, store


def test_emit_advisory_for_readiness_evaluation(populated_store):
    candidate, signal, store = populated_store
    advisory = emit_control_advisory(
        ControlAdvisoryRequest(
            subject_candidate_id=candidate["candidate_id"],
            summary_kind="readiness_evaluation",
            release_readiness_signal_artifact_id=signal["artifact_id"],
            risk_failure_artifact_ids=(),
            delegates_to=("REL", "CDE"),
        ),
        store=store,
    )
    assert advisory["advisory_only"] is True
    assert advisory["summary_kind"] == "readiness_evaluation"
    assert advisory["release_readiness_signal_artifact_id"] == signal["artifact_id"]
    assert advisory["delegates_to"] == ["REL", "CDE"]


def test_advisory_rejects_unknown_kind(populated_store):
    _, _, store = populated_store
    with pytest.raises(ControlIntegrationError, match="invalid_kind"):
        build_control_advisory(
            ControlAdvisoryRequest(
                subject_candidate_id="cand_x",
                summary_kind="rubber_stamp",
            ),
            store=store,
        )


def test_advisory_rejects_missing_readiness_signal(store):
    with pytest.raises(ControlIntegrationError, match="missing_readiness_signal"):
        build_control_advisory(
            ControlAdvisoryRequest(
                subject_candidate_id="cand_x",
                summary_kind="readiness_evaluation",
                release_readiness_signal_artifact_id="hop_rs_signal_does_not_exist",
            ),
            store=store,
        )


def test_advisory_rejects_missing_failure_reference(store):
    with pytest.raises(ControlIntegrationError, match="missing_failure"):
        build_control_advisory(
            ControlAdvisoryRequest(
                subject_candidate_id="cand_x",
                summary_kind="rollback_signal_request",
                risk_failure_artifact_ids=("hop_failure_does_not_exist",),
            ),
            store=store,
        )


def test_advisory_rejects_empty_delegates(store):
    with pytest.raises(ControlIntegrationError, match="no_delegates"):
        build_control_advisory(
            ControlAdvisoryRequest(
                subject_candidate_id="cand_x",
                summary_kind="trend_signal",
                delegates_to=(),
            ),
            store=store,
        )


def test_list_advisories_filters(populated_store):
    candidate, signal, store = populated_store
    emit_control_advisory(
        ControlAdvisoryRequest(
            subject_candidate_id=candidate["candidate_id"],
            summary_kind="readiness_evaluation",
            release_readiness_signal_artifact_id=signal["artifact_id"],
        ),
        store=store,
    )
    found = list(
        list_advisories(
            store,
            subject_candidate_id=candidate["candidate_id"],
            summary_kind="readiness_evaluation",
        )
    )
    assert len(found) == 1
    other_kind = list(
        list_advisories(store, summary_kind="rollback_signal_request")
    )
    assert len(other_kind) == 0


def test_advisory_idempotent(populated_store):
    candidate, signal, store = populated_store
    req = ControlAdvisoryRequest(
        subject_candidate_id=candidate["candidate_id"],
        summary_kind="readiness_evaluation",
        release_readiness_signal_artifact_id=signal["artifact_id"],
    )
    a = emit_control_advisory(req, store=store)
    b = emit_control_advisory(req, store=store)
    assert a["artifact_id"] == b["artifact_id"]
