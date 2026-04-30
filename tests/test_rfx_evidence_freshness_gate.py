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


def test_non_dict_record_does_not_raise():
    # P1 fix: a non-dict row must emit rfx_freshness_malformed_record, not AttributeError.
    result = check_rfx_evidence_freshness(
        evidence_records=["not-a-dict"],
        reference_time_seconds=_REF_TIME,
    )
    assert "rfx_freshness_malformed_record" in result["reason_codes_emitted"]
    assert result["status"] == "stale"


def test_mixed_records_malformed_skipped():
    result = check_rfx_evidence_freshness(
        evidence_records=[_rec(), "bad"],
        reference_time_seconds=_REF_TIME,
    )
    assert "rfx_freshness_malformed_record" in result["reason_codes_emitted"]
    assert result["signals"]["fresh_count"] == 1


def test_none_evidence_records_does_not_raise():
    # P2 fix: None evidence_records must not raise TypeError; must emit rfx_freshness_empty_inputs.
    result = check_rfx_evidence_freshness(
        evidence_records=None,
        reference_time_seconds=_REF_TIME,
    )
    assert "rfx_freshness_empty_inputs" in result["reason_codes_emitted"]
    assert result["artifact_type"] == "rfx_evidence_freshness_gate_result"
    assert result["status"] == "stale"


def test_nan_timestamp_flagged():
    # P2 fix: NaN float timestamp must not pass as fresh; must emit missing_timestamp.
    result = check_rfx_evidence_freshness(
        evidence_records=[{"id": "ev-nan", "timestamp_seconds": float("nan")}],
        reference_time_seconds=_REF_TIME,
    )
    assert "rfx_freshness_missing_timestamp" in result["reason_codes_emitted"]
    assert result["signals"]["fresh_count"] == 0


def test_inf_timestamp_flagged():
    # P2 fix: inf float timestamp must not pass as fresh; must emit missing_timestamp.
    result = check_rfx_evidence_freshness(
        evidence_records=[{"id": "ev-inf", "timestamp_seconds": float("inf")}],
        reference_time_seconds=_REF_TIME,
    )
    assert "rfx_freshness_missing_timestamp" in result["reason_codes_emitted"]
    assert result["signals"]["fresh_count"] == 0


def test_nan_string_timestamp_flagged():
    # P2 fix: "NaN" string timestamp must not pass as fresh; must emit missing_timestamp.
    result = check_rfx_evidence_freshness(
        evidence_records=[{"id": "ev-nanstr", "timestamp_seconds": "NaN"}],
        reference_time_seconds=_REF_TIME,
    )
    assert "rfx_freshness_missing_timestamp" in result["reason_codes_emitted"]
    assert result["signals"]["fresh_count"] == 0


def test_non_iterable_evidence_records_does_not_raise():
    # P1 fix: truthy non-iterable evidence_records (e.g. integer 1 from bad
    # deserialization) must not raise TypeError; must emit rfx_freshness_empty_inputs
    # and return a valid artifact.
    result = check_rfx_evidence_freshness(
        evidence_records=1,
        reference_time_seconds=_REF_TIME,
    )
    assert "rfx_freshness_empty_inputs" in result["reason_codes_emitted"]
    assert result["artifact_type"] == "rfx_evidence_freshness_gate_result"


def test_nan_max_age_flagged():
    # P2 fix: float('nan') max_age_seconds must not pass as valid; must emit
    # rfx_freshness_invalid_max_age since nan comparisons always return False,
    # which would silently mark all evidence fresh.
    result = check_rfx_evidence_freshness(
        evidence_records=[_rec()],
        reference_time_seconds=_REF_TIME,
        max_age_seconds=float("nan"),
    )
    assert "rfx_freshness_invalid_max_age" in result["reason_codes_emitted"]


def test_inf_max_age_flagged():
    # P2 fix: float('inf') max_age_seconds must not pass as valid; must emit
    # rfx_freshness_invalid_max_age since an infinite window accepts all evidence.
    result = check_rfx_evidence_freshness(
        evidence_records=[_rec()],
        reference_time_seconds=_REF_TIME,
        max_age_seconds=float("inf"),
    )
    assert "rfx_freshness_invalid_max_age" in result["reason_codes_emitted"]


def test_nan_reference_time_flagged():
    # P2 fix: float('nan') reference_time_seconds must emit rfx_freshness_invalid_reference_time;
    # nan arithmetic makes age comparisons always False, causing fail-open.
    result = check_rfx_evidence_freshness(
        evidence_records=[_rec()],
        reference_time_seconds=float("nan"),
        max_age_seconds=3600.0,
    )
    assert "rfx_freshness_invalid_reference_time" in result["reason_codes_emitted"]
    assert result["signals"]["fresh_count"] == 0
    assert result["status"] == "stale"


def test_neg_inf_reference_time_flagged():
    # P2 fix: float('-inf') reference_time_seconds must emit rfx_freshness_invalid_reference_time;
    # age = -inf - ts = -inf, so -inf > max_age is False, causing fail-open.
    result = check_rfx_evidence_freshness(
        evidence_records=[_rec()],
        reference_time_seconds=float("-inf"),
        max_age_seconds=3600.0,
    )
    assert "rfx_freshness_invalid_reference_time" in result["reason_codes_emitted"]
    assert result["signals"]["fresh_count"] == 0
    assert result["status"] == "stale"


def test_future_timestamp_flagged():
    # P1 fix: a record with timestamp_seconds > reference_time_seconds (negative age)
    # must emit rfx_freshness_future_timestamp and not be counted as fresh.
    result = check_rfx_evidence_freshness(
        evidence_records=[{"id": "future", "timestamp_seconds": _REF_TIME + 1000.0}],
        reference_time_seconds=_REF_TIME,
        max_age_seconds=3600.0,
    )
    assert "rfx_freshness_future_timestamp" in result["reason_codes_emitted"]
    assert result["signals"]["fresh_count"] == 0
    assert result["status"] == "stale"


def test_future_timestamp_not_in_stale_ids():
    # P1 fix: future-timestamp records appear in stale_record_ids (they are not fresh).
    result = check_rfx_evidence_freshness(
        evidence_records=[{"id": "future", "timestamp_seconds": _REF_TIME + 9999.0}],
        reference_time_seconds=_REF_TIME,
        max_age_seconds=3600.0,
    )
    assert "future" in result["stale_record_ids"]
