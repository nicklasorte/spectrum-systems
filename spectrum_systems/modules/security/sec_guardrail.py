"""SEC: Security guardrail — high-risk execution requires SEL sign-off.

Artifacts flagged as HIGH risk cannot be promoted without an explicit
security approval record in the approvals store.
"""

from __future__ import annotations

from typing import Dict, Tuple


def get_security_approval(
    artifact_id: str,
    risk_level: str,
    approvals: Dict,
) -> Tuple[bool, Dict]:
    """Verify security approval for an artifact.

    Parameters
    ----------
    artifact_id:
        The artifact to check.
    risk_level:
        The risk classification ('HIGH', 'MEDIUM', 'LOW').
    approvals:
        Dict mapping artifact_id → approval record (from SEL).

    Returns
    -------
    (approved, report)
    """
    if risk_level != "HIGH":
        return True, {"reason": f"Risk level '{risk_level}' does not require SEC approval"}

    approval = approvals.get(artifact_id)
    if not approval or approval.get("status") != "approved":
        return False, {
            "reason": "HIGH-risk artifact requires SEL approval before promotion",
            "artifact_id": artifact_id,
            "approval_found": approval is not None,
        }

    return True, {
        "reason": "SEL approval verified",
        "artifact_id": artifact_id,
        "approval_id": approval.get("approval_id"),
    }
