"""NX-25: certification prerequisite tests."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.certification_prerequisites import (
    CANONICAL_CERTIFICATION_REASON_CODES,
    assert_certification_prerequisites,
)


def _evidence() -> dict:
    return dict(
        eval_summary={"status": "healthy"},
        lineage_summary={"status": "healthy"},
        replay_summary={"status": "healthy"},
        control_decision={"decision": "allow"},
        enforcement_record={"enforcement_action": "allow_execution"},
        registry_violations=[],
        authority_shape_preflight_signal={"status": "pass"},
    )


def test_full_evidence_allows() -> None:
    res = assert_certification_prerequisites(**_evidence())
    assert res["decision"] == "allow"
    assert res["reason_code"] == "CERT_OK"


def test_red_team_missing_eval_pass_blocks() -> None:
    ev = _evidence()
    ev["eval_summary"] = {"status": "blocked"}
    res = assert_certification_prerequisites(**ev)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CERT_MISSING_EVAL_PASS"


def test_red_team_missing_lineage_blocks() -> None:
    ev = _evidence()
    ev["lineage_summary"] = None
    res = assert_certification_prerequisites(**ev)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CERT_MISSING_LINEAGE"


def test_red_team_missing_replay_readiness_blocks() -> None:
    ev = _evidence()
    ev["replay_summary"] = {"status": "blocked"}
    res = assert_certification_prerequisites(**ev)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CERT_MISSING_REPLAY_READINESS"


def test_red_team_missing_control_decision_blocks() -> None:
    ev = _evidence()
    ev["control_decision"] = {"decision": "block"}
    res = assert_certification_prerequisites(**ev)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CERT_MISSING_CONTROL_DECISION"


def test_red_team_missing_enforcement_record_blocks_when_state_changing() -> None:
    ev = _evidence()
    ev["enforcement_record"] = None
    res = assert_certification_prerequisites(**ev)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CERT_MISSING_ENFORCEMENT_RECORD"


def test_non_state_changing_does_not_require_enforcement() -> None:
    ev = _evidence()
    ev["enforcement_record"] = None
    res = assert_certification_prerequisites(state_changing=False, **ev)
    assert res["decision"] == "allow"


def test_red_team_active_registry_violation_blocks() -> None:
    ev = _evidence()
    ev["registry_violations"] = [{"violation": "demoted system claims authority"}]
    res = assert_certification_prerequisites(**ev)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CERT_REGISTRY_VIOLATION_PRESENT"


def test_canonical_reason_codes_finite() -> None:
    assert "CERT_OK" in CANONICAL_CERTIFICATION_REASON_CODES
    assert "CERT_MISSING_EVAL_PASS" in CANONICAL_CERTIFICATION_REASON_CODES
    assert "CERT_MISSING_AUTHORITY_SHAPE_PREFLIGHT" in CANONICAL_CERTIFICATION_REASON_CODES


def test_red_team_missing_authority_shape_preflight_blocks() -> None:
    ev = _evidence()
    ev["authority_shape_preflight_signal"] = None
    res = assert_certification_prerequisites(**ev)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CERT_MISSING_AUTHORITY_SHAPE_PREFLIGHT"


def test_red_team_failing_authority_shape_preflight_blocks() -> None:
    ev = _evidence()
    ev["authority_shape_preflight_signal"] = {"status": "fail"}
    res = assert_certification_prerequisites(**ev)
    assert res["decision"] == "block"
    assert res["reason_code"] == "CERT_MISSING_AUTHORITY_SHAPE_PREFLIGHT"
