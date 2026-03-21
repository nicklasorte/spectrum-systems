"""Tests for BAH drift_detection_engine."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.drift_detection_engine import (  # noqa: E402
    DriftDetectionError,
    run_drift_detection,
    validate_drift_detection_result,
)


def _artifact(*, replay_id: str = "replay-001", value: float = 10.0) -> dict:
    return {
        "artifact_type": "replay_result",
        "schema_version": "1.0.0",
        "replay_id": replay_id,
        "source_trace_id": "trace-001",
        "replayed_at": "2026-03-21T00:00:00Z",
        "status": "success",
        "prerequisites_valid": True,
        "prerequisite_errors": [],
        "steps_executed": [
            {
                "step_index": 0,
                "span_name": "operation",
                "original_span_id": "span-001",
                "status": "ok",
                "replayed_at": "2026-03-21T00:00:00Z",
            }
        ],
        "output_comparison": {
            "compared": True,
            "matched": True,
            "differences": [
                {
                    "field": "metric",
                    "original_value": value,
                    "replay_value": value,
                }
            ],
        },
        "determinism_notes": [],
        "context": {"run_id": "run-001"},
    }


def test_identical_artifacts_no_drift():
    replay = _artifact(replay_id="replay-100", value=10.0)
    baseline = deepcopy(replay)
    result = run_drift_detection(replay, baseline)
    assert result["drift_status"] == "no_drift"
    assert result["drift_metrics"]["field_mismatches"] == 0


def test_within_tolerance_no_drift():
    replay = _artifact(replay_id="replay-101", value=10.01)
    baseline = _artifact(replay_id="replay-001", value=10.0)
    result = run_drift_detection(replay, baseline, config={"abs_tolerance": 0.05, "rel_tolerance": 0.02})
    assert result["drift_status"] == "no_drift"


def test_numeric_exceeds_tolerance_detected():
    replay = _artifact(replay_id="replay-102", value=11.0)
    baseline = _artifact(replay_id="replay-001", value=10.0)
    result = run_drift_detection(replay, baseline, config={"abs_tolerance": 0.1, "rel_tolerance": 0.01})
    assert result["drift_status"] == "drift_detected"
    assert "numeric_tolerance_exceeded" in result["thresholds_triggered"]


def test_config_without_required_fields_is_valid():
    replay = _artifact(replay_id="replay-102a", value=10.01)
    baseline = _artifact(replay_id="replay-001", value=10.0)
    result = run_drift_detection(replay, baseline, config={"abs_tolerance": 0.05, "rel_tolerance": 0.02})
    assert result["drift_status"] == "no_drift"


def test_config_required_fields_empty_list_is_valid():
    replay = _artifact(replay_id="replay-102b", value=10.01)
    baseline = _artifact(replay_id="replay-001", value=10.0)
    result = run_drift_detection(
        replay,
        baseline,
        config={"abs_tolerance": 0.05, "rel_tolerance": 0.02, "required_fields": []},
    )
    assert result["drift_status"] == "no_drift"


def test_config_required_fields_none_normalized_to_empty_list():
    replay = _artifact(replay_id="replay-102c", value=10.01)
    baseline = _artifact(replay_id="replay-001", value=10.0)
    result = run_drift_detection(
        replay,
        baseline,
        config={"abs_tolerance": 0.05, "rel_tolerance": 0.02, "required_fields": None},
    )
    assert result["drift_status"] == "no_drift"


@pytest.mark.parametrize("invalid_required_fields", [(), "field.path"])
def test_config_invalid_required_fields_type_fails(invalid_required_fields):
    replay = _artifact(replay_id="replay-102d", value=10.01)
    baseline = _artifact(replay_id="replay-001", value=10.0)
    with pytest.raises(DriftDetectionError, match="config.required_fields must be a list of field paths"):
        run_drift_detection(
            replay,
            baseline,
            config={
                "abs_tolerance": 0.05,
                "rel_tolerance": 0.02,
                "required_fields": invalid_required_fields,
            },
        )


def test_missing_field_detected():
    replay = _artifact(replay_id="replay-103", value=10.0)
    baseline = _artifact(replay_id="replay-001", value=10.0)
    baseline["context"]["baseline_only_field"] = "present"
    result = run_drift_detection(replay, baseline)
    assert result["drift_status"] == "drift_detected"
    assert "missing_fields" in result["thresholds_triggered"]


def test_extra_field_detected():
    replay = _artifact(replay_id="replay-104", value=10.0)
    baseline = _artifact(replay_id="replay-001", value=10.0)
    replay["context"]["new_metric"] = 1
    result = run_drift_detection(replay, baseline)
    assert result["drift_status"] == "drift_detected"
    assert "extra_fields" in result["thresholds_triggered"]


def test_missing_baseline_indeterminate():
    replay = _artifact(replay_id="replay-105", value=10.0)
    result = run_drift_detection(replay, None)
    assert result["drift_status"] == "indeterminate"
    assert result["baseline_id"] == "baseline_missing"


def test_invalid_schema_fails_closed():
    replay = _artifact(replay_id="replay-106", value=10.0)
    baseline = _artifact(replay_id="replay-001", value=10.0)
    replay["schema_version"] = "9.9.9"
    with pytest.raises(DriftDetectionError):
        run_drift_detection(replay, baseline)


def test_malformed_input_fails_closed():
    baseline = _artifact(replay_id="replay-001", value=10.0)
    with pytest.raises(DriftDetectionError):
        run_drift_detection("not-a-dict", baseline)


def test_output_schema_validation_passes_for_valid_result():
    replay = _artifact(replay_id="replay-107", value=10.0)
    baseline = _artifact(replay_id="replay-001", value=10.0)
    result = run_drift_detection(replay, baseline)
    assert validate_drift_detection_result(result) == []
