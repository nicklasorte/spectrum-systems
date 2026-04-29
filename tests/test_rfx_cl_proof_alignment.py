"""Tests for rfx_cl_proof_alignment (RFX-N16)."""

from spectrum_systems.modules.runtime.rfx_cl_proof_alignment import (
    check_rfx_cl_proof_alignment,
)

_CL_SCHEMA = {
    "status": "str",
    "reason_codes_emitted": "list",
    "trace_ref": "str",
    "signals": "dict",
}


# RT-N16: RFX proof diverges from CL proof shape → must fail.
def test_rt_n16_missing_field_fails():
    rfx_proof = {"status": "ok", "reason_codes_emitted": [], "signals": {}}
    # trace_ref is missing
    result = check_rfx_cl_proof_alignment(rfx_proof=rfx_proof, cl_proof_schema=_CL_SCHEMA)
    assert "rfx_cl_proof_missing_rfx_field" in result["reason_codes_emitted"]
    assert result["status"] == "misaligned"


def test_rt_n16_aligned_proof_passes():
    rfx_proof = {"status": "ok", "reason_codes_emitted": [], "trace_ref": "t-001", "signals": {}}
    result = check_rfx_cl_proof_alignment(rfx_proof=rfx_proof, cl_proof_schema=_CL_SCHEMA)
    assert result["status"] == "aligned"
    assert result["reason_codes_emitted"] == []


def test_type_mismatch_flagged():
    rfx_proof = {"status": "ok", "reason_codes_emitted": "not_a_list", "trace_ref": "t", "signals": {}}
    result = check_rfx_cl_proof_alignment(rfx_proof=rfx_proof, cl_proof_schema=_CL_SCHEMA)
    assert "rfx_cl_proof_type_mismatch" in result["reason_codes_emitted"]


def test_empty_rfx_proof_flagged():
    result = check_rfx_cl_proof_alignment(rfx_proof=None, cl_proof_schema=_CL_SCHEMA)
    assert "rfx_cl_proof_empty_rfx" in result["reason_codes_emitted"]


def test_empty_cl_schema_flagged():
    result = check_rfx_cl_proof_alignment(rfx_proof={"status": "ok"}, cl_proof_schema=None)
    assert "rfx_cl_proof_empty_cl" in result["reason_codes_emitted"]


def test_extra_authority_field_flagged():
    rfx_proof = {
        "status": "ok",
        "reason_codes_emitted": [],
        "trace_ref": "t",
        "signals": {},
        "decision_outcome": "allow",  # authority field not in CL schema
    }
    result = check_rfx_cl_proof_alignment(rfx_proof=rfx_proof, cl_proof_schema=_CL_SCHEMA)
    assert "rfx_cl_proof_extra_authority_field" in result["reason_codes_emitted"]
    assert "decision_outcome" in result["extra_authority_fields"]


def test_alignment_rate_full():
    rfx_proof = {"status": "ok", "reason_codes_emitted": [], "trace_ref": "t", "signals": {}}
    result = check_rfx_cl_proof_alignment(rfx_proof=rfx_proof, cl_proof_schema=_CL_SCHEMA)
    assert result["signals"]["alignment_rate"] == 1.0


def test_artifact_type():
    rfx_proof = {"status": "ok", "reason_codes_emitted": [], "trace_ref": "t", "signals": {}}
    result = check_rfx_cl_proof_alignment(rfx_proof=rfx_proof, cl_proof_schema=_CL_SCHEMA)
    assert result["artifact_type"] == "rfx_cl_proof_alignment_result"
