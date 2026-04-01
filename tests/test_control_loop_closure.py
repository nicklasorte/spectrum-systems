from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.runtime.control_loop_closure import (
    ControlLoopClosureError,
    assert_evaluation_control_authority_only,
    evaluate_artifact_release_readiness,
    evaluate_control_loop_closure_bundle,
)


def test_closure_bundle_happy_path() -> None:
    bundle = load_example("control_loop_closure_evidence_bundle")
    result = evaluate_control_loop_closure_bundle(bundle)
    assert result["ready_for_hard_gate"] is True


def test_closure_bundle_fails_when_replay_parity_false() -> None:
    bundle = load_example("control_loop_closure_evidence_bundle")
    bundle["replay_parity_exact"] = False
    with pytest.raises(ControlLoopClosureError, match="replay_parity_exact"):
        evaluate_control_loop_closure_bundle(bundle)


def test_release_readiness_requires_trace_audit_complete() -> None:
    bundle = load_example("control_loop_closure_evidence_bundle")
    with pytest.raises(ControlLoopClosureError, match="trace completeness"):
        evaluate_artifact_release_readiness(
            closure_bundle=bundle,
            replay_validation={"parity": True},
            trace_audit={"complete": False},
        )


def test_authority_only_rejects_legacy_budget_decision() -> None:
    decision = load_example("evaluation_control_decision")
    payload = {
        "evaluation_control_decision": decision,
        "legacy_budget_decision": {"decision": "allow"},
    }
    with pytest.raises(ControlLoopClosureError, match="legacy budget decision"):
        assert_evaluation_control_authority_only(payload)


def test_recurrence_prevention_closure_requires_policy_update_ref() -> None:
    bundle = load_example("control_loop_closure_evidence_bundle")
    mutated = copy.deepcopy(bundle)
    mutated["recurrence_prevention_closure"].pop("policy_update_ref")
    with pytest.raises(ControlLoopClosureError, match="policy_update_ref"):
        evaluate_control_loop_closure_bundle(mutated)
