from __future__ import annotations

from copy import deepcopy

import pytest

from spectrum_systems.modules.runtime.judgment_engine import JudgmentEngineError, select_policy
from spectrum_systems.modules.runtime.judgment_policy_lifecycle import (
    JudgmentPolicyLifecycleError,
    PromotionInputs,
    evaluate_promotion_gates,
    is_trace_in_canary_cohort,
    transition_policy,
)


def _policy(*, version: str, status: str) -> dict:
    return {
        "artifact_id": "judgment-policy-artifact-release-readiness-v1",
        "artifact_version": version,
        "status": status,
    }


def _trace() -> dict:
    return {"trace_id": "trace-1", "run_id": "run-1", "rollout_id": "rollout-1"}


def _actor() -> dict:
    return {"actor_id": "controller", "actor_type": "system", "module": "runtime.judgment_policy_lifecycle"}


def _signals(*, eval_passed: bool = True, drift: bool = False, budget: str = "healthy") -> PromotionInputs:
    return PromotionInputs(
        judgment_eval_result={"eval_results": [{"eval_type": "evidence_coverage", "passed": eval_passed}]},
        judgment_drift_signal={"group_signals": [{"drift_detected": drift}]},
        judgment_error_budget_status={"status": budget},
        judgment_calibration_result={"calibration_health": {"status": "healthy"}},
        remediation_readiness_statuses=[{"closure_eligible": True}],
        control_ready=True,
    )


def test_create_draft_to_canary_transition_requires_rollout_artifact() -> None:
    draft_policy = _policy(version="1.1.0", status="draft")

    with pytest.raises(JudgmentPolicyLifecycleError, match="requires explicit rollout artifact"):
        transition_policy(
            policy=draft_policy,
            lifecycle_action="enter_canary",
            trace=_trace(),
            actor=_actor(),
            created_at="2026-03-30T00:00:00Z",
            standards_version="1.0.99",
            source_reason={"reasons": ["initial canary"], "triggering_signals": ["operator"]},
            required_gates={"rollout_declared": True},
        )


def test_canary_policy_applies_only_to_selected_cohort() -> None:
    cohort = {"kind": "environment", "values": ["staging"]}
    assert is_trace_in_canary_cohort("trace-a", cohort, "staging") is True
    assert is_trace_in_canary_cohort("trace-a", cohort, "prod") is False


def test_promotion_from_canary_to_active_when_gates_pass() -> None:
    canary = _policy(version="1.1.0", status="canary")
    gates = evaluate_promotion_gates(_signals())
    promoted, lifecycle = transition_policy(
        policy=canary,
        lifecycle_action="promote_active",
        trace=_trace(),
        actor=_actor(),
        created_at="2026-03-30T00:10:00Z",
        standards_version="1.0.99",
        source_reason={"reasons": ["promotion gates healthy"], "triggering_signals": ["eval/drift/budget"]},
        required_gates=gates,
    )
    assert promoted["status"] == "active"
    assert lifecycle["lifecycle_action"] == "promote_active"


def test_missing_required_signals_block_promotion_fail_closed() -> None:
    with pytest.raises(JudgmentPolicyLifecycleError, match="requires judgment_eval_result"):
        evaluate_promotion_gates(
            PromotionInputs(
                judgment_eval_result=None,
                judgment_drift_signal={"group_signals": []},
                judgment_error_budget_status={"status": "healthy"},
                remediation_readiness_statuses=[],
                control_ready=True,
            )
        )


def test_rollback_restores_prior_active_version_deterministically() -> None:
    current = _policy(version="1.2.0", status="active")
    prior_active = _policy(version="1.1.0", status="active")
    gates = {"explicit_rollback_reason": True, "target_policy_valid": True}

    _, first = transition_policy(
        policy=current,
        target_policy=prior_active,
        lifecycle_action="rollback",
        trace=_trace(),
        actor=_actor(),
        created_at="2026-03-30T00:20:00Z",
        standards_version="1.0.99",
        source_reason={"reasons": ["drift threshold exceeded"], "triggering_signals": ["judgment_drift_signal"]},
        required_gates=gates,
    )
    _, second = transition_policy(
        policy=current,
        target_policy=prior_active,
        lifecycle_action="rollback",
        trace=_trace(),
        actor=_actor(),
        created_at="2026-03-30T00:20:00Z",
        standards_version="1.0.99",
        source_reason={"reasons": ["drift threshold exceeded"], "triggering_signals": ["judgment_drift_signal"]},
        required_gates=gates,
    )
    assert first == second


def test_revoked_policy_cannot_be_selected() -> None:
    with pytest.raises(JudgmentEngineError, match="no applicable governed judgment policy"):
        select_policy(
            policy_paths=["contracts/examples/judgment_policy.json"],
            judgment_type="artifact_release_readiness",
            scope="autonomous_cycle",
            environment="prod",
            trace_id="trace-1",
            lifecycle_records=[
                {
                    "policy_id": "judgment-policy-artifact-release-readiness-v1",
                    "to_version": "1.0.0",
                    "lifecycle_action": "revoke",
                    "resulting_status": "revoked",
                }
            ],
            rollout_records=[],
        )


def test_missing_lifecycle_artifact_fails_closed_selection() -> None:
    with pytest.raises(JudgmentEngineError, match="no applicable governed judgment policy"):
        select_policy(
            policy_paths=["contracts/examples/judgment_policy.json"],
            judgment_type="artifact_release_readiness",
            scope="autonomous_cycle",
            environment="prod",
            trace_id="trace-1",
            lifecycle_records=[],
            rollout_records=[],
            governed_runtime=True,
        )


def test_canary_policy_without_rollout_fails_closed_selection() -> None:
    with pytest.raises(JudgmentEngineError, match="no applicable governed judgment policy"):
        select_policy(
            policy_paths=["contracts/examples/judgment_policy.json"],
            judgment_type="artifact_release_readiness",
            scope="autonomous_cycle",
            environment="prod",
            trace_id="trace-1",
            lifecycle_records=[
                {
                    "policy_id": "judgment-policy-artifact-release-readiness-v1",
                    "to_version": "1.0.0",
                    "lifecycle_action": "enter_canary",
                    "resulting_status": "canary",
                }
            ],
            rollout_records=[],
            governed_runtime=True,
        )


def test_deterministic_repeated_lifecycle_transition_for_same_inputs() -> None:
    canary = _policy(version="1.1.0", status="canary")
    gates = evaluate_promotion_gates(_signals())
    args = dict(
        policy=canary,
        lifecycle_action="promote_active",
        trace=_trace(),
        actor=_actor(),
        created_at="2026-03-30T00:30:00Z",
        standards_version="1.0.99",
        source_reason={"reasons": ["all signals healthy"], "triggering_signals": ["eval", "drift", "budget"]},
        required_gates=gates,
    )
    first = transition_policy(**deepcopy(args))
    second = transition_policy(**deepcopy(args))
    assert first == second


def test_degraded_calibration_blocks_promotion_gate() -> None:
    gates = evaluate_promotion_gates(
        PromotionInputs(
            judgment_eval_result={"eval_results": [{"eval_type": "evidence_coverage", "passed": True}]},
            judgment_drift_signal={"group_signals": [{"drift_detected": False}]},
            judgment_error_budget_status={"status": "healthy"},
            judgment_calibration_result={
                "calibration_health": {"status": "failing"}
            },
            remediation_readiness_statuses=[{"closure_eligible": True}],
            control_ready=True,
        )
    )
    assert gates["calibration_within_bounds"] is False
    assert gates["calibration_lifecycle_block"] is True


def test_missing_required_calibration_evidence_fails_closed() -> None:
    with pytest.raises(JudgmentPolicyLifecycleError, match="requires judgment_calibration_result"):
        evaluate_promotion_gates(
            PromotionInputs(
                judgment_eval_result={"eval_results": [{"eval_type": "evidence_coverage", "passed": True}]},
                judgment_drift_signal={"group_signals": [{"drift_detected": False}]},
                judgment_error_budget_status={"status": "healthy"},
                judgment_calibration_result=None,
                remediation_readiness_statuses=[{"closure_eligible": True}],
                control_ready=True,
                calibration_required=True,
            )
        )
