from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.decision_quality_control import (
    evaluate_calibration,
    evaluate_decision_quality_budget,
    evaluate_judgment_promotion_gate,
)


def test_decision_quality_budget_deterministic_and_exhaustion() -> None:
    kwargs = {
        "decision_quality_budget_id": "DQB-AAAAAAAAAAAA",
        "scope": {"artifact_family": "judgment", "route": "promotion", "policy": "lifecycle", "judgment_class": "required"},
        "failure_taxonomy_records": [{"severity": "critical"}],
        "override_governance_records": [{"override_state": "active"}],
        "eval_results": [{"decision": "allow", "result_status": "fail"}],
        "promotion_consistency_records": [{"promotion_state": "deny"}],
        "drift_signals": [{"drift_detected": True}],
        "budget_thresholds": {"safe": 0.05, "warning": 0.1, "freeze_candidate": 0.2, "block": 0.3},
        "created_at": "2026-04-04T00:00:00Z",
        "trace_id": "trace-test",
    }
    first = evaluate_decision_quality_budget(**kwargs)
    second = evaluate_decision_quality_budget(**kwargs)
    assert first == second
    assert first["budget_exhausted"] is True
    assert first["severity"] == "block"


def test_decision_quality_budget_missing_inputs_fail_closed() -> None:
    with pytest.raises(ValueError):
        evaluate_decision_quality_budget(
            decision_quality_budget_id="DQB-AAAAAAAAAAAA",
            scope={"artifact_family": "judgment", "route": "promotion", "policy": "lifecycle", "judgment_class": "required"},
            failure_taxonomy_records=[],
            override_governance_records=[],
            eval_results=[],
            promotion_consistency_records=[],
            drift_signals=[],
            budget_thresholds={"safe": 0.05, "warning": 0.1, "freeze_candidate": 0.2, "block": 0.3},
            created_at="2026-04-04T00:00:00Z",
            trace_id="trace-test",
        )


def test_calibration_degradation_is_slower_for_improvement() -> None:
    degraded = evaluate_calibration(
        calibration_id="CAL-AAAAAAAAAAAA",
        scope={"artifact_family": "judgment", "route": "promotion", "policy": "lifecycle", "judgment_class": "required"},
        judgment_records=[{"confidence": 0.95}, {"confidence": 0.9}],
        eval_results=[{"result_status": "fail"}, {"result_status": "fail"}],
        post_hoc_correctness_signals=[{"correctness": "incorrect"}, {"correctness": "incorrect"}],
        prior_calibration_assessment={"calibration_error": 0.1},
        sample_window_size=5,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-test",
    )
    improving = evaluate_calibration(
        calibration_id="CAL-BBBBBBBBBBBB",
        scope={"artifact_family": "judgment", "route": "promotion", "policy": "lifecycle", "judgment_class": "required"},
        judgment_records=[{"confidence": 0.5}, {"confidence": 0.6}],
        eval_results=[{"result_status": "pass"}, {"result_status": "pass"}],
        post_hoc_correctness_signals=[{"correctness": "correct"}, {"correctness": "correct"}],
        prior_calibration_assessment=degraded,
        sample_window_size=5,
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-test",
    )
    assert degraded["drift_delta"] > 0
    assert improving["drift_delta"] < 0
    assert abs(improving["drift_delta"]) < abs(degraded["drift_delta"])


def test_promotion_gate_denies_without_coverage_or_calibration() -> None:
    gate = evaluate_judgment_promotion_gate(
        source_batch_id="BATCH-I",
        required_judgment_refs=[],
        decision_quality_budget_status={"budget_exhausted": False, "severity": "none"},
        calibration_assessment_record=None,
        promotion_consistency_record={"runs_considered": 3, "promotion_state": "allow"},
        supporting_artifact_refs=["promotion_consistency_record:PCR-AAAAAAAAAAAA"],
        created_at="2026-04-04T00:00:00Z",
        trace_id="trace-test",
    )
    assert gate["promotion_decision"] == "deny"
    assert "required_judgment_refs_missing" in gate["reason_codes"]
    assert "calibration_assessment_record_missing" in gate["reason_codes"]
