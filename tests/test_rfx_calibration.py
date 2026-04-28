"""Tests for RFX-13 calibration + confidence control."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_calibration import (
    RFXCalibrationError,
    assert_rfx_calibration,
)


def test_high_confidence_failed_outcome_flags() -> None:
    samples = [
        {"confidence": 0.95, "outcome": "incorrect", "evidence_refs": ["e-1"]},
    ]
    with pytest.raises(RFXCalibrationError, match="rfx_overconfidence_risk"):
        assert_rfx_calibration(samples=samples)


def test_confidence_without_evidence_blocks() -> None:
    samples = [
        {"confidence": 0.9, "outcome": "correct", "evidence_refs": []},
    ]
    with pytest.raises(RFXCalibrationError, match="rfx_confidence_without_evidence"):
        assert_rfx_calibration(samples=samples)


def test_calibrated_confidence_passes() -> None:
    samples = [
        {"confidence": 0.9, "outcome": "correct", "evidence_refs": ["e-1"]},
        {"confidence": 0.5, "outcome": "correct", "evidence_refs": ["e-2"]},
    ]
    record = assert_rfx_calibration(samples=samples)
    assert record["artifact_type"] == "rfx_calibration_record"


def test_drift_across_runs_detected() -> None:
    historical = [{"confidence": 0.5, "outcome": "correct", "evidence_refs": ["e-h"]}]
    samples = [{"confidence": 0.95, "outcome": "correct", "evidence_refs": ["e-1"]}]
    with pytest.raises(RFXCalibrationError, match="rfx_confidence_drift_detected"):
        assert_rfx_calibration(samples=samples, historical_samples=historical, drift_delta=0.2)


def test_underconfidence_signal_recorded() -> None:
    samples = [{"confidence": 0.2, "outcome": "correct", "evidence_refs": ["e-1"]}]
    record = assert_rfx_calibration(samples=samples)
    assert record["underconfidence_events"]


# ---------------------------------------------------------------------------
# RT-21 red-team: high-confidence recommendation without evidence refs
# ---------------------------------------------------------------------------


def test_rt21_red_team_high_confidence_no_evidence_blocks_then_revalidates() -> None:
    bad = [{"confidence": 0.95, "outcome": "correct", "evidence_refs": []}]
    with pytest.raises(RFXCalibrationError, match="rfx_confidence_without_evidence"):
        assert_rfx_calibration(samples=bad)

    fixed = [{"confidence": 0.95, "outcome": "correct", "evidence_refs": ["e-1", "e-2"]}]
    record = assert_rfx_calibration(samples=fixed)
    assert record["artifact_type"] == "rfx_calibration_record"
