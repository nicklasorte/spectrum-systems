"""NT-07..09: Artifact tier drift monitor + tier escape red team + fix.

Validates:
  - tier drift between proof runs is detected
  - report/test_temp/generated_cache cannot satisfy evidence (direct)
  - indirect reference laundering through a canonical wrapper is blocked
  - missing tier metadata is surfaced
  - artifact moving from low-trust → evidence is blocked unless overridden
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.observability.artifact_tier_audit import (
    CANONICAL_TIER_VALIDATION_REASON_CODES,
    LOW_TRUST_TIERS,
    audit_artifacts,
    audit_tier_drift,
    classify_artifact,
    load_artifact_tier_policy,
    validate_promotion_evidence_tiers,
    validate_transitive_evidence_tiers,
)


@pytest.fixture(scope="module")
def policy() -> dict:
    return load_artifact_tier_policy()


def test_low_trust_tiers_finite() -> None:
    assert set(LOW_TRUST_TIERS) == {"report", "generated_cache", "test_temp"}


def test_drift_canonical_reasons_exposed() -> None:
    for code in (
        "TIER_DRIFT_DETECTED",
        "TIER_INDIRECT_LAUNDERING",
        "TIER_MISSING_METADATA",
        "TIER_LOW_TO_EVIDENCE_DRIFT",
    ):
        assert code in CANONICAL_TIER_VALIDATION_REASON_CODES


# ---- NT-07: drift monitor ----


def test_drift_no_change_allows() -> None:
    items = [
        {"artifact_id": "exec-1", "artifact_type": "pqx_slice_execution_record"},
        {"artifact_id": "evl-1", "artifact_type": "eval_slice_summary"},
    ]
    a = audit_artifacts(items)
    b = audit_artifacts(items)
    drift = audit_tier_drift(previous_audit=a, current_audit=b)
    assert drift["decision"] == "allow"
    assert drift["reason_code"] == "TIER_OK"


def test_drift_low_to_evidence_blocks() -> None:
    """An artifact_id flips from report tier to evidence tier."""
    prev = audit_artifacts(
        [{"artifact_id": "x-1", "artifact_path": "outputs/reports/r.md"}]
    )
    curr = audit_artifacts(
        [{"artifact_id": "x-1", "artifact_type": "eval_slice_summary"}]
    )
    drift = audit_tier_drift(previous_audit=prev, current_audit=curr)
    assert drift["decision"] == "block"
    assert drift["reason_code"] == "TIER_LOW_TO_EVIDENCE_DRIFT"
    assert drift["laundered"]


def test_drift_evidence_to_evidence_no_alert() -> None:
    prev = audit_artifacts(
        [{"artifact_id": "y-1", "artifact_type": "eval_slice_summary"}]
    )
    curr = audit_artifacts(
        [{"artifact_id": "y-1", "artifact_type": "lineage_completeness_report"}]
    )
    drift = audit_tier_drift(previous_audit=prev, current_audit=curr)
    # Both classify as 'evidence' tier, so no drift.
    assert drift["decision"] == "allow"


def test_drift_canonical_to_evidence_is_drift_but_not_laundering() -> None:
    prev = audit_artifacts(
        [{"artifact_id": "z-1", "artifact_type": "pqx_slice_execution_record"}]
    )
    curr = audit_artifacts(
        [{"artifact_id": "z-1", "artifact_type": "eval_slice_summary"}]
    )
    drift = audit_tier_drift(previous_audit=prev, current_audit=curr)
    assert drift["decision"] == "block"
    assert drift["reason_code"] == "TIER_DRIFT_DETECTED"
    assert drift["laundered"] == []


def test_drift_missing_tier_metadata_blocks() -> None:
    """An artifact present without artifact_id surfaces as missing metadata."""
    prev = {"items": []}
    curr = {
        "items": [
            {"artifact_id": "no-tier-1", "tier": ""},
        ]
    }
    drift = audit_tier_drift(previous_audit=prev, current_audit=curr)
    assert drift["decision"] == "block"
    assert drift["reason_code"] == "TIER_MISSING_METADATA"


# ---- NT-08 red team — tier escape ----


def test_red_team_indirect_laundering_via_wrapper_blocks(policy: dict) -> None:
    """Wrap a report artifact inside a canonical-typed evidence_index that
    references it. The transitive validator must block."""
    wrapper = {
        "artifact_id": "wrapper-1",
        "artifact_type": "certification_evidence_index",
        "evidence_refs": ["smuggled-report-1"],
    }
    artifact_store = {
        "smuggled-report-1": {
            "artifact_path": "outputs/reports/sneaky.md",
        }
    }
    res = validate_transitive_evidence_tiers(
        promotion_evidence_items=[wrapper],
        artifact_store=artifact_store,
        validation_id="vt-launder-1",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_INDIRECT_LAUNDERING"
    assert res["transitive_violations"]


def test_red_team_test_temp_via_canonical_ref_blocks(policy: dict) -> None:
    wrapper = {
        "artifact_id": "wrapper-2",
        "artifact_type": "loop_proof_bundle",
        "evidence_refs": ["scratch-fixture"],
    }
    artifact_store = {
        "scratch-fixture": {
            "artifact_path": "tests/fixtures/scratch.json",
        }
    }
    res = validate_transitive_evidence_tiers(
        promotion_evidence_items=[wrapper],
        artifact_store=artifact_store,
        validation_id="vt-launder-2",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_INDIRECT_LAUNDERING"


def test_red_team_generated_cache_via_canonical_ref_blocks(policy: dict) -> None:
    wrapper = {
        "artifact_id": "wrapper-3",
        "artifact_type": "loop_proof_bundle",
        "evidence_refs": ["cache-1"],
    }
    artifact_store = {
        "cache-1": {
            "artifact_path": "outputs/cache/snapshot.json",
        }
    }
    res = validate_transitive_evidence_tiers(
        promotion_evidence_items=[wrapper],
        artifact_store=artifact_store,
        validation_id="vt-launder-3",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_INDIRECT_LAUNDERING"


def test_red_team_omitted_tier_inferred_as_evidence_blocks(policy: dict) -> None:
    """An artifact without explicit tier whose path matches a tier rule."""
    res = validate_promotion_evidence_tiers(
        [
            {
                "artifact_id": "no-explicit-tier",
                "artifact_path": "outputs/reports/sneak.md",
            }
        ],
        validation_id="vt-tier-omit",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_REPORT_AS_AUTHORITY"


def test_transitive_passes_when_referenced_evidence_is_allowed(policy: dict) -> None:
    wrapper = {
        "artifact_id": "wrapper-good",
        "artifact_type": "loop_proof_bundle",
        "evidence_refs": ["evl-1"],
    }
    artifact_store = {
        "evl-1": {"artifact_type": "eval_slice_summary"},
    }
    res = validate_transitive_evidence_tiers(
        promotion_evidence_items=[wrapper],
        artifact_store=artifact_store,
        validation_id="vt-good",
    )
    assert res["decision"] == "allow"
    assert res["transitive_violations"] == []


def test_transitive_passes_when_no_refs(policy: dict) -> None:
    wrapper = {
        "artifact_id": "wrapper-empty",
        "artifact_type": "loop_proof_bundle",
    }
    res = validate_transitive_evidence_tiers(
        promotion_evidence_items=[wrapper],
        artifact_store={},
        validation_id="vt-empty",
    )
    assert res["decision"] == "allow"
