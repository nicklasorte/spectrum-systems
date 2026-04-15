from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.wpg.common import ensure_contract, stable_hash


def build_judgment_record(*, critique_artifact: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    findings = critique_artifact.get("outputs", {}).get("findings", [])
    selected_outcome = "block" if any(row.get("severity") == "high" for row in findings) else "approve"
    rationale = [f"finding:{row.get('section_title')}:{row.get('severity')}" for row in findings] or ["finding:none"]
    record = deepcopy(load_example("judgment_record"))
    record["artifact_id"] = f"jdg-{stable_hash(rationale)[:12]}"
    record["selected_outcome"] = selected_outcome
    record["cycle_id"] = "cycle-" + trace_id.lower().replace("_", "-")
    record["rationale_summary"] = "; ".join(rationale)
    record["rules_applied"] = ["critic_findings_considered"]
    return ensure_contract(record, "judgment_record")


def retrieve_precedent(*, judgment_record: Dict[str, Any], prior_records: List[Dict[str, Any]], trace_id: str) -> Dict[str, Any]:
    target = set(str(judgment_record.get("rationale_summary", "")).split(";"))
    scored = []
    for row in prior_records:
        prior_text = set(str(row.get("rationale_summary", "")).split(";"))
        overlap = len(target & prior_text)
        scored.append({"record_ref": row.get("artifact_id", "unknown"), "score": float(overlap)})
    scored.sort(key=lambda x: (-x["score"], x["record_ref"]))
    return ensure_contract(
        {
            "artifact_type": "precedent_retrieval",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "judgment_id": judgment_record.get("artifact_id", "unknown"),
            "precedents": scored[:3],
            "evaluation_refs": {
                "control_decision": {
                    "stage": "precedent_retrieval",
                    "decision": "ALLOW",
                    "reasons": ["precedent_ranked"],
                    "enforcement": {"action": "proceed"},
                }
            },
        },
        "precedent_retrieval",
    )


def evaluate_judgment(*, judgment_record: Dict[str, Any], precedent_retrieval: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    rationale = str(judgment_record.get("rationale_summary", "")).strip()
    precedents = precedent_retrieval.get("precedents", [])
    checks = [
        {"check_id": "rationale_non_empty", "passed": bool(rationale)},
        {"check_id": "precedent_considered", "passed": len(precedents) > 0},
    ]
    failed = [row["check_id"] for row in checks if not row["passed"]]
    decision = "BLOCK" if failed else "ALLOW"
    return ensure_contract(
        {
            "artifact_type": "judgment_eval",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "judgment_id": judgment_record.get("artifact_id", "unknown"),
            "checks": checks,
            "evaluation_refs": {
                "control_decision": {
                    "stage": "judgment_eval",
                    "decision": decision,
                    "reasons": failed or ["judgment_quality_ok"],
                    "enforcement": {"action": "trigger_repair" if failed else "proceed"},
                }
            },
        },
        "judgment_eval",
    )
