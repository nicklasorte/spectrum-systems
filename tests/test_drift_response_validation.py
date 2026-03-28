"""Tests for VAL-09 drift response validation."""

from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.governance.drift_response_validation import (
    DriftResponseValidationError,
    run_drift_response_validation,
)


def _payload() -> dict:
    replay = load_example("replay_result")
    replay["consistency_status"] = "match"
    replay["drift_detected"] = False
    replay["failure_reason"] = None
    return {
        "replay_results": [copy.deepcopy(replay)],
        "baseline_gate_policy": load_example("baseline_gate_policy"),
    }


def _threshold_map(result: dict) -> dict:
    return {entry["case_id"]: entry for entry in result["threshold_crossings"]}


def test_gradual_drift_increase_detection_is_monotonic() -> None:
    result = run_drift_response_validation(_payload())
    progressive = [p for p in result["detection_points"] if p["case_id"].startswith("VAL09-A-")]
    strengths = [p["signal_strength"] for p in sorted(progressive, key=lambda x: x["run_index"])]
    assert strengths == sorted(strengths)
    assert strengths[-1] > strengths[0]


def test_threshold_crossing_triggers_warning_or_freeze() -> None:
    result = run_drift_response_validation(_payload())
    crossing = _threshold_map(result)["VAL09-B"]
    assert crossing["crossed"] is True
    assert crossing["actual_response"] in {"warn", "freeze", "block"}


def test_late_stage_drift_blocks() -> None:
    result = run_drift_response_validation(_payload())
    crossing = _threshold_map(result)["VAL09-C"]
    assert crossing["crossed"] is True
    assert crossing["actual_response"] == "block"


def test_flat_baseline_has_no_false_drift() -> None:
    result = run_drift_response_validation(_payload())
    case_d = [d for d in result["detection_points"] if d["case_id"] == "VAL09-D"][0]
    assert case_d["signal_strength"] == 0.0
    assert case_d["drift_status"] == "no_drift"


def test_insufficient_input_fails_closed() -> None:
    with pytest.raises(DriftResponseValidationError, match="replay_results"):
        run_drift_response_validation({"replay_results": [], "baseline_gate_policy": load_example("baseline_gate_policy")})


def test_final_status_passes_without_missed_or_delayed_responses() -> None:
    result = run_drift_response_validation(_payload())
    assert result["missed_detection"] is False
    assert result["delayed_response"] is False
    assert result["incorrect_response"] is False
    assert result["final_status"] == "PASSED"
