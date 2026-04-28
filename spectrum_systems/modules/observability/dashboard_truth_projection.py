"""OC-07..09: Dashboard truth projection (non-owning support seam).

Builds a read-only projection of repo proof onto the dashboard / public
surface. The projection answers eight questions in a single record:

    current_status, latest_proof_ref, owning_system, reason_code,
    bottleneck_category, next_safe_action, freshness_status,
    alignment_status

Drift between repo truth and the dashboard surface is reported as
findings (``missing_owner``, ``stale_status``, ``digest_mismatch``,
``ref_corrupt``, ``missing_proof_ref``, ``missing_dashboard_ref``,
``category_mismatch``). The projection enforces fail-closed behaviour:

  * any ``digest_mismatch``, ``ref_corrupt``, ``missing_proof_ref``,
    or ``missing_dashboard_ref`` finding promotes alignment_status to
    at least ``drifted`` and severity ``block``.
  * ``stale_status`` forces ``freshness_status = stale``.
  * absent inputs (no repo_truth or no dashboard_view) yield
    ``alignment_status = unknown`` and ``current_status = unknown``.

Module is non-owning. MAP retains projection topology authority; the
projection itself is an evidence-binding view.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional


class DashboardTruthProjectionError(ValueError):
    """Raised when the projection cannot be deterministically constructed."""


def _digest_of(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _truthy_str(v: Any) -> Optional[str]:
    if isinstance(v, str) and v.strip():
        return v
    return None


def build_dashboard_truth_projection(
    *,
    projection_id: str,
    audit_timestamp: str,
    repo_truth: Optional[Mapping[str, Any]],
    dashboard_view: Optional[Mapping[str, Any]],
    freshness_audit: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a deterministic dashboard truth projection record.

    Inputs:
      * ``repo_truth`` — the local proof view, typically derived from
        a ``loop_proof_bundle`` and ``bottleneck_classification``.
        Expected keys: ``current_status``, ``latest_proof_ref``,
        ``owning_system``, ``reason_code``, ``bottleneck_category``,
        ``next_safe_action``, ``proof_digest``.
      * ``dashboard_view`` — the dashboard/public artifact reference,
        same shape as ``repo_truth``.
      * ``freshness_audit`` — optional output of the trust artifact
        freshness audit. The projection consumes only the
        ``overall_status`` field (``ok`` / ``stale`` / ``unknown``).
    """
    if not isinstance(projection_id, str) or not projection_id.strip():
        raise DashboardTruthProjectionError(
            "projection_id must be a non-empty string"
        )
    if not isinstance(audit_timestamp, str) or not audit_timestamp.strip():
        raise DashboardTruthProjectionError(
            "audit_timestamp must be a non-empty string"
        )

    findings: List[Dict[str, Any]] = []

    if repo_truth is None and dashboard_view is None:
        return {
            "artifact_type": "dashboard_truth_projection",
            "schema_version": "1.0.0",
            "projection_id": projection_id,
            "audit_timestamp": audit_timestamp,
            "current_status": "unknown",
            "latest_proof_ref": None,
            "owning_system": None,
            "reason_code": "DASHBOARD_PROJECTION_UNKNOWN_NO_INPUT",
            "bottleneck_category": "unknown",
            "next_safe_action": "investigate",
            "freshness_status": "unknown",
            "alignment_status": "unknown",
            "alignment_findings": [],
            "non_authority_assertions": [
                "preparatory_only",
                "not_control_authority",
                "not_certification_authority",
                "not_enforcement_authority",
            ],
        }

    if repo_truth is None:
        findings.append(
            {
                "finding_kind": "missing_proof_ref",
                "reason_code": "DASHBOARD_PROJECTION_MISSING_REPO_PROOF",
                "severity": "block",
            }
        )
        repo_truth = {}
    if dashboard_view is None:
        findings.append(
            {
                "finding_kind": "missing_dashboard_ref",
                "reason_code": "DASHBOARD_PROJECTION_MISSING_DASHBOARD_VIEW",
                "severity": "block",
            }
        )
        dashboard_view = {}

    repo_status = _truthy_str(repo_truth.get("current_status")) or "unknown"
    dash_status = _truthy_str(dashboard_view.get("current_status")) or "unknown"
    repo_proof_ref = _truthy_str(repo_truth.get("latest_proof_ref"))
    dash_proof_ref = _truthy_str(dashboard_view.get("latest_proof_ref"))
    repo_owner = _truthy_str(repo_truth.get("owning_system"))
    dash_owner = _truthy_str(dashboard_view.get("owning_system"))
    repo_reason = _truthy_str(repo_truth.get("reason_code")) or "DASHBOARD_PROJECTION_UNKNOWN"
    repo_category = _truthy_str(repo_truth.get("bottleneck_category")) or "unknown"
    dash_category = _truthy_str(dashboard_view.get("bottleneck_category"))
    repo_action = _truthy_str(repo_truth.get("next_safe_action")) or "investigate"
    repo_digest = _truthy_str(repo_truth.get("proof_digest"))
    dash_digest = _truthy_str(dashboard_view.get("proof_digest"))

    # missing owner finding
    if repo_owner and not dash_owner:
        findings.append(
            {
                "finding_kind": "missing_owner",
                "reason_code": "DASHBOARD_PROJECTION_MISSING_OWNER",
                "severity": "warn",
            }
        )

    # status drift / stale_status
    if repo_status != dash_status:
        findings.append(
            {
                "finding_kind": "stale_status",
                "reason_code": "DASHBOARD_PROJECTION_STATUS_DRIFT",
                "severity": "block",
            }
        )

    # digest mismatch
    if repo_digest and dash_digest and repo_digest != dash_digest:
        findings.append(
            {
                "finding_kind": "digest_mismatch",
                "reason_code": "DASHBOARD_PROJECTION_DIGEST_MISMATCH",
                "severity": "block",
            }
        )

    # ref corrupt: dashboard ref non-empty but neither matches repo ref nor
    # is a syntactically valid identifier (we treat any string with control
    # characters or whitespace as corrupt).
    if dash_proof_ref is not None and (
        any(ch.isspace() for ch in dash_proof_ref) or not dash_proof_ref.isprintable()
    ):
        findings.append(
            {
                "finding_kind": "ref_corrupt",
                "reason_code": "DASHBOARD_PROJECTION_REF_CORRUPT",
                "severity": "block",
            }
        )

    # category mismatch
    if dash_category is not None and dash_category != repo_category:
        findings.append(
            {
                "finding_kind": "category_mismatch",
                "reason_code": "DASHBOARD_PROJECTION_CATEGORY_MISMATCH",
                "severity": "block",
            }
        )

    # freshness status from audit
    freshness_status = "unknown"
    if isinstance(freshness_audit, Mapping):
        overall = _truthy_str(freshness_audit.get("overall_status"))
        if overall == "ok":
            freshness_status = "fresh"
        elif overall in ("stale", "blocked"):
            freshness_status = "stale"
        elif overall == "unknown":
            freshness_status = "unknown"

    if freshness_status == "stale":
        findings.append(
            {
                "finding_kind": "stale_status",
                "reason_code": "DASHBOARD_PROJECTION_PROOF_STALE",
                "severity": "block",
            }
        )

    block_findings = [f for f in findings if f.get("severity") == "block"]
    warn_findings = [f for f in findings if f.get("severity") == "warn"]

    # Determine alignment_status (deterministic)
    if any(
        f["finding_kind"] in ("missing_proof_ref", "missing_dashboard_ref")
        for f in findings
    ):
        alignment_status = "missing"
    elif any(
        f["finding_kind"] in ("ref_corrupt", "digest_mismatch")
        for f in findings
    ):
        alignment_status = "corrupt"
    elif block_findings:
        alignment_status = "drifted"
    elif warn_findings:
        alignment_status = "drifted"
    elif repo_status == "unknown" or dash_status == "unknown":
        alignment_status = "unknown"
    else:
        alignment_status = "aligned"

    # current_status: aligned -> repo_status; otherwise unknown unless
    # we have a fresh repo_status (block findings still require unknown).
    if alignment_status == "aligned":
        current_status = repo_status if repo_status in ("pass", "block", "freeze") else "unknown"
    else:
        current_status = "unknown"

    return {
        "artifact_type": "dashboard_truth_projection",
        "schema_version": "1.0.0",
        "projection_id": projection_id,
        "audit_timestamp": audit_timestamp,
        "current_status": current_status,
        "latest_proof_ref": repo_proof_ref,
        "owning_system": repo_owner,
        "reason_code": repo_reason,
        "bottleneck_category": repo_category,
        "next_safe_action": repo_action,
        "freshness_status": freshness_status,
        "alignment_status": alignment_status,
        "alignment_findings": findings,
        "non_authority_assertions": [
            "preparatory_only",
            "not_control_authority",
            "not_certification_authority",
            "not_enforcement_authority",
        ],
    }
