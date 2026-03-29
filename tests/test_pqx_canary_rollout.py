from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.pqx_canary_rollout import (
    PQXCanaryRolloutError,
    build_canary_decision_record,
    build_canary_evaluation_record,
)


def _rollout(status: str = "active") -> dict:
    return {
        "rollout_scope": "bundle_only",
        "affected_bundle_ids": ["BUNDLE-PQX-CORE"],
        "affected_slice_ids": ["AI-01"],
        "canary_status": status,
        "success_criteria": ["no_regression"],
        "failure_criteria": ["trace_drift"],
        "fallback_behavior": "freeze",
    }


def test_valid_canary_rollout_is_admitted() -> None:
    record = build_canary_decision_record(
        rollout_id="canary-1",
        change_type="routing",
        rollout=_rollout(),
        run_id="run-1",
        trace_id="trace-1",
        created_at="2026-03-29T00:00:00Z",
    )
    assert record["decision"] == "admit"


def test_under_specified_rollout_is_blocked() -> None:
    with pytest.raises(PQXCanaryRolloutError, match="under-specified canary rollout"):
        build_canary_decision_record(
            rollout_id="canary-2",
            change_type="routing",
            rollout={"rollout_scope": "bundle_only"},
            run_id="run-2",
            trace_id="trace-2",
            created_at="2026-03-29T00:00:00Z",
        )


def test_failed_canary_freezes_broader_rollout() -> None:
    decision = build_canary_decision_record(
        rollout_id="canary-3",
        change_type="prompt",
        rollout=_rollout(),
        run_id="run-3",
        trace_id="trace-3",
        created_at="2026-03-29T00:00:00Z",
    )
    evaluation = build_canary_evaluation_record(
        decision_record=decision,
        observed_metrics={"no_regression": False},
        created_at="2026-03-29T00:01:00Z",
    )
    assert evaluation["evaluation_outcome"] == "fail"
    assert evaluation["scheduling_freeze"] is True
    assert "BUNDLE-PQX-CORE" in evaluation["frozen_paths"]


def test_successful_canary_only_allows_bounded_advance() -> None:
    decision = build_canary_decision_record(
        rollout_id="canary-4",
        change_type="model",
        rollout=_rollout(),
        run_id="run-4",
        trace_id="trace-4",
        created_at="2026-03-29T00:00:00Z",
    )
    evaluation = build_canary_evaluation_record(
        decision_record=decision,
        observed_metrics={"no_regression": True},
        created_at="2026-03-29T00:01:00Z",
    )
    assert evaluation["evaluation_outcome"] == "pass"
    assert evaluation["scheduling_freeze"] is False
