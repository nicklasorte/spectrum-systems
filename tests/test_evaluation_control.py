from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.runtime.evaluation_control import (  # noqa: E402
    EvaluationControlError,
    build_evaluation_control_decision,
)
from spectrum_systems.modules.runtime.evaluation_auto_generation import (  # noqa: E402
    generate_failure_eval_case,
    register_failure_eval_case,
)


def _replay_result() -> dict:
    return copy.deepcopy(load_example("replay_result"))


def _failure_eval_case() -> tuple[dict, dict]:
    artifact = generate_failure_eval_case(
        source_artifact={
            "artifact_type": "agent_failure_record",
            "id": "afr-cl01-001",
            "trace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        },
        source_run_id="run-cl01-001",
        stage="control",
        runtime_environment="test",
        execution_result={"continuation_allowed": False, "publication_blocked": True, "decision_blocked": True},
    )
    registry: dict[str, dict] = {}
    binding = register_failure_eval_case(
        failure_eval_case=artifact,
        eval_registry=registry,
        policy_id="failure-binding-policy-v1",
        trigger_condition="on_failure_record_emitted",
    )
    return artifact, binding


def test_replay_result_healthy_allows() -> None:
    decision = build_evaluation_control_decision(_replay_result())
    assert decision["system_response"] == "allow"
    assert decision["decision"] == "allow"


def test_replay_result_with_explicit_drift_metric_is_supported() -> None:
    replay = _replay_result()
    replay["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = 0.0
    decision = build_evaluation_control_decision(replay)
    assert decision["system_response"] == "allow"
    assert decision["decision"] == "allow"


def test_non_replay_input_fails_closed() -> None:
    with pytest.raises(EvaluationControlError, match="RUNTIME_REPLAY_BOUNDARY_VIOLATION"):
        build_evaluation_control_decision({"artifact_type": "eval_summary"})


def test_partial_replay_without_observability_fails_closed() -> None:
    replay = _replay_result()
    replay.pop("observability_metrics")
    with pytest.raises(EvaluationControlError, match="must embed observability_metrics"):
        build_evaluation_control_decision(replay)


def test_partial_replay_without_error_budget_fails_closed() -> None:
    replay = _replay_result()
    replay.pop("error_budget_status")
    with pytest.raises(EvaluationControlError, match="must embed error_budget_status"):
        build_evaluation_control_decision(replay)


def test_invalid_trace_linkage_fails_closed() -> None:
    replay = _replay_result()
    replay["observability_metrics"]["trace_refs"]["trace_id"] = "trace-mismatch"
    with pytest.raises(EvaluationControlError, match="REPLAY_INVALID_TRACE_LINKAGE"):
        build_evaluation_control_decision(replay)


def test_decision_id_is_deterministic_for_identical_replay_inputs() -> None:
    replay = _replay_result()
    first = build_evaluation_control_decision(replay)
    second = build_evaluation_control_decision(copy.deepcopy(replay))
    assert first["decision_id"] == second["decision_id"]


def test_missing_optional_drift_metric_is_deterministic() -> None:
    replay = _replay_result()
    replay["observability_metrics"]["metrics"].pop("drift_exceed_threshold_rate", None)
    first = build_evaluation_control_decision(replay)
    second = build_evaluation_control_decision(copy.deepcopy(replay))
    assert first["decision_id"] == second["decision_id"]


def test_explicit_drift_metric_is_deterministic() -> None:
    replay = _replay_result()
    replay["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = 0.0
    first = build_evaluation_control_decision(replay)
    second = build_evaluation_control_decision(copy.deepcopy(replay))
    assert first["decision_id"] == second["decision_id"]


def test_budget_warning_forces_warn_response() -> None:
    replay = _replay_result()
    replay["error_budget_status"]["budget_status"] = "warning"
    replay["error_budget_status"]["highest_severity"] = "warning"
    replay["error_budget_status"]["triggered_conditions"] = [
        {
            "metric_name": "replay_success_rate",
            "status": "warning",
            "consumption_ratio": 0.9,
        }
    ]
    decision = build_evaluation_control_decision(replay)
    assert decision["system_response"] == "warn"
    assert decision["decision"] == "require_review"
    assert "budget_warning" in decision["triggered_signals"]


def test_trust_breach_with_budget_warning_remains_deny() -> None:
    replay = _replay_result()
    replay["consistency_status"] = "mismatch"
    replay["drift_detected"] = True
    replay["error_budget_status"]["budget_status"] = "warning"
    replay["error_budget_status"]["highest_severity"] = "warning"
    replay["error_budget_status"]["triggered_conditions"] = [
        {
            "metric_name": "replay_success_rate",
            "status": "warning",
            "consumption_ratio": 0.9,
        }
    ]
    decision = build_evaluation_control_decision(replay)
    assert decision["system_response"] == "block"
    assert decision["decision"] == "deny"
    assert decision["rationale_code"] == "deny_trust_breach"
    assert "budget_warning" in decision["triggered_signals"]


def test_budget_exhausted_forces_non_allow_response() -> None:
    replay = _replay_result()
    replay["error_budget_status"]["budget_status"] = "exhausted"
    replay["error_budget_status"]["highest_severity"] = "exhausted"
    replay["error_budget_status"]["triggered_conditions"] = [
        {
            "metric_name": "replay_success_rate",
            "status": "exhausted",
            "consumption_ratio": 1.0,
        }
    ]
    decision = build_evaluation_control_decision(replay)
    assert decision["system_response"] in {"freeze", "block"}
    assert decision["decision"] == "deny"
    assert "budget_exhausted" in decision["triggered_signals"]


def test_missing_budget_evaluation_blocks() -> None:
    replay = _replay_result()
    replay["error_budget_status"]["objectives"] = []
    with pytest.raises(EvaluationControlError, match="replay_result failed validation"):
        build_evaluation_control_decision(replay)


def test_budget_invalid_forces_deny_response() -> None:
    replay = _replay_result()
    replay["error_budget_status"]["budget_status"] = "invalid"
    replay["error_budget_status"]["highest_severity"] = "invalid"
    replay["error_budget_status"]["triggered_conditions"] = []
    decision = build_evaluation_control_decision(replay)
    assert decision["system_response"] == "block"
    assert decision["decision"] == "deny"
    assert decision["rationale_code"] == "deny_budget_invalid"
    assert "budget_invalid" in decision["triggered_signals"]


def test_indeterminate_replay_routes_to_trust_breach_rationale() -> None:
    replay = _replay_result()
    replay["consistency_status"] = "indeterminate"
    replay["failure_reason"] = "indeterminate_replay_consistency"
    replay["drift_detected"] = False

    decision = build_evaluation_control_decision(replay)

    assert decision["decision"] == "deny"
    assert decision["rationale_code"] == "deny_trust_breach"
    assert "indeterminate_failure" in decision["triggered_signals"]


def test_failure_eval_case_requires_policy_binding() -> None:
    failure_eval, _ = _failure_eval_case()
    with pytest.raises(EvaluationControlError, match="requires deterministic failure_policy_binding"):
        build_evaluation_control_decision(failure_eval)


def test_failure_eval_case_with_policy_binding_routes_to_non_allow() -> None:
    failure_eval, binding = _failure_eval_case()
    decision = build_evaluation_control_decision(failure_eval, failure_policy_binding=binding)
    assert decision["decision"] in {"deny", "require_review"}
    assert decision["input_signal_reference"]["signal_type"] == "failure_eval_case"


def test_control_loop_consumes_recurrence_prevention() -> None:
    failure_eval, binding = _failure_eval_case()
    decision = build_evaluation_control_decision(failure_eval, failure_policy_binding=binding)
    assert decision["decision"] in {"deny", "require_review"}
    assert decision["system_response"] in {"warn", "block"}


def test_repeat_failure_escalates_decision() -> None:
    failure_eval, binding = _failure_eval_case()
    binding["recurrence_count"] = 3
    decision = build_evaluation_control_decision(failure_eval, failure_policy_binding=binding)
    assert decision["decision"] == "deny"
    assert decision["system_response"] == "block"
    assert decision["rationale_code"] in {"deny_repeat_failure_escalation", "deny_trust_breach"}


def test_prevention_without_control_consumption_fails() -> None:
    failure_eval, binding = _failure_eval_case()
    binding.pop("recurrence_prevention_artifact")
    with pytest.raises(EvaluationControlError, match="recurrence_prevention_artifact"):
        build_evaluation_control_decision(failure_eval, failure_policy_binding=binding)


def test_ambiguous_recurrence_scope_blocks() -> None:
    failure_eval, binding = _failure_eval_case()
    binding["recurrence_scope"]["runtime_environment"] = "*"
    with pytest.raises(EvaluationControlError, match="ambiguous recurrence scope"):
        build_evaluation_control_decision(failure_eval, failure_policy_binding=binding)


def test_active_runtime_rejects_relaxed_thresholds() -> None:
    replay = _replay_result()
    with pytest.raises(EvaluationControlError, match="cannot relax reliability_threshold"):
        build_evaluation_control_decision(
            replay,
            thresholds={"reliability_threshold": 0.6, "drift_threshold": 0.2, "trust_threshold": 0.8},
        )


def test_comparative_analysis_allows_relaxed_thresholds() -> None:
    replay = _replay_result()
    decision = build_evaluation_control_decision(
        replay,
        thresholds={"reliability_threshold": 0.6, "drift_threshold": 0.2, "trust_threshold": 0.8},
        threshold_context="comparative_analysis",
    )
    assert decision["decision"] in {"allow", "require_review", "deny"}


def test_threshold_context_is_explicit_and_fail_closed() -> None:
    replay = _replay_result()
    with pytest.raises(EvaluationControlError, match="threshold_context"):
        build_evaluation_control_decision(
            replay,
            thresholds={"reliability_threshold": 0.6},
            threshold_context="runtime_fallback",  # type: ignore[arg-type]
        )


def test_malformed_threshold_payload_fails_closed_in_both_contexts() -> None:
    replay = _replay_result()
    with pytest.raises(EvaluationControlError, match="must be numeric"):
        build_evaluation_control_decision(
            replay,
            thresholds={"reliability_threshold": "low"},  # type: ignore[dict-item]
        )
    with pytest.raises(EvaluationControlError, match="must be numeric"):
        build_evaluation_control_decision(
            replay,
            thresholds={"reliability_threshold": "low"},  # type: ignore[dict-item]
            threshold_context="comparative_analysis",
        )


def test_review_signal_fail_overrides_allow_to_block() -> None:
    replay = _replay_result()
    review_signal = {
        "artifact_type": "review_control_signal",
        "schema_version": "1.0.0",
        "review_signal_id": "rcs-aaaaaaaaaaaaaaaaaaaa",
        "review_id": "review-a",
        "review_type": "Test Review",
        "gate_assessment": "FAIL",
        "scale_recommendation": "NO",
        "critical_findings": ["critical"],
        "confidence": 0.8,
        "trace_linkage": {
            "source_review_path": "docs/reviews/test.md",
            "source_hash": "a" * 64,
            "review_date": "2026-04-01",
        },
    }
    decision = build_evaluation_control_decision(replay, review_control_signal=review_signal)
    assert decision["system_response"] == "block"
    assert decision["decision"] == "deny"


def test_review_signal_conditional_requires_review_without_bypass() -> None:
    replay = _replay_result()
    review_signal = {
        "artifact_type": "review_control_signal",
        "schema_version": "1.0.0",
        "review_signal_id": "rcs-bbbbbbbbbbbbbbbbbbbb",
        "review_id": "review-b",
        "review_type": "Test Review",
        "gate_assessment": "CONDITIONAL",
        "scale_recommendation": "YES",
        "critical_findings": [],
        "confidence": 0.7,
        "trace_linkage": {
            "source_review_path": "docs/reviews/test.md",
            "source_hash": "b" * 64,
            "review_date": "2026-04-01",
        },
    }
    decision = build_evaluation_control_decision(replay, review_control_signal=review_signal)
    assert decision["system_response"] == "warn"
    assert decision["decision"] == "require_review"
