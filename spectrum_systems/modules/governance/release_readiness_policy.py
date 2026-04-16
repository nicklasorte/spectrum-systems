from __future__ import annotations
from typing import Dict
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract

REQUIRED_ARTIFACT_KEYS = ["eval_coverage", "critique", "contradictions", "comment_dispositions", "override_hotspots", "evidence_gap_hotspots", "drift_signals", "checkpoint"]

def evaluate_release_readiness(*, trace_id: str, inputs: Dict[str, dict]) -> Dict[str, dict]:
    missing = [k for k in REQUIRED_ARTIFACT_KEYS if k not in inputs]
    if missing:
        raise BNEBlockError(f"missing required downstream artifacts: {missing}")
    unresolved_critical = bool(inputs["contradictions"].get("critical_open", 0) or inputs["critique"].get("critical_open", 0) or inputs["comment_dispositions"].get("unresolved_critical", 0))
    policy_result = ensure_contract({
        "artifact_type": "release_readiness_policy_result",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "outputs": {"missing_inputs": missing, "unresolved_critical": unresolved_critical, "decision": "BLOCK" if unresolved_critical else "ALLOW"},
    }, "release_readiness_policy_result")
    readiness = ensure_contract({
        "artifact_type": "wpg_release_readiness_artifact",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "outputs": {"decision": policy_result["outputs"]["decision"], "consumed_inputs": REQUIRED_ARTIFACT_KEYS},
    }, "wpg_release_readiness_artifact")
    return {"readiness": readiness, "policy_result": policy_result}
