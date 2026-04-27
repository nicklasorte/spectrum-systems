"""NT-01..03: Trust artifact freshness audit + red-team + fix.

Covers:
  * NT-01: A current artifact is reported ``current``.
  * NT-02 (red team): stale or mismatched-digest artifacts block.
  * NT-03 (fix): every block carries a canonical reason; no silent fallback.
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.observability.trust_artifact_freshness import (
    TrustArtifactFreshnessError,
    audit_artifact_freshness,
    audit_trust_artifact_freshness,
    load_trust_artifact_freshness_policy,
)


NOW = "2026-04-27T12:00:00Z"


def _fresh_evidence_index(**overrides):
    base = {
        "artifact_type": "certification_evidence_index",
        "input_digest": "in-abc",
        "source_evidence_digest": "src-abc",
        "generated_at": "2026-04-25T12:00:00Z",
    }
    base.update(overrides)
    return base


def test_policy_loads_with_required_fields():
    pol = load_trust_artifact_freshness_policy()
    assert pol["artifact_type"] == "trust_artifact_freshness_policy"
    assert isinstance(pol["rules"], list)
    types = {r["match_artifact_type"] for r in pol["rules"]}
    # The roadmap demands these be tracked
    for required in (
        "artifact_tier_policy",
        "reason_code_alias_map",
        "certification_evidence_index",
        "loop_proof_bundle",
        "failure_trace",
        "replay_lineage_join_summary",
        "slo_signal_policy",
    ):
        assert required in types


def test_current_evidence_index_is_current_when_digests_and_timestamp_match():
    art = _fresh_evidence_index()
    res = audit_artifact_freshness(
        art,
        expected_input_digest="in-abc",
        expected_source_digest="src-abc",
        now_iso=NOW,
    )
    assert res["status"] == "current"
    assert res["reason_code"] == "TRUST_FRESHNESS_OK"
    assert res["checks"]["source_digest_match"] is True
    assert res["checks"]["input_digest_match"] is True


def test_source_digest_mismatch_blocks_even_when_timestamp_fresh():
    """NT-02 red team: timestamp says fresh, but source digest changed."""
    art = _fresh_evidence_index()
    res = audit_artifact_freshness(
        art,
        expected_source_digest="src-DIFFERENT",
        now_iso=NOW,
    )
    assert res["status"] == "stale"
    assert res["reason_code"] == "TRUST_FRESHNESS_DIGEST_MISMATCH"
    assert res["canonical_reason"] == "CERTIFICATION_GAP"
    assert res["checks"]["source_digest_match"] is False


def test_input_digest_mismatch_blocks_even_when_timestamp_fresh():
    art = _fresh_evidence_index()
    res = audit_artifact_freshness(
        art,
        expected_input_digest="in-DIFFERENT",
        now_iso=NOW,
    )
    assert res["status"] == "stale"
    assert res["reason_code"] == "TRUST_FRESHNESS_DIGEST_MISMATCH"


def test_source_digest_present_but_no_expected_yields_unknown_not_current():
    """Timestamp alone must not declare ``current`` when source digest is
    available but the caller did not supply the expected digest. Silent
    fallback to timestamp-only is forbidden."""
    art = _fresh_evidence_index()
    res = audit_artifact_freshness(art, now_iso=NOW)
    assert res["status"] == "unknown"
    assert res["reason_code"] == "TRUST_FRESHNESS_UNKNOWN"


def test_stale_timestamp_blocks_even_when_digest_matches():
    art = _fresh_evidence_index(generated_at="2025-01-01T00:00:00Z")
    res = audit_artifact_freshness(
        art,
        expected_input_digest="in-abc",
        expected_source_digest="src-abc",
        now_iso=NOW,
    )
    assert res["status"] == "stale"
    assert res["reason_code"] == "TRUST_FRESHNESS_EVIDENCE_INDEX_STALE"


def test_unknown_artifact_type_is_unknown_not_current():
    res = audit_artifact_freshness(
        {"artifact_type": "definitely_not_tracked"},
        now_iso=NOW,
    )
    assert res["status"] == "unknown"
    assert res["reason_code"] == "TRUST_FRESHNESS_UNKNOWN"


def test_alias_map_freshness_uses_policy_id_field():
    art = {
        "artifact_type": "reason_code_alias_map",
        "policy_id": "NS-04-reason-code-aliases",
        "checked_at": "2026-04-25T12:00:00Z",
    }
    res = audit_artifact_freshness(
        art,
        expected_input_digest="NS-04-reason-code-aliases",
        now_iso=NOW,
    )
    assert res["status"] == "current"
    assert res["reason_code"] == "TRUST_FRESHNESS_OK"


def test_proof_bundle_stale_uses_proof_bundle_specific_reason():
    art = {
        "artifact_type": "loop_proof_bundle",
        "input_digest": "lp-abc",
        "source_evidence_digest": "src-lp",
        "generated_at": "2025-01-01T00:00:00Z",
    }
    res = audit_artifact_freshness(
        art,
        expected_input_digest="lp-abc",
        expected_source_digest="src-lp",
        now_iso=NOW,
    )
    assert res["status"] == "stale"
    assert res["reason_code"] == "TRUST_FRESHNESS_PROOF_BUNDLE_STALE"


def test_audit_trust_artifact_freshness_aggregates_blocking_reasons():
    arts = [
        _fresh_evidence_index(),
        {
            "artifact_type": "loop_proof_bundle",
            "input_digest": "lp-1",
            "source_evidence_digest": "src-1",
            "generated_at": "2026-04-25T12:00:00Z",
        },
        {
            "artifact_type": "failure_trace",
            "input_digest": "ft-old",
            "generated_at": "2025-01-01T00:00:00Z",
        },
    ]
    expected = {
        "certification_evidence_index": {"input": "in-abc", "source": "src-abc"},
        "loop_proof_bundle": {"input": "lp-1", "source": "src-DIFFERENT"},
        "failure_trace": {"input": "ft-old"},
    }
    summary = audit_trust_artifact_freshness(
        arts, expected_digests_by_type=expected, now_iso=NOW
    )
    # 1 current, 2 stale (one digest mismatch, one timestamp expired)
    assert summary["counts"]["current"] == 1
    assert summary["counts"]["stale"] == 2
    assert summary["overall_status"] == "stale"
    # Each blocking reason carries the artifact_type and reason_code
    joined = "\n".join(summary["blocking_reasons"])
    assert "loop_proof_bundle" in joined
    assert "failure_trace" in joined


def test_audit_artifact_freshness_requires_mapping():
    with pytest.raises(TrustArtifactFreshnessError):
        audit_artifact_freshness("not a mapping", now_iso=NOW)  # type: ignore[arg-type]


def test_no_silent_fallback_to_timestamp_when_source_digest_recorded():
    """Source digest is recorded but caller did not supply an expected one.
    The artifact's timestamp would be fresh — but we must NOT report
    ``current`` because the digest is the dominant signal and we cannot
    verify it. Result must be ``unknown``."""
    art = _fresh_evidence_index()
    res = audit_artifact_freshness(
        art,
        expected_input_digest="in-abc",  # only input checked, source recorded but unverified
        now_iso=NOW,
    )
    assert res["status"] == "unknown"
    assert res["reason_code"] == "TRUST_FRESHNESS_UNKNOWN"
