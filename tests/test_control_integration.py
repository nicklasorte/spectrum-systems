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
from tests.helpers.replay_result_builder import make_canonical_replay_result  # noqa: E402


def _replay_result_artifact(*, replay_success_rate: float = 0.95, drift_rate: float = 0.05, consistency_status: str = "match") -> Dict[str, Any]:
    artifact = make_canonical_replay_result(
        replay_id="RPL-control-integration-001",
        trace_id="44444444-4444-4444-8444-444444444444",
        replay_run_id="eval-run-20260322T000000Z",
    )
    artifact["observability_metrics"]["metrics"]["replay_success_rate"] = replay_success_rate
    artifact["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = drift_rate
    for objective in artifact["error_budget_status"]["objectives"]:
        metric_name = objective["metric_name"]
        if metric_name == "replay_success_rate":
            objective["observed_value"] = replay_success_rate
        if metric_name == "drift_exceed_threshold_rate":
            objective["observed_value"] = drift_rate
    artifact["consistency_status"] = consistency_status
    artifact["drift_detected"] = consistency_status == "mismatch"
    artifact["failure_reason"] = None
    return artifact


def _ctx(artifact: Any | None = None) -> Dict[str, Any]:
    return {
        "artifact": artifact if artifact is not None else _replay_result_artifact(),
        "stage": "synthesis",
        "runtime_environment": "test",
    }


def test_replay_result_path_allows_and_emits_decision() -> None:
    result = enforce_control_before_execution(_ctx())
    assert result["continuation_allowed"] is True
    assert result["execution_status"] == "success"
    assert result["evaluation_control_decision"]["decision"] == "allow"
    assert result["enforcement_result"]["final_status"] == "allow"


def test_replay_result_block_path_denies_and_blocks() -> None:
    artifact = _replay_result_artifact(replay_success_rate=0.3, drift_rate=0.9, consistency_status="mismatch")
    result = enforce_control_before_execution(_ctx(artifact=artifact))
    assert result["continuation_allowed"] is False
    assert result["execution_status"] == "blocked"
    assert result["enforcement_result"]["final_status"] == "deny"
    assert result["generated_failure_eval_case"]["artifact_type"] == "failure_eval_case"


def test_unsupported_artifact_type_raises_hard_error() -> None:
    artifact = {"artifact_type": "eval_summary", "schema_version": "1.0.0"}
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


def test_missing_error_budget_status_fails_closed() -> None:
    artifact = _replay_result_artifact()
    artifact.pop("error_budget_status")
    with pytest.raises(ContractRuntimeError, match="missing required error_budget_status"):
        enforce_control_before_execution(_ctx(artifact=artifact))


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

    result, integration = run_simulation_with_control(
        _ctx(artifact=_replay_result_artifact(replay_success_rate=0.3, drift_rate=0.9, consistency_status="mismatch")),
        sim_fn,
    )

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
    result = enforce_control_before_execution(
        _ctx(artifact=_replay_result_artifact(replay_success_rate=0.3, drift_rate=0.9, consistency_status="mismatch"))
    )
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
        result = enforce_control_before_execution(_ctx())

    assert result["continuation_allowed"] is False
    assert result["execution_status"] == "blocked"
    assert result["generated_failure_eval_case_error"]["error_type"] == "EvalCaseGenerationError"
    assert result["generated_failure_eval_case_error"]["message"] == "boom"


def test_require_review_is_blocked_for_publication_and_decision() -> None:
    with patch(
        "spectrum_systems.modules.runtime.control_integration.enforce_control_decision",
        return_value={
            "artifact_type": "enforcement_result",
            "schema_version": "1.1.0",
            "enforcement_result_id": "ENF-REVIEW-1",
            "timestamp": "2026-03-22T00:00:00Z",
            "trace_id": "44444444-4444-4444-8444-444444444444",
            "run_id": "eval-run-20260322T000000Z",
            "input_decision_reference": "ecd-review-1",
            "enforcement_action": "require_manual_review",
            "final_status": "require_review",
            "rationale_code": "require_review_warning_signal",
            "fail_closed": True,
            "enforcement_path": "baf_single_path",
            "provenance": {
                "source_artifact_type": "evaluation_control_decision",
                "source_artifact_id": "ecd-review-1",
            },
        },
    ):
        result = enforce_control_before_execution(_ctx())

    assert result["continuation_allowed"] is False
    assert result["execution_status"] == "blocked"
    assert result["publication_blocked"] is True
    assert result["decision_blocked"] is True
    assert result["human_review_required"] is True
    assert result["escalation_triggered"] is False
