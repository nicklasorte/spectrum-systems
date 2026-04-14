"""Deterministic required PR check alignment audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"not_object:{path}")
    return payload


def _extract_authoritative_job(workflow_payload: dict[str, Any], *, authoritative_job_id: str) -> tuple[str, str, str]:
    jobs = workflow_payload.get("jobs")
    if not isinstance(jobs, dict):
        raise ValueError("workflow_missing_jobs")
    pytest_job = jobs.get(authoritative_job_id)
    if not isinstance(pytest_job, dict):
        raise ValueError("workflow_missing_authoritative_job")
    display_name = str(pytest_job.get("name") or "").strip()
    if not display_name:
        raise ValueError("workflow_missing_authoritative_job_name")
    workflow_name = str(workflow_payload.get("name") or "").strip() or "artifact-boundary"
    return workflow_name, authoritative_job_id, display_name


def run_required_check_alignment_audit(
    *,
    workflow_payload: dict[str, Any],
    required_policy_payload: dict[str, Any],
    local_required_checks_payloads: list[dict[str, Any]] | None = None,
    live_required_checks_payload: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    policy_job_id = str(required_policy_payload.get("authoritative_job_id") or "").strip()
    if not policy_job_id:
        raise ValueError("policy_missing_authoritative_job_id")

    workflow_name, authoritative_job_id, authoritative_display_name = _extract_authoritative_job(
        workflow_payload,
        authoritative_job_id=policy_job_id,
    )
    expected_required_check = f"{workflow_name} / {authoritative_display_name}"

    local_required_checks_payloads = local_required_checks_payloads or []

    blocking_reasons: list[str] = []
    operator_actions_required: list[str] = []

    required_status_check_name = str(required_policy_payload.get("required_status_check_name") or "").strip()
    policy_workflow = str(required_policy_payload.get("workflow") or "").strip()
    policy_job_id = str(required_policy_payload.get("authoritative_job_id") or "").strip()
    policy_display_name = str(required_policy_payload.get("authoritative_display_name") or "").strip()

    if required_status_check_name != expected_required_check:
        blocking_reasons.append("POLICY_REQUIRED_CHECK_NAME_MISMATCH")
    if policy_workflow != workflow_name:
        blocking_reasons.append("POLICY_WORKFLOW_MISMATCH")
    if policy_job_id != authoritative_job_id:
        blocking_reasons.append("POLICY_JOB_ID_MISMATCH")
    if policy_display_name != authoritative_display_name:
        blocking_reasons.append("POLICY_DISPLAY_NAME_MISMATCH")

    local_policy_alignment_status = "aligned"
    if blocking_reasons:
        local_policy_alignment_status = "contradiction"

    local_config_reasons: list[str] = []
    for payload in local_required_checks_payloads:
        checks = payload.get("required_status_checks")
        if not isinstance(checks, list):
            continue
        normalized = {str(item).strip() for item in checks if str(item).strip()}
        if not normalized:
            continue
        if expected_required_check not in normalized:
            local_config_reasons.append("LOCAL_REQUIRED_CHECKS_MISSING_EXPECTED")
        obsolete = {"contract-preflight"}
        if obsolete & normalized:
            local_config_reasons.append("LOCAL_REQUIRED_CHECKS_REFERENCE_OBSOLETE")

    if local_config_reasons:
        local_policy_alignment_status = "contradiction"
        blocking_reasons.extend(local_config_reasons)

    live_github_alignment_status = "unknown"
    if live_required_checks_payload is not None:
        checks = live_required_checks_payload.get("required_status_checks")
        if isinstance(checks, list):
            normalized = {str(item).strip() for item in checks if str(item).strip()}
            if expected_required_check in normalized:
                live_github_alignment_status = "aligned"
            else:
                live_github_alignment_status = "misaligned"
                blocking_reasons.append("LIVE_GITHUB_REQUIRED_CHECK_MISSING_EXPECTED")
            if "contract-preflight" in normalized:
                live_github_alignment_status = "misaligned"
                blocking_reasons.append("LIVE_GITHUB_REQUIRED_CHECK_REFERENCES_OBSOLETE")
        else:
            blocking_reasons.append("LIVE_GITHUB_REQUIRED_CHECKS_UNREADABLE")
            live_github_alignment_status = "unknown"

    if live_github_alignment_status == "unknown":
        operator_actions_required.append(
            "Verify GitHub branch protection required status checks include exactly 'PR / pytest' and remove obsolete checks."
        )

    blocking_reasons = sorted(set(blocking_reasons))
    operator_actions_required = sorted(set(operator_actions_required))

    if blocking_reasons:
        final_decision = "BLOCK"
    elif live_github_alignment_status == "aligned":
        final_decision = "PASS"
    else:
        final_decision = "WARN"

    result = {
        "artifact_type": "required_check_alignment_audit_result",
        "schema_version": "1.0.0",
        "expected_required_check": expected_required_check,
        "workflow_name": workflow_name,
        "authoritative_job_id": authoritative_job_id,
        "authoritative_display_name": authoritative_display_name,
        "local_policy_alignment_status": local_policy_alignment_status,
        "live_github_alignment_status": live_github_alignment_status,
        "final_decision": final_decision,
        "blocking_reasons": blocking_reasons,
        "operator_actions_required": operator_actions_required,
        "generated_at": generated_at or _utc_now(),
    }
    validate_artifact(result, "required_check_alignment_audit_result")
    return result


__all__ = ["run_required_check_alignment_audit"]
