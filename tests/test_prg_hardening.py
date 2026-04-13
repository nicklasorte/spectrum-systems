from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.prg_hardening import (
    PRGHardeningError,
    build_governance_bundle,
    build_governance_conflict_record,
    build_governance_effectiveness,
    build_governance_readiness,
    build_recommendation_rework_debt,
    check_adoption_candidate_integrity,
    check_governance_to_rdx_integrity,
    check_pattern_report_integrity,
    check_recommendation_authority_boundary,
    check_trust_posture_snapshot_integrity,
    enforce_prg_boundary,
    run_governance_eval,
    run_governance_recommendation_engine,
    run_prg_boundary_redteam,
    run_prg_semantic_redteam,
    validate_recommendation_replay,
)


def _program_brief() -> dict:
    return {
        "program_id": "PRG-ROADMAP-EXECUTION",
        "lineage_ref": "lineage:prg:001",
    }


def _signal_bundle() -> dict:
    return {
        "missing_eval_coverage": ["S1", "S2"],
        "override_hotspots": [],
    }


def test_prg_contract_examples_validate() -> None:
    for name in (
        "evaluation_pattern_report",
        "policy_change_candidate",
        "slice_contract_update_candidate",
        "program_alignment_assessment",
        "prioritized_adoption_candidate_set",
        "adaptive_readiness_record",
        "prg_governance_eval_result",
        "prg_governance_readiness_record",
        "prg_governance_conflict_record",
        "prg_governance_bundle",
        "prg_governance_effectiveness_record",
        "prg_recommendation_rework_debt_record",
    ):
        validate_artifact(load_example(name), name)


def test_prg_01_02_03_04_06_07_engine_eval_alignment_replay() -> None:
    failures = enforce_prg_boundary(
        consumed_inputs=["roadmap_signal_bundle", "runtime_execution_state"],
        emitted_outputs=["prioritized_adoption_candidate_set", "closure_decision_artifact"],
        claimed_actions=["execute_work:batch-1"],
    )
    assert "invalid_upstream_input:runtime_execution_state" in failures
    assert "invalid_downstream_output:closure_decision_artifact" in failures
    assert "forbidden_owner_overlap:execute_work:batch-1" in failures

    outputs = run_governance_recommendation_engine(
        program_brief=_program_brief(),
        roadmap_signal_bundle=_signal_bundle(),
        evaluation_patterns=[{"pattern_code": "missing_eval_coverage"}, {"pattern_code": "missing_eval_coverage"}],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-prg-001",
    )
    eval_result = run_governance_eval(
        pattern_report=outputs["pattern_report"],
        candidate_set=outputs["candidate_set"],
        alignment_assessment=outputs["alignment_assessment"],
        evidence_refs=["ev:1", "ev:2"],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-prg-001",
    )
    assert eval_result["evaluation_status"] == "pass"

    replay_ok, replay_fails = validate_recommendation_replay(
        prior_inputs={"program_brief": _program_brief(), "signal": _signal_bundle()},
        replay_inputs={"program_brief": _program_brief(), "signal": _signal_bundle()},
        prior_outputs=outputs,
        replay_outputs=copy.deepcopy(outputs),
    )
    assert replay_ok is True
    assert replay_fails == []


def test_prg_05_08_08a_08b_08c_08d_08e_09_and_redteam_fix_loops() -> None:
    outputs = run_governance_recommendation_engine(
        program_brief=_program_brief(),
        roadmap_signal_bundle=_signal_bundle(),
        evaluation_patterns=[{"pattern_code": "P1"}, {"pattern_code": "P1"}, {"pattern_code": "P2"}],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-prg-001",
    )
    eval_result = run_governance_eval(
        pattern_report=outputs["pattern_report"],
        candidate_set=outputs["candidate_set"],
        alignment_assessment=outputs["alignment_assessment"],
        evidence_refs=["ev:1", "ev:2", "ev:3"],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-prg-001",
    )
    readiness = build_governance_readiness(
        eval_result=eval_result,
        evidence_complete=True,
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-prg-001",
    )
    assert readiness["readiness_status"] == "candidate_only"

    assert check_recommendation_authority_boundary(recommendation_artifacts=[{"artifact_id": "a1", "used_for": "policy_decision"}]) == [
        "recommendation_authority_leakage:a1"
    ]
    assert check_adoption_candidate_integrity(candidate_set=outputs["candidate_set"]) == []
    assert check_trust_posture_snapshot_integrity(trust_posture_snapshot={"evidence_refs": ["signal:s1"]}) == []

    debt = build_recommendation_rework_debt(
        recommendation_history=[
            {"recommendation_key": "k1"},
            {"recommendation_key": "k1"},
            {"recommendation_key": "k2"},
        ],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-prg-001",
    )
    assert debt["debt_status"] == "elevated"

    assert check_governance_to_rdx_integrity(
        prg_handoff={"authority_scope": "recommendation_only"},
        rdx_input={"authority_scope": "recommendation_input"},
    ) == []
    assert check_pattern_report_integrity(report=outputs["pattern_report"]) == []

    rt1 = run_prg_boundary_redteam(
        fixtures=[
            {"fixture_id": "RT1-AUTH-LEAK", "should_fail_closed": True, "observed": "accepted"},
            {"fixture_id": "RT1-BLOCKED", "should_fail_closed": True, "observed": "blocked"},
        ]
    )
    rt2 = run_prg_semantic_redteam(
        fixtures=[
            {"fixture_id": "RT2-PRIORITY-INVERSION", "semantic_risk": True, "observed": "accepted"},
            {"fixture_id": "RT2-BLOCKED", "semantic_risk": True, "observed": "blocked"},
        ]
    )
    assert [row["fixture_id"] for row in rt1] == ["RT1-AUTH-LEAK"]
    assert [row["fixture_id"] for row in rt2] == ["RT2-PRIORITY-INVERSION"]

    conflict = build_governance_conflict_record(
        conflict_codes=["RT1-AUTH-LEAK", "RT2-PRIORITY-INVERSION"],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-prg-001",
    )
    assert conflict["severity"] == "high"

    effectiveness = build_governance_effectiveness(
        outcomes=[
            {"trust_improved": True, "drift_reduced": True, "alignment_improved": True},
            {"trust_improved": True, "drift_reduced": False, "alignment_improved": True},
            {"trust_improved": False, "drift_reduced": True, "alignment_improved": True},
        ],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-prg-001",
    )
    assert effectiveness["value_status"] == "improving"

    bundle = build_governance_bundle(
        artifact_refs=[
            f"evaluation_pattern_report:{outputs['pattern_report']['report_id']}",
            f"prioritized_adoption_candidate_set:{outputs['candidate_set']['candidate_set_id']}",
            f"prg_governance_eval_result:{eval_result['eval_id']}",
        ],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-prg-001",
    )
    assert bundle["artifact_type"] == "prg_governance_bundle"

    with pytest.raises(PRGHardeningError, match="effectiveness_outcomes_required"):
        build_governance_effectiveness(outcomes=[], created_at="2026-04-13T00:00:00Z", trace_id="trace-prg-001")

    with pytest.raises(PRGHardeningError, match="governance_inputs_insufficient"):
        run_governance_recommendation_engine(
            program_brief=_program_brief(),
            roadmap_signal_bundle={"missing_eval_coverage": [], "override_hotspots": []},
            evaluation_patterns=[],
            created_at="2026-04-13T00:00:00Z",
            trace_id="trace-prg-001",
        )
