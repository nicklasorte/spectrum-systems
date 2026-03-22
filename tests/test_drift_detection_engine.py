"""Tests for BAH fail-closed deterministic drift detection."""

from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.drift_detection_engine import (  # noqa: E402
    DriftDetectionError,
    detect_drift,
)


def _replay_result() -> dict:
    return {
        "artifact_type": "replay_result",
        "schema_version": "1.1.0",
        "replay_id": "RPL-test-001",
        "original_run_id": "eval-run-001",
        "replay_run_id": "eval-run-001",
        "timestamp": "2026-03-22T00:00:00Z",
        "trace_id": "trace-eval-001",
        "input_artifact_reference": "eval_summary:eval-run-001",
        "original_decision_reference": "ECD-eval-run-001-ALLOW",
        "original_enforcement_reference": "ENF-000000000001",
        "replay_decision_reference": "ECD-eval-run-001-ALLOW",
        "replay_enforcement_reference": "ENF-000000000002",
        "replay_decision": "allow",
        "replay_enforcement_action": "allow_execution",
        "replay_final_status": "allow",
        "original_enforcement_action": "allow_execution",
        "original_final_status": "allow",
        "consistency_status": "match",
        "drift_detected": False,
        "failure_reason": None,
        "replay_path": "bag_replay_engine",
        "provenance": {
            "source_artifact_type": "eval_summary",
            "source_artifact_id": "eval-run-001",
        },
    }


def _expected_id(source_run_id: str, replay_run_id: str, drift_type: str) -> str:
    return hashlib.sha256(f"{source_run_id}{replay_run_id}{drift_type}".encode("utf-8")).hexdigest()


def test_perfect_match_returns_no_drift() -> None:
    replay = _replay_result()
    replay_before = copy.deepcopy(replay)

    result = detect_drift(replay)

    assert replay == replay_before
    assert result["drift_detected"] is False
    assert result["drift_type"] == "none"
    assert result["drift_severity"] == "none"
    assert result["drift_result_id"] == _expected_id("eval-run-001", "eval-run-001", "none")


def test_status_mismatch_returns_high_severity() -> None:
    replay = _replay_result()
    replay["replay_final_status"] = "deny"
    replay["consistency_status"] = "mismatch"
    replay["drift_detected"] = True

    result = detect_drift(replay)

    assert result["drift_type"] == "status_mismatch"
    assert result["drift_severity"] == "high"


def test_action_mismatch_returns_medium_severity() -> None:
    replay = _replay_result()
    replay["replay_enforcement_action"] = "deny_execution"
    replay["consistency_status"] = "mismatch"
    replay["drift_detected"] = True

    result = detect_drift(replay)

    assert result["drift_type"] == "action_mismatch"
    assert result["drift_severity"] == "medium"


def test_missing_original_returns_critical() -> None:
    replay = _replay_result()
    del replay["original_enforcement_action"]

    result = detect_drift(replay)

    assert result["drift_type"] == "missing_original"
    assert result["drift_severity"] == "critical"


def test_missing_replay_returns_critical() -> None:
    replay = _replay_result()
    del replay["replay_enforcement_action"]

    result = detect_drift(replay)

    assert result["drift_type"] == "missing_replay"
    assert result["drift_severity"] == "critical"


def test_indeterminate_returns_high_severity() -> None:
    replay = _replay_result()
    replay["consistency_status"] = "indeterminate"
    replay["failure_reason"] = "REPLAY_EXECUTION_FAILED:RuntimeError"

    result = detect_drift(replay)

    assert result["drift_type"] == "indeterminate"
    assert result["drift_severity"] == "high"


def test_invalid_input_raises_error() -> None:
    replay = _replay_result()
    replay["replay_final_status"] = "unknown-status"

    with pytest.raises(DriftDetectionError):
        detect_drift(replay)
