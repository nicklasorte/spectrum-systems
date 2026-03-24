"""Tests for BN.7 — strict BAF control integration boundary."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.contract_runtime import ContractRuntimeError  # noqa: E402
from spectrum_systems.modules.runtime.control_integration import (  # noqa: E402
    enforce_control_before_execution,
    generate_working_paper_with_control,
    run_simulation_with_control,
    summarize_control_integration,
)
from spectrum_systems.modules.runtime.control_loop import ControlLoopError  # noqa: E402
from spectrum_systems.modules.runtime.enforcement_engine import EnforcementError  # noqa: E402
from spectrum_systems.modules.runtime.evaluation_auto_generation import EvalCaseGenerationError  # noqa: E402


def _eval_summary_artifact() -> Dict[str, Any]:
    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "eval_run_id": "eval-run-20260322T000000Z",
        "pass_rate": 0.95,
        "failure_rate": 0.05,
        "drift_rate": 0.05,
        "reproducibility_score": 0.95,
        "system_status": "healthy",
    }


def _ctx(artifact: Any | None = None) -> Dict[str, Any]:
    return {
        "artifact": artifact if artifact is not None else _eval_summary_artifact(),
        "stage": "synthesis",
        "runtime_environment": "test",
    }


def _failure_eval_case_artifact() -> Dict[str, Any]:
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


def test_eval_summary_path_allows_and_emits_decision() -> None:
    result = enforce_control_before_execution(_ctx())
    assert result["continuation_allowed"] is True
    assert result["execution_status"] == "success"
    assert result["evaluation_control_decision"]["decision"] == "allow"
    assert result["enforcement_result"]["final_status"] == "allow"


def test_failure_eval_case_path_denies_and_blocks() -> None:
    artifact = _failure_eval_case_artifact()
    result = enforce_control_before_execution(_ctx(artifact=artifact))
    assert result["continuation_allowed"] is False
    assert result["execution_status"] == "blocked"
    assert result["enforcement_result"]["final_status"] == "deny"
    assert result["generated_failure_eval_case"]["artifact_type"] == "failure_eval_case"


def test_unsupported_artifact_type_raises_hard_error() -> None:
    artifact = {"artifact_type": "run_bundle", "schema_version": "1.0.0"}
    with pytest.raises(ContractRuntimeError, match="unsupported governed artifact_type"):
        enforce_control_before_execution(_ctx(artifact=artifact))


def test_non_dict_artifact_raises_hard_error() -> None:
    with pytest.raises(ContractRuntimeError, match="artifact must be a dict"):
        enforce_control_before_execution(_ctx(artifact="not-a-dict"))


def test_unknown_final_status_raises_and_never_allows() -> None:
    with patch(
        "spectrum_systems.modules.runtime.control_integration.enforce_control_decision",
        return_value={
            "final_status": "maybe",
            "input_decision_reference": "ecd-1",
            "enforcement_result_id": "enf-1",
        },
    ):
        with pytest.raises(ContractRuntimeError, match="unsupported enforcement_result.final_status"):
            enforce_control_before_execution(_ctx())


def test_control_loop_error_is_wrapped_as_contract_runtime_error() -> None:
    with patch(
        "spectrum_systems.modules.runtime.control_integration.run_control_loop",
        side_effect=ControlLoopError("boom"),
    ):
        with pytest.raises(ContractRuntimeError, match="control loop evaluation failed"):
            enforce_control_before_execution(_ctx())


def test_enforcement_error_is_wrapped_as_contract_runtime_error() -> None:
    with patch(
        "spectrum_systems.modules.runtime.control_integration.enforce_control_decision",
        side_effect=EnforcementError("boom"),
    ):
        with pytest.raises(ContractRuntimeError, match="enforcement mapping failed"):
            enforce_control_before_execution(_ctx())


def test_simulation_adapter_blocks_execution() -> None:
    called = []

    def sim_fn() -> str:
        called.append("ran")
        return "ok"

    result, integration = run_simulation_with_control(_ctx(artifact=_failure_eval_case_artifact()), sim_fn)

    assert result is None
    assert integration["continuation_allowed"] is False
    assert called == []


def test_working_paper_adapter_allows_execution() -> None:
    def gen_fn() -> Dict[str, str]:
        return {"paper": "ok"}

    paper, integration = generate_working_paper_with_control(_ctx(), gen_fn)
    assert integration["continuation_allowed"] is True
    assert paper == {"paper": "ok"}


def test_summarize_control_integration_is_structured() -> None:
    result = enforce_control_before_execution(_ctx(artifact=_failure_eval_case_artifact()))
    summary = summarize_control_integration(_ctx(), result)
    assert "BN.7" in summary
    assert "continuation_allowed" in summary
    assert "execution_status" in summary
    assert "Failure Eval Artifact" in summary


def test_blocked_execution_fails_closed_if_auto_generation_fails() -> None:
    with patch(
        "spectrum_systems.modules.runtime.control_integration.enforce_control_decision",
        return_value={
            "artifact_type": "enforcement_result",
            "schema_version": "1.1.0",
            "enforcement_result_id": "ENF-123",
            "timestamp": "2026-03-22T00:00:00Z",
            "trace_id": "44444444-4444-4444-8444-444444444444",
            "run_id": "eval-run-20260322T000000Z",
            "input_decision_reference": "ecd-1",
            "enforcement_action": "deny_execution",
            "final_status": "deny",
            "rationale_code": "deny_reliability_breach",
            "fail_closed": True,
            "enforcement_path": "baf_single_path",
            "provenance": {
                "source_artifact_type": "evaluation_control_decision",
                "source_artifact_id": "ecd-1",
            },
        },
    ), patch(
        "spectrum_systems.modules.runtime.control_integration.generate_failure_eval_case",
        side_effect=EvalCaseGenerationError("boom"),
    ):
        with pytest.raises(ContractRuntimeError, match="failure_eval_case generation required"):
            enforce_control_before_execution(_ctx())
