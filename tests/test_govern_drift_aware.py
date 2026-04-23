"""Tests for drift-aware admission gating in GOVERNSystem — RT-Loop-07 through RT-Loop-09."""

import pytest
from spectrum_systems.govern.govern import GOVERNSystem


@pytest.fixture
def govern():
    return GOVERNSystem()


def test_policy_check_blocks_on_critical_drift(govern):
    """RT-Loop-07: Critical drift signal blocks artifact admission."""
    artifact = {"artifact_type": "execution_slice", "artifact_id": "slice-001"}

    critical_drift_state = {
        "signals": [
            {"signal_type": "decision_divergence", "severity": "critical", "value": 0.25}
        ]
    }

    passed, reason = govern.policy_check(artifact=artifact, drift_state=critical_drift_state)

    assert not passed
    assert "critical" in reason.lower()
    assert "admission paused" in reason.lower()


def test_policy_check_allows_on_no_drift(govern):
    """RT-Loop-08: Empty drift signals allow normal admission."""
    artifact = {"artifact_type": "execution_slice", "artifact_id": "slice-002"}

    passed, reason = govern.policy_check(artifact=artifact, drift_state={"signals": []})

    assert passed
    assert "PASS" in reason


def test_policy_check_warns_on_warning_drift(govern):
    """RT-Loop-09: Warning-level drift logs but does not block admission."""
    artifact = {"artifact_type": "execution_slice", "artifact_id": "slice-003"}

    warning_drift_state = {
        "signals": [
            {"signal_type": "exception_rate", "severity": "warning", "value": 0.015}
        ]
    }

    passed, reason = govern.policy_check(artifact=artifact, drift_state=warning_drift_state)

    assert passed
    assert "PASS" in reason


def test_policy_check_no_drift_state_unchanged(govern):
    """Existing callers omitting drift_state still get normal policy_check behaviour."""
    artifact = {"artifact_type": "execution_slice", "artifact_id": "slice-004"}

    passed, reason = govern.policy_check(artifact=artifact)

    assert passed
    assert "PASS" in reason
