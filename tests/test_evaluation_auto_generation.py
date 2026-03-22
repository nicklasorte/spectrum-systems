"""Tests for deterministic failure → eval_case auto-generation."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import patch

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.evaluation_auto_generation import (
    EvalCaseGenerationError,
    generate_eval_case_from_failure,
)


def _artifact(**overrides: Any) -> Dict[str, Any]:
    base = {
        "artifact_type": "eval_summary",
        "artifact_id": "ART-001",
        "trace_id": "trace-001",
        "pass_rate": 0.9,
        "drift_rate": 0.1,
        "reproducibility_score": 0.95,
        "decision": "allow",
    }
    base.update(overrides)
    return base


def _trace() -> Dict[str, Any]:
    return {"trace_id": "trace-ctx-001", "run_id": "run-001"}


def test_execution_failure_maps_to_eval_case() -> None:
    result = generate_eval_case_from_failure(_artifact(), {"status": "error"}, _trace())
    assert result["failure_mode"] == "execution_failure"
    assert result["expected_behavior"] == "deny"
    assert result["observed_behavior"] == "deny"
    validate_artifact(result, "eval_case")


def test_indeterminate_maps_to_eval_case() -> None:
    result = generate_eval_case_from_failure(
        _artifact(decision="indeterminate"),
        {"status": "indeterminate"},
        _trace(),
    )
    assert result["failure_mode"] == "indeterminate"
    assert result["observed_behavior"] == "indeterminate"
    validate_artifact(result, "eval_case")


def test_threshold_breach_maps_to_eval_case() -> None:
    result = generate_eval_case_from_failure(
        _artifact(decision="deny"),
        {"status": "deny"},
        _trace(),
    )
    assert result["failure_mode"] == "threshold_breach"
    validate_artifact(result, "eval_case")


def test_drift_detected_maps_to_eval_case() -> None:
    result = generate_eval_case_from_failure(
        _artifact(drift_signal={"delta": 0.4}),
        {"status": "deny", "drift_signal": {"delta": 0.4}},
        _trace(),
    )
    assert result["failure_mode"] == "drift_detected"
    validate_artifact(result, "eval_case")


def test_schema_violation_maps_to_eval_case() -> None:
    result = generate_eval_case_from_failure(
        _artifact(),
        {"status": "schema_violation", "validators_failed": ["artifact_schema"]},
        _trace(),
    )
    assert result["failure_mode"] == "schema_violation"
    validate_artifact(result, "eval_case")


def test_generation_is_deterministic_for_same_structured_inputs() -> None:
    with patch("spectrum_systems.modules.runtime.evaluation_auto_generation._now_iso", return_value="2026-03-21T23:00:00Z"):
        with patch("spectrum_systems.modules.runtime.evaluation_auto_generation.uuid.uuid4") as mock_uuid:
            class _U:
                def __str__(self) -> str:
                    return "33333333-3333-4333-8333-333333333333"

            mock_uuid.return_value = _U()
            first = generate_eval_case_from_failure(_artifact(), {"status": "error"}, _trace())
            second = generate_eval_case_from_failure(_artifact(), {"status": "error"}, _trace())

    assert first == second


def test_fail_closed_on_missing_required_fields() -> None:
    with pytest.raises(EvalCaseGenerationError):
        generate_eval_case_from_failure({"artifact_type": "eval_summary"}, {"status": "error"}, {"trace_id": "t-only"})


def test_reproducibility_requires_seed_when_seed_present() -> None:
    result = generate_eval_case_from_failure(
        _artifact(seed=7),
        {"status": "error"},
        _trace(),
    )
    assert result["reproducibility"] == {
        "deterministic": False,
        "requires_seed": True,
        "seed_value": 7,
    }
    validate_artifact(result, "eval_case")
