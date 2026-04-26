"""Tests for the RFX LOOP-08 telemetry-enforced SLO gate (Part 4)."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_telemetry_slo_gate import (
    RFXTelemetrySLOError,
    assert_rfx_telemetry_slo_eligible,
)


_OBS_FULL = {
    "obs_id": "obs-1",
    "trace_id": "trace-1",
    "execution_path_coverage": ["AEX", "PQX", "EVL", "TPA", "CDE", "SEL"],
    "artifact_linkage": ["lin:001", "rep:001"],
    "failure_logs": [],
    "completeness": "pass",
}

_SLO_OK_DERIVED = {
    "slo_id": "slo-1",
    "status": "within_budget",
    "obs_ref": "obs-1",
}


def test_full_obs_and_derived_slo_passes() -> None:
    # Must not raise
    assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=_SLO_OK_DERIVED)


def test_missing_obs_blocks() -> None:
    with pytest.raises(RFXTelemetrySLOError, match="rfx_missing_obs_telemetry"):
        assert_rfx_telemetry_slo_eligible(obs=None, slo=_SLO_OK_DERIVED)


def test_missing_slo_blocks() -> None:
    with pytest.raises(RFXTelemetrySLOError, match="rfx_missing_slo"):
        assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=None)


@pytest.mark.parametrize("missing_key", [
    "trace_id", "execution_path_coverage", "artifact_linkage", "failure_logs",
])
def test_obs_missing_required_field_blocks(missing_key: str) -> None:
    obs = {k: v for k, v in _OBS_FULL.items() if k != missing_key}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_incomplete"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_obs_completeness_must_be_pass() -> None:
    obs = {**_OBS_FULL, "completeness": "incomplete"}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_incomplete"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_fake_slo_ok_with_missing_obs_segments_fires_inconsistency() -> None:
    """SLO posture ok + OBS missing trace segments → cross-check fires."""
    obs = {**_OBS_FULL}
    obs.pop("trace_id")
    with pytest.raises(RFXTelemetrySLOError) as exc:
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)
    msg = str(exc.value)
    assert "rfx_obs_incomplete" in msg
    assert "rfx_slo_inconsistent_with_obs" in msg


def test_slo_without_obs_ref_fires_inconsistency() -> None:
    independent_slo = {"slo_id": "slo-1", "status": "within_budget"}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_slo_inconsistent_with_obs"):
        assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=independent_slo)


def test_slo_burn_status_blocks_directly() -> None:
    burning_slo = {"slo_id": "slo-1", "status": "over_budget", "obs_ref": "obs-1"}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_slo_block"):
        assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=burning_slo)


def test_obs_with_completeness_true_passes() -> None:
    obs = {**_OBS_FULL, "completeness": True}
    # Must not raise
    assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


# ---------------------------------------------------------------------------
# Documented OBS-source aliases must all be honored by _slo_derived_from_obs.
# ---------------------------------------------------------------------------


def test_slo_with_derived_from_obs_string_alias_passes() -> None:
    """The documented bare ``derived_from_obs: "<obs_id>"`` alias must be
    accepted as an OBS source reference (regression for Codex P2 finding)."""
    slo = {"slo_id": "slo-1", "status": "within_budget", "derived_from_obs": "obs-1"}
    # Must not raise.
    assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=slo)


def test_slo_with_source_obs_id_alias_passes() -> None:
    slo = {"slo_id": "slo-1", "status": "within_budget", "source_obs_id": "obs-1"}
    assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=slo)


def test_slo_with_derived_from_obs_id_alias_passes() -> None:
    slo = {"slo_id": "slo-1", "status": "within_budget", "derived_from_obs_id": "obs-1"}
    assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=slo)


def test_slo_with_derived_from_obs_bool_alone_is_not_enough() -> None:
    """Boolean ``derived_from_obs=True`` without a matching id alias must
    NOT count as derived — fail-closed against an unverifiable claim."""
    slo = {"slo_id": "slo-1", "status": "within_budget", "derived_from_obs": True}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_slo_inconsistent_with_obs"):
        assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=slo)


def test_slo_with_derived_from_obs_string_mismatch_blocks() -> None:
    slo = {"slo_id": "slo-1", "status": "within_budget", "derived_from_obs": "obs-other"}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_slo_inconsistent_with_obs"):
        assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=slo)
