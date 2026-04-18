from __future__ import annotations
from copy import deepcopy
import hashlib
from typing import Any, Dict, List
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract


def evaluate_promotion_requirements(*, trace_id: str, profile: Dict[str, any], artifact_family: str, provided: Dict[str, List[str]]) -> Dict[str, any]:
    ensure_contract(profile, "promotion_requirement_profile")
    req = profile.get("outputs", {}).get("families", {}).get(artifact_family)
    if not req:
        raise BNEBlockError(f"missing promotion requirement profile for family={artifact_family}")
    missing = {k: sorted(set(v) - set(provided.get(k, []))) for k, v in req.items()}
    flat_missing = [f"{k}:{x}" for k, vals in missing.items() for x in vals]
    record = ensure_contract({
        "artifact_type": "promotion_requirement_evaluation_record",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "outputs": {"artifact_family": artifact_family, "missing_prerequisites": flat_missing, "decision": "BLOCK" if flat_missing else "ALLOW"},
    }, "promotion_requirement_evaluation_record")
    return record


def issue_promotion_gate_decision_from_evidence(
    *,
    evidence: Dict[str, Any],
    run_id: str,
    trace_id: str,
    supporting_artifact_refs: List[str] | None = None,
    emitted_at: str = "2026-04-18T00:00:00Z",
) -> Dict[str, Any]:
    """Canonical GOV/CDE-aligned promotion decision issuance from non-authoritative evidence."""
    ensure_contract(evidence, "promotion_gate_evidence_record")
    reasons = [str(reason) for reason in evidence.get("blocking_reasons", []) if str(reason).strip()]
    promotion_allowed = not reasons and evidence.get("gate_status") == "pass"
    decision_seed = f"{trace_id}:{run_id}:{'ok' if promotion_allowed else 'blocked'}".encode("utf-8")
    decision_id = f"pgd-{hashlib.sha256(decision_seed).hexdigest()[:16]}"
    decision_artifact = {
        "artifact_type": "promotion_gate_decision_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "decision_id": decision_id,
        "run_id": run_id,
        "terminal_state": "ready_for_merge" if promotion_allowed else "blocked",
        "certification_status": "certified" if promotion_allowed else "missing_or_incomplete",
        "promotion_allowed": promotion_allowed,
        "missing_requirements": deepcopy(reasons),
        "supporting_artifact_refs": supporting_artifact_refs or [f"promotion_gate_evidence_record:{trace_id}"],
        "trace_refs": [trace_id],
        "emitted_at": emitted_at,
    }
    ensure_contract(decision_artifact, "promotion_gate_decision_artifact")
    return decision_artifact
