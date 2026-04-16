from __future__ import annotations
from typing import Dict, List
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
