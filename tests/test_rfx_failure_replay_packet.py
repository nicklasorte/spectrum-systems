"""Tests for rfx_failure_replay_packet (RFX-N13)."""

from spectrum_systems.modules.runtime.rfx_failure_replay_packet import (
    build_rfx_failure_replay_packet,
)


def _full_record(**kw):
    base = {
        "failure_id": "fail-001",
        "reproduction_inputs": {"trigger": "missing_schema"},
        "expected_outcome": "schema_validation_error",
        "trace_ref": "trace-abc",
        "system_context": {"module": "pqx_execution_authority", "version": "1.0"},
    }
    base.update(kw)
    return base


# RT-N13: replay packet lacks minimal reproduction inputs → must fail.
def test_rt_n13_missing_inputs_fails():
    result = build_rfx_failure_replay_packet(
        failure_record={"failure_id": "x", "trace_ref": "t", "expected_outcome": "blocked",
                        "system_context": {"m": "mod"}}
    )
    assert "rfx_replay_missing_inputs" in result["reason_codes_emitted"]
    assert result["status"] == "incomplete"


def test_rt_n13_complete_packet_passes():
    result = build_rfx_failure_replay_packet(failure_record=_full_record())
    assert result["status"] == "complete"
    assert result["reason_codes_emitted"] == []


def test_empty_record_fails():
    result = build_rfx_failure_replay_packet(failure_record=None)
    assert "rfx_replay_packet_empty" in result["reason_codes_emitted"]


def test_missing_failure_id_flagged():
    result = build_rfx_failure_replay_packet(failure_record=_full_record(failure_id=""))
    assert "rfx_replay_missing_failure_id" in result["reason_codes_emitted"]


def test_missing_trace_ref_flagged():
    result = build_rfx_failure_replay_packet(failure_record=_full_record(trace_ref=None))
    assert "rfx_replay_missing_trace_ref" in result["reason_codes_emitted"]


def test_missing_expected_outcome_flagged():
    result = build_rfx_failure_replay_packet(failure_record=_full_record(expected_outcome=None))
    assert "rfx_replay_missing_expected" in result["reason_codes_emitted"]


def test_missing_system_context_flagged():
    result = build_rfx_failure_replay_packet(failure_record=_full_record(system_context=None))
    assert "rfx_replay_missing_system_context" in result["reason_codes_emitted"]


def test_packet_id_is_stable():
    r1 = build_rfx_failure_replay_packet(failure_record=_full_record())
    r2 = build_rfx_failure_replay_packet(failure_record=_full_record())
    assert r1["packet_id"] == r2["packet_id"]
    assert r1["packet_id"] is not None


def test_completeness_score_full():
    result = build_rfx_failure_replay_packet(failure_record=_full_record())
    assert result["signals"]["completeness_score"] == 1.0


def test_artifact_type():
    result = build_rfx_failure_replay_packet(failure_record=_full_record())
    assert result["artifact_type"] == "rfx_failure_replay_packet"


def test_numeric_failure_id_does_not_raise():
    # P1 fix: numeric failure_id from JSON payloads must not raise AttributeError.
    result = build_rfx_failure_replay_packet(failure_record=_full_record(failure_id=42))
    assert result["artifact_type"] == "rfx_failure_replay_packet"
    assert result["failure_id"] == "42"


def test_whitespace_only_trace_ref_flagged():
    # P1 fix: whitespace-only trace_ref must be treated as absent.
    result = build_rfx_failure_replay_packet(failure_record=_full_record(trace_ref="   "))
    assert "rfx_replay_missing_trace_ref" in result["reason_codes_emitted"]
    assert result["status"] == "incomplete"
