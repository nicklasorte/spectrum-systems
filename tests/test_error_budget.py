"""Tests for deterministic SRE-09 error budget computation."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.error_budget import (  # noqa: E402
    ErrorBudgetError,
    build_error_budget_status,
)


def _slo(operator: str = "gte", target: float = 0.99, metric: str = "replay_success_rate") -> dict:
    return {
        "slo_id": "7f6f4f35a3d9c73fec0faece8f35f98af88c9b270e2d6a8a907a5162e03f8f8f",
        "artifact_type": "service_level_objective",
        "schema_version": "1.0.0",
        "timestamp": "2026-03-24T00:00:00Z",
        "service_name": "spectrum-runtime-control",
        "service_scope": "runtime_replay_control_surface",
        "objective_window": "rolling_24h",
        "objectives": [
            {
                "metric_name": metric,
                "target_operator": operator,
                "target_value": target,
                "unit": "ratio",
                "severity_on_breach": "block",
                "description": "test objective",
            }
        ],
        "policy_id": "sre-observability-policy-v1",
        "generated_by_version": "sre-08-sre-10@1.0.0",
    }


def _observability(value: float = 1.0) -> dict:
    return {
        "artifact_id": "5b98439dd1a2382e9a7ea440e0e3da573f84ec6a1278ae55a2e0893a0f8e83d6",
        "artifact_type": "observability_metrics",
        "schema_version": "1.0.0",
        "timestamp": "2026-03-24T00:00:00Z",
        "trace_refs": {"trace_id": "trace-eval-001"},
        "measurement_scope": "single_replay_run",
        "run_ids": ["eval-run-001"],
        "source_artifact_ids": ["RPL-trace-eval-001"],
        "metric_window": "single_run",
        "metrics": {
            "total_runs": 1,
            "replay_success_rate": value,
        },
        "slo_id": "7f6f4f35a3d9c73fec0faece8f35f98af88c9b270e2d6a8a907a5162e03f8f8f",
        "policy_id": "sre-observability-policy-v1",
        "breach_summary": {
            "breached_metrics": [],
            "highest_severity": "none",
            "reasons": [],
        },
        "generated_by_version": "observability_metrics.py@1.0.0",
    }


def _policy(warning: float = 0.5, exhausted: float = 1.0) -> dict:
    return {
        "artifact_type": "error_budget_policy",
        "schema_version": "1.0.0",
        "policy_id": "sre-error-budget-policy-v1",
        "measurement_window": "single_run",
        "supported_metrics": ["replay_success_rate"],
        "warning_consumption_ratio": warning,
        "exhausted_consumption_ratio": exhausted,
        "unknown_metric_handling": "fail_closed",
        "missing_metric_handling": "fail_closed",
        "generated_by_version": "sre-09@1.0.0",
    }


def test_healthy_objective_case() -> None:
    status = build_error_budget_status(_observability(1.0), _slo(), policy=_policy())
    validate_artifact(status, "error_budget_status")
    assert status["budget_status"] == "healthy"
    assert status["objectives"][0]["status"] == "healthy"


def test_warning_objective_case() -> None:
    status = build_error_budget_status(_observability(0.985), _slo(), policy=_policy(warning=0.3, exhausted=0.8))
    assert status["budget_status"] == "warning"
    assert status["objectives"][0]["status"] == "warning"


def test_exhausted_objective_case() -> None:
    status = build_error_budget_status(_observability(0.95), _slo(), policy=_policy())
    assert status["budget_status"] == "exhausted"
    assert status["objectives"][0]["status"] == "exhausted"


def test_invalid_due_to_malformed_observability_input() -> None:
    bad = _observability()
    bad.pop("metrics")
    with pytest.raises(ErrorBudgetError, match="observability_metrics failed validation"):
        build_error_budget_status(bad, _slo(), policy=_policy())


def test_invalid_due_to_slo_policy_metric_mismatch() -> None:
    with pytest.raises(ErrorBudgetError, match="not allowed by policy"):
        build_error_budget_status(_observability(), _slo(metric="replay_success_rate"), policy={**_policy(), "supported_metrics": ["drift_exceed_threshold_rate"]})


def test_unknown_metric_name_fails_closed() -> None:
    with pytest.raises(ErrorBudgetError, match="service_level_objective failed validation"):
        build_error_budget_status(_observability(), _slo(metric="not_supported_metric"), policy=_policy())


def test_deterministic_repeated_run_output() -> None:
    obs = _observability(0.99)
    slo = _slo(target=0.99)
    policy = _policy()
    first = build_error_budget_status(copy.deepcopy(obs), copy.deepcopy(slo), policy=copy.deepcopy(policy))
    second = build_error_budget_status(copy.deepcopy(obs), copy.deepcopy(slo), policy=copy.deepcopy(policy))
    assert first == second


def test_operator_direction_correctness_for_lte_and_eq() -> None:
    # lte objective with measured above target should consume budget
    lte_status = build_error_budget_status(
        _observability(0.2),
        _slo(operator="lte", target=0.1),
        policy=_policy(),
    )
    assert lte_status["objectives"][0]["consumed_error"] == 0.1
    assert lte_status["objectives"][0]["status"] == "exhausted"

    # eq objective with mismatch should consume full (binary) budget
    eq_status = build_error_budget_status(
        _observability(0.9),
        _slo(operator="eq", target=1.0),
        policy=_policy(),
    )
    assert eq_status["objectives"][0]["consumption_ratio"] == 1.0
    assert eq_status["budget_status"] == "exhausted"
