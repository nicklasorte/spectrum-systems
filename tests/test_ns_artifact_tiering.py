"""NS-01..03: Artifact tiering, audit, and retention enforcement."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.observability.artifact_tier_audit import (
    CANONICAL_TIER_VALIDATION_REASON_CODES,
    ArtifactTierError,
    audit_artifacts,
    classify_artifact,
    load_artifact_tier_policy,
    validate_promotion_evidence_tiers,
)


@pytest.fixture(scope="module")
def policy() -> dict:
    return load_artifact_tier_policy()


def test_canonical_artifact_type_classified_canonical(policy: dict) -> None:
    cls = classify_artifact(
        {"artifact_id": "exec-1", "artifact_type": "pqx_slice_execution_record"},
        policy,
    )
    assert cls["tier"] == "canonical"
    assert cls["promotion_relevant"] is True
    assert cls["replay_relevant"] is True


def test_evidence_artifact_type_classified_evidence(policy: dict) -> None:
    cls = classify_artifact(
        {"artifact_id": "evl-1", "artifact_type": "eval_slice_summary"},
        policy,
    )
    assert cls["tier"] == "evidence"
    assert cls["promotion_relevant"] is True


def test_test_temp_path_classified_test_temp(policy: dict) -> None:
    cls = classify_artifact(
        {"artifact_id": "t-1", "artifact_path": "tests/fixtures/foo.json"},
        policy,
    )
    assert cls["tier"] == "test_temp"
    assert cls["promotion_relevant"] is False


def test_generated_cache_path_classified_generated_cache(policy: dict) -> None:
    cls = classify_artifact(
        {"artifact_id": "g-1", "artifact_path": "outputs/cache/dashboard.json"},
        policy,
    )
    assert cls["tier"] == "generated_cache"
    assert cls["promotion_relevant"] is False


def test_report_path_classified_report(policy: dict) -> None:
    cls = classify_artifact(
        {"artifact_id": "r-1", "artifact_path": "outputs/reports/repo_health.md"},
        policy,
    )
    assert cls["tier"] == "report"


def test_explicit_tier_takes_precedence(policy: dict) -> None:
    cls = classify_artifact(
        {"artifact_id": "x", "artifact_type": "pqx_slice_execution_record", "tier": "report"},
        policy,
    )
    assert cls["tier"] == "report"


def test_unknown_path_defaults_to_default_tier(policy: dict) -> None:
    cls = classify_artifact({"artifact_id": "u-1", "artifact_path": "weird/loc.json"}, policy)
    assert cls["tier"] == policy["default_tier_when_unmatched"]


def test_classify_requires_artifact_id(policy: dict) -> None:
    with pytest.raises(ArtifactTierError):
        classify_artifact({"artifact_type": "eval_slice_summary"}, policy)


# ---- NS-02: Red team — artifact sprawl ----


def test_red_team_test_temp_blocks_promotion_evidence() -> None:
    res = validate_promotion_evidence_tiers(
        [
            {"artifact_id": "ev-1", "artifact_type": "eval_slice_summary"},
            {"artifact_id": "t-1", "artifact_path": "tests/fixtures/eval.json"},
        ],
        validation_id="vt-1",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_TEST_TEMP_AS_EVIDENCE"


def test_red_team_report_artifact_treated_as_authority_blocks() -> None:
    res = validate_promotion_evidence_tiers(
        [
            {"artifact_id": "rep-1", "artifact_path": "outputs/reports/cov.md"},
        ],
        validation_id="vt-2",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_REPORT_AS_AUTHORITY"


def test_red_team_generated_cache_treated_as_canonical_blocks() -> None:
    res = validate_promotion_evidence_tiers(
        [
            {"artifact_id": "g-1", "artifact_path": "outputs/cache/snapshot.json"},
        ],
        validation_id="vt-3",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_GENERATED_CACHE_AS_CANONICAL"


def test_red_team_duplicate_low_signal_artifacts_detected() -> None:
    audit = audit_artifacts(
        [
            {"artifact_id": "a", "artifact_type": "eval_slice_summary",
             "artifact_path": "outputs/cov.json", "content_hash": "h1"},
            {"artifact_id": "b", "artifact_type": "eval_slice_summary",
             "artifact_path": "outputs/cov.json", "content_hash": "h1"},
        ]
    )
    assert len(audit["duplicates"]) == 1
    assert audit["duplicates"][0]["artifact_id"] == "b"


def test_red_team_stale_generated_cache_detected() -> None:
    audit = audit_artifacts(
        [
            {
                "artifact_id": "g-1",
                "artifact_path": "outputs/cache/old.json",
                "generated_at": "2020-01-01T00:00:00Z",
            }
        ],
        now_iso="2026-04-27T00:00:00Z",
    )
    assert "g-1" in audit["stale"]


def test_canonical_and_evidence_artifacts_pass_promotion_validation() -> None:
    res = validate_promotion_evidence_tiers(
        [
            {"artifact_id": "exec-1", "artifact_type": "pqx_slice_execution_record"},
            {"artifact_id": "evl-1", "artifact_type": "eval_slice_summary"},
            {"artifact_id": "rep-1", "artifact_type": "replay_integrity_record"},
            {"artifact_id": "lin-1", "artifact_type": "lineage_completeness_report"},
        ],
        validation_id="vt-ok",
    )
    assert res["decision"] == "allow"
    assert res["reason_code"] == "TIER_OK"
    assert res["tier_counts"].get("canonical", 0) >= 1
    assert res["tier_counts"].get("evidence", 0) >= 3


def test_canonical_reason_codes_finite() -> None:
    assert "TIER_OK" in CANONICAL_TIER_VALIDATION_REASON_CODES
    assert "TIER_TEST_TEMP_AS_EVIDENCE" in CANONICAL_TIER_VALIDATION_REASON_CODES
    assert "TIER_REPORT_AS_AUTHORITY" in CANONICAL_TIER_VALIDATION_REASON_CODES
    assert "TIER_GENERATED_CACHE_AS_CANONICAL" in CANONICAL_TIER_VALIDATION_REASON_CODES
