from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.tlc_hardening import (
    TLCHardeningError,
    build_tlc_orchestration_readiness,
    build_tlc_routing_bundle,
    compute_tlc_orchestration_effectiveness,
    detect_handoff_dead_loop,
    detect_owner_boundary_leakage,
    enforce_prep_vs_authority_integrity,
    evaluate_tlc_routing_bundle,
    run_tlc_boundary_redteam,
    run_tlc_semantic_redteam,
    track_handoff_debt,
    validate_cross_system_handoff_integrity,
    validate_route_to_closure_integrity,
    validate_route_to_review_integrity,
    validate_tlc_routing_replay,
    verify_tlc_closeout_gate,
)
from tests.helpers_repo_write_lineage import build_valid_repo_write_lineage


def _inputs() -> dict[str, object]:
    lineage = build_valid_repo_write_lineage(request_id="req-tlc-hard-1", trace_id="trace-tlc-hard-1")
    return lineage


def test_tlc_new_contract_examples_validate() -> None:
    for name in (
        "tlc_routing_bundle",
        "tlc_routing_eval_result",
        "tlc_routing_conflict_record",
        "tlc_orchestration_readiness_record",
        "tlc_orchestration_effectiveness_record",
        "tlc_handoff_debt_record",
    ):
        validate_artifact(load_example(name), name)


def test_build_and_eval_tlc_routing_bundle_deterministic() -> None:
    governed = _inputs()
    bundle_a = build_tlc_routing_bundle(
        run_id="tlc-hard-001",
        trace_id="trace-tlc-hard-1",
        governed_inputs=copy.deepcopy(governed),
        created_at="2026-04-12T00:00:00Z",
    )
    bundle_b = build_tlc_routing_bundle(
        run_id="tlc-hard-001",
        trace_id="trace-tlc-hard-1",
        governed_inputs=copy.deepcopy(governed),
        created_at="2026-04-12T00:00:00Z",
    )
    assert bundle_a == bundle_b

    eval_result = evaluate_tlc_routing_bundle(
        routing_bundle=bundle_a,
        required_artifacts=copy.deepcopy(governed),
        created_at="2026-04-12T00:00:00Z",
    )
    assert eval_result["evaluation_status"] == "pass"


def test_boundary_checks_replay_and_integrity_guards() -> None:
    governed = _inputs()
    bundle = build_tlc_routing_bundle(
        run_id="tlc-hard-002",
        trace_id="trace-tlc-hard-1",
        governed_inputs=copy.deepcopy(governed),
        created_at="2026-04-12T00:00:00Z",
    )
    eval_result = evaluate_tlc_routing_bundle(
        routing_bundle=bundle,
        required_artifacts=copy.deepcopy(governed),
        created_at="2026-04-12T00:00:00Z",
    )

    assert validate_cross_system_handoff_integrity(routing_bundle=bundle, expected_trace_id="trace-tlc-hard-1") == []
    replay_ok, replay_fails = validate_tlc_routing_replay(
        prior_bundle=bundle,
        replay_bundle=copy.deepcopy(bundle),
        prior_eval=eval_result,
        replay_eval=copy.deepcopy(eval_result),
    )
    assert replay_ok is True
    assert replay_fails == []

    readiness = build_tlc_orchestration_readiness(
        run_id="tlc-hard-002",
        trace_id="trace-tlc-hard-1",
        routing_eval=eval_result,
        handoff_failures=[],
        created_at="2026-04-12T00:00:00Z",
    )
    assert readiness["readiness_status"] == "candidate_only"


def test_prep_authority_dead_loop_owner_leakage_and_route_integrity_guards() -> None:
    prep_fails = enforce_prep_vs_authority_integrity(
        artifact_refs=["batch_progression:1", "closure_decision_artifact:CDE-1"],
        non_authority_assertions=["tlc_not_execution_authority"],
    )
    assert "prep_artifact_substitutes_closure_authority" in prep_fails
    assert "missing_non_authority_assertion" in prep_fails

    assert detect_handoff_dead_loop(route_sequence=["TLC", "RQX", "TLC", "RQX"]) == ["handoff_dead_loop_detected"]

    leaks = detect_owner_boundary_leakage(claimed_owner_actions=["execute_work_slice:foo", "safe:trace_only"])
    assert leaks == ["owner_boundary_leakage:execute_work_slice:foo"]

    review_failures = validate_route_to_review_integrity(
        routing_bundle={"target_system": "RQX"},
        handoff_payload={"execution_payload": {"danger": True}, "closure_authority": True},
    )
    assert "review_handoff_smuggles_execution_semantics" in review_failures
    assert "review_handoff_smuggles_closure_authority" in review_failures

    closure_failures = validate_route_to_closure_integrity(
        progression_refs=["batch_progression:next"],
        closure_authority_present=False,
    )
    assert closure_failures == ["progression_artifact_used_without_cde_closure_authority"]


def test_handoff_debt_effectiveness_redteam_and_fixloop_regressions() -> None:
    debt = track_handoff_debt(
        dispositions=[
            {"handoff_disposition": "hold", "target_system": "RQX", "route_reason_codes": ["x"]},
            {"handoff_disposition": "escalate", "target_system": "RQX", "route_reason_codes": ["x"]},
        ],
        trace_id="trace-tlc-hard-1",
        created_at="2026-04-12T00:00:00Z",
    )
    assert debt["debt_status"] == "elevated"

    effectiveness = compute_tlc_orchestration_effectiveness(
        run_outcomes=[
            {"progressed": True, "dead_loop": False, "bypass": False},
            {"progressed": True, "dead_loop": False, "bypass": False},
            {"progressed": False, "dead_loop": True, "bypass": False},
        ],
        window_id="batch-tlc-001",
        created_at="2026-04-12T00:00:00Z",
    )
    assert effectiveness["runs_evaluated"] == 3

    rt1 = run_tlc_boundary_redteam(
        fixtures=[
            {"fixture_id": "RT1-01", "should_fail_closed": True, "observed": "accepted"},
            {"fixture_id": "RT1-02", "should_fail_closed": True, "observed": "blocked"},
        ]
    )
    assert [row["fixture_id"] for row in rt1] == ["RT1-01"]

    rt2 = run_tlc_semantic_redteam(
        fixtures=[
            {"fixture_id": "RT2-01", "semantic_drift": True, "observed": "accepted"},
            {"fixture_id": "RT2-02", "semantic_drift": True, "observed": "blocked"},
        ]
    )
    assert [row["fixture_id"] for row in rt2] == ["RT2-01"]


def test_fail_closed_missing_governed_inputs() -> None:
    with pytest.raises(TLCHardeningError, match="routing_bundle_missing_inputs"):
        build_tlc_routing_bundle(
            run_id="tlc-hard-003",
            trace_id="trace-tlc-hard-3",
            governed_inputs={"build_admission_record": {}},
            created_at="2026-04-12T00:00:00Z",
        )


def test_effectiveness_requires_non_empty_outcomes() -> None:
    with pytest.raises(TLCHardeningError, match="effectiveness_requires_outcomes"):
        compute_tlc_orchestration_effectiveness(run_outcomes=[], window_id="x", created_at="2026-04-12T00:00:00Z")


def test_tlc_closeout_gate_operationally_real() -> None:
    governed = _inputs()
    bundle = build_tlc_routing_bundle(
        run_id="tlc-closeout-001",
        trace_id="trace-tlc-hard-1",
        governed_inputs=copy.deepcopy(governed),
        created_at="2026-04-12T00:00:00Z",
    )
    eval_result = evaluate_tlc_routing_bundle(
        routing_bundle=bundle,
        required_artifacts=copy.deepcopy(governed),
        created_at="2026-04-12T00:00:00Z",
    )
    readiness = build_tlc_orchestration_readiness(
        run_id="tlc-closeout-001",
        trace_id="trace-tlc-hard-1",
        routing_eval=eval_result,
        handoff_failures=[],
        created_at="2026-04-12T00:00:00Z",
    )
    closeout = verify_tlc_closeout_gate(
        routing_eval=eval_result,
        readiness=readiness,
        replay_match=True,
        dead_loop_failures=[],
        non_authority_assertions=["tlc_not_closure_authority", "tlc_not_execution_authority"],
    )
    assert closeout["closeout_status"] == "closed"
