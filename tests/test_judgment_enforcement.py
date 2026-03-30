from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.runtime.control_loop import run_judgment_learning_control_loop  # noqa: E402
from spectrum_systems.modules.runtime.judgment_enforcement import (  # noqa: E402
    evaluate_judgment_enforcement_traceability,
)


def _inputs() -> dict[str, Any]:
    drift = copy.deepcopy(load_example("judgment_drift_signal"))
    drift["group_signals"][0]["deltas"] = {
        "approval_rate_delta": 0.01,
        "block_rate_delta": 0.01,
        "error_rate_delta": 0.01,
        "calibration_ece_delta": 0.01,
    }
    drift["group_signals"][0]["drift_detected"] = False
    calibration = copy.deepcopy(load_example("judgment_calibration_result"))
    calibration["group_metrics"][0]["expected_calibration_error"] = 0.02
    return {
        "judgment_eval_result": copy.deepcopy(load_example("judgment_eval_result")),
        "judgment_calibration_result": calibration,
        "judgment_drift_signal": drift,
        "judgment_error_budget_status": copy.deepcopy(load_example("judgment_error_budget_status")),
        "judgment_policy": copy.deepcopy(load_example("judgment_policy")),
        "trace_context": {"trace_id": "trace-001", "replay_run_id": "run-001"},
        "created_at": "2026-03-30T00:20:00Z",
    }


def test_allow_escalation_emits_action_and_outcome_and_allows_progression() -> None:
    result = run_judgment_learning_control_loop(**_inputs())
    assert result["decision"] == "allow"
    assert result["judgment_enforcement_action_record"]["action_type"] == "promote_or_continue"
    assert result["judgment_enforcement_outcome_record"]["progression_status"] == "allowed"
    assert result["progression_allowed"] is True


def test_warn_path_emits_warning_action_and_operator_remediation_for_policy_required_warning() -> None:
    inputs = _inputs()
    inputs["judgment_calibration_result"]["group_metrics"][0]["expected_calibration_error"] = 0.06
    result = run_judgment_learning_control_loop(**inputs)
    assert result["decision"] == "warn"
    assert result["judgment_enforcement_action_record"]["action_type"] == "continue_with_warning"
    assert result["judgment_operator_remediation_record"] is not None
    assert result["progression_allowed"] is False


def test_freeze_path_emits_freeze_action_and_prevents_progression() -> None:
    inputs = _inputs()
    inputs["judgment_drift_signal"]["group_signals"][0]["deltas"]["error_rate_delta"] = 0.06
    result = run_judgment_learning_control_loop(**inputs)
    assert result["decision"] == "freeze"
    assert result["judgment_enforcement_action_record"]["action_type"] == "freeze_pipeline_or_freeze_scope"
    assert result["judgment_enforcement_outcome_record"]["progression_status"] == "frozen"
    assert result["progression_allowed"] is False


def test_block_path_emits_block_action_and_prevents_progression() -> None:
    inputs = _inputs()
    inputs["judgment_error_budget_status"]["status"] = "exhausted"
    result = run_judgment_learning_control_loop(**inputs)
    assert result["decision"] == "block"
    assert result["judgment_enforcement_action_record"]["action_type"] == "block_artifact_or_block_progression"
    assert result["judgment_enforcement_outcome_record"]["progression_status"] == "prevented"
    assert result["progression_allowed"] is False


def test_missing_enforcement_action_artifact_fails_closed() -> None:
    result = run_judgment_learning_control_loop(**_inputs())
    traceability = evaluate_judgment_enforcement_traceability(
        escalation_record=result["judgment_control_escalation_record"],
        action_record=None,
        outcome_record=result["judgment_enforcement_outcome_record"],
        remediation_record=result["judgment_operator_remediation_record"],
    )
    assert traceability["progression_allowed"] is False
    assert "missing enforcement action artifact" in traceability["blocking_reasons"]


def test_missing_enforcement_outcome_artifact_fails_closed() -> None:
    result = run_judgment_learning_control_loop(**_inputs())
    traceability = evaluate_judgment_enforcement_traceability(
        escalation_record=result["judgment_control_escalation_record"],
        action_record=result["judgment_enforcement_action_record"],
        outcome_record=None,
        remediation_record=result["judgment_operator_remediation_record"],
    )
    assert traceability["progression_allowed"] is False
    assert "missing enforcement outcome artifact" in traceability["blocking_reasons"]


def test_deterministic_escalation_input_produces_same_action_and_outcome_shape() -> None:
    first = run_judgment_learning_control_loop(**_inputs())
    second = run_judgment_learning_control_loop(**_inputs())
    assert first["judgment_enforcement_action_record"] == second["judgment_enforcement_action_record"]
    assert first["judgment_enforcement_outcome_record"] == second["judgment_enforcement_outcome_record"]
