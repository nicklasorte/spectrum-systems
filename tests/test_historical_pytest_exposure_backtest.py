from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.historical_pytest_exposure_backtest import (
    classify_historical_item,
    run_historical_pytest_exposure_backtest,
)


def test_classifies_missing_pytest_execution_evidence() -> None:
    classified = classify_historical_item(
        {
            "artifact_type": "contract_preflight_result_artifact",
            "control_signal": {"strategy_gate_decision": "ALLOW"},
            "pytest_selection_integrity": {"selection_integrity_decision": "ALLOW"},
            "trace": {"fallback_used": False},
        }
    )
    assert classified["classification"] == "suspect_missing_pytest_execution"


def test_classifies_missing_artifact_boundary_enforcement_evidence() -> None:
    classified = classify_historical_item(
        {
            "artifact_type": "contract_preflight_result_artifact",
            "control_signal": {"strategy_gate_decision": "ALLOW"},
            "pytest_execution": {"event_name": "pull_request", "pytest_execution_count": 1, "selected_targets": ["tests/x.py"]},
            "pytest_selection_integrity": {"selection_integrity_decision": "ALLOW"},
            "pytest_execution_record_ref": "outputs/contract_preflight/pytest_execution_record.json",
            "pytest_selection_integrity_result_ref": "outputs/contract_preflight/pytest_selection_integrity_result.json",
            "trace": {"fallback_used": False},
        }
    )
    assert classified["classification"] == "suspect_missing_artifact_boundary_enforcement"


def test_classifies_insufficient_evidence_explicitly() -> None:
    classified = classify_historical_item(
        {
            "artifact_type": "contract_preflight_result_artifact",
            "control_signal": {"strategy_gate_decision": "BLOCK"},
            "pytest_execution": {"event_name": "pull_request", "pytest_execution_count": 1, "selected_targets": ["tests/x.py"]},
            "pytest_selection_integrity": {"selection_integrity_decision": "ALLOW"},
            "pytest_execution_record_ref": "outputs/contract_preflight/pytest_execution_record.json",
            "pytest_selection_integrity_result_ref": "outputs/contract_preflight/pytest_selection_integrity_result.json",
            "pytest_artifact_linkage": {"pytest_execution_record_ref": "outputs/contract_preflight/pytest_execution_record.json"},
            "trace": {"fallback_used": False},
        }
    )
    assert classified["classification"] == "insufficient_evidence_to_determine"
    assert classified["confidence"] == "low"


def test_summary_counts_are_deterministic() -> None:
    result = run_historical_pytest_exposure_backtest(
        evidence_sources={
            "audit_window": {
                "window_label": "x",
                "scan_roots": ["outputs"],
                "artifact_globs": ["**/contract_preflight_result_artifact.json"],
                "max_items": 3,
            }
        },
        evaluated_items=[
            {
                "run_id": "run-1",
                "control_signal": {"strategy_gate_decision": "ALLOW"},
                "pytest_selection_integrity": {"selection_integrity_decision": "ALLOW"},
                "trace": {"fallback_used": False},
            },
            {
                "run_id": "run-2",
                "control_signal": {"strategy_gate_decision": "BLOCK"},
                "pytest_execution": {"event_name": "pull_request", "pytest_execution_count": 1, "selected_targets": ["tests/x.py"]},
                "pytest_selection_integrity": {"selection_integrity_decision": "ALLOW"},
                "pytest_execution_record_ref": "outputs/contract_preflight/pytest_execution_record.json",
                "pytest_selection_integrity_result_ref": "outputs/contract_preflight/pytest_selection_integrity_result.json",
                "pytest_artifact_linkage": {"pytest_execution_record_ref": "outputs/contract_preflight/pytest_execution_record.json"},
                "trace": {"fallback_used": False},
            },
        ],
        generated_at="2026-04-14T00:00:00Z",
    )
    assert result["summary_counts"] == {
        "insufficient_evidence_to_determine": 1,
        "suspect_missing_pytest_execution": 1,
    }
    validate_artifact(result, "historical_pytest_exposure_backtest_result")
