"""Deterministic tests for baseline gate decision module."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.runtime.baseline_gating import (  # noqa: E402
    BaselineGatingError,
    build_baseline_gate_decision,
)


def _policy() -> dict:
    return load_example("baseline_gate_policy")


def _drift(status: str = "no_drift") -> dict:
    drift = load_example("drift_detection_result")
    drift["drift_status"] = status
    drift["triggered_thresholds"] = []
    if status == "within_threshold":
        drift["triggered_thresholds"] = [
            {
                "dimension": "enforcement_action_delta",
                "severity": "warn",
                "value": 1,
                "threshold": 0,
            }
        ]
    if status in {"exceeds_threshold", "invalid_comparison"}:
        drift["triggered_thresholds"] = [
            {
                "dimension": "final_status_delta",
                "severity": "block",
                "value": 1,
                "threshold": 0,
            }
        ]
    return drift


def test_no_drift_maps_to_pass_allow() -> None:
    decision = build_baseline_gate_decision(_drift("no_drift"), _policy())
    assert decision["status"] == "pass"
    assert decision["enforcement_action"] == "allow"


def test_within_threshold_warn_band_maps_to_warn_flag() -> None:
    decision = build_baseline_gate_decision(_drift("within_threshold"), _policy())
    assert decision["status"] == "warn"
    assert decision["enforcement_action"] == "flag"


def test_exceeds_threshold_maps_to_block() -> None:
    decision = build_baseline_gate_decision(_drift("exceeds_threshold"), _policy())
    assert decision["status"] == "block"
    assert decision["enforcement_action"] == "block_promotion"


def test_invalid_comparison_maps_to_block() -> None:
    decision = build_baseline_gate_decision(_drift("invalid_comparison"), _policy())
    assert decision["status"] == "block"
    assert decision["enforcement_action"] == "block_promotion"


def test_malformed_drift_artifact_fails_closed() -> None:
    drift = _drift("no_drift")
    drift.pop("artifact_id")

    with pytest.raises(BaselineGatingError):
        build_baseline_gate_decision(drift, _policy())


def test_deterministic_repeated_output() -> None:
    drift = _drift("no_drift")
    left = build_baseline_gate_decision(copy.deepcopy(drift), _policy())
    right = build_baseline_gate_decision(copy.deepcopy(drift), _policy())
    assert left == right
