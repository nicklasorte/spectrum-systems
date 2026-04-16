"""AEA-001-FIX composition helpers.

This module intentionally avoids emitting owner-local artifacts for TLX/CON/EVL/EVD/LIN/REP/OBS/
PRM/CTX/CAP/SLO/QOS/PRG. Those artifacts must be produced by their canonical owner modules and
only referenced here for integration composition.
"""

from __future__ import annotations

from typing import Any


class AEACompositionError(RuntimeError):
    """Fail-closed error when composition input violates ownership boundaries."""


PROTECTED_CDE_ARTIFACT_TYPES = {
    "cde_ai_bypass_kill_switch_decision",
    "cde_ai_trust_posture_decision",
    "cde_partial_disable_ai_decision",
}


def compose_owner_posture_refs(*, owner_artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compose by reference only; never recompute owner-local posture."""
    refs: dict[str, str] = {}
    for owner, artifact in owner_artifacts.items():
        artifact_owner = str(artifact.get("owner", ""))
        if artifact_owner != owner:
            raise AEACompositionError(f"owner_mismatch:{owner}:{artifact_owner}")
        record_id = str(artifact.get("record_id", "")).strip()
        if not record_id:
            raise AEACompositionError(f"missing_record_id:{owner}")
        refs[owner] = record_id

    return {
        "composed_owner_refs": refs,
        "owner_count": len(refs),
        "composition_mode": "produce_reference_compose",
    }


def enforce_no_protected_authority_leaks(*, owner_artifacts: dict[str, dict[str, Any]]) -> None:
    """Reject non-CDE artifacts that look like protected continuation authority outputs."""
    for owner, artifact in owner_artifacts.items():
        artifact_type = str(artifact.get("artifact_type", ""))
        if artifact_type in PROTECTED_CDE_ARTIFACT_TYPES and owner != "CDE":
            raise AEACompositionError(f"protected_authority_leak:{owner}:{artifact_type}")


def require_cde_decision(*, cde_decision: dict[str, Any], required_owner_refs: dict[str, str]) -> dict[str, Any]:
    """Accept only CDE-owned final authority outputs and ensure they reference composed posture refs."""
    if cde_decision.get("owner") != "CDE":
        raise AEACompositionError("final_authority_must_be_cde")

    artifact_type = str(cde_decision.get("artifact_type", ""))
    if artifact_type not in PROTECTED_CDE_ARTIFACT_TYPES:
        raise AEACompositionError(f"unexpected_cde_artifact_type:{artifact_type}")

    evidence_refs = {str(item) for item in cde_decision.get("evidence_refs", [])}
    missing = [ref for ref in required_owner_refs.values() if ref not in evidence_refs]
    if missing:
        raise AEACompositionError(f"missing_composed_refs:{','.join(sorted(missing))}")

    return cde_decision
