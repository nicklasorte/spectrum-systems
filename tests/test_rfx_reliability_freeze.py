"""Tests for the RFX LOOP-07 reliability-freeze guard (Part 2)."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_failure_profile import (
    RFXFailureProfileThresholds,
)
from spectrum_systems.modules.runtime.rfx_reliability_freeze import (
    RFXReliabilityFreezeError,
    assert_rfx_reliability_posture,
)


def _failure(ts: float, code: str = "exec_error") -> dict:
    return {"timestamp_seconds": ts, "reason_code": code}


_OK_SLO = {
    "slo_id": "slo-1",
    "status": "within_budget",
    "obs_ref": "obs-1",
    "derived_from_obs": True,
}


def test_clean_posture_returns_profile() -> None:
    profile = assert_rfx_reliability_posture(
        recent_failures=[],
        replay_results=[{"trace_id": "t", "match": True}],
        window_seconds=60,
        slo=_OK_SLO,
    )
    assert profile["instability_score"] == 0.0


def test_burst_failure_freezes() -> None:
    failures = [_failure(80.0 + i) for i in range(5)]
    with pytest.raises(RFXReliabilityFreezeError) as exc:
        assert_rfx_reliability_posture(
            recent_failures=failures,
            replay_results=[],
            window_seconds=100,
            slo=_OK_SLO,
        )
    assert "rfx_burst_failure_detected" in str(exc.value)
    rec = exc.value.freeze_record
    assert rec is not None
    assert rec["pqx_execution_blocked"] is True
    assert rec["sel_enforcement_signal"] == "halt_requested"


def test_recurring_pattern_freezes() -> None:
    failures = [_failure(t, "schema_drift") for t in (10.0, 20.0, 30.0)]
    with pytest.raises(RFXReliabilityFreezeError) as exc:
        assert_rfx_reliability_posture(
            recent_failures=failures,
            replay_results=[],
            window_seconds=120,
            slo=_OK_SLO,
        )
    assert "rfx_recurring_failure_pattern_detected" in str(exc.value)


def test_replay_drift_freezes() -> None:
    replays = [{"trace_id": f"t{i}", "match": False} for i in range(3)]
    replays.append({"trace_id": "tok", "match": True})
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_replay_drift_detected"):
        assert_rfx_reliability_posture(
            recent_failures=[],
            replay_results=replays,
            window_seconds=60,
            slo=_OK_SLO,
        )


def test_instability_score_freezes_when_threshold_breached() -> None:
    failures = [_failure(80.0 + i, "code_a") for i in range(5)]
    replays = [{"trace_id": f"t{i}", "match": False} for i in range(8)]
    th = RFXFailureProfileThresholds(instability_score_block=0.4)
    with pytest.raises(RFXReliabilityFreezeError) as exc:
        assert_rfx_reliability_posture(
            recent_failures=failures,
            replay_results=replays,
            window_seconds=100,
            slo=_OK_SLO,
            thresholds=th,
        )
    msg = str(exc.value)
    assert "rfx_instability_detected" in msg


def test_slo_burn_freezes() -> None:
    bad_slo = {**_OK_SLO, "status": "over_budget"}
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_slo_burn_detected"):
        assert_rfx_reliability_posture(
            recent_failures=[],
            replay_results=[{"trace_id": "t", "match": True}],
            window_seconds=60,
            slo=bad_slo,
        )


def test_missing_slo_signals_unknown_state() -> None:
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_reliability_state_unknown"):
        assert_rfx_reliability_posture(
            recent_failures=[],
            replay_results=[],
            window_seconds=60,
            slo=None,
        )


def test_explicit_burn_flag_overrides_ok_status() -> None:
    sneaky_slo = {**_OK_SLO, "burn_rate_breach": True}
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_slo_burn_detected"):
        assert_rfx_reliability_posture(
            recent_failures=[],
            replay_results=[{"trace_id": "t", "match": True}],
            window_seconds=60,
            slo=sneaky_slo,
        )


def test_invalid_window_signals_unknown_state() -> None:
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_reliability_state_unknown"):
        assert_rfx_reliability_posture(
            recent_failures=[],
            replay_results=[],
            window_seconds=0,
            slo=_OK_SLO,
        )


def test_malformed_failure_row_freezes_with_deterministic_reason() -> None:
    """Codex P1 regression: a non-dict failure row must produce a
    deterministic ``rfx_malformed_telemetry_input`` reason instead of
    raising raw AttributeError/TypeError from downstream helpers."""
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_malformed_telemetry_input"):
        assert_rfx_reliability_posture(
            recent_failures=["bad-row"],
            replay_results=[],
            window_seconds=60,
            slo=_OK_SLO,
        )


def test_malformed_replay_row_freezes_with_deterministic_reason() -> None:
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_malformed_telemetry_input"):
        assert_rfx_reliability_posture(
            recent_failures=[],
            replay_results=[123, {"trace_id": "t", "match": True}],
            window_seconds=60,
            slo=_OK_SLO,
        )


def test_aggregated_reasons_contain_multiple_codes() -> None:
    failures = [_failure(t, "schema_drift") for t in (80.0, 85.0, 90.0)]
    replays = [{"trace_id": f"t{i}", "match": False} for i in range(3)]
    bad_slo = {**_OK_SLO, "status": "over_budget"}
    with pytest.raises(RFXReliabilityFreezeError) as exc:
        assert_rfx_reliability_posture(
            recent_failures=failures,
            replay_results=replays,
            window_seconds=100,
            slo=bad_slo,
        )
    msg = str(exc.value)
    for code in (
        "rfx_burst_failure_detected",
        "rfx_recurring_failure_pattern_detected",
        "rfx_replay_drift_detected",
        "rfx_slo_burn_detected",
    ):
        assert code in msg
