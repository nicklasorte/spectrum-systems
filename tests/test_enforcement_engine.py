from __future__ import annotations

import copy
import sys
from pathlib import Path
import warnings

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.enforcement_engine import (  # noqa: E402
    EnforcementError,
    enforce_budget_decision,
    enforce_control_decision,
    validate_enforcement_result,
)


def _decision(decision: str = "allow") -> dict:
    return {
        "artifact_type": "evaluation_control_decision",
        "schema_version": "1.1.0",
        "decision_id": "ecd-20260322T000000Z",
        "eval_run_id": "eval-run-20260322T000000Z",
        "system_status": "healthy" if decision == "allow" else "warning",
        "system_response": "allow" if decision == "allow" else "warn",
        "triggered_signals": [] if decision == "allow" else ["reliability_breach"],
        "threshold_snapshot": {
            "reliability_threshold": 0.85,
            "drift_threshold": 0.2,
            "trust_threshold": 0.8,
        },
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "created_at": "2026-03-22T00:00:00Z",
        "decision": decision,
        "rationale_code": {
            "allow": "allow_healthy_eval_summary",
            "deny": "deny_stability_breach",
            "require_review": "require_review_warning_signal",
        }[decision],
        "input_signal_reference": {
            "signal_type": "eval_summary",
            "source_artifact_id": "eval-run-20260322T000000Z",
        },
        "run_id": "eval-run-20260322T000000Z",
    }


def test_allow_decision_maps_to_allow_execution_and_allow() -> None:
    result = enforce_control_decision(_decision("allow"))
    assert result["enforcement_action"] == "allow_execution"
    assert result["final_status"] == "allow"
    assert validate_enforcement_result(result) == []


def test_deny_decision_maps_to_deny_execution_and_deny() -> None:
    decision = _decision("deny")
    decision["system_status"] = "blocked"
    decision["system_response"] = "block"
    decision["triggered_signals"] = ["stability_breach"]

    result = enforce_control_decision(decision)
    assert result["enforcement_action"] == "deny_execution"
    assert result["final_status"] == "deny"
    assert result["fail_closed"] is True


def test_require_review_decision_maps_to_manual_review_and_require_review() -> None:
    result = enforce_control_decision(_decision("require_review"))
    assert result["enforcement_action"] == "require_manual_review"
    assert result["final_status"] == "require_review"
    assert result["fail_closed"] is True


def test_malformed_decision_artifact_raises_error() -> None:
    with pytest.raises(EnforcementError, match="failed validation"):
        enforce_control_decision({"bad": "input"})


def test_missing_decision_field_raises_error() -> None:
    malformed = copy.deepcopy(_decision("allow"))
    malformed.pop("decision")
    with pytest.raises(EnforcementError):
        enforce_control_decision(malformed)


def test_returned_artifact_validates_against_schema() -> None:
    result = enforce_control_decision(_decision("allow"))
    assert validate_enforcement_result(result) == []


def test_legacy_enforce_budget_decision_emits_deprecation_warning() -> None:
    legacy_decision = {
        "artifact_type": "evaluation_budget_decision",
        "schema_version": "1.0.0",
        "decision_id": "legacy-1",
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "run_id": "run-1",
        "system_status": "healthy",
        "system_response": "allow",
        "reasons": ["legacy"],
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        enforce_budget_decision(legacy_decision)
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_legacy_enforce_budget_decision_rejects_unapproved_callers() -> None:
    legacy_decision = {
        "artifact_type": "evaluation_budget_decision",
        "schema_version": "1.0.0",
        "decision_id": "legacy-2",
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "run_id": "run-2",
        "system_status": "healthy",
        "system_response": "allow",
        "reasons": ["legacy"],
    }

    module_source = """
from spectrum_systems.modules.runtime.enforcement_engine import enforce_budget_decision

def call_legacy(decision):
    return enforce_budget_decision(decision)
"""
    namespace: dict = {"__name__": "manual_script"}
    exec(module_source, namespace)
    with pytest.raises(
        EnforcementError,
        match="restricted to explicitly approved legacy callers",
    ):
        namespace["call_legacy"](legacy_decision)


def test_no_non_test_callers_of_legacy_enforcement_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    callers = []
    for path in repo_root.rglob("*.py"):
        rel = path.relative_to(repo_root)
        if "tests/" in str(rel):
            continue
        if rel == Path("spectrum_systems/modules/runtime/enforcement_engine.py"):
            continue
        text = path.read_text(encoding="utf-8")
        if "enforce_budget_decision(" in text:
            callers.append(str(rel))
    assert sorted(callers) == sorted(
        [
            "spectrum_systems/modules/runtime/control_executor.py",
            "spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py",
        ]
    )
