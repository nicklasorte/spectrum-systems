from __future__ import annotations

from typing import Any, Mapping

REQUIRED_FIELDS = (
    "proof_id",
    "run_id",
    "trace_id",
    "owner_context",
    "failure_ref",
    "eval_ref",
    "repair_ref",
    "learn_ref",
    "recommend_ref",
)

STAGE_COMPRESSION_MAP = {
    "admission": "Admit",
    "admit": "Admit",
    "evaluation": "Prove",
    "prove": "Prove",
    "fix": "Repair",
    "repair": "Repair",
    "trend": "Learn",
    "learn": "Learn",
    "recommendation": "Recommend",
    "recommend": "Recommend",
}


def _normalize_stage(value: Any) -> str:
    stage = str(value or "").strip().lower()
    return STAGE_COMPRESSION_MAP.get(stage, "")


def build_rfx_loop_proof(*, proof: Mapping[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []

    for field in REQUIRED_FIELDS:
        if not proof.get(field):
            reasons.append("rfx_loop_proof_missing_required_field")

    stage_map = {}
    for key in ("admit", "prove", "repair", "learn", "recommend"):
        compressed = _normalize_stage(proof.get(f"{key}_stage") or key)
        if not compressed:
            reasons.append("rfx_loop_proof_unknown_stage")
            compressed = "Unknown"
        stage_map[key] = compressed

    failing_stage = _normalize_stage(proof.get("failing_stage"))
    if not failing_stage:
        reasons.append("rfx_loop_proof_failing_stage_missing")

    reason_codes = sorted({str(x) for x in (proof.get("reason_codes") or []) if str(x).strip()})
    if not reason_codes:
        reasons.append("rfx_loop_proof_reason_missing")

    if len(reason_codes) > 3:
        reasons.append("rfx_loop_proof_reason_flood")

    primary_reason = reason_codes[0] if reason_codes else "rfx_loop_proof_reason_missing"

    if not proof.get("repair_hint"):
        reasons.append("rfx_loop_proof_repair_hint_missing")

    if not proof.get("owner_context"):
        reasons.append("rfx_loop_proof_owner_missing")

    status = "valid" if not reasons else "invalid"
    return {
        "artifact_type": "rfx_loop_proof",
        "schema_version": "1.0.0",
        "status": status,
        "proof_id": proof.get("proof_id"),
        "run_id": proof.get("run_id"),
        "trace_id": proof.get("trace_id"),
        "owner_context": proof.get("owner_context"),
        "failing_stage": failing_stage or "Unknown",
        "stage_map": stage_map,
        "primary_reason_code": primary_reason,
        "reason_codes_emitted": sorted(set(reasons)),
        "debug": {
            "repair_hint": proof.get("repair_hint"),
            "operator_action": proof.get("operator_action") or "triage_failure",
        },
        "refs": {
            "failure_ref": proof.get("failure_ref"),
            "eval_ref": proof.get("eval_ref"),
            "repair_ref": proof.get("repair_ref"),
            "learn_ref": proof.get("learn_ref"),
            "recommend_ref": proof.get("recommend_ref"),
        },
        "signals": {
            "reason_count": len(reason_codes),
            "required_field_coverage": round(
                100.0 * sum(1 for field in REQUIRED_FIELDS if proof.get(field)) / len(REQUIRED_FIELDS),
                2,
            ),
        },
    }
