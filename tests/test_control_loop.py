from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.control_loop import (  # noqa: E402
    ControlLoopError,
    run_control_loop,
)


def _trace_context() -> Dict[str, Any]:
    return {
        "execution_id": "exec-001",
        "stage": "synthesis",
        "runtime_environment": "test",
    }


def _eval_summary() -> Dict[str, Any]:
    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "eval_run_id": "eval-run-20260321T120000Z",
        "pass_rate": 0.95,
        "failure_rate": 0.05,
        "drift_rate": 0.05,
        "reproducibility_score": 0.95,
        "system_status": "healthy",
    }


def _failure_eval_case() -> Dict[str, Any]:
    return {
        "artifact_type": "failure_eval_case",
        "schema_version": "1.0.0",
        "trace_id": "11111111-1111-4111-8111-111111111111",
        "eval_case_id": "failure-eval-case-001",
        "input_artifact_refs": ["artifact://runtime/evaluation_summary/trace-1"],
        "expected_output_spec": {
            "failure_modes": ["threshold_breach", "indeterminate"],
            "required_response": "block_and_escalate",
            "minimum_decision_count": 1,
        },
        "scoring_rubric": {
            "weights": {
                "corrective_action_completeness": 0.6,
                "reproducibility": 0.4,
            },
            "pass_threshold": 1.0,
        },
        "evaluation_type": "deterministic",
        "created_from": "failure_trace",
    }


def test_eval_summary_allow_path() -> None:
    result = run_control_loop(_eval_summary(), _trace_context())
    decision = result["evaluation_control_decision"]
    assert decision["decision"] == "allow"
    assert decision["system_response"] == "allow"
    assert result["control_trace"]["evaluation_path"] == "evaluation_control_from_eval_summary"


def test_eval_summary_deny_path() -> None:
    artifact = _eval_summary()
    artifact["reproducibility_score"] = 0.4
    result = run_control_loop(artifact, _trace_context())
    decision = result["evaluation_control_decision"]
    assert decision["decision"] == "deny"
    assert decision["system_response"] == "block"


def test_failure_eval_case_always_denies() -> None:
    result = run_control_loop(_failure_eval_case(), _trace_context())
    decision = result["evaluation_control_decision"]
    assert decision["decision"] == "deny"
    assert decision["rationale_code"] == "deny_failure_eval_case"
    assert result["control_trace"]["signal_type"] == "failure_eval_case"


def test_malformed_artifact_raises_error() -> None:
    malformed = {"artifact_type": "eval_summary", "eval_run_id": "only-id"}
    with pytest.raises(ControlLoopError, match="normalized signal missing required field"):
        run_control_loop(malformed, _trace_context())


def test_unknown_artifact_type_raises_error() -> None:
    with pytest.raises(ControlLoopError, match="unsupported artifact_type"):
        run_control_loop({"artifact_type": "unknown"}, _trace_context())
