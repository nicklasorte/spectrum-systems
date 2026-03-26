from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.regression_harness import (  # noqa: E402
    InvalidSuiteError,
    MissingTraceError,
    RegressionHarnessError,
    run_regression_suite,
    run_trace_regression,
    validate_regression_run_result,
)


def _write_json(path: Path, payload: Dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _make_replay_result(*, replay_id: str = "r-1", trace_id: str = "trace-001") -> Dict[str, Any]:
    return {
        "artifact_type": "replay_result",
        "schema_version": "1.1.3",
        "replay_id": replay_id,
        "original_run_id": "run-original-1",
        "replay_run_id": "run-replay-1",
        "timestamp": "2026-03-26T00:00:00Z",
        "trace_id": trace_id,
        "input_artifact_reference": "eval_summary:artifact-1",
        "original_decision_reference": "decision-1",
        "original_enforcement_reference": "enforcement-1",
        "replay_decision_reference": "decision-r1",
        "replay_enforcement_reference": "enforcement-r1",
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
            "source_artifact_id": "artifact-1",
        },
    }


def _suite(tmp: Path, baseline_path: Path, current_path: Path) -> Path:
    suite = {
        "suite_id": "sre-04-suite",
        "suite_name": "SRE-04",
        "version": "1.0.0",
        "created_at": "2026-03-26T00:00:00Z",
        "description": "Regression lock",
        "traces": [
            {
                "trace_id": "trace-001",
                "expected_decision_status": "consistent",
                "minimum_reproducibility_score": 1.0,
                "tags": ["ci"],
                "baseline_replay_result_path": str(baseline_path),
                "current_replay_result_path": str(current_path),
            }
        ],
    }
    return _write_json(tmp / "suite.json", suite)


def test_successful_regression_pass_against_baseline(tmp_path: Path) -> None:
    baseline = _write_json(tmp_path / "baseline.json", _make_replay_result(replay_id="rb"))
    current = _write_json(tmp_path / "current.json", _make_replay_result(replay_id="rc"))

    result = run_regression_suite(_suite(tmp_path, baseline, current))

    assert result["overall_status"] == "pass"
    assert result["regression_status"] == "pass"
    assert result["results"][0]["mismatch_summary"] == []
    assert validate_regression_run_result(result) == []


def test_baseline_missing_fails_closed(tmp_path: Path) -> None:
    current = _write_json(tmp_path / "current.json", _make_replay_result(replay_id="rc"))
    missing = tmp_path / "missing-baseline.json"
    with pytest.raises(MissingTraceError, match="baseline artifact file not found"):
        run_regression_suite(_suite(tmp_path, missing, current))


def test_mismatched_replay_fails_and_emits_governed_result(tmp_path: Path) -> None:
    baseline = _make_replay_result(replay_id="rb")
    current = deepcopy(baseline)
    current["replay_id"] = "rc"
    current["replay_final_status"] = "deny"
    current["replay_decision"] = "deny"
    current["consistency_status"] = "mismatch"
    current["drift_detected"] = True

    baseline_path = _write_json(tmp_path / "baseline.json", baseline)
    current_path = _write_json(tmp_path / "current.json", current)

    result = run_regression_suite(_suite(tmp_path, baseline_path, current_path))

    assert result["overall_status"] == "fail"
    trace_result = result["results"][0]
    assert trace_result["passed"] is False
    assert trace_result["mismatch_summary"]
    assert trace_result["baseline_replay_result_id"] == "rb"
    assert trace_result["current_replay_result_id"] == "rc"


def test_incompatible_artifact_type_fails_closed(tmp_path: Path) -> None:
    baseline = _make_replay_result(replay_id="rb")
    baseline["artifact_type"] = "not_replay_result"
    baseline_path = _write_json(tmp_path / "baseline.json", baseline)
    current_path = _write_json(tmp_path / "current.json", _make_replay_result(replay_id="rc"))

    entry = {
        "trace_id": "trace-001",
        "baseline_replay_result_path": str(baseline_path),
        "current_replay_result_path": str(current_path),
    }
    with pytest.raises(RegressionHarnessError, match="schema validation failed"):
        run_trace_regression(entry)


def test_deterministic_same_input_same_regression_result_behavior(tmp_path: Path) -> None:
    baseline = _write_json(tmp_path / "baseline.json", _make_replay_result(replay_id="rb"))
    current = _write_json(tmp_path / "current.json", _make_replay_result(replay_id="rc"))
    suite_path = _suite(tmp_path, baseline, current)

    first = run_regression_suite(suite_path)
    second = run_regression_suite(suite_path)

    assert first["run_id"] == second["run_id"]
    assert first["results"][0]["comparison_digest"] == second["results"][0]["comparison_digest"]


def test_invalid_suite_missing_paths_fails_closed(tmp_path: Path) -> None:
    bad_suite = {
        "suite_id": "bad",
        "suite_name": "bad",
        "version": "1",
        "created_at": "2026-03-26T00:00:00Z",
        "description": "bad",
        "traces": [{"trace_id": "trace-001", "expected_decision_status": "consistent", "minimum_reproducibility_score": 1.0, "tags": []}],
    }
    suite_path = _write_json(tmp_path / "bad_suite.json", bad_suite)
    with pytest.raises(InvalidSuiteError):
        run_regression_suite(suite_path)
