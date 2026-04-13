from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.map_projection_hardening import (
    MAPProjectionError,
    build_map_projection_bundle,
    build_map_projection_conflict_record,
    build_map_projection_debt_record,
    build_map_projection_effectiveness,
    build_map_projection_readiness,
    build_map_projection_record,
    enforce_map_boundary,
    evaluate_map_projection,
    run_map_boundary_redteam,
    run_map_semantic_redteam,
    validate_map_projection_replay,
)


def _source_bundle() -> dict:
    return load_example("review_projection_bundle_artifact")


def test_map_contract_examples_validate() -> None:
    for name in (
        "map_projection_record",
        "map_projection_eval_result",
        "map_projection_readiness_record",
        "map_projection_conflict_record",
        "map_projection_bundle",
        "map_projection_effectiveness_record",
        "map_projection_debt_record",
    ):
        validate_artifact(load_example(name), name)


def test_map_01_to_09_foundation_pipeline() -> None:
    source = _source_bundle()
    boundary_fails = enforce_map_boundary(
        upstream_artifact_type="review_projection_bundle_artifact",
        claimed_actions=["format_projection"],
        emitted_artifact_types=["map_projection_record", "map_projection_eval_result"],
    )
    assert boundary_fails == []

    record = build_map_projection_record(
        review_projection_bundle_artifact=source,
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-map-001",
    )
    eval_result = evaluate_map_projection(
        source_bundle=source,
        projection_record=record,
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-map-001",
    )
    assert eval_result["evaluation_status"] == "pass"

    replay_ok, replay_fails = validate_map_projection_replay(
        prior_input=source,
        replay_input=copy.deepcopy(source),
        prior_projection=record,
        replay_projection=copy.deepcopy(record),
    )
    assert replay_ok is True
    assert replay_fails == []

    readiness = build_map_projection_readiness(
        eval_result=eval_result,
        evidence_refs=["ev:1", "ev:2"],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-map-001",
    )
    assert readiness["readiness_status"] == "candidate_only"

    conflict = build_map_projection_conflict_record(
        eval_result=eval_result,
        redteam_findings=[],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-map-001",
    )
    debt = build_map_projection_debt_record(
        incidents=[{"incident_code": "field_loss"}, {"incident_code": "field_loss"}],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-map-001",
    )
    effectiveness = build_map_projection_effectiveness(
        outcomes=[
            {"usability_improved": True, "semantic_distortion_detected": False, "authority_confusion_detected": False},
            {"usability_improved": True, "semantic_distortion_detected": False, "authority_confusion_detected": False},
            {"usability_improved": False, "semantic_distortion_detected": True, "authority_confusion_detected": False},
        ],
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-map-001",
    )
    bundle = build_map_projection_bundle(
        projection_record=record,
        eval_result=eval_result,
        readiness_record=readiness,
        conflict_record=conflict,
        debt_record=debt,
        effectiveness_record=effectiveness,
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-map-001",
    )
    assert bundle["artifact_type"] == "map_projection_bundle"


def test_map_08a_08b_08d_08e_detectors_fail_closed() -> None:
    source = _source_bundle()
    record = build_map_projection_record(
        review_projection_bundle_artifact=source,
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-map-001",
    )

    tampered = copy.deepcopy(record)
    tampered["status_markers"]["blocker_present"] = False
    tampered["projected_payload"]["roadmap_projection_ref"] = "rrp-ffffffffffffffff"
    tampered["non_authority_assertions"] = ["looks_authoritative"]

    result = evaluate_map_projection(
        source_bundle=source,
        projection_record=tampered,
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-map-001",
    )
    assert result["evaluation_status"] == "fail"
    assert "status_washing_detector" in result["fail_reasons"]
    assert "required_field_preservation" in result["fail_reasons"]
    assert "projection_to_governance_integrity" in result["fail_reasons"]


def test_map_rt1_fx1_and_rt2_fx2_exploits_become_regressions() -> None:
    rt1 = run_map_boundary_redteam(
        fixtures=[
            {"fixture_id": "RT1-AUTHORITY-LOOKING", "should_fail_closed": True, "observed": "accepted"},
            {"fixture_id": "RT1-BLOCKED", "should_fail_closed": True, "observed": "blocked"},
        ]
    )
    rt2 = run_map_semantic_redteam(
        fixtures=[
            {"fixture_id": "RT2-STATUS-WASH", "semantic_risk": True, "observed": "accepted"},
            {"fixture_id": "RT2-BLOCKED", "semantic_risk": True, "observed": "blocked"},
        ]
    )
    assert [f["fixture_id"] for f in rt1] == ["RT1-AUTHORITY-LOOKING"]
    assert [f["fixture_id"] for f in rt2] == ["RT2-STATUS-WASH"]

    source = _source_bundle()
    source_without_roadmap = copy.deepcopy(source)
    source_without_roadmap.pop("roadmap_projection", None)
    with pytest.raises(MAPProjectionError, match="required_projection_sections_missing"):
        build_map_projection_record(
            review_projection_bundle_artifact=source_without_roadmap,
            created_at="2026-04-13T00:00:00Z",
            trace_id="trace-map-001",
        )


def test_map_boundary_fencing_blocks_owner_creep() -> None:
    fails = enforce_map_boundary(
        upstream_artifact_type="review_integration_packet_artifact",
        claimed_actions=["interpret_review:packet", "issue_policy:update"],
        emitted_artifact_types=["closure_decision_artifact"],
    )
    assert "invalid_upstream_artifact:review_integration_packet_artifact" in fails
    assert "forbidden_owner_overlap:interpret_review:packet" in fails
    assert "forbidden_owner_overlap:issue_policy:update" in fails
    assert "invalid_downstream_artifact:closure_decision_artifact" in fails


def test_map_replay_detects_drift() -> None:
    source = _source_bundle()
    record = build_map_projection_record(
        review_projection_bundle_artifact=source,
        created_at="2026-04-13T00:00:00Z",
        trace_id="trace-map-001",
    )
    drifted = copy.deepcopy(record)
    drifted["projected_payload"]["readiness_item_count"] += 1

    ok, fails = validate_map_projection_replay(
        prior_input=source,
        replay_input=source,
        prior_projection=record,
        replay_projection=drifted,
    )
    assert ok is False
    assert fails == ["projection_replay_output_drift"]
