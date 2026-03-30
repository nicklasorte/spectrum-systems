from __future__ import annotations

import pytest

from spectrum_systems.orchestration.fix_plan import FixPlanError, build_fix_plan_artifact


def _manifest() -> dict:
    return {
        "cycle_id": "cycle-test",
        "current_state": "blocked",
        "updated_at": "2026-03-30T00:00:00Z",
    }


def _decision() -> dict:
    return {
        "decision_id": "d" * 64,
        "current_state": "blocked",
    }


def _remediation(remediation_class: str) -> dict:
    return {
        "remediation_id": "a" * 64,
        "cycle_id": "cycle-test",
        "decision_id": "d" * 64,
        "current_state": "blocked",
        "normalized_category": "blocking_drift_finding",
        "remediation_class": remediation_class,
        "blocking": True,
        "evidence_refs": ["drift_detection_result_path:exceeds_threshold"],
        "policy_id": "DRIFT_REMEDIATION_POLICY",
        "policy_version": "1.0.0",
        "policy_hash": "b" * 64,
    }


@pytest.mark.parametrize(
    "remediation_class",
    [
        "manifest_repair",
        "provenance_repair",
        "contract_repair",
        "roadmap_repair",
        "review_repair",
        "execution_artifact_repair",
        "governance_alignment_repair",
        "judgment_evidence_repair",
        "certification_input_repair",
    ],
)
def test_fix_plan_generation_for_each_remediation_class_family(remediation_class: str) -> None:
    artifact = build_fix_plan_artifact(manifest=_manifest(), decision=_decision(), remediation=_remediation(remediation_class))
    assert artifact["remediation_class"] == remediation_class
    assert artifact["required_actions"]
    assert artifact["validation_requirements"]
    assert artifact["completion_criteria"]


def test_deterministic_fix_plan_ids() -> None:
    first = build_fix_plan_artifact(manifest=_manifest(), decision=_decision(), remediation=_remediation("roadmap_repair"))
    second = build_fix_plan_artifact(manifest=_manifest(), decision=_decision(), remediation=_remediation("roadmap_repair"))
    assert first["fix_plan_id"] == second["fix_plan_id"]


def test_missing_inputs_fail_closed() -> None:
    bad = _remediation("roadmap_repair")
    bad.pop("policy_hash")
    with pytest.raises(FixPlanError):
        build_fix_plan_artifact(manifest=_manifest(), decision=_decision(), remediation=bad)


def test_validation_requirements_and_completion_criteria_populated_deterministically() -> None:
    artifact = build_fix_plan_artifact(manifest=_manifest(), decision=_decision(), remediation=_remediation("roadmap_repair"))
    assert artifact["validation_requirements"] == [
        "schema:drift_remediation_artifact",
        "schema:fix_plan_artifact",
        "policy:DRIFT_REMEDIATION_POLICY@1.0.0",
    ]
    assert artifact["completion_criteria"] == [
        "blocking_drift_finding resolved",
        "next_step_decision.blocking == false",
    ]
