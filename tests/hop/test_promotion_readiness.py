"""Tests for promotion_readiness.py — search + held-out, fail-closed, advisory."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop.evaluator import evaluate_candidate
from spectrum_systems.modules.hop.promotion_readiness import (
    ReadinessSignalConfig,
    ReadinessSignalInputs,
    evaluate_and_persist,
    evaluate_release_readiness,
    list_risk_failures_for_candidate,
)
from spectrum_systems.modules.hop.schemas import validate_hop_artifact
from tests.hop.conftest import make_baseline_candidate


@pytest.fixture()
def saturated_pair(eval_set, heldout_eval_set, store):
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    search = evaluate_candidate(candidate_payload=candidate, eval_set=eval_set, store=store)
    heldout = evaluate_candidate(
        candidate_payload=candidate, eval_set=heldout_eval_set, store=store
    )
    return candidate, search["score"], heldout["score"]


def test_ready_signal_on_saturated_baseline(saturated_pair, store):
    candidate, search_score, heldout_score = saturated_pair
    signal = evaluate_release_readiness(
        inputs=ReadinessSignalInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
            risk_failures=(),
        ),
        store=store,
    )
    assert signal["readiness_signal"] == "ready_signal"
    assert signal["advisory_only"] is True
    assert signal["delegates_to"] == "REL"
    validate_hop_artifact(signal, "hop_harness_release_readiness_signal")
    checks = {r["check"] for r in signal["rationale"]}
    assert {
        "candidate_admitted",
        "search_set_disjoint_from_heldout",
        "search_score_threshold",
        "heldout_score_threshold",
        "trace_completeness",
        "no_risk_failures",
    } <= checks
    assert all(r["passed"] for r in signal["rationale"])


def test_risk_signal_below_search_threshold(saturated_pair, store):
    candidate, search_score, heldout_score = saturated_pair
    cfg = ReadinessSignalConfig(search_score_threshold=2.0)  # impossible
    signal = evaluate_release_readiness(
        inputs=ReadinessSignalInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
        ),
        store=store,
        config=cfg,
    )
    assert signal["readiness_signal"] == "risk_signal"
    failed = [r for r in signal["rationale"] if not r["passed"]]
    assert any(r["check"] == "search_score_threshold" for r in failed)


def test_risk_signal_below_heldout_threshold(saturated_pair, store):
    candidate, search_score, heldout_score = saturated_pair
    cfg = ReadinessSignalConfig(heldout_score_threshold=2.0)
    signal = evaluate_release_readiness(
        inputs=ReadinessSignalInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
        ),
        store=store,
        config=cfg,
    )
    assert signal["readiness_signal"] == "risk_signal"
    failed = {r["check"] for r in signal["rationale"] if not r["passed"]}
    assert "heldout_score_threshold" in failed


def test_risk_signal_when_search_eq_heldout(saturated_pair, store):
    candidate, search_score, _ = saturated_pair
    signal = evaluate_release_readiness(
        inputs=ReadinessSignalInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=search_score,  # forbidden — same eval_set_id
        ),
        store=store,
    )
    assert signal["readiness_signal"] == "risk_signal"
    failed = {r["check"] for r in signal["rationale"] if not r["passed"]}
    assert "search_set_disjoint_from_heldout" in failed


def test_risk_signal_with_risk_failures(saturated_pair, store):
    candidate, search_score, heldout_score = saturated_pair
    fake_risk = {"hypothesis_id": "h1", "blocks_promotion": True}
    signal = evaluate_release_readiness(
        inputs=ReadinessSignalInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
            risk_failures=(fake_risk,),
        ),
        store=store,
    )
    assert signal["readiness_signal"] == "risk_signal"
    assert signal["risk_failure_count"] == 1


def test_risk_signal_when_candidate_not_admitted(
    eval_set, heldout_eval_set, store
):
    candidate = make_baseline_candidate()
    # Deliberately do NOT write candidate to the store.
    search = evaluate_candidate(candidate_payload=candidate, eval_set=eval_set)
    heldout = evaluate_candidate(
        candidate_payload=candidate, eval_set=heldout_eval_set
    )
    signal = evaluate_release_readiness(
        inputs=ReadinessSignalInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search["score"],
            heldout_score=heldout["score"],
        ),
        store=store,
    )
    assert signal["readiness_signal"] == "risk_signal"
    failed = {r["check"] for r in signal["rationale"] if not r["passed"]}
    assert "candidate_admitted" in failed


def test_evaluate_and_persist_writes_artifact(saturated_pair, store):
    candidate, search_score, heldout_score = saturated_pair
    signal = evaluate_and_persist(
        inputs=ReadinessSignalInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
        ),
        store=store,
    )
    # Idempotent: a second call with the same inputs must not raise.
    again = evaluate_and_persist(
        inputs=ReadinessSignalInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
        ),
        store=store,
    )
    assert signal["artifact_id"] == again["artifact_id"]


def test_list_risk_failures_filters_by_blocks_promotion(saturated_pair, store):
    candidate, _, _ = saturated_pair
    risks = list_risk_failures_for_candidate(store, candidate["candidate_id"])
    # In the saturated baseline run there are no risk failures.
    assert all(bool(b.get("blocks_promotion")) for b in risks)


def test_readiness_signal_artifact_advisory_only(saturated_pair, store):
    candidate, search_score, heldout_score = saturated_pair
    signal = evaluate_release_readiness(
        inputs=ReadinessSignalInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
        ),
        store=store,
    )
    assert signal["advisory_only"] is True
    # readiness_signal is constrained to {ready_signal, warn_signal, risk_signal};
    # the harness has no execution authority value.
    assert signal["readiness_signal"] in {"ready_signal", "warn_signal", "risk_signal"}
