from spectrum_systems.opx.runtime import OPX_004_MANDATORY_TEST_COVERAGE, run_opx_004_roadmap


def test_opx_004_serial_build_covers_durability_and_self_correction_slices():
    summary = run_opx_004_roadmap()

    # 1-3 replay/drift/eval expansion
    assert summary["replay"]["no_silent_skip"] is True
    assert len(summary["replay"]["runs"]) == 6
    assert summary["drift"]["deterministic"] is True
    assert summary["eval_expansion"]["authoritative"] is False

    # 4 lifecycle bundle
    assert summary["policy_lifecycle"]["valid"] is True
    assert summary["judgment_lifecycle"]["stale_or_retired_blocked"]
    assert summary["override_lifecycle"]["escalation_triggered"] is True
    assert summary["context_lifecycle"]["blocked_by"] == "TPA"
    assert summary["artifact_aging"]["stale"]

    # 5-7 consistency/calibration/volatility/alignment/promotion/failure routing
    assert summary["consistency"]["deterministic_check"] is True
    assert summary["calibration"]["bucketed_brier"] == 0.12
    assert summary["volatility"]["fragile_cases"] == ["policy-vs-context-edge"]
    assert summary["alignment_drift"]["detected"] is True
    assert summary["replay_regression_gate"]["promotion_status"] == "blocked"
    assert summary["failure_routing"]["route"]["schema_mismatch"] == "FRE"
    assert summary["failure_patterns"]["feeds_prg"] is True

    # 8-11 red-team/maintain/coherence/cross-module
    assert summary["redteam"]["bounded"] is True
    assert summary["maintain"]["deterministic_output_hash"] == "019467080b1621b3"
    assert summary["evidence_coherence"]["status"] == "fail"
    assert summary["cross_module_consistency"]["status"] == "drift_detected"

    # 12-14 health/rollback/audit
    assert summary["system_health_index"]["authoritative"] is False
    assert summary["rollback"]["owner_path"] == ["TLC", "CDE", "SEL"]
    assert summary["rollback"]["auto_rollback"] is False
    assert len(summary["audit_log"]["events"]) == 3
    assert summary["audit_log"]["query_faq"][0]["module"] == "faq"

    # 15-18 prediction/operator/feedback/invariants
    assert summary["anomaly_prediction"]["recommendation_grade"] is True
    assert summary["anomaly_prediction"]["authoritative"] is False
    assert summary["operator_drift"]["override_creep_delta"] > 0
    assert summary["feedback_loop_closure"]["closed_loop"] is True
    assert all(summary["invariants"].values())

    # 19-23 strategic+external+multi-actor+self-improvement
    assert summary["policy_outcome_simulation"]["authoritative"] is False
    assert summary["strategic_plan"]["authoritative"] is False
    assert summary["tradeoff_model"]["authoritative"] is False
    assert summary["external_feedback_ingestion"]["eval_expansion_delta"] == 2
    assert summary["multi_actor_model"]["deterministic"] is True
    assert summary["self_improvement_governance"]["self_apply_allowed"] is False

    # 24
    assert summary["non_duplication"] is True
    assert len(OPX_004_MANDATORY_TEST_COVERAGE) == 24
