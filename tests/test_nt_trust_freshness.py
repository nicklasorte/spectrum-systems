"""NT-01..03: Trust artifact freshness audit + stale proof red team.

Validates the freshness audit module against the seven trust artifact kinds
that gate the canonical loop. Also runs the NT-02 red team: stale or
mismatched proof artifacts must block certification readiness with a
canonical reason and never silently fall back to the old proof.
"""

from __future__ import annotations

import json

import pytest

from spectrum_systems.modules.observability.trust_artifact_freshness import (
    CANONICAL_FRESHNESS_REASON_CODES,
    REQUIRED_TRUST_ARTIFACT_KINDS,
    TrustFreshnessError,
    audit_trust_artifact_freshness,
    load_trust_artifact_freshness_policy,
)


def _digest(payload):
    import hashlib

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fresh_artifacts() -> dict:
    """Build a freshness-passing bundle for all required kinds."""
    inputs = {"k": "v"}
    digest = _digest(inputs)
    return {
        kind: {
            "artifact_id": f"{kind}-1",
            "producer_inputs": inputs,
            "producer_input_digest": digest,
            "generated_at": "2026-04-26T12:00:00Z",
        }
        for kind in REQUIRED_TRUST_ARTIFACT_KINDS
    }


# ---- NT-01 contract ----


def test_required_kinds_finite_and_known() -> None:
    assert set(REQUIRED_TRUST_ARTIFACT_KINDS) == {
        "artifact_tier_policy",
        "reason_code_alias_map",
        "certification_evidence_index",
        "loop_proof_bundle",
        "failure_trace",
        "replay_lineage_join_summary",
        "slo_signal_policy",
    }


def test_canonical_freshness_reason_codes_finite() -> None:
    assert "TRUST_FRESHNESS_OK" in CANONICAL_FRESHNESS_REASON_CODES
    assert "TRUST_FRESHNESS_STALE_DIGEST_MISMATCH" in CANONICAL_FRESHNESS_REASON_CODES
    assert "TRUST_FRESHNESS_UNKNOWN_NO_PROOF" in CANONICAL_FRESHNESS_REASON_CODES


def test_policy_loadable_and_well_formed() -> None:
    pol = load_trust_artifact_freshness_policy()
    assert pol["artifact_type"] == "trust_artifact_freshness_policy"
    for kind in REQUIRED_TRUST_ARTIFACT_KINDS:
        assert kind in pol["artifact_kinds"], f"missing policy entry for {kind}"


def test_audit_id_required() -> None:
    with pytest.raises(TrustFreshnessError):
        audit_trust_artifact_freshness(
            audit_id="", artifacts=_fresh_artifacts(), now_iso="2026-04-27T12:00:00Z"
        )


def test_full_fresh_bundle_is_current() -> None:
    res = audit_trust_artifact_freshness(
        audit_id="aud-1",
        artifacts=_fresh_artifacts(),
        now_iso="2026-04-27T12:00:00Z",
    )
    assert res["status"] == "current"
    assert res["canonical_reason"] == "TRUST_FRESHNESS_OK"
    assert res["stale_kinds"] == []
    assert res["unknown_kinds"] == []


# ---- NT-02 red team — stale / mismatched / silent-fallback ----


def test_red_team_stale_certification_evidence_index_blocks() -> None:
    arts = _fresh_artifacts()
    # Mutate inputs but keep the OLD declared digest.
    arts["certification_evidence_index"]["producer_inputs"] = {"k": "TAMPERED"}
    res = audit_trust_artifact_freshness(
        audit_id="aud-2",
        artifacts=arts,
        now_iso="2026-04-27T12:00:00Z",
    )
    assert res["status"] == "stale"
    assert res["canonical_reason"] == "TRUST_FRESHNESS_STALE_DIGEST_MISMATCH"
    assert "certification_evidence_index" in res["stale_kinds"]


def test_red_team_stale_alias_map_blocks() -> None:
    arts = _fresh_artifacts()
    arts["reason_code_alias_map"]["producer_inputs"] = {"changed": True}
    res = audit_trust_artifact_freshness(
        audit_id="aud-3",
        artifacts=arts,
        now_iso="2026-04-27T12:00:00Z",
    )
    assert res["status"] == "stale"
    assert "reason_code_alias_map" in res["stale_kinds"]


def test_red_team_stale_loop_proof_bundle_blocks() -> None:
    arts = _fresh_artifacts()
    # Old declared digest, new producer_inputs
    arts["loop_proof_bundle"]["producer_input_digest"] = "deadbeef" * 8
    res = audit_trust_artifact_freshness(
        audit_id="aud-4", artifacts=arts, now_iso="2026-04-27T12:00:00Z"
    )
    assert res["status"] == "stale"
    assert "loop_proof_bundle" in res["stale_kinds"]


def test_red_team_stale_replay_lineage_summary_blocks() -> None:
    arts = _fresh_artifacts()
    # Source digest mismatch path: declare a source digest that doesn't
    # match the supplied source artifact.
    arts["replay_lineage_join_summary"]["source_artifact_id"] = "src-1"
    arts["replay_lineage_join_summary"]["source_artifact_digest"] = "ff" * 32
    res = audit_trust_artifact_freshness(
        audit_id="aud-5",
        artifacts=arts,
        source_artifacts={"src-1": {"different": "payload"}},
        now_iso="2026-04-27T12:00:00Z",
    )
    assert res["status"] == "stale"
    assert (
        res["canonical_reason"]
        == "TRUST_FRESHNESS_STALE_SOURCE_DIGEST_MISMATCH"
    )


def test_red_team_stale_artifact_tier_policy_blocks_via_timestamp() -> None:
    arts = _fresh_artifacts()
    # Drop digest signal entirely; provide only an ancient timestamp.
    arts["artifact_tier_policy"] = {
        "artifact_id": "atp-1",
        "generated_at": "2019-01-01T00:00:00Z",
    }
    res = audit_trust_artifact_freshness(
        audit_id="aud-6", artifacts=arts, now_iso="2026-04-27T12:00:00Z"
    )
    assert res["status"] == "stale"
    assert res["canonical_reason"] == "TRUST_FRESHNESS_STALE_TIMESTAMP"


def test_red_team_stale_slo_signal_policy_blocks() -> None:
    arts = _fresh_artifacts()
    arts["slo_signal_policy"]["producer_inputs"] = {"shifted": True}
    res = audit_trust_artifact_freshness(
        audit_id="aud-7", artifacts=arts, now_iso="2026-04-27T12:00:00Z"
    )
    assert res["status"] == "stale"
    assert "slo_signal_policy" in res["stale_kinds"]


def test_red_team_no_proof_at_all_is_unknown_and_blocks() -> None:
    arts = _fresh_artifacts()
    # Strip every freshness signal from one item.
    arts["failure_trace"] = {"artifact_id": "ft-no-proof"}
    res = audit_trust_artifact_freshness(
        audit_id="aud-8", artifacts=arts, now_iso="2026-04-27T12:00:00Z"
    )
    assert res["status"] == "stale"
    assert res["canonical_reason"] == "TRUST_FRESHNESS_UNKNOWN_NO_PROOF"
    assert "failure_trace" in res["unknown_kinds"]


def test_red_team_missing_artifact_blocks_with_canonical_reason() -> None:
    arts = _fresh_artifacts()
    arts["loop_proof_bundle"] = None
    res = audit_trust_artifact_freshness(
        audit_id="aud-9", artifacts=arts, now_iso="2026-04-27T12:00:00Z"
    )
    assert res["status"] == "stale"
    assert res["canonical_reason"] == "TRUST_FRESHNESS_MISSING_ARTIFACT"
    assert "loop_proof_bundle" in res["stale_kinds"]


def test_audit_does_not_silently_fall_back_to_old_proof() -> None:
    """Even if a previous freshness audit was 'current', the next audit
    must recompute digests; a tampered inputs payload cannot be hidden
    by re-using the old declared digest."""
    arts = _fresh_artifacts()
    # First pass: clean
    res_clean = audit_trust_artifact_freshness(
        audit_id="aud-10a",
        artifacts=arts,
        now_iso="2026-04-27T12:00:00Z",
    )
    assert res_clean["status"] == "current"

    # Tamper inputs but keep digest from before; second pass must catch it.
    arts["certification_evidence_index"]["producer_inputs"] = {"new": "data"}
    res_dirty = audit_trust_artifact_freshness(
        audit_id="aud-10b",
        artifacts=arts,
        now_iso="2026-04-27T12:00:00Z",
    )
    assert res_dirty["status"] == "stale"
    assert (
        res_dirty["canonical_reason"]
        == "TRUST_FRESHNESS_STALE_DIGEST_MISMATCH"
    )


def test_human_readable_lists_first_blocking_kind() -> None:
    arts = _fresh_artifacts()
    arts["reason_code_alias_map"]["producer_inputs"] = {"tampered": True}
    res = audit_trust_artifact_freshness(
        audit_id="aud-11", artifacts=arts, now_iso="2026-04-27T12:00:00Z"
    )
    assert "first_blocking_kind: reason_code_alias_map" in res["human_readable"]
    assert "TRUST_FRESHNESS_STALE_DIGEST_MISMATCH" in res["human_readable"]


# ---- NT-03 freshness fix verification ----


def test_freshness_canonicalizes_to_certification_gap() -> None:
    """All TRUST_FRESHNESS_* aliases canonicalize to CERTIFICATION_GAP."""
    from spectrum_systems.modules.observability.reason_code_canonicalizer import (
        canonicalize_reason_code,
    )

    for code in CANONICAL_FRESHNESS_REASON_CODES:
        result = canonicalize_reason_code(code)
        assert result["canonical_category"] == "CERTIFICATION_GAP", code
