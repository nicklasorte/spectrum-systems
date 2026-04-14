from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.pytest_trust_gap_audit import classify_artifact, run_pytest_trust_gap_audit


def test_missing_evidence_is_flagged() -> None:
    artifact = {"artifact_type": "contract_preflight_result_artifact", "preflight_status": "passed", "control_signal": {"strategy_gate_decision": "ALLOW"}}
    classified = classify_artifact(artifact)
    assert "MISSING_PYTEST_EXECUTION_ARTIFACT" in classified["reason_codes"]


def test_weak_evidence_is_flagged() -> None:
    artifact = {
        "artifact_type": "contract_preflight_result_artifact",
        "preflight_status": "passed",
        "control_signal": {"strategy_gate_decision": "ALLOW"},
        "pytest_execution": {"event_name": "pull_request", "pytest_execution_count": 1, "selected_targets": ["tests/x.py"]},
        "pytest_selection_integrity": {"selection_integrity_decision": "BLOCK"},
    }
    classified = classify_artifact(artifact)
    assert classified["classification"] == "weak_evidence"
    assert "PYTEST_SELECTION_INTEGRITY_NOT_ALLOW" in classified["reason_codes"]


def test_clean_evidence_is_classified_clean() -> None:
    artifact = {
        "artifact_type": "contract_preflight_result_artifact",
        "preflight_status": "passed",
        "control_signal": {"strategy_gate_decision": "ALLOW"},
        "pytest_execution": {"event_name": "pull_request", "pytest_execution_count": 1, "selected_targets": ["tests/x.py"]},
        "pytest_selection_integrity": {"selection_integrity_decision": "ALLOW"},
    }
    classified = classify_artifact(artifact)
    assert classified["classification"] == "clean_evidence"


def test_audit_result_validates_contract() -> None:
    result = run_pytest_trust_gap_audit(scanned_artifacts=[], audit_scope={"roots": ["outputs"], "artifact_globs": ["**/contract_preflight_result_artifact.json"], "max_artifacts": 20, "repo_root": "/repo"})
    validate_artifact(result, "pytest_trust_gap_audit_result")
