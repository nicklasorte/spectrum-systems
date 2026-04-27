"""NX-19..21: Context admission red-team and gate tests."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.context_admission_gate import (
    CANONICAL_CTX_REASON_CODES,
    ContextAdmissionError,
    admit_context_bundle,
)


def _good_candidate(cid: str = "c1", role: str = "evidence", trust_level: str = "trusted") -> dict:
    return {
        "candidate_id": cid,
        "role": role,
        "trust_level": trust_level,
        "artifact_type": "context_evidence",
        "schema_version": "1.0.0",
        "provenance": {"source": "system_repo"},
        "expires_at": "2099-01-01T00:00:00Z",
        "topic": "spec",
        "assertion": "the spec is valid",
    }


def _bundle(*candidates) -> dict:
    return {
        "preflight_passed": True,
        "admitted_candidates": list(candidates),
    }


def test_clean_bundle_admits() -> None:
    res = admit_context_bundle(bundle=_bundle(_good_candidate()))
    assert res["decision"] == "allow"
    assert res["reason_code"] == "CTX_OK"


# ---- NX-20 red team ----


def test_red_team_missing_provenance_blocks() -> None:
    cand = _good_candidate()
    cand.pop("provenance")
    res = admit_context_bundle(bundle=_bundle(cand))
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_MISSING_PROVENANCE"


def test_red_team_empty_provenance_blocks() -> None:
    cand = _good_candidate()
    cand["provenance"] = {}
    res = admit_context_bundle(bundle=_bundle(cand))
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_MISSING_PROVENANCE"


def test_red_team_stale_ttl_blocks() -> None:
    cand = _good_candidate()
    cand["expires_at"] = "2020-01-01T00:00:00Z"
    res = admit_context_bundle(bundle=_bundle(cand))
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_STALE_TTL"


def test_red_team_schema_incompatibility_blocks() -> None:
    cand = _good_candidate()
    cand["schema_version"] = "0.1.0"
    res = admit_context_bundle(
        bundle=_bundle(cand),
        expected_schema_versions={"context_evidence": "1.0.0"},
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_SCHEMA_INCOMPATIBLE"


def test_red_team_untrusted_instruction_injection_blocks() -> None:
    cand = _good_candidate(role="instruction", trust_level="untrusted")
    res = admit_context_bundle(bundle=_bundle(cand))
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_UNTRUSTED_INSTRUCTION"


def test_red_team_untrusted_system_role_blocks() -> None:
    cand = _good_candidate(role="system", trust_level="untrusted")
    res = admit_context_bundle(bundle=_bundle(cand))
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_UNTRUSTED_INSTRUCTION"


def test_red_team_conflicting_context_blocks() -> None:
    a = _good_candidate("a")
    b = _good_candidate("b")
    b["assertion"] = "the spec is invalid"
    res = admit_context_bundle(bundle=_bundle(a, b))
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_CONTRADICTORY_CONTEXT"


def test_red_team_missing_preflight_blocks() -> None:
    bundle = _bundle(_good_candidate())
    bundle["preflight_passed"] = False
    res = admit_context_bundle(bundle=bundle)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_MISSING_PREFLIGHT"


def test_red_team_malformed_candidate_blocks() -> None:
    bundle = {"preflight_passed": True, "admitted_candidates": ["not a dict"]}
    res = admit_context_bundle(bundle=bundle)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_MALFORMED_BUNDLE"


def test_red_team_malformed_candidates_field_blocks() -> None:
    bundle = {"preflight_passed": True, "admitted_candidates": "oops"}
    res = admit_context_bundle(bundle=bundle)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CTX_MALFORMED_BUNDLE"


def test_invalid_now_raises() -> None:
    with pytest.raises(ContextAdmissionError):
        admit_context_bundle(bundle=_bundle(_good_candidate()), now_iso="not-a-date")


def test_canonical_reason_codes_finite() -> None:
    assert "CTX_OK" in CANONICAL_CTX_REASON_CODES
    assert "CTX_UNTRUSTED_INSTRUCTION" in CANONICAL_CTX_REASON_CODES
