"""NT-07..09: Artifact tier drift monitor — validation, red team, fix."""

from __future__ import annotations

from spectrum_systems.modules.observability.artifact_tier_drift import (
    detect_tier_drift,
    validate_transitive_promotion_evidence_tiers,
)


def _eval_evidence(artifact_id="evl-1"):
    return {
        "artifact_id": artifact_id,
        "artifact_type": "eval_slice_summary",
    }


def _report_artifact(artifact_id="rep-1"):
    return {
        "artifact_id": artifact_id,
        "artifact_type": "dashboard_report",
        "artifact_path": "outputs/reports/dashboard.json",
    }


def _test_temp_artifact(artifact_id="tt-1"):
    return {
        "artifact_id": artifact_id,
        "artifact_type": "test_fixture",
        "artifact_path": "tests/fixtures/blob.json",
    }


def _generated_cache(artifact_id="gc-1"):
    return {
        "artifact_id": artifact_id,
        "artifact_type": "trust_graph_snapshot",
        "artifact_path": "outputs/snapshots/trust_graph.json",
    }


def test_canonical_promotion_evidence_with_evidence_transitive_passes():
    res = validate_transitive_promotion_evidence_tiers(
        [
            {"artifact_id": "lpb-1", "artifact_type": "loop_proof_bundle"},
        ],
        referenced_evidence_items=[_eval_evidence()],
        validation_id="atd-1",
    )
    assert res["decision"] == "allow"
    assert res["reason_code"] == "TIER_DRIFT_OK"


def test_report_artifact_as_top_evidence_blocks():
    """Red team: a dashboard report must not be top-level promotion evidence."""
    res = validate_transitive_promotion_evidence_tiers(
        [_report_artifact()],
        validation_id="atd-2",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_DRIFT_LOW_TO_EVIDENCE_UNAUTHORIZED"


def test_test_temp_referenced_through_canonical_wrapper_still_blocks():
    """Indirect reference laundering: wrapping a test_temp item in a
    loop_proof_bundle reference does not make it admissible."""
    res = validate_transitive_promotion_evidence_tiers(
        [{"artifact_id": "lpb-1", "artifact_type": "loop_proof_bundle"}],
        referenced_evidence_items=[_test_temp_artifact()],
        validation_id="atd-3",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_DRIFT_INDIRECT_EVIDENCE_LAUNDERING"


def test_generated_cache_referenced_through_wrapper_blocks():
    res = validate_transitive_promotion_evidence_tiers(
        [{"artifact_id": "lpb-1", "artifact_type": "loop_proof_bundle"}],
        referenced_evidence_items=[_generated_cache()],
        validation_id="atd-4",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_DRIFT_INDIRECT_EVIDENCE_LAUNDERING"


def test_missing_tier_metadata_is_blocked_not_inferred():
    """Red team: artifact with no tier, no path, no type."""
    res = validate_transitive_promotion_evidence_tiers(
        [{"artifact_id": "anon-1"}],
        validation_id="atd-5",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_DRIFT_METADATA_MISSING"


def test_inferred_evidence_tier_blocks_when_no_explicit_metadata():
    """A bare artifact_id with no metadata at all → metadata-missing.
    Even if classified by the policy default, that classification is not
    silently treated as evidence."""
    res = validate_transitive_promotion_evidence_tiers(
        [{"artifact_id": "anon-2"}],
        validation_id="atd-6",
    )
    assert res["decision"] == "block"


def test_tier_drift_detected_between_two_runs():
    prev = {
        "items": [
            {"artifact_id": "evl-1", "tier": "evidence"},
            {"artifact_id": "lpb-1", "tier": "canonical"},
        ]
    }
    curr = {
        "items": [
            {"artifact_id": "evl-1", "tier": "report"},  # tier drift
            {"artifact_id": "lpb-1", "tier": "canonical"},
        ]
    }
    res = detect_tier_drift(prev, curr)
    assert res["drift_status"] == "drift"
    assert res["reason_code"] == "TIER_DRIFT_CHANGED_BETWEEN_RUNS"
    drifted_ids = {d["artifact_id"] for d in res["drifted"]}
    assert "evl-1" in drifted_ids


def test_tier_drift_no_change_is_ok():
    prev = {"items": [{"artifact_id": "evl-1", "tier": "evidence"}]}
    curr = {"items": [{"artifact_id": "evl-1", "tier": "evidence"}]}
    res = detect_tier_drift(prev, curr)
    assert res["drift_status"] == "ok"
    assert res["drifted"] == []


def test_tier_drift_missing_baseline_is_unknown_not_pass():
    res = detect_tier_drift(None, {"items": []})
    assert res["drift_status"] == "unknown_baseline"
    assert res["blocking_reasons"]
