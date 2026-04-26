"""Tests for the RFX adversarial reliability anti-gaming guard (Part 6)."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_adversarial_reliability_guard import (
    RFXAdversarialReliabilityError,
    assert_rfx_adversarial_reliability_guard,
)


_OBS_OK = {
    "obs_id": "obs-1",
    "trace_id": "trace-1",
    "execution_path_coverage": ["AEX", "PQX"],
    "artifact_linkage": ["lin:1"],
    "failure_logs": [],
    "completeness": "pass",
}

_SLO_OK = {"slo_id": "slo-1", "status": "within_budget"}


def test_clean_inputs_pass() -> None:
    assert_rfx_adversarial_reliability_guard(
        recent_failures=[],
        replay_results=[{"trace_id": "trace-1", "match": True}],
        obs=_OBS_OK,
        slo=_SLO_OK,
    )


def test_zero_failures_with_obs_failure_logs_blocks() -> None:
    obs = {**_OBS_OK, "failure_logs": [{"reason": "drift"}]}
    with pytest.raises(RFXAdversarialReliabilityError, match="rfx_suspicious_signal_suppression"):
        assert_rfx_adversarial_reliability_guard(
            recent_failures=[], replay_results=[], obs=obs, slo=_SLO_OK,
        )


def test_zero_failures_with_replay_mismatches_blocks() -> None:
    replays = [{"trace_id": "t", "match": False}]
    with pytest.raises(RFXAdversarialReliabilityError, match="rfx_metrics_inconsistency"):
        assert_rfx_adversarial_reliability_guard(
            recent_failures=[], replay_results=replays, obs=_OBS_OK, slo=_SLO_OK,
        )


def test_slo_ok_with_replay_mismatches_blocks() -> None:
    replays = [{"trace_id": "t", "match": False}]
    failures = [{"timestamp_seconds": 5, "reason_code": "x"}]  # avoid suppression code
    with pytest.raises(RFXAdversarialReliabilityError, match="rfx_metrics_inconsistency"):
        assert_rfx_adversarial_reliability_guard(
            recent_failures=failures, replay_results=replays, obs=_OBS_OK, slo=_SLO_OK,
        )


def test_slo_ok_with_burn_flag_no_failures_blocks() -> None:
    sneaky = {**_SLO_OK, "burn_rate_breach": True}
    with pytest.raises(RFXAdversarialReliabilityError, match="rfx_suspicious_signal_suppression"):
        assert_rfx_adversarial_reliability_guard(
            recent_failures=[], replay_results=[], obs=_OBS_OK, slo=sneaky,
        )


def test_slo_ok_with_obs_missing_slices_blocks() -> None:
    obs_missing = {k: v for k, v in _OBS_OK.items() if k != "failure_logs"}
    with pytest.raises(RFXAdversarialReliabilityError, match="rfx_missing_data_slice"):
        assert_rfx_adversarial_reliability_guard(
            recent_failures=[], replay_results=[], obs=obs_missing, slo=_SLO_OK,
        )


def test_slo_ok_with_no_obs_blocks() -> None:
    with pytest.raises(RFXAdversarialReliabilityError, match="rfx_missing_data_slice"):
        assert_rfx_adversarial_reliability_guard(
            recent_failures=[], replay_results=[], obs=None, slo=_SLO_OK,
        )


def test_failures_present_no_obs_failure_logs_passes() -> None:
    """Real failures with empty OBS failure_logs is *not* itself adversarial
    — it could simply mean those failures are recorded elsewhere. The guard
    only triggers on the inverse pattern (zero failures + non-empty logs)."""
    failures = [{"timestamp_seconds": 5, "reason_code": "x"}]
    assert_rfx_adversarial_reliability_guard(
        recent_failures=failures,
        replay_results=[{"trace_id": "t", "match": True}],
        obs=_OBS_OK,
        slo=_SLO_OK,
    )
