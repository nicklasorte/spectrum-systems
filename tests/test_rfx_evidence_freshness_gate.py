"""Tests for rfx_evidence_freshness_gate (RFX-N15)."""

from spectrum_systems.modules.runtime.rfx_evidence_freshness_gate import (
    check_rfx_evidence_freshness,
)

_REF_TIME = 1_000_000.0


def _rec(id="ev1", age_seconds=60.0, **kw):
    return {"id": id, "timestamp_seconds": _REF_TIME - age_seconds, **kw}


# RT-N15: stale proof input must fail.
def test_rt_n15_stale_input_blocked():
    result = check_rfx_evidence_freshness(
        evidence_records=[_rec(age_seconds=7200.0)],
        reference_time_seconds=_REF_TIME,
        max_age_seconds=3600.0,
    )
    assert "rfx_freshness_stale" in result["reason_codes_emitted"]
    assert result["status"] == "stale"


def test_rt_n15_fresh_input_passes():
    result = check_rfx_evidence_freshness(
        evidence_records=[_rec(age_seconds=100.0)],
        reference_time_seconds=_REF_TIME,
        max_age_seconds=3600.0,
    )
    assert result["status"] == "fresh"
    assert result["reason_codes_emitted"] == []


def test_missing_timestamp_flagged():
    result = check_rfx_evidence_freshness(
        evidence_records=[{"id": "ev1"}],
        reference_time_seconds=_REF_TIME,
    )
    assert "rfx_freshness_missing_timestamp" in result["reason_codes_emitted"]


def test_empty_records_flagged():
    result = check_rfx_evidence_freshness(
        evidence_records=[],
        reference_time_seconds=_REF_TIME,
    )
    assert "rfx_freshness_empty_inputs" in result["reason_codes_emitted"]


def test_invalid_max_age_flagged():
    result = check_rfx_evidence_freshness(
        evidence_records=[_rec()],
        reference_time_seconds=_REF_TIME,
        max_age_seconds=-1.0,
    )
    assert "rfx_freshness_invalid_max_age" in result["reason_codes_emitted"]


def test_mixed_fresh_and_stale():
    result = check_rfx_evidence_freshness(
        evidence_records=[_rec(id="fresh", age_seconds=10.0), _rec(id="stale", age_seconds=9999.0)],
        reference_time_seconds=_REF_TIME,
        max_age_seconds=3600.0,
    )
    assert result["signals"]["fresh_count"] == 1
    assert result["signals"]["stale_count"] == 1


def test_freshness_rate_all_fresh():
    result = check_rfx_evidence_freshness(
        evidence_records=[_rec(id=f"e{i}", age_seconds=1.0) for i in range(5)],
        reference_time_seconds=_REF_TIME,
    )
    assert result["signals"]["freshness_rate"] == 1.0


def test_artifact_type():
    result = check_rfx_evidence_freshness(evidence_records=[_rec()], reference_time_seconds=_REF_TIME)
    assert result["artifact_type"] == "rfx_evidence_freshness_gate_result"
