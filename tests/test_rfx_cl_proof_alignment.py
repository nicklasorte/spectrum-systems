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


def test_bool_rejected_for_int_field():
    # P2 fix: bool is a subclass of int; True/False must not pass int type check.
    schema = {"count": "int"}
    result = check_rfx_cl_proof_alignment(rfx_proof={"count": True}, cl_proof_schema=schema)
    assert "rfx_cl_proof_type_mismatch" in result["reason_codes_emitted"]

    result_false = check_rfx_cl_proof_alignment(rfx_proof={"count": False}, cl_proof_schema=schema)
    assert "rfx_cl_proof_type_mismatch" in result_false["reason_codes_emitted"]


def test_int_value_accepted_for_int_field():
    schema = {"count": "int"}
    result = check_rfx_cl_proof_alignment(rfx_proof={"count": 42}, cl_proof_schema=schema)
    assert "rfx_cl_proof_type_mismatch" not in result["reason_codes_emitted"]


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


def test_unknown_schema_type_flagged():
    # P2 fix: unknown type name (e.g. typo "string") must emit rfx_cl_proof_unknown_schema_type
    # instead of silently skipping the type check and reporting aligned.
    rfx_proof = {"status": "ok", "reason_codes_emitted": [], "trace_ref": "t", "signals": {}}
    schema_with_typo = {**_CL_SCHEMA, "status": "string"}  # "string" is not in _TYPE_MAP
    result = check_rfx_cl_proof_alignment(rfx_proof=rfx_proof, cl_proof_schema=schema_with_typo)
    assert "rfx_cl_proof_unknown_schema_type" in result["reason_codes_emitted"]
    assert result["status"] == "misaligned"


def test_unknown_schema_type_not_silently_aligned():
    # P2 fix: a field with an unknown type label must not pass as aligned.
    rfx_proof = {"status": "ok", "reason_codes_emitted": [], "trace_ref": "t", "signals": {}}
    schema_with_typo = {**_CL_SCHEMA, "status": "string"}
    result = check_rfx_cl_proof_alignment(rfx_proof=rfx_proof, cl_proof_schema=schema_with_typo)
    assert "status" in result["mismatched_fields"]


def test_non_dict_rfx_proof_flagged():
    # P1 fix: truthy non-dict rfx_proof (e.g. a string) must emit rfx_cl_proof_empty_rfx
    # instead of crashing with TypeError/AttributeError.
    result = check_rfx_cl_proof_alignment(rfx_proof="not-a-dict", cl_proof_schema=_CL_SCHEMA)
    assert "rfx_cl_proof_empty_rfx" in result["reason_codes_emitted"]
    assert result["status"] == "misaligned"


def test_list_rfx_proof_flagged():
    # P1 fix: list rfx_proof must also emit rfx_cl_proof_empty_rfx without raising.
    result = check_rfx_cl_proof_alignment(rfx_proof=["a", "b"], cl_proof_schema=_CL_SCHEMA)
    assert "rfx_cl_proof_empty_rfx" in result["reason_codes_emitted"]
    assert result["status"] == "misaligned"


def test_non_dict_cl_schema_does_not_raise():
    # P1 fix: truthy non-dict cl_proof_schema (e.g. a list) must not raise AttributeError.
    result = check_rfx_cl_proof_alignment(rfx_proof={"status": "ok"}, cl_proof_schema=["not-a-dict"])
    assert "rfx_cl_proof_empty_cl" in result["reason_codes_emitted"]
    assert result["artifact_type"] == "rfx_cl_proof_alignment_result"
    assert result["status"] == "misaligned"


def test_type_mismatch_does_not_inflate_alignment_rate():
    # P2 fix: type-mismatched fields must not count toward present_count / alignment_rate.
    schema = {"status": "str", "count": "int"}
    rfx_proof = {"status": "ok", "count": "not-an-int"}  # count present but wrong type
    result = check_rfx_cl_proof_alignment(rfx_proof=rfx_proof, cl_proof_schema=schema)
    assert "rfx_cl_proof_type_mismatch" in result["reason_codes_emitted"]
    assert result["status"] == "misaligned"
    # Only the valid-typed field counts; the mismatched one must not inflate the rate.
    assert result["signals"]["alignment_rate"] < 1.0
    assert result["signals"]["present_field_count"] == 1
