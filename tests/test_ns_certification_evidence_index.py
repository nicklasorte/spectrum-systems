"""NS-10..12: Certification evidence index — completeness + red-team."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.certification_evidence_index import (
    CertificationEvidenceIndexError,
    build_certification_evidence_index,
)


def _full_evidence() -> dict:
    return dict(
        index_id="cei-1",
        trace_id="tCEI",
        eval_summary={"artifact_id": "evl-1", "status": "healthy"},
        lineage_summary={"artifact_id": "lin-1", "status": "healthy"},
        replay_summary={"artifact_id": "rep-1", "status": "healthy"},
        control_decision={"decision_id": "cde-1", "decision": "allow"},
        enforcement_action={
            "enforcement_id": "sel-1",
            "enforcement_action": "allow_execution",
        },
        authority_shape_preflight={"artifact_id": "asp-1", "status": "pass"},
        registry_validation={"artifact_id": "reg-1", "status": "pass", "violations": []},
        artifact_tier_validation={
            "validation_id": "tier-1",
            "decision": "allow",
            "reason_code": "TIER_OK",
        },
    )


def test_full_evidence_yields_ready_status() -> None:
    idx = build_certification_evidence_index(**_full_evidence())
    assert idx["status"] == "ready"
    assert idx["blocking_reason_canonical"] == "CERT_OK"
    assert idx["missing_references"] == []
    refs = idx["references"]
    assert refs["eval_summary_ref"] == "evl-1"
    assert refs["lineage_summary_ref"] == "lin-1"
    assert refs["replay_summary_ref"] == "rep-1"
    assert refs["control_decision_ref"] == "cde-1"
    assert refs["enforcement_action_ref"] == "sel-1"
    assert refs["authority_shape_preflight_ref"] == "asp-1"
    assert refs["registry_validation_ref"] == "reg-1"
    assert refs["artifact_tier_validation_ref"] == "tier-1"
    assert "ready" in idx["human_readable"]


# ---- NS-11: red team — required evidence missing/corrupt blocks ----


def test_red_team_missing_eval_blocks() -> None:
    ev = _full_evidence()
    ev["eval_summary"] = None
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "blocked"
    assert idx["blocking_reason_canonical"] in {
        "CERTIFICATION_GAP",
        "EVAL_FAILURE",
        "MISSING_ARTIFACT",
    }
    assert "eval_summary_ref" in idx["missing_references"]


def test_red_team_corrupt_eval_status_blocks() -> None:
    ev = _full_evidence()
    ev["eval_summary"] = {"artifact_id": "evl-bad", "status": "blocked"}
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "blocked"
    assert "CERT_MISSING_EVAL_PASS" in idx["blocking_detail_codes"]


def test_red_team_missing_lineage_blocks() -> None:
    ev = _full_evidence()
    ev["lineage_summary"] = None
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "blocked"
    assert "lineage_summary_ref" in idx["missing_references"]


def test_red_team_missing_replay_blocks() -> None:
    ev = _full_evidence()
    ev["replay_summary"] = None
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "blocked"
    assert "replay_summary_ref" in idx["missing_references"]


def test_red_team_missing_control_decision_blocks() -> None:
    ev = _full_evidence()
    ev["control_decision"] = None
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "blocked"
    assert "control_decision_ref" in idx["missing_references"]


def test_red_team_freeze_control_decision_yields_frozen_status() -> None:
    ev = _full_evidence()
    ev["control_decision"] = {"decision_id": "cde-frz", "decision": "freeze"}
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "frozen"


def test_red_team_missing_enforcement_blocks_when_state_changing() -> None:
    ev = _full_evidence()
    ev["enforcement_action"] = None
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "blocked"
    assert "enforcement_action_ref" in idx["missing_references"]


def test_red_team_missing_enforcement_does_not_block_for_non_state_changing() -> None:
    ev = _full_evidence()
    ev["enforcement_action"] = None
    ev["state_changing"] = False
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "ready"


def test_red_team_missing_authority_shape_preflight_blocks() -> None:
    ev = _full_evidence()
    ev["authority_shape_preflight"] = None
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "blocked"
    assert "authority_shape_preflight_ref" in idx["missing_references"]


def test_red_team_failing_authority_shape_preflight_blocks() -> None:
    ev = _full_evidence()
    ev["authority_shape_preflight"] = {"artifact_id": "asp-bad", "status": "fail"}
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "blocked"
    assert "CERT_MISSING_AUTHORITY_SHAPE_PREFLIGHT" in idx["blocking_detail_codes"]


def test_red_team_missing_registry_validation_blocks() -> None:
    ev = _full_evidence()
    ev["registry_validation"] = None
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "blocked"
    assert "registry_validation_ref" in idx["missing_references"]


def test_red_team_registry_violations_block() -> None:
    ev = _full_evidence()
    ev["registry_validation"] = {
        "artifact_id": "reg-bad",
        "status": "fail",
        "violations": ["NX-02: ..."],
    }
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "blocked"
    assert "CERT_REGISTRY_VIOLATION_PRESENT" in idx["blocking_detail_codes"]


def test_red_team_missing_artifact_tier_validation_blocks() -> None:
    ev = _full_evidence()
    ev["artifact_tier_validation"] = None
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "blocked"
    assert "artifact_tier_validation_ref" in idx["missing_references"]


def test_red_team_failing_artifact_tier_validation_blocks() -> None:
    ev = _full_evidence()
    ev["artifact_tier_validation"] = {
        "validation_id": "tier-bad",
        "decision": "block",
        "reason_code": "TIER_TEST_TEMP_AS_EVIDENCE",
    }
    idx = build_certification_evidence_index(**ev)
    assert idx["status"] == "blocked"


def test_index_id_required() -> None:
    ev = _full_evidence()
    ev["index_id"] = ""
    with pytest.raises(CertificationEvidenceIndexError):
        build_certification_evidence_index(**ev)


def test_index_does_not_embed_full_evidence_payload() -> None:
    """NS-10: the index must hold references only, not duplicates of the
    underlying artifacts."""
    ev = _full_evidence()
    ev["eval_summary"] = {
        "artifact_id": "evl-1",
        "status": "healthy",
        "huge_payload": ["x"] * 10000,  # would be wasteful to embed
    }
    idx = build_certification_evidence_index(**ev)
    assert "huge_payload" not in str(idx["references"])
    # the human_readable summary is a compact one-page string
    assert len(idx["human_readable"]) < 4000
