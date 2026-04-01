"""RE18 control-loop closure authority helpers."""

from __future__ import annotations

from typing import Any


class ControlLoopClosureError(ValueError):
    """Raised when control-loop closure evidence is missing or malformed."""


_CANONICAL_CHAIN = (
    "pqx_execution_record_refs",
    "output_artifact_refs",
    "eval_summary_refs",
    "control_decision_refs",
    "enforcement_action_refs",
    "replay_trace_refs",
)


_REQUIRED_RECURRENCE_KEYS = (
    "failure_class",
    "remediation_asset_ref",
    "regression_fixture_ref",
    "policy_update_ref",
)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_non_empty_list(bundle: dict[str, Any], key: str) -> list[str]:
    value = bundle.get(key)
    if not isinstance(value, list) or not value or not all(_non_empty_string(item) for item in value):
        raise ControlLoopClosureError(f"missing or malformed evidence list: {key}")
    return [str(item) for item in value]


def assert_evaluation_control_authority_only(payload: dict[str, Any]) -> None:
    decision = payload.get("evaluation_control_decision")
    if not isinstance(decision, dict):
        raise ControlLoopClosureError("evaluation_control_decision must be present and object")
    if payload.get("legacy_budget_decision") is not None:
        raise ControlLoopClosureError("legacy budget decision path is forbidden")
    if not _non_empty_string(decision.get("decision_id")):
        raise ControlLoopClosureError("evaluation_control_decision.decision_id is required")


def verify_recurrence_prevention_closure(closure: dict[str, Any]) -> None:
    for key in _REQUIRED_RECURRENCE_KEYS:
        if not _non_empty_string(closure.get(key)):
            raise ControlLoopClosureError(f"recurrence_prevention_closure missing {key}")


def evaluate_control_loop_closure_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ControlLoopClosureError("control_loop_closure_evidence_bundle must be an object")

    for key in _CANONICAL_CHAIN:
        _require_non_empty_list(bundle, key)

    recurrence = bundle.get("recurrence_prevention_closure")
    if not isinstance(recurrence, dict):
        raise ControlLoopClosureError("recurrence_prevention_closure must be present")
    verify_recurrence_prevention_closure(recurrence)

    replay_parity_exact = bundle.get("replay_parity_exact")
    if replay_parity_exact is not True:
        raise ControlLoopClosureError("replay_parity_exact must be true")

    trace_complete = bundle.get("trace_completeness")
    if trace_complete is not True:
        raise ControlLoopClosureError("trace_completeness must be true")

    return {
        "bundle_complete": True,
        "replay_parity_exact": True,
        "trace_completeness": True,
        "ready_for_hard_gate": True,
    }


def evaluate_artifact_release_readiness(
    *,
    closure_bundle: dict[str, Any] | None,
    replay_validation: dict[str, Any] | None,
    trace_audit: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(closure_bundle, dict):
        raise ControlLoopClosureError("artifact_release_readiness requires control_loop_closure_evidence_bundle")
    evaluate_control_loop_closure_bundle(closure_bundle)

    if not isinstance(replay_validation, dict) or replay_validation.get("parity") is not True:
        raise ControlLoopClosureError("artifact_release_readiness requires replay parity=true")
    if not isinstance(trace_audit, dict) or trace_audit.get("complete") is not True:
        raise ControlLoopClosureError("artifact_release_readiness requires trace completeness=true")

    return {
        "judgment_type": "artifact_release_readiness",
        "decision": "pass",
        "required_evidence": [
            "control_loop_closure_evidence_bundle",
            "replay_parity",
            "trace_completeness",
        ],
    }
