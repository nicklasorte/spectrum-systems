"""Deterministic tests for runtime baseline drift detection."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.runtime.drift_detection import (  # noqa: E402
    DriftDetectionError,
    build_drift_detection_result,
)


def _replay() -> dict:
    return load_example("replay_result")


def _policy() -> dict:
    return load_example("baseline_gate_policy")


def test_identical_baseline_returns_no_drift() -> None:
    current = _replay()
    baseline = copy.deepcopy(current)

    result = build_drift_detection_result(current, baseline, _policy())

    assert result["drift_status"] == "no_drift"
    assert result["triggered_thresholds"] == []


def test_delta_within_threshold_returns_within_threshold() -> None:
    current = _replay()
    baseline = copy.deepcopy(current)
    current["replay_enforcement_action"] = "deny_execution"
    current["consistency_status"] = "mismatch"
    current["drift_detected"] = True

    policy = _policy()
    policy["thresholds"]["enforcement_action_delta"]["block_if_greater_than"] = 2
    policy["thresholds"]["consistency_mismatch_delta"]["block_if_greater_than"] = 2
    policy["thresholds"]["drift_detected_delta"]["block_if_greater_than"] = 2

    result = build_drift_detection_result(current, baseline, policy)

    assert result["drift_status"] == "within_threshold"
    assert any(item["severity"] == "warn" for item in result["triggered_thresholds"])


def test_delta_exceeds_threshold_returns_exceeds_threshold() -> None:
    current = _replay()
    baseline = copy.deepcopy(current)
    current["replay_final_status"] = "deny"
    current["consistency_status"] = "mismatch"
    current["drift_detected"] = True

    result = build_drift_detection_result(current, baseline, _policy())

    assert result["drift_status"] == "exceeds_threshold"


def test_missing_baseline_metric_fails_closed() -> None:
    current = _replay()
    baseline = copy.deepcopy(current)
    baseline.pop("replay_enforcement_action")

    with pytest.raises(DriftDetectionError):
        build_drift_detection_result(current, baseline, _policy())


def test_malformed_policy_fails_closed() -> None:
    current = _replay()
    baseline = copy.deepcopy(current)
    policy = _policy()
    policy.pop("thresholds")

    with pytest.raises(DriftDetectionError):
        build_drift_detection_result(current, baseline, policy)


def test_deterministic_repeated_run_output() -> None:
    current = _replay()
    baseline = copy.deepcopy(current)

    left = build_drift_detection_result(current, baseline, _policy())
    right = build_drift_detection_result(current, baseline, _policy())

    assert left == right
