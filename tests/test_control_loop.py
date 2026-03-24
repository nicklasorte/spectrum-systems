from __future__ import annotations

import copy
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
import spectrum_systems.modules.runtime.control_loop as control_loop  # noqa: E402


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
        "schema_version": "1.1.0",
        "trace_id": "11111111-1111-4111-8111-111111111111",
        "eval_case_id": "fec-001",
        "created_at": "2026-03-24T00:00:00Z",
        "source_run_id": "agrun-001",
        "source_artifact_type": "agent_failure_record",
        "source_artifact_id": "afr-001",
        "failure_class": "runtime_failure",
        "failure_stage": "runtime_boundary",
        "triggering_condition": "governed_runtime_failure_artifact",
        "normalized_inputs": {
            "stage": "eval",
            "runtime_environment": "agent_golden_path",
            "continuation_allowed": False,
            "publication_blocked": True,
            "decision_blocked": True,
            "human_review_required": False,
            "escalation_triggered": True,
        },
        "expected_system_behavior": "system_must_fail_closed_and_emit_failure_artifact",
        "observed_system_behavior": "runtime_failed_with_governed_failure_artifact",
        "evaluation_goal": "controller_must_deny_and_require_remediation",
        "pass_criteria": {
            "decision_must_remain_denied": True,
            "review_or_remediation_required": True,
            "replay_reproducible": True,
        },
        "provenance": {
            "source_artifact_ref": "agent_failure_record:afr-001",
            "generation_path": "ag_runtime_failure_eval_auto_generation",
            "generated_by_module": "spectrum_systems.modules.runtime.evaluation_auto_generation",
        },
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


def test_failure_eval_case_decision_id_is_deterministic_for_identical_inputs() -> None:
    artifact = _failure_eval_case()
    first = run_control_loop(artifact, _trace_context())["evaluation_control_decision"]
    second = run_control_loop(copy.deepcopy(artifact), _trace_context())["evaluation_control_decision"]
    assert first["decision_id"] == second["decision_id"]


def test_failure_eval_case_created_at_can_vary_without_changing_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _failure_eval_case()
    monkeypatch.setattr(control_loop, "_now_iso", lambda: "2026-03-23T00:00:00Z")
    first = run_control_loop(artifact, _trace_context())["evaluation_control_decision"]
    monkeypatch.setattr(control_loop, "_now_iso", lambda: "2026-03-23T00:01:00Z")
    second = run_control_loop(artifact, _trace_context())["evaluation_control_decision"]

    assert first["created_at"] != second["created_at"]
    assert first["decision_id"] == second["decision_id"]


def test_malformed_artifact_raises_error() -> None:
    malformed = {"artifact_type": "eval_summary", "eval_run_id": "only-id"}
    with pytest.raises(ControlLoopError, match="normalized signal missing required field"):
        run_control_loop(malformed, _trace_context())


def test_unknown_artifact_type_raises_error() -> None:
    with pytest.raises(ControlLoopError, match="unsupported artifact_type"):
        run_control_loop({"artifact_type": "unknown"}, _trace_context())
