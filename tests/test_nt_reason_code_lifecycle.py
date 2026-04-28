"""NT-10..12: Reason-code coverage audit + sprawl red team + lifecycle fix.

Validates:
  - alias coverage audit detects unmapped/unused/duplicates/forbidden
  - lifecycle states are exposed by canonicalize_reason_code
  - forbidden aliases raise at the policy boundary
  - deprecated aliases still resolve, but the lifecycle field exposes the
    deprecation so callers can warn
  - new high-level blocking codes without canonical mapping fail closed
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.observability.reason_code_canonicalizer import (
    ALIAS_LIFECYCLE_STATES,
    CANONICAL_CATEGORIES,
    ReasonCodeError,
    assert_canonical_or_alias,
    audit_reason_code_coverage,
    canonicalize_reason_code,
)


# ---- NT-10: coverage audit ----


def test_lifecycle_states_finite() -> None:
    assert set(ALIAS_LIFECYCLE_STATES) == {
        "active",
        "deprecated",
        "merged",
        "forbidden",
    }


def test_audit_detects_unmapped_blocking_code() -> None:
    res = audit_reason_code_coverage(
        emitted_codes=[],
        expected_blocking_codes=["totally_unknown_blocker"],
    )
    assert "totally_unknown_blocker" in res["unmapped_blocking_codes"]


def test_audit_detects_forbidden_emitted() -> None:
    res = audit_reason_code_coverage(
        emitted_codes=["shutdown_required", "cert_missing_eval_pass"],
    )
    assert "shutdown_required" in res["forbidden_emitted"]


def test_audit_detects_deprecated_emitted() -> None:
    res = audit_reason_code_coverage(
        emitted_codes=["weak_evidence_coverage"],
    )
    assert "weak_evidence_coverage" in res["deprecated_emitted"]


def test_audit_detects_unused_aliases() -> None:
    res = audit_reason_code_coverage(emitted_codes=[])
    # Many active aliases will be 'unused' here, but deprecated/forbidden
    # ones must NOT appear as unused.
    assert "weak_evidence_coverage" not in res["unused_aliases"]
    assert "shutdown_required" not in res["unused_aliases"]


def test_audit_summary_string_present() -> None:
    res = audit_reason_code_coverage(emitted_codes=["cert_missing_eval_pass"])
    assert "reason-code coverage" in res["summary"]


# ---- NT-11 red team — sprawl ----


def test_red_team_unknown_high_level_blocking_string_raises() -> None:
    with pytest.raises(ReasonCodeError):
        assert_canonical_or_alias("blocked")


def test_red_team_forbidden_alias_raises_at_boundary() -> None:
    with pytest.raises(ReasonCodeError):
        assert_canonical_or_alias("shutdown_required")


def test_red_team_forbidden_alias_via_other_emit_path_raises() -> None:
    with pytest.raises(ReasonCodeError):
        assert_canonical_or_alias("auto_promote")


def test_red_team_unknown_blocking_code_raises() -> None:
    with pytest.raises(ReasonCodeError):
        assert_canonical_or_alias("not_a_real_code_anywhere")


def test_red_team_canonicalize_unknown_returns_unknown() -> None:
    """Unknown reason codes must NOT silently be classified into a canonical
    category. They must come back as UNKNOWN so callers fail closed."""
    res = canonicalize_reason_code("totally_made_up_code")
    assert res["canonical_category"] == "UNKNOWN"


# ---- NT-12 lifecycle ----


def test_active_alias_resolves_with_active_lifecycle() -> None:
    res = canonicalize_reason_code("cert_missing_eval_pass")
    assert res["canonical_category"] == "CERTIFICATION_GAP"
    assert res["lifecycle"] == "active"


def test_deprecated_alias_resolves_with_deprecated_lifecycle() -> None:
    res = canonicalize_reason_code("weak_evidence_coverage")
    assert res["canonical_category"] in CANONICAL_CATEGORIES
    assert res["lifecycle"] == "deprecated"


def test_forbidden_alias_canonicalizes_but_boundary_blocks() -> None:
    """canonicalize_reason_code returns lifecycle=forbidden so the
    failure-trace surface preserves the detail; assert_canonical_or_alias
    is the boundary that hard-blocks emission."""
    res = canonicalize_reason_code("shutdown_required")
    assert res["lifecycle"] == "forbidden"


def test_canonical_categories_remain_finite_after_lifecycle_addition() -> None:
    """NT-12 must not silently broaden the canonical category set."""
    assert len(set(CANONICAL_CATEGORIES)) == 12
    for required in (
        "EVAL_FAILURE",
        "REPLAY_MISMATCH",
        "LINEAGE_GAP",
        "CONTEXT_ADMISSION_FAILURE",
        "CERTIFICATION_GAP",
        "AUTHORITY_SHAPE_VIOLATION",
        "CONTROL_CHAIN_VIOLATION",
    ):
        assert required in CANONICAL_CATEGORIES


def test_freshness_alias_present_and_active() -> None:
    res = canonicalize_reason_code("trust_freshness_stale_digest_mismatch")
    assert res["canonical_category"] == "CERTIFICATION_GAP"
    assert res["lifecycle"] == "active"


def test_proof_size_alias_present_and_active() -> None:
    res = canonicalize_reason_code("proof_size_over_ref_budget")
    assert res["canonical_category"] == "CERTIFICATION_GAP"
    assert res["lifecycle"] == "active"


def test_tier_drift_alias_present() -> None:
    res = canonicalize_reason_code("tier_drift_detected")
    assert res["canonical_category"] == "POLICY_MISMATCH"


def test_audit_aliases_with_missing_category_returns_empty_for_well_formed_map() -> None:
    res = audit_reason_code_coverage(emitted_codes=[])
    assert res["aliases_with_missing_category"] == []
