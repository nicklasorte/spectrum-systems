from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.required_check_alignment_audit import run_required_check_alignment_audit


WORKFLOW = {
    "name": "artifact-boundary",
    "jobs": {
        "pytest-pr": {
            "name": "PR / pytest"
        }
    },
}


def test_required_check_alignment_passes_when_live_evidence_matches() -> None:
    result = run_required_check_alignment_audit(
        workflow_payload=WORKFLOW,
        required_policy_payload={
            "workflow": "artifact-boundary",
            "authoritative_job_id": "pytest-pr",
            "authoritative_display_name": "PR / pytest",
            "required_status_check_name": "PR / pytest",
        },
        live_required_checks_payload={"required_status_checks": ["PR / pytest"]},
        generated_at="2026-04-14T00:00:00Z",
    )
    assert result["final_decision"] == "PASS"
    assert result["live_github_alignment_status"] == "aligned"
    validate_artifact(result, "required_check_alignment_audit_result")


def test_required_check_alignment_blocks_on_obsolete_local_policy_reference() -> None:
    result = run_required_check_alignment_audit(
        workflow_payload=WORKFLOW,
        required_policy_payload={
            "workflow": "artifact-boundary",
            "authoritative_job_id": "pytest-pr",
            "authoritative_display_name": "PR / pytest",
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
            "workflow": "artifact-boundary",
            "authoritative_job_id": "pytest-pr",
            "authoritative_display_name": "PR / pytest",
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
            "authoritative_job_id": "pytest-pr",
            "authoritative_display_name": "PR / pytest",
            "required_status_check_name": "PR / pytest",
        },
        generated_at="2026-04-14T00:00:00Z",
    )
    assert result["final_decision"] == "BLOCK"
    assert "POLICY_WORKFLOW_MISMATCH" in result["blocking_reasons"]
