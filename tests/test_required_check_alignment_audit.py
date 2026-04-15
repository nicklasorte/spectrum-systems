from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.required_check_alignment_audit import run_required_check_alignment_audit


WORKFLOW = {
    "name": "PR",
    "jobs": {
        "pytest": {
            "name": "pytest"
        }
    },
}


def test_required_check_alignment_passes_when_live_evidence_matches() -> None:
    result = run_required_check_alignment_audit(
        workflow_payload=WORKFLOW,
        required_policy_payload={
            "workflow": "PR",
            "authoritative_job_id": "pytest",
            "authoritative_display_name": "pytest",
            "required_status_check_name": "PR / pytest",
        },
        live_required_checks_payload={"required_status_checks": ["PR / pytest"]},
        generated_at="2026-04-14T00:00:00Z",
    )
    assert result["final_decision"] == "PASS"
    assert result["live_github_alignment_status"] == "aligned"
    assert result["mismatch_details"] == []
    validate_artifact(result, "required_check_alignment_audit_result")


def test_required_check_alignment_blocks_on_obsolete_local_policy_reference() -> None:
    result = run_required_check_alignment_audit(
        workflow_payload=WORKFLOW,
        required_policy_payload={
            "workflow": "PR",
            "authoritative_job_id": "pytest",
            "authoritative_display_name": "pytest",
            "required_status_check_name": "PR / pytest",
        },
        local_required_checks_payloads=[{"required_status_checks": ["contract-preflight"]}],
        generated_at="2026-04-14T00:00:00Z",
    )
    assert result["final_decision"] == "BLOCK"
    assert "LOCAL_REQUIRED_CHECKS_REFERENCE_OBSOLETE" in result["blocking_reasons"]


def test_required_check_alignment_warns_when_live_settings_cannot_be_proven() -> None:
    result = run_required_check_alignment_audit(
        workflow_payload=WORKFLOW,
        required_policy_payload={
            "workflow": "PR",
            "authoritative_job_id": "pytest",
            "authoritative_display_name": "pytest",
            "required_status_check_name": "PR / pytest",
        },
        generated_at="2026-04-14T00:00:00Z",
    )
    assert result["final_decision"] == "WARN"
    assert result["live_github_alignment_status"] == "unknown"
    assert result["operator_actions_required"]


def test_required_check_alignment_detects_policy_workflow_drift() -> None:
    result = run_required_check_alignment_audit(
        workflow_payload=WORKFLOW,
        required_policy_payload={
            "workflow": "artifact-boundary-legacy",
            "authoritative_job_id": "pytest",
            "authoritative_display_name": "pytest",
            "required_status_check_name": "PR / pytest",
        },
        generated_at="2026-04-14T00:00:00Z",
    )
    assert result["final_decision"] == "BLOCK"
    assert "POLICY_WORKFLOW_MISMATCH" in result["blocking_reasons"]
    mismatch_classes = {entry["mismatch_class"] for entry in result["mismatch_details"]}
    assert "POLICY_WORKFLOW_MISMATCH" in mismatch_classes


def test_required_check_alignment_drift_is_structured_when_workflow_job_missing() -> None:
    result = run_required_check_alignment_audit(
        workflow_payload={"name": "PR", "jobs": {}},
        required_policy_payload={
            "workflow": "PR",
            "authoritative_job_id": "pytest",
            "authoritative_display_name": "pytest",
            "required_status_check_name": "PR / pytest",
        },
        generated_at="2026-04-14T00:00:00Z",
    )
    assert result["final_decision"] == "BLOCK"
    mismatch_classes = {entry["mismatch_class"] for entry in result["mismatch_details"]}
    assert "WORKFLOW_MISSING_AUTHORITATIVE_JOB" in mismatch_classes
    assert "POLICY_JOB_ID_MISMATCH" not in result["blocking_reasons"]
