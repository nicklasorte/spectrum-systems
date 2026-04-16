from __future__ import annotations
from typing import Dict, List
from spectrum_systems.modules.runtime.bne_utils import ensure_contract


def derive_judgment_policy_candidates(*, trace_id: str, judgments: List[Dict[str, any]], threshold: int = 20) -> Dict[str, any]:
    strong = [j for j in judgments if len(j.get("rationale", "")) >= threshold]
    return ensure_contract({
        "artifact_type": "judgment_policy_candidate_artifact",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "outputs": {"candidate_count": len(strong), "rationale_threshold": threshold, "decision": "WARN" if len(strong) < len(judgments) else "ALLOW"},
    }, "judgment_policy_candidate_artifact")
