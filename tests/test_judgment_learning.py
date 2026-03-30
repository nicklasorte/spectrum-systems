from __future__ import annotations

from copy import deepcopy

import pytest

from spectrum_systems.modules.runtime.judgment_eval_runner import run_judgment_evals
from spectrum_systems.modules.runtime.judgment_learning import (
    JudgmentLearningError,
    build_judgment_outcome_label,
    run_judgment_calibration,
    run_judgment_drift_signal,
)


def _judgment_record() -> dict:
    return {
        "artifact_type": "judgment_record",
        "artifact_id": "judgment-record-cycle-0001",
        "artifact_version": "1.1.0",
        "schema_version": "1.1.0",
        "standards_version": "1.0.94",
        "judgment_type": "artifact_release_readiness",
        "selected_outcome": "approve",
        "cycle_id": "cycle-0001",
        "policy_ref": "contracts/examples/judgment_policy.json",
        "claims_considered": [
            {
                "claim_id": "claim-001",
                "claim_text": "claim",
                "is_material": True,
                "supported_by_evidence_ids": ["evidence-1"],
            }
        ],
        "evidence_refs": ["evidence-1"],
        "rules_applied": ["approve-high-quality"],
        "alternatives_considered": [],
        "uncertainties": [],
        "conditions_under_which_decision_changes": ["inputs change"],
        "precedent_retrieval": {
            "method_id": "exact-field-overlap",
            "method_version": "1.0.0",
            "threshold": 0.5,
            "top_k": 3,
            "similarity_basis": "matching scope_tag and risk_level fields",
            "scored_precedents": [],
        },
        "context_fingerprint": {"scope_tag": "autonomous_cycle", "risk_level": "low", "environment": "prod"},
        "rationale_summary": "ready",
        "created_at": "2026-03-30T00:00:00Z",
        "environment": "prod",
        "confidence_score": 0.9,
    }


def _application_record() -> dict:
    return {
        "artifact_type": "judgment_application_record",
        "artifact_id": "judgment-application-cycle-0001",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.94",
        "judgment_record_ref": "judgment_record::cycle-0001",
        "selected_policy_ref": "contracts/examples/judgment_policy.json",
        "matched_policy_refs": ["contracts/examples/judgment_policy.json"],
        "conflicts": [],
        "deviations": [],
        "final_outcome": "approve",
        "created_at": "2026-03-30T00:00:00Z",
    }


def _policy(*, require_reference: bool) -> dict:
    return {
        "judgment_eval_requirements": {
            "evidence_coverage": {"minimum_score": 1.0, "fail_closed_on_missing_material": True},
            "replay_consistency": {"required": True, "require_reference_artifact": require_reference},
        }
    }


def test_replay_reference_mismatch_fails_closed() -> None:
    replay_reference = {
        "artifact_type": "replay_result",
        "expected_outcome": "block",
        "replay_reference": {"fingerprint_hash": "a" * 64},
    }
    result = run_judgment_evals(
        cycle_id="cycle-0001",
        created_at="2026-03-30T00:00:00Z",
        judgment_record=_judgment_record(),
        application_record=_application_record(),
        policy=_policy(require_reference=True),
        replay_reference=replay_reference,
        replay_reference_source="contracts/examples/replay_result.json",
    )
    replay_eval = next(item for item in result["eval_results"] if item["eval_type"] == "replay_consistency")
    assert replay_eval["passed"] is False
    assert replay_eval["details"]["comparison_result"] == "mismatch"


def test_labeled_outcome_ingestion_builds_valid_artifact() -> None:
    artifact = build_judgment_outcome_label(
        artifact_id="label-1",
        judgment_id="judgment-record-cycle-0001",
        observed_outcome="approve",
        expected_outcome="approve",
        correctness=True,
        source="human_review",
        timestamp="2026-03-30T00:00:00Z",
    )
    assert artifact["artifact_type"] == "judgment_outcome_label"


def test_calibration_metrics_are_deterministic() -> None:
    labels = [
        build_judgment_outcome_label(
            artifact_id="label-1",
            judgment_id="judgment-record-cycle-0001",
            observed_outcome="approve",
            expected_outcome="approve",
            correctness=True,
            source="human_review",
            timestamp="2026-03-30T00:00:00Z",
        ),
        build_judgment_outcome_label(
            artifact_id="label-2",
            judgment_id="judgment-record-cycle-0002",
            observed_outcome="block",
            expected_outcome="approve",
            correctness=False,
            source="downstream_signal",
            timestamp="2026-03-30T00:01:00Z",
        ),
    ]
    records = {
        "judgment-record-cycle-0001": _judgment_record(),
        "judgment-record-cycle-0002": _judgment_record() | {"artifact_id": "judgment-record-cycle-0002", "selected_outcome": "block"},
    }
    a = run_judgment_calibration(
        artifact_id="calibration-a",
        labels=labels,
        judgment_records_by_id=deepcopy(records),
        created_at="2026-03-30T00:02:00Z",
    )
    b = run_judgment_calibration(
        artifact_id="calibration-a",
        labels=labels,
        judgment_records_by_id=deepcopy(records),
        created_at="2026-03-30T00:02:00Z",
    )
    assert a == b


def test_drift_signal_computation_is_deterministic() -> None:
    baseline = {
        "artifact_type": "judgment_calibration_result",
        "artifact_id": "baseline",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.94",
        "grouping_keys": ["judgment_type", "policy_version", "environment"],
        "group_metrics": [
            {
                "judgment_type": "artifact_release_readiness",
                "policy_version": "1.1.0",
                "environment": "prod",
                "sample_size": 10,
                "accuracy": 0.9,
                "mean_confidence": 0.9,
                "expected_calibration_error": 0.02,
                "calibration_delta": 0.0,
                "confidence_signal": "well_calibrated",
                "ece_bins": [{"bin": "0.9-1.0", "count": 10, "mean_confidence": 0.9, "mean_accuracy": 0.9, "absolute_gap": 0.0}],
                "outcome_distribution": {"approve": 9, "block": 1},
                "error_rate": 0.1,
            }
        ],
        "formulas": {
            "accuracy": "correct_count / sample_size",
            "expected_calibration_error": "sum_over_bins((bin_count / total_count) * abs(bin_accuracy - bin_mean_confidence))",
            "calibration_delta": "mean_confidence - accuracy",
        },
        "created_at": "2026-03-30T00:02:00Z",
    }
    current = deepcopy(baseline)
    current["artifact_id"] = "current"
    current["group_metrics"][0]["outcome_distribution"] = {"approve": 6, "block": 4}
    current["group_metrics"][0]["error_rate"] = 0.3
    current["group_metrics"][0]["expected_calibration_error"] = 0.12

    a = run_judgment_drift_signal(artifact_id="drift-1", baseline=baseline, current=current, created_at="2026-03-30T00:03:00Z")
    b = run_judgment_drift_signal(artifact_id="drift-1", baseline=baseline, current=current, created_at="2026-03-30T00:03:00Z")
    assert a == b


def test_missing_label_data_fails_closed() -> None:
    with pytest.raises(JudgmentLearningError, match="at least one judgment_outcome_label"):
        run_judgment_calibration(
            artifact_id="calibration-empty",
            labels=[],
            judgment_records_by_id={},
            created_at="2026-03-30T00:03:00Z",
        )


def test_missing_replay_reference_when_required_is_blocked() -> None:
    result = run_judgment_evals(
        cycle_id="cycle-0001",
        created_at="2026-03-30T00:00:00Z",
        judgment_record=_judgment_record(),
        application_record=_application_record(),
        policy=_policy(require_reference=True),
        replay_reference=None,
    )
    replay_eval = next(item for item in result["eval_results"] if item["eval_type"] == "replay_consistency")
    assert replay_eval["passed"] is False
    assert replay_eval["details"]["mismatch_reason"] == "required_replay_reference_missing"
