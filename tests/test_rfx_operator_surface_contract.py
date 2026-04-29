"""Tests for rfx_operator_surface_contract (RFX-N11)."""

from spectrum_systems.modules.runtime.rfx_operator_surface_contract import (
    validate_rfx_operator_surface,
)


def _compact(status="ready", reason_codes_emitted=None, proof_ref="proof-001", **kw):
    return {
        "status": status,
        "reason_codes_emitted": reason_codes_emitted if reason_codes_emitted is not None else [],
        "proof_ref": proof_ref,
        **kw,
    }


# RT-N11: operator surface exposes raw artifact wall → must fail.
def test_rt_n11_raw_artifact_wall_blocked():
    result = validate_rfx_operator_surface(
        records=[{
            "status": "ready",
            "reason_codes_emitted": [],
            "proof_ref": "p-001",
            "cases": [{"id": "c1"}],  # raw artifact leak
        }]
    )
    assert "rfx_operator_surface_raw_artifact_leak" in result["reason_codes_emitted"]
    assert result["status"] == "invalid"


def test_rt_n11_compact_record_passes():
    result = validate_rfx_operator_surface(records=[_compact()])
    assert result["status"] == "valid"
    assert result["reason_codes_emitted"] == []


def test_empty_records_flagged():
    result = validate_rfx_operator_surface(records=[])
    assert "rfx_operator_surface_empty" in result["reason_codes_emitted"]


def test_missing_status_flagged():
    rec = _compact()
    del rec["status"]
    result = validate_rfx_operator_surface(records=[rec])
    assert "rfx_operator_surface_missing_status" in result["reason_codes_emitted"]


def test_missing_reason_codes_flagged():
    rec = _compact()
    del rec["reason_codes_emitted"]
    result = validate_rfx_operator_surface(records=[rec])
    assert "rfx_operator_surface_missing_reason" in result["reason_codes_emitted"]


def test_missing_proof_ref_flagged():
    rec = _compact(proof_ref=None)
    result = validate_rfx_operator_surface(records=[rec])
    assert "rfx_operator_surface_missing_proof_ref" in result["reason_codes_emitted"]


def test_violations_field_is_raw_artifact():
    result = validate_rfx_operator_surface(
        records=[{**_compact(), "violations": []}]
    )
    assert "rfx_operator_surface_raw_artifact_leak" in result["reason_codes_emitted"]


def test_signals_valid_count():
    result = validate_rfx_operator_surface(records=[_compact(), _compact(proof_ref="p2")])
    assert result["signals"]["valid_record_count"] == 2


def test_artifact_type():
    result = validate_rfx_operator_surface(records=[_compact()])
    assert result["artifact_type"] == "rfx_operator_surface_contract_result"


def test_reason_codes_none_flagged():
    # P2 fix: reason_codes_emitted=None must fail — key presence alone is not enough.
    # Build the record directly to bypass the _compact helper's None→[] coercion.
    result = validate_rfx_operator_surface(
        records=[{"status": "ready", "reason_codes_emitted": None, "proof_ref": "p-1"}]
    )
    assert "rfx_operator_surface_missing_reason" in result["reason_codes_emitted"]


def test_reason_codes_string_flagged():
    result = validate_rfx_operator_surface(
        records=[{"status": "ready", "reason_codes_emitted": "not-a-list", "proof_ref": "p-1"}]
    )
    assert "rfx_operator_surface_missing_reason" in result["reason_codes_emitted"]
