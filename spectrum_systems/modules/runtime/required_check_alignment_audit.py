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


def _mismatch(
    *,
    mismatch_class: str,
    expected_policy_value: str,
    discovered_workflow_value: str,
    recommended_remediation: str,
    blocking: bool = True,
) -> dict[str, Any]:
    return {
        "mismatch_class": mismatch_class,
        "expected_policy_value": expected_policy_value,
        "discovered_workflow_value": discovered_workflow_value,
        "blocking": bool(blocking),
        "recommended_remediation": recommended_remediation,
    }


def run_required_check_alignment_audit(
    *,
    workflow_payload: dict[str, Any],
    required_policy_payload: dict[str, Any],
    local_required_checks_payloads: list[dict[str, Any]] | None = None,
    live_required_checks_payload: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    policy_job_id = str(required_policy_payload.get("authoritative_job_id") or "").strip()
    policy_workflow = str(required_policy_payload.get("workflow") or "").strip()
    policy_display_name = str(required_policy_payload.get("authoritative_display_name") or "").strip()
    required_status_check_name = str(required_policy_payload.get("required_status_check_name") or "").strip()

    discovered_workflow_name = str(workflow_payload.get("name") or "").strip() or "artifact-boundary"
    discovered_job_id = policy_job_id or "pytest"
    discovered_display_name = ""
    expected_required_check = required_status_check_name or f"{policy_workflow or discovered_workflow_name} / {policy_display_name or 'pytest'}"
    mismatch_details: list[dict[str, Any]] = []

    jobs = workflow_payload.get("jobs")
    if not isinstance(jobs, dict):
        mismatch_details.append(
            _mismatch(
                mismatch_class="WORKFLOW_MISSING_JOBS",
                expected_policy_value="workflow.jobs object with authoritative job",
                discovered_workflow_value="missing_or_invalid_workflow.jobs",
                recommended_remediation="Define workflow jobs map and include policy authoritative_job_id.",
            )
        )
    elif policy_job_id and isinstance(jobs.get(policy_job_id), dict):
        discovered_job = jobs.get(policy_job_id) or {}
        discovered_display_name = str(discovered_job.get("name") or "").strip()
        discovered_job_id = policy_job_id
        expected_required_check = f"{discovered_workflow_name} / {discovered_display_name or policy_display_name or 'pytest'}"
    else:
        mismatch_details.append(
            _mismatch(
                mismatch_class="WORKFLOW_MISSING_AUTHORITATIVE_JOB",
                expected_policy_value=policy_job_id or "authoritative_job_id",
                discovered_workflow_value="missing",
                recommended_remediation="Align policy authoritative_job_id to a real workflow job id and set a job name.",
            )
        )

    if policy_job_id and not discovered_display_name and isinstance(jobs, dict) and isinstance(jobs.get(policy_job_id), dict):
        mismatch_details.append(
            _mismatch(
                mismatch_class="WORKFLOW_MISSING_AUTHORITATIVE_JOB_NAME",
                expected_policy_value="non-empty workflow job display name",
                discovered_workflow_value="empty",
                recommended_remediation="Set jobs.<authoritative_job_id>.name so required check surface is explicit.",
            )
        )

    local_required_checks_payloads = local_required_checks_payloads or []

    blocking_reasons: list[str] = []
    operator_actions_required: list[str] = []
    authoritative_job_id = discovered_job_id
    authoritative_display_name = discovered_display_name or policy_display_name or "pytest"
    workflow_name = discovered_workflow_name

    if required_status_check_name != expected_required_check:
        blocking_reasons.append("POLICY_REQUIRED_CHECK_NAME_MISMATCH")
        mismatch_details.append(
            _mismatch(
                mismatch_class="POLICY_REQUIRED_CHECK_NAME_MISMATCH",
                expected_policy_value=required_status_check_name or "<missing>",
                discovered_workflow_value=expected_required_check,
                recommended_remediation="Set policy required_status_check_name to match workflow/check surface.",
            )
        )
    if policy_workflow != workflow_name:
        blocking_reasons.append("POLICY_WORKFLOW_MISMATCH")
        mismatch_details.append(
            _mismatch(
                mismatch_class="POLICY_WORKFLOW_MISMATCH",
                expected_policy_value=policy_workflow or "<missing>",
                discovered_workflow_value=workflow_name,
                recommended_remediation="Set policy workflow to the authoritative workflow name.",
            )
        )
    if policy_job_id != authoritative_job_id:
        blocking_reasons.append("POLICY_JOB_ID_MISMATCH")
        mismatch_details.append(
            _mismatch(
                mismatch_class="POLICY_JOB_ID_MISMATCH",
                expected_policy_value=policy_job_id or "<missing>",
                discovered_workflow_value=authoritative_job_id,
                recommended_remediation="Set policy authoritative_job_id to the authoritative workflow job id.",
            )
        )
    if policy_display_name != authoritative_display_name:
        blocking_reasons.append("POLICY_DISPLAY_NAME_MISMATCH")
        mismatch_details.append(
            _mismatch(
                mismatch_class="POLICY_DISPLAY_NAME_MISMATCH",
                expected_policy_value=policy_display_name or "<missing>",
                discovered_workflow_value=authoritative_display_name,
                recommended_remediation="Set policy authoritative_display_name to the workflow job display name.",
            )
        )

    local_policy_alignment_status = "aligned"
    if blocking_reasons or mismatch_details:
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
            mismatch_details.append(
                _mismatch(
                    mismatch_class="LOCAL_REQUIRED_CHECKS_MISSING_EXPECTED",
                    expected_policy_value=expected_required_check,
                    discovered_workflow_value=", ".join(sorted(normalized)) or "<empty>",
                    recommended_remediation="Update local required status checks evidence to include authoritative check.",
                )
            )
        obsolete = {"contract-preflight"}
        if obsolete & normalized:
            local_config_reasons.append("LOCAL_REQUIRED_CHECKS_REFERENCE_OBSOLETE")
            mismatch_details.append(
                _mismatch(
                    mismatch_class="LOCAL_REQUIRED_CHECKS_REFERENCE_OBSOLETE",
                    expected_policy_value="no obsolete required checks",
                    discovered_workflow_value=", ".join(sorted(obsolete & normalized)),
                    recommended_remediation="Remove obsolete required checks from local branch-protection snapshots.",
                )
            )

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
                mismatch_details.append(
                    _mismatch(
                        mismatch_class="LIVE_GITHUB_REQUIRED_CHECK_MISSING_EXPECTED",
                        expected_policy_value=expected_required_check,
                        discovered_workflow_value=", ".join(sorted(normalized)) or "<empty>",
                        recommended_remediation="Update GitHub branch protection to require the authoritative check.",
                    )
                )
            if "contract-preflight" in normalized:
                live_github_alignment_status = "misaligned"
                blocking_reasons.append("LIVE_GITHUB_REQUIRED_CHECK_REFERENCES_OBSOLETE")
                mismatch_details.append(
                    _mismatch(
                        mismatch_class="LIVE_GITHUB_REQUIRED_CHECK_REFERENCES_OBSOLETE",
                        expected_policy_value="no obsolete checks",
                        discovered_workflow_value="contract-preflight",
                        recommended_remediation="Remove obsolete contract-preflight from GitHub required checks.",
                    )
                )
        else:
            blocking_reasons.append("LIVE_GITHUB_REQUIRED_CHECKS_UNREADABLE")
            live_github_alignment_status = "unknown"
            mismatch_details.append(
                _mismatch(
                    mismatch_class="LIVE_GITHUB_REQUIRED_CHECKS_UNREADABLE",
                    expected_policy_value="readable required_status_checks array",
                    discovered_workflow_value="missing_or_invalid_required_status_checks",
                    recommended_remediation="Collect readable live required checks evidence payload and rerun audit.",
                )
            )

    if live_github_alignment_status == "unknown":
        operator_actions_required.append(
            "Verify GitHub branch protection required status checks include exactly 'PR / pytest' and remove obsolete checks."
        )

    blocking_reasons = sorted(set(blocking_reasons))
    operator_actions_required = sorted(set(operator_actions_required))
    mismatch_details = sorted(
        mismatch_details,
        key=lambda item: (
            str(item.get("mismatch_class") or ""),
            str(item.get("expected_policy_value") or ""),
            str(item.get("discovered_workflow_value") or ""),
        ),
    )

    if any(bool(item.get("blocking")) for item in mismatch_details) or blocking_reasons:
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
        "mismatch_details": mismatch_details,
        "operator_actions_required": operator_actions_required,
        "generated_at": generated_at or _utc_now(),
    }
    validate_artifact(result, "required_check_alignment_audit_result")
    return result


__all__ = ["run_required_check_alignment_audit"]
