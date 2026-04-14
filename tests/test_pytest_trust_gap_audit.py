from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.pytest_trust_gap_audit import classify_artifact, run_pytest_trust_gap_audit


def test_backtest_classifies_missing_execution_evidence() -> None:
    artifact = {
        "artifact_type": "contract_preflight_result_artifact",
        "preflight_status": "passed",
        "control_signal": {"strategy_gate_decision": "ALLOW"},
        "pytest_selection_integrity": {"selection_integrity_decision": "ALLOW"},
    }
    classified = classify_artifact(artifact)
    assert classified["classification"] == "insufficient_evidence_to_determine"
    assert "MISSING_PYTEST_EXECUTION_ARTIFACT" in classified["reasons"]


def test_backtest_classifies_missing_selection_integrity_evidence_for_pr() -> None:
    artifact = {
        "artifact_type": "contract_preflight_result_artifact",
        "preflight_status": "passed",
        "control_signal": {"strategy_gate_decision": "ALLOW"},
        "pytest_execution": {"event_name": "pull_request", "pytest_execution_count": 1, "selected_targets": ["tests/x.py"]},
        "pytest_execution_record_ref": "outputs/contract_preflight/pytest_execution_record.json",
    }
    classified = classify_artifact(artifact)
    assert classified["classification"] == "suspect_missing_selection_integrity_evidence"
    assert "MISSING_PYTEST_SELECTION_INTEGRITY_ARTIFACT" in classified["reasons"]


def test_backtest_classifies_insufficient_evidence_explicitly() -> None:
    artifact = {
        "artifact_type": "contract_preflight_result_artifact",
        "control_signal": {"strategy_gate_decision": "ALLOW"},
        "pytest_execution": {"pytest_execution_count": 1, "selected_targets": ["tests/x.py"]},
        "pytest_selection_integrity": {"selection_integrity_decision": "ALLOW"},
    }
    classified = classify_artifact(artifact)
    assert classified["classification"] == "insufficient_evidence_to_determine"
    assert classified["confidence_level"] == "low"


def test_backtest_result_validates_contract() -> None:
    result = run_pytest_trust_gap_audit(
        scanned_artifacts=[],
        audit_scope={
            "roots": ["outputs"],
            "artifact_globs": ["**/contract_preflight_result_artifact.json"],
            "max_artifacts": 20,
            "repo_root": "/repo",
        },
        generated_at="2026-04-14T00:00:00Z",
    )
    validate_artifact(result, "pytest_trust_gap_backtest_result")
