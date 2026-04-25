"""Tests for promotion_gate.py — search + held-out, fail-closed, advisory."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop.evaluator import evaluate_candidate
from spectrum_systems.modules.hop.promotion_gate import (
    PromotionGateConfig,
    PromotionGateInputs,
    evaluate_and_persist,
    evaluate_promotion,
    list_blocking_failures_for_candidate,
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


def test_promotion_gate_allow_on_saturated_baseline(saturated_pair, store):
    candidate, search_score, heldout_score = saturated_pair
    decision = evaluate_promotion(
        inputs=PromotionGateInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
            blocking_failures=(),
        ),
        store=store,
    )
    assert decision["decision"] == "allow"
    assert decision["advisory_only"] is True
    validate_hop_artifact(decision, "hop_harness_promotion_decision")
    # All checks must have explicit rationale entries.
    checks = {r["check"] for r in decision["rationale"]}
    assert {
        "candidate_admitted",
        "search_set_disjoint_from_heldout",
        "search_score_threshold",
        "heldout_score_threshold",
        "trace_completeness",
        "no_blocking_failures",
    } <= checks
    assert all(r["passed"] for r in decision["rationale"])


def test_promotion_gate_blocks_below_search_threshold(saturated_pair, store):
    candidate, search_score, heldout_score = saturated_pair
    cfg = PromotionGateConfig(search_score_threshold=2.0)  # impossible
    decision = evaluate_promotion(
        inputs=PromotionGateInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
        ),
        store=store,
        config=cfg,
    )
    assert decision["decision"] == "block"
    failed = [r for r in decision["rationale"] if not r["passed"]]
    assert any(r["check"] == "search_score_threshold" for r in failed)


def test_promotion_gate_blocks_below_heldout_threshold(saturated_pair, store):
    candidate, search_score, heldout_score = saturated_pair
    cfg = PromotionGateConfig(heldout_score_threshold=2.0)
    decision = evaluate_promotion(
        inputs=PromotionGateInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
        ),
        store=store,
        config=cfg,
    )
    assert decision["decision"] == "block"
    failed = {r["check"] for r in decision["rationale"] if not r["passed"]}
    assert "heldout_score_threshold" in failed


def test_promotion_gate_blocks_when_search_eq_heldout(saturated_pair, store):
    candidate, search_score, _ = saturated_pair
    decision = evaluate_promotion(
        inputs=PromotionGateInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=search_score,  # forbidden — same eval_set_id
        ),
        store=store,
    )
    assert decision["decision"] == "block"
    failed = {r["check"] for r in decision["rationale"] if not r["passed"]}
    assert "search_set_disjoint_from_heldout" in failed


def test_promotion_gate_blocks_with_blocking_failures(saturated_pair, store):
    candidate, search_score, heldout_score = saturated_pair
    fake_blocking = {"hypothesis_id": "h1", "blocks_promotion": True}
    decision = evaluate_promotion(
        inputs=PromotionGateInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
            blocking_failures=(fake_blocking,),
        ),
        store=store,
    )
    assert decision["decision"] == "block"
    assert decision["blocking_failure_count"] == 1


def test_promotion_gate_blocks_when_candidate_not_admitted(
    eval_set, heldout_eval_set, store
):
    candidate = make_baseline_candidate()
    # Deliberately do NOT write candidate to the store.
    search = evaluate_candidate(candidate_payload=candidate, eval_set=eval_set)
    heldout = evaluate_candidate(
        candidate_payload=candidate, eval_set=heldout_eval_set
    )
    decision = evaluate_promotion(
        inputs=PromotionGateInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search["score"],
            heldout_score=heldout["score"],
        ),
        store=store,
    )
    assert decision["decision"] == "block"
    failed = {r["check"] for r in decision["rationale"] if not r["passed"]}
    assert "candidate_admitted" in failed


def test_evaluate_and_persist_writes_artifact(saturated_pair, store):
    candidate, search_score, heldout_score = saturated_pair
    decision = evaluate_and_persist(
        inputs=PromotionGateInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
        ),
        store=store,
    )
    # Idempotent: a second call with the same inputs must not raise.
    again = evaluate_and_persist(
        inputs=PromotionGateInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
        ),
        store=store,
    )
    assert decision["artifact_id"] == again["artifact_id"]


def test_list_blocking_failures_filters_by_blocks_promotion(saturated_pair, store):
    candidate, _, _ = saturated_pair
    blocking = list_blocking_failures_for_candidate(store, candidate["candidate_id"])
    # In the saturated baseline run there are no blocking failures.
    assert all(bool(b.get("blocks_promotion")) for b in blocking)


def test_promotion_gate_decision_artifact_advisory_only(saturated_pair, store):
    candidate, search_score, heldout_score = saturated_pair
    decision = evaluate_promotion(
        inputs=PromotionGateInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
        ),
        store=store,
    )
    assert decision["advisory_only"] is True
    # The schema constrains decision to ['allow','warn','block'] — there is no
    # 'promote' literal anywhere in HOP.
    assert decision["decision"] in {"allow", "warn", "block"}
