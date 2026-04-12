"""FRE bounded repair generation/evaluation/readiness foundation.

FRE is non-authoritative and never executes repair actions.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class FRERepairFlowError(ValueError):
    """Raised when FRE boundary checks fail closed."""


_ALLOWED_FAILURE_TYPES = {
    "missing_artifact",
    "invalid_artifact_shape",
    "cross_artifact_mismatch",
    "authenticity_lineage_mismatch",
    "slice_contract_mismatch",
    "runtime_logic_defect",
    "policy_blocked",
    "retry_budget_exhausted",
}


def _canonical_digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _required_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FRERepairFlowError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_refs(values: Any, *, field: str, min_items: int = 1) -> list[str]:
    if not isinstance(values, list):
        raise FRERepairFlowError(f"{field} must be a list")
    refs = sorted({str(item).strip() for item in values if isinstance(item, str) and item.strip()})
    if len(refs) < min_items:
        raise FRERepairFlowError(f"{field} must include at least {min_items} non-empty entries")
    return refs


def generate_repair_candidate(*, failure_packet: Mapping[str, Any], trace_id: str, max_scope_refs: int = 5) -> dict[str, Any]:
    """Generate deterministic bounded repair candidate from normalized failure packet."""
    if failure_packet.get("artifact_type") != "execution_failure_packet":
        raise FRERepairFlowError("FRE upstream requires execution_failure_packet artifact_type")

    failure_type = _required_str(failure_packet.get("classified_failure_type"), "classified_failure_type")
    if failure_type not in _ALLOWED_FAILURE_TYPES:
        raise FRERepairFlowError("FRE upstream failure class is not allowed")

    scope_refs = _normalize_refs(failure_packet.get("affected_artifact_refs", []), field="affected_artifact_refs")
    if len(scope_refs) > max_scope_refs:
        raise FRERepairFlowError("repair candidate rejected: scope exceeds bounded authority")

    bounded_actions = [f"update_artifact:{ref}" for ref in scope_refs]
    candidate_payload = {
        "failure_packet_id": _required_str(failure_packet.get("failure_packet_id"), "failure_packet_id"),
        "scope_refs": scope_refs,
        "failure_type": failure_type,
        "trace_id": _required_str(trace_id, "trace_id"),
    }
    candidate_id = f"fre-rc-{_canonical_digest(candidate_payload)[:16]}"

    candidate = {
        "artifact_type": "repair_candidate",
        "schema_version": "1.0.0",
        "candidate_id": candidate_id,
        "trace_id": trace_id,
        "failure_packet_ref": f"execution_failure_packet:{failure_packet['failure_packet_id']}",
        "lineage_refs": [
            f"execution_failure_packet:{failure_packet['failure_packet_id']}",
            f"trace:{trace_id}",
        ],
        "scope_refs": scope_refs,
        "bounded_actions": bounded_actions,
        "required_evidence_refs": _normalize_refs(
            list(failure_packet.get("trace_refs", [])) + list(failure_packet.get("validation_refs", [])),
            field="required_evidence_refs",
        ),
        "non_authority_assertions": [
            "candidate_only_non_authoritative",
            "fre_must_not_execute_repairs",
            "fre_must_not_authorize_continuation",
        ],
    }
    validate_artifact(candidate, "repair_candidate")
    return candidate


def evaluate_repair_candidate(*, repair_candidate: Mapping[str, Any], replay_compatible: bool = True) -> dict[str, Any]:
    """Evaluate boundedness and structural viability before downstream use."""
    validate_artifact(dict(repair_candidate), "repair_candidate")

    fail_reasons: list[str] = []
    if not repair_candidate.get("scope_refs"):
        fail_reasons.append("scope_refs_missing")
    if not repair_candidate.get("required_evidence_refs"):
        fail_reasons.append("required_evidence_missing")
    if any(not str(x).startswith("update_artifact:") for x in repair_candidate.get("bounded_actions", [])):
        fail_reasons.append("non_bounded_action_detected")
    if replay_compatible is not True:
        fail_reasons.append("replay_provenance_incompatible")

    status = "pass" if not fail_reasons else "fail"
    eval_id = f"fre-reval-{_canonical_digest([repair_candidate['candidate_id'], fail_reasons])[:16]}"
    result = {
        "artifact_type": "repair_eval_result",
        "schema_version": "1.0.0",
        "eval_id": eval_id,
        "trace_id": repair_candidate["trace_id"],
        "repair_candidate_ref": f"repair_candidate:{repair_candidate['candidate_id']}",
        "boundedness_passed": "non_bounded_action_detected" not in fail_reasons and "scope_refs_missing" not in fail_reasons,
        "scope_compliance_passed": bool(repair_candidate.get("scope_refs")),
        "evidence_presence_passed": "required_evidence_missing" not in fail_reasons,
        "replay_provenance_compatible": replay_compatible is True,
        "structural_viability_passed": len(fail_reasons) == 0,
        "result": status,
        "fail_reasons": sorted(set(fail_reasons)),
    }
    validate_artifact(result, "repair_eval_result")
    return result


def build_repair_effectiveness_record(*, repair_candidate: Mapping[str, Any], repair_eval_result: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(repair_candidate), "repair_candidate")
    validate_artifact(dict(repair_eval_result), "repair_eval_result")

    record = {
        "artifact_type": "repair_effectiveness_record",
        "schema_version": "1.0.0",
        "record_id": f"fre-eff-{_canonical_digest([repair_candidate['candidate_id'], repair_eval_result['eval_id']])[:16]}",
        "trace_id": repair_candidate["trace_id"],
        "repair_candidate_ref": f"repair_candidate:{repair_candidate['candidate_id']}",
        "repair_eval_result_ref": f"repair_eval_result:{repair_eval_result['eval_id']}",
        "effectiveness_state": "candidate_effective" if repair_eval_result["result"] == "pass" else "candidate_not_effective",
        "non_authority_assertions": ["effectiveness_record_is_observational_only"],
    }
    validate_artifact(record, "repair_effectiveness_record")
    return record


def build_repair_recurrence_record(*, repair_candidate: Mapping[str, Any], recurrence_count: int) -> dict[str, Any]:
    validate_artifact(dict(repair_candidate), "repair_candidate")
    if recurrence_count < 0:
        raise FRERepairFlowError("recurrence_count must be >= 0")
    record = {
        "artifact_type": "repair_recurrence_record",
        "schema_version": "1.0.0",
        "record_id": f"fre-rec-{_canonical_digest([repair_candidate['candidate_id'], recurrence_count])[:16]}",
        "trace_id": repair_candidate["trace_id"],
        "repair_candidate_ref": f"repair_candidate:{repair_candidate['candidate_id']}",
        "recurrence_count": recurrence_count,
        "recurrence_state": "recurring" if recurrence_count > 0 else "not_recurring",
    }
    validate_artifact(record, "repair_recurrence_record")
    return record


def build_repair_readiness_candidate(*, repair_candidate: Mapping[str, Any], repair_eval_result: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(repair_candidate), "repair_candidate")
    validate_artifact(dict(repair_eval_result), "repair_eval_result")

    reasons: list[str] = []
    if repair_eval_result.get("result") != "pass":
        reasons.append("repair_eval_not_passed")
    if not repair_candidate.get("required_evidence_refs"):
        reasons.append("required_evidence_missing")

    readiness = {
        "artifact_type": "repair_readiness_candidate",
        "schema_version": "1.0.0",
        "readiness_id": f"fre-ready-{_canonical_digest([repair_candidate['candidate_id'], repair_eval_result['eval_id'], reasons])[:16]}",
        "trace_id": repair_candidate["trace_id"],
        "repair_candidate_ref": f"repair_candidate:{repair_candidate['candidate_id']}",
        "repair_eval_result_ref": f"repair_eval_result:{repair_eval_result['eval_id']}",
        "candidate_ready": len(reasons) == 0,
        "blocking_reasons": sorted(set(reasons)),
        "non_authority_assertions": [
            "candidate_only_non_authoritative",
            "cannot_authorize_execution",
            "cannot_authorize_progression",
        ],
    }
    validate_artifact(readiness, "repair_readiness_candidate")
    return readiness


def build_repair_bundle(
    *,
    repair_candidate: Mapping[str, Any],
    repair_eval_result: Mapping[str, Any],
    repair_effectiveness_record: Mapping[str, Any],
    repair_recurrence_record: Mapping[str, Any],
    repair_readiness_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    validate_artifact(dict(repair_candidate), "repair_candidate")
    validate_artifact(dict(repair_eval_result), "repair_eval_result")
    validate_artifact(dict(repair_effectiveness_record), "repair_effectiveness_record")
    validate_artifact(dict(repair_recurrence_record), "repair_recurrence_record")
    validate_artifact(dict(repair_readiness_candidate), "repair_readiness_candidate")

    bundle = {
        "artifact_type": "repair_bundle",
        "schema_version": "1.0.0",
        "bundle_id": f"fre-bundle-{_canonical_digest([repair_candidate['candidate_id'], repair_eval_result['eval_id']])[:16]}",
        "trace_id": repair_candidate["trace_id"],
        "repair_candidate_ref": f"repair_candidate:{repair_candidate['candidate_id']}",
        "repair_eval_result_ref": f"repair_eval_result:{repair_eval_result['eval_id']}",
        "repair_effectiveness_record_ref": f"repair_effectiveness_record:{repair_effectiveness_record['record_id']}",
        "repair_recurrence_record_ref": f"repair_recurrence_record:{repair_recurrence_record['record_id']}",
        "repair_readiness_candidate_ref": f"repair_readiness_candidate:{repair_readiness_candidate['readiness_id']}",
        "non_authority_assertions": ["bundle_is_candidate_only_non_authoritative"],
    }
    validate_artifact(bundle, "repair_bundle")
    return bundle
