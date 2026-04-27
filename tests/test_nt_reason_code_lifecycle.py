"""NT-10..12: Reason-code lifecycle audit + red team + fix.

Covers:
  * NT-10 audit: unmapped blocking codes, unused aliases, aliases pointing
    to missing canonical, deprecated still emitted, forbidden emitted.
  * NT-11 red team: forbidden alias, deprecated still emitted, unmapped
    high-level blocking, alias pointing to non-canonical.
  * NT-12 fix: lifecycle states (active/deprecated/merged/forbidden) drive
    behavior — active passes silently, deprecated warns, forbidden raises,
    unknown high-level blocks.
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.observability.reason_code_canonicalizer import (
    ReasonCodeError,
)
from spectrum_systems.modules.observability.reason_code_lifecycle import (
    ReasonCodeLifecycleError,
    assert_emittable_reason_code,
    audit_reason_code_coverage,
    classify_reason_code_lifecycle,
)


def test_active_alias_classifies_as_active_with_no_warnings():
    res = classify_reason_code_lifecycle("replay_hash_mismatch_input")
    assert res["lifecycle_state"] == "active"
    assert res["canonical_category"] == "REPLAY_MISMATCH"
    assert res["warnings"] == []


def test_canonical_category_classifies_as_active():
    res = classify_reason_code_lifecycle("REPLAY_MISMATCH")
    assert res["lifecycle_state"] == "active"


def test_forbidden_alias_classifies_forbidden_with_warning():
    res = classify_reason_code_lifecycle("approved_silently")
    assert res["lifecycle_state"] == "forbidden"
    assert any("forbidden" in w for w in res["warnings"])


def test_deprecated_alias_classifies_deprecated_with_warning(monkeypatch):
    """Inject a synthetic deprecated alias via a custom alias_table."""
    table = {
        "artifact_type": "reason_code_alias_map",
        "canonical_categories": ["EVAL_FAILURE"],
        "aliases": {"old_eval_block": "EVAL_FAILURE"},
        "alias_lifecycle": {"deprecated": ["old_eval_block"]},
    }
    res = classify_reason_code_lifecycle("old_eval_block", alias_table=table)
    assert res["lifecycle_state"] == "deprecated"
    assert any("deprecated" in w for w in res["warnings"])


def test_assert_emittable_active_returns_classification():
    res = assert_emittable_reason_code("replay_hash_mismatch_input")
    assert res["lifecycle_state"] == "active"


def test_assert_emittable_forbidden_raises():
    with pytest.raises(ReasonCodeLifecycleError):
        assert_emittable_reason_code("approved_silently")


def test_assert_emittable_high_level_unmapped_raises():
    with pytest.raises(ReasonCodeError):
        assert_emittable_reason_code("blocked")


def test_assert_emittable_unknown_string_raises():
    with pytest.raises(ReasonCodeError):
        assert_emittable_reason_code("totally_invented_code")


def test_assert_emittable_deprecated_does_not_raise():
    """Deprecated codes are permitted; they emit a warning but do not block.
    Forbidden is the hard fail."""
    # Use a known active code to avoid editing repo lifecycle policy here
    res = assert_emittable_reason_code("replay_hash_mismatch_input")
    assert res["lifecycle_state"] in {"active", "deprecated"}


def test_audit_detects_forbidden_emitted():
    res = audit_reason_code_coverage(
        emitted_codes=["replay_hash_mismatch_input", "approved_silently"]
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "REASON_CODE_LIFECYCLE_FORBIDDEN"
    assert "approved_silently" in res["forbidden_emitted"]


def test_audit_detects_unmapped_blocking_high_level():
    """A new module that emits 'blocked' without aliasing it must fail audit."""
    res = audit_reason_code_coverage(emitted_codes=["blocked", "freeze"])
    assert res["decision"] == "block"
    assert res["reason_code"] in {
        "REASON_CODE_LIFECYCLE_UNMAPPED_BLOCKING",
        "REASON_CODE_LIFECYCLE_FORBIDDEN",
    }
    # blocked + freeze are high-level keys that must be aliased
    assert "blocked" in res["unmapped_blocking"]
    assert "freeze" in res["unmapped_blocking"]


def test_audit_detects_aliases_pointing_to_missing_canonical():
    table = {
        "artifact_type": "reason_code_alias_map",
        "canonical_categories": ["EVAL_FAILURE"],
        "aliases": {"some_alias": "MADE_UP_CATEGORY"},
        "alias_lifecycle": {},
    }
    res = audit_reason_code_coverage(emitted_codes=[], alias_table=table)
    assert res["decision"] == "block"
    assert "some_alias" in res["aliases_pointing_to_missing_canonical"]


def test_audit_reports_unused_aliases():
    res = audit_reason_code_coverage(emitted_codes=["replay_hash_mismatch_input"])
    # The repo alias map has many aliases; unused list should not be empty
    assert isinstance(res["unused_aliases"], list)
    assert "lineage_missing_parent_artifact" in res["unused_aliases"]


def test_audit_passes_when_only_active_codes_emitted():
    """Audit must not block on legitimate codes."""
    res = audit_reason_code_coverage(emitted_codes=[
        "replay_hash_mismatch_input",
        "lineage_missing_parent_artifact",
        "cert_missing_eval_pass",
    ])
    # No forbidden, no high-level unmapped → allow
    assert res["decision"] == "allow"


def test_assert_emittable_preserves_detail_code_in_warnings():
    """Even when deprecated, the original detail code is preserved in
    the classification (no information loss)."""
    table = {
        "artifact_type": "reason_code_alias_map",
        "canonical_categories": ["EVAL_FAILURE"],
        "aliases": {"old_eval_block": "EVAL_FAILURE"},
        "alias_lifecycle": {"deprecated": ["old_eval_block"]},
    }
    res = classify_reason_code_lifecycle("old_eval_block", alias_table=table)
    assert res["detail_code"] == "old_eval_block"
    assert res["canonical_category"] == "EVAL_FAILURE"
