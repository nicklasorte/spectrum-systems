from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.foundation_roadmap import (
    FoundationInputs,
    FoundationRoadmapError,
    ROADMAP_STEPS,
    build_foundation_roadmap_execution_record,
)


def _base_inputs() -> FoundationInputs:
    return FoundationInputs(
        trace_id="trace-001",
        run_id="run-001",
        governed_family="roadmap_execution_report",
        judgment_artifacts={
            "judgment_record": {"artifact_id": "jr-1"},
            "judgment_eval_result": {"artifact_id": "je-1"},
            "judgment_policy": {"artifact_id": "jp-1"},
        },
        judgment_type="promotion_judgment",
        required_eval_matrix={
            "promotion_judgment": ["evidence_coverage", "policy_alignment", "replay_consistency"],
        },
        provided_eval_types=["evidence_coverage", "policy_alignment", "replay_consistency"],
        eval_passed=True,
        policy_deviation_detected=False,
        candidate_policy_version="2.1.0-canary.1",
        active_policy_version="2.0.5",
        precedent_records=[
            {"precedent_id": "prec-001", "active": True, "artifact_family": "roadmap_execution_report"},
            {"precedent_id": "prec-002", "active": True, "artifact_family": "roadmap_execution_report"},
            {"precedent_id": "prec-003", "active": False, "artifact_family": "roadmap_execution_report"},
        ],
        policy_conflicts=[],
        budget_signals={"quality": 0.31, "latency": 0.4, "cost": 0.2, "override_pressure": 0.1, "replay_stability": 0.2},
        failure_events=[
            {"event_type": "override", "id": "f-1"},
            {"event_type": "evidence_gap", "id": "f-2"},
        ],
        certification_ready=True,
        certification_layers={
            "replay_integrity": True,
            "contract_integrity": True,
            "fail_closed": True,
            "control_enforcement": True,
        },
        signed_provenance_present=True,
        trace_complete=True,
        replay_hash_expected="abc",
        replay_hash_actual="abc",
        route_id="route-main",
        prompt_version="prompt-v7",
        policy_version="2.1.0-canary.1",
        challenger_policy_versions=["2.1.0-canary.1", "2.1.0-canary.2"],
        calibration_error=0.03,
    )


def test_build_foundation_execution_record_happy_path() -> None:
    record = build_foundation_roadmap_execution_record(_base_inputs())
    assert tuple(row["step_id"] for row in record["roadmap_steps"]) == ROADMAP_STEPS
    assert record["primary_control_decision"] == "allow"
    assert record["derived_artifacts"]["override_hotspot_report"]["override_count"] == 1
    assert record["derived_artifacts"]["evidence_gap_hotspot_report"]["evidence_gap_count"] == 1


def test_missing_required_judgment_artifact_fails_closed() -> None:
    base = _base_inputs()
    broken = dict(base.judgment_artifacts)
    broken.pop("judgment_eval_result")
    with pytest.raises(FoundationRoadmapError, match="missing required judgment artifact"):
        build_foundation_roadmap_execution_record(FoundationInputs(**{**base.__dict__, "judgment_artifacts": broken}))


def test_missing_required_eval_type_fails_closed() -> None:
    base = _base_inputs()
    with pytest.raises(FoundationRoadmapError, match="missing required judgment eval types"):
        build_foundation_roadmap_execution_record(FoundationInputs(**{**base.__dict__, "provided_eval_types": ["evidence_coverage"]}))


def test_certification_trace_and_signature_enforce_block() -> None:
    base = _base_inputs()
    record = build_foundation_roadmap_execution_record(
        FoundationInputs(
            **{
                **base.__dict__,
                "certification_ready": False,
                "trace_complete": False,
                "signed_provenance_present": False,
            }
        )
    )
    assert record["primary_control_decision"] == "block"


def test_conflict_and_replay_mismatch_enforce_freeze() -> None:
    base = _base_inputs()
    record = build_foundation_roadmap_execution_record(
        FoundationInputs(
            **{
                **base.__dict__,
                "policy_conflicts": [{"severity": "critical", "policy_ids": ["a", "b"]}],
                "replay_hash_actual": "mismatch",
            }
        )
    )
    assert record["primary_control_decision"] == "freeze"


def test_certification_layer_expansion_is_required() -> None:
    base = _base_inputs()
    with pytest.raises(FoundationRoadmapError, match="certification layer expansion incomplete"):
        build_foundation_roadmap_execution_record(
            FoundationInputs(
                **{
                    **base.__dict__,
                    "certification_layers": {
                        "replay_integrity": True,
                        "contract_integrity": True,
                        "fail_closed": False,
                        "control_enforcement": True,
                    },
                }
            )
        )
