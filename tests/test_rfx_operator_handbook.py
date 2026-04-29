"""Tests for rfx_operator_handbook (RFX-N20)."""

from spectrum_systems.modules.runtime.rfx_operator_handbook import (
    build_rfx_operator_handbook,
)


def _entry(**kw):
    base = {
        "code": "rfx_v2_outcome_mismatch",
        "plain_action": "Re-run the golden corpus check against the current artifact output.",
        "owner_context": "RFX phase label — see system_registry.md",
        "failure_prevented": "Undetected regression to known historical failure.",
        "severity": "high",
    }
    base.update(kw)
    return base


# RT-N20: handbook reason code lacking plain-language action → must fail.
def test_rt_n20_missing_plain_action_fails():
    result = build_rfx_operator_handbook(
        reason_code_entries=[_entry(plain_action="")]
    )
    assert "rfx_handbook_missing_action" in result["reason_codes_emitted"]
    assert result["status"] == "incomplete"


def test_rt_n20_complete_entry_passes():
    result = build_rfx_operator_handbook(reason_code_entries=[_entry()])
    assert result["status"] == "complete"
    assert result["reason_codes_emitted"] == []


def test_empty_entries_flagged():
    result = build_rfx_operator_handbook(reason_code_entries=[])
    assert "rfx_handbook_empty" in result["reason_codes_emitted"]


def test_missing_owner_context_flagged():
    result = build_rfx_operator_handbook(reason_code_entries=[_entry(owner_context="")])
    assert "rfx_handbook_missing_owner" in result["reason_codes_emitted"]


def test_duplicate_code_flagged():
    result = build_rfx_operator_handbook(
        reason_code_entries=[_entry(), _entry(plain_action="Different action.")]
    )
    assert "rfx_handbook_duplicate_code" in result["reason_codes_emitted"]


def test_coverage_rate_full():
    result = build_rfx_operator_handbook(reason_code_entries=[_entry(), _entry(code="rfx_v2_corpus_empty")])
    assert result["signals"]["coverage_rate"] == 1.0
    assert result["signals"]["covered_codes"] == 2


def test_handbook_entry_fields():
    result = build_rfx_operator_handbook(reason_code_entries=[_entry()])
    e = result["entries"][0]
    assert e["code"] == "rfx_v2_outcome_mismatch"
    assert e["plain_action"] is not None
    assert e["owner_context"] is not None


def test_artifact_type():
    result = build_rfx_operator_handbook(reason_code_entries=[_entry()])
    assert result["artifact_type"] == "rfx_operator_handbook"
