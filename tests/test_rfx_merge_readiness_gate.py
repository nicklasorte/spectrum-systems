"""Tests for rfx_merge_readiness_gate (RFX-N19)."""

from spectrum_systems.modules.runtime.rfx_merge_readiness_gate import (
    check_rfx_merge_readiness,
)


def _ready(**kw):
    base = {
        "rfx_proof_ref": "proof-001",
        "evl_evidence_ref": "evl-001",
        "lin_lineage_ref": "lin-001",
        "rep_replay_ref": "rep-001",
        "authority_shape_check": True,
        "authority_drift_check": True,
        "system_registry_check": True,
        "pytest_passed": True,
        "red_team_coverage": True,
        "trace_ref": "trace-001",
    }
    base.update(kw)
    return base


# RT-N19: merge readiness allows missing proof → must fail.
def test_rt_n19_missing_proof_blocked():
    result = check_rfx_merge_readiness(readiness_record=_ready(rfx_proof_ref=None))
    assert "rfx_merge_missing_proof" in result["reason_codes_emitted"]
    assert result["status"] == "not_ready"


# RT-N19: missing guard blocked.
def test_rt_n19_missing_guard_blocked():
    result = check_rfx_merge_readiness(readiness_record=_ready(authority_shape_check=False))
    assert "rfx_merge_missing_guard" in result["reason_codes_emitted"]


# RT-N19: missing test evidence blocked.
def test_rt_n19_missing_test_blocked():
    result = check_rfx_merge_readiness(readiness_record=_ready(pytest_passed=False))
    assert "rfx_merge_missing_test" in result["reason_codes_emitted"]


def test_rt_n19_fully_ready_passes():
    result = check_rfx_merge_readiness(readiness_record=_ready())
    assert result["status"] == "ready"
    assert result["reason_codes_emitted"] == []


def test_empty_record_blocked():
    result = check_rfx_merge_readiness(readiness_record=None)
    assert "rfx_merge_empty" in result["reason_codes_emitted"]


def test_missing_trace_ref_flagged():
    result = check_rfx_merge_readiness(readiness_record=_ready(trace_ref=None))
    assert "rfx_merge_missing_trace" in result["reason_codes_emitted"]


def test_missing_all_proofs():
    rec = _ready(rfx_proof_ref=None, evl_evidence_ref=None, lin_lineage_ref=None, rep_replay_ref=None)
    result = check_rfx_merge_readiness(readiness_record=rec)
    assert result["missing_proofs"] == ["rfx_proof_ref", "evl_evidence_ref", "lin_lineage_ref", "rep_replay_ref"]


def test_proof_coverage_full():
    result = check_rfx_merge_readiness(readiness_record=_ready())
    assert result["signals"]["proof_coverage"] == 1.0
    assert result["signals"]["guard_coverage"] == 1.0
    assert result["signals"]["test_coverage"] == 1.0


def test_artifact_type():
    result = check_rfx_merge_readiness(readiness_record=_ready())
    assert result["artifact_type"] == "rfx_merge_readiness_gate_result"


def test_string_false_guard_flagged():
    # P1 fix: string "false" must not pass as a boolean True guard condition.
    result = check_rfx_merge_readiness(readiness_record=_ready(authority_shape_check="false"))
    assert "rfx_merge_missing_guard" in result["reason_codes_emitted"]
    assert result["status"] == "not_ready"


def test_string_false_test_flagged():
    # P1 fix: string "false" must not pass as a boolean True test condition.
    result = check_rfx_merge_readiness(readiness_record=_ready(pytest_passed="false"))
    assert "rfx_merge_missing_test" in result["reason_codes_emitted"]
    assert result["status"] == "not_ready"


def test_truthy_string_guard_flagged():
    # P1 fix: any non-True truthy value (e.g., "yes") must also require strict bool True.
    result = check_rfx_merge_readiness(readiness_record=_ready(authority_drift_check="yes"))
    assert "rfx_merge_missing_guard" in result["reason_codes_emitted"]


def test_whitespace_only_proof_ref_flagged():
    # P1 fix: whitespace-only proof ref must not satisfy proof presence check.
    result = check_rfx_merge_readiness(readiness_record=_ready(rfx_proof_ref="   "))
    assert "rfx_merge_missing_proof" in result["reason_codes_emitted"]
    assert result["status"] == "not_ready"


def test_numeric_proof_ref_flagged():
    # P1 fix: a numeric proof ref must not satisfy the string proof presence check.
    result = check_rfx_merge_readiness(readiness_record=_ready(rfx_proof_ref=42))
    assert "rfx_merge_missing_proof" in result["reason_codes_emitted"]
    assert result["status"] == "not_ready"
