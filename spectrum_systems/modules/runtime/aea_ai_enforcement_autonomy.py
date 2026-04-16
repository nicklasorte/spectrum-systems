"""AEA runtime fail-closed enforcement helpers (surgical scope)."""

from __future__ import annotations

from typing import Any


class AEACompositionError(RuntimeError):
    """Fail-closed error when ownership or posture constraints are violated."""


REQUIRED_UPSTREAM_OWNERS = {
    "TLX",
    "CON",
    "EVL",
    "EVD",
    "LIN",
    "REP",
    "OBS",
    "PRM",
    "CTX",
    "CAP",
    "SLO",
    "QOS",
    "PRG",
}

PROTECTED_CDE_ARTIFACT_TYPES = {
    "cde_ai_bypass_kill_switch_decision",
    "cde_ai_trust_posture_decision",
    "cde_partial_disable_ai_decision",
}

BLOCKING_STATES = {"halt", "blocked", "freeze", "suspend"}


def detect_tlx_mediation(call_site: dict[str, Any]) -> bool:
    """Return True only for structurally-proven TLX mediation."""
    mediation = call_site.get("mediation")
    if not isinstance(mediation, dict):
        return False
    if mediation.get("owner") != "TLX":
        return False
    dispatch_ref = str(mediation.get("dispatch_record_ref", "")).strip()
    if not dispatch_ref:
        return False
    call_path = mediation.get("call_path")
    if not isinstance(call_path, list) or not all(isinstance(step, str) and step for step in call_path):
        return False
    if "tlx_dispatch" not in call_path and "tlx_ai_adapter_dispatch_record" not in call_path:
        return False
    if call_site.get("direct_provider_call", False):
        return False
    return True


def compose_owner_posture_refs(*, owner_artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing = sorted(REQUIRED_UPSTREAM_OWNERS - set(owner_artifacts.keys()))
    if missing:
        raise AEACompositionError(f"missing_required_owners:{','.join(missing)}")

    refs: dict[str, str] = {}
    for owner in sorted(REQUIRED_UPSTREAM_OWNERS):
        artifact = owner_artifacts[owner]
        payload_owner = str(artifact.get("owner", ""))
        if payload_owner != owner:
            raise AEACompositionError(f"owner_mismatch:{owner}:{payload_owner}")
        record_id = str(artifact.get("record_id", "")).strip()
        if not record_id:
            raise AEACompositionError(f"missing_record_id:{owner}")
        refs[owner] = record_id

    return {
        "composed_owner_refs": refs,
        "required_owner_set": sorted(REQUIRED_UPSTREAM_OWNERS),
        "composition_mode": "produce_reference_compose",
    }


def enforce_no_protected_authority_leaks(*, owner_artifacts: dict[str, dict[str, Any]]) -> None:
    for map_key, artifact in owner_artifacts.items():
        payload_owner = str(artifact.get("owner", ""))
        if payload_owner != map_key:
            raise AEACompositionError(f"map_key_owner_mismatch:{map_key}:{payload_owner}")

        artifact_type = str(artifact.get("artifact_type", ""))
        if artifact_type in PROTECTED_CDE_ARTIFACT_TYPES and payload_owner != "CDE":
            raise AEACompositionError(f"protected_authority_leak:{payload_owner}:{artifact_type}")


def require_cde_decision(*, cde_decision: dict[str, Any], required_owner_refs: dict[str, str]) -> dict[str, Any]:
    if set(required_owner_refs.keys()) != REQUIRED_UPSTREAM_OWNERS:
        missing = sorted(REQUIRED_UPSTREAM_OWNERS - set(required_owner_refs.keys()))
        raise AEACompositionError(f"incomplete_required_owner_refs:{','.join(missing)}")

    if cde_decision.get("owner") != "CDE":
        raise AEACompositionError("final_authority_must_be_cde")

    artifact_type = str(cde_decision.get("artifact_type", ""))
    if artifact_type not in PROTECTED_CDE_ARTIFACT_TYPES:
        raise AEACompositionError(f"unexpected_cde_artifact_type:{artifact_type}")

    evidence_refs = {str(item) for item in cde_decision.get("evidence_refs", [])}
    missing_refs = [ref for ref in required_owner_refs.values() if ref not in evidence_refs]
    if missing_refs:
        raise AEACompositionError(f"missing_composed_refs:{','.join(sorted(missing_refs))}")

    return cde_decision


def final_ai_full_system_rerun_status(*, final_tlx_status: str, coverage_status: str, cde_bundle: dict[str, dict[str, Any]]) -> str:
    if final_tlx_status != "pass" or coverage_status != "pass":
        return "fail"
    kill = str(cde_bundle.get("kill", {}).get("status", "")).lower()
    trust = str(cde_bundle.get("trust", {}).get("status", "")).lower()
    if kill in BLOCKING_STATES:
        return "fail"
    if trust in BLOCKING_STATES:
        return "fail"
    return "pass"
