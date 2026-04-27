import pytest

from spectrum_systems.modules.governance.trust_compression import audit_reason_code_lifecycle
from spectrum_systems.modules.observability.reason_code_canonicalizer import ReasonCodeError, assert_canonical_or_alias, canonicalize_reason_code


def test_reason_lifecycle_forbidden_blocks() -> None:
    report = audit_reason_code_lifecycle(emitted_codes=["blocked"])
    assert report["decision"] == "block"
    assert "blocked" in report["forbidden_aliases_emitted"]


def test_canonicalizer_marks_deprecated() -> None:
    res = canonicalize_reason_code("schema_invalid")
    assert res["lifecycle_status"] == "deprecated"


def test_forbidden_alias_rejected() -> None:
    with pytest.raises(ReasonCodeError):
        assert_canonical_or_alias("freeze")
