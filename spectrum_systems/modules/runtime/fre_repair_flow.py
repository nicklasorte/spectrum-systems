"""FRE bounded repair generation/evaluation/readiness foundation.

FRE is non-authoritative and never executes repair actions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

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

_ALLOWED_REPAIR_CLASSES = {"artifact_only", "schema_adjustment", "test_only", "runtime_code"}


def _canonical_digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


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
    replay_id = f"replay-{_required_str(failure_packet.get('failure_packet_id'), 'failure_packet_id')}"
    input_digest = _canonical_digest(failure_packet)
    candidate_payload = {
        "failure_packet_id": _required_str(failure_packet.get("failure_packet_id"), "failure_packet_id"),
        "scope_refs": scope_refs,
        "failure_type": failure_type,
        "trace_id": _required_str(trace_id, "trace_id"),
        "input_digest": input_digest,
    }
    candidate_id = f"fre-rc-{_canonical_digest(candidate_payload)[:16]}"

    candidate = {
        "artifact_type": "repair_candidate",
        "schema_version": "1.1.0",
        "candidate_id": candidate_id,
        "trace_id": trace_id,
        "replay_id": replay_id,
        "input_digest": input_digest,
        "failure_packet_ref": f"execution_failure_packet:{failure_packet['failure_packet_id']}",
        "lineage_refs": [
            f"execution_failure_packet:{failure_packet['failure_packet_id']}",
            f"trace:{trace_id}",
        ],
        "scope_refs": scope_refs,
        "repair_class": "artifact_only",
        "bounded_actions": bounded_actions,
        "expected_post_condition": f"failure_type:{failure_type}:resolved_without_execution",
        "required_evidence_refs": _normalize_refs(
            list(failure_packet.get("trace_refs", [])) + list(failure_packet.get("validation_refs", [])),
            field="required_evidence_refs",
        ),
        "non_authority_assertions": [
            "candidate_only_non_authoritative",
            "fre_must_not_execute_repairs",
            "fre_must_not_authorize_continuation",
            "fre_must_not_decide_control_outcome",
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
    if repair_candidate.get("repair_class") not in _ALLOWED_REPAIR_CLASSES:
        fail_reasons.append("repair_class_not_allowed")

    status = "pass" if not fail_reasons else "fail"
    eval_id = f"fre-reval-{_canonical_digest([repair_candidate['candidate_id'], fail_reasons])[:16]}"
    result = {
        "artifact_type": "repair_eval_result",
        "schema_version": "1.1.0",
        "eval_id": eval_id,
        "trace_id": repair_candidate["trace_id"],
        "replay_id": repair_candidate["replay_id"],
        "input_digest": repair_candidate["input_digest"],
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


def build_repair_effectiveness_record(
    *,
    repair_candidate: Mapping[str, Any],
    repair_eval_result: Mapping[str, Any],
    observed_outcome: str = "resolved",
) -> dict[str, Any]:
    validate_artifact(dict(repair_candidate), "repair_candidate")
    validate_artifact(dict(repair_eval_result), "repair_eval_result")
    if observed_outcome not in {"resolved", "unresolved", "regressed"}:
        raise FRERepairFlowError("observed_outcome must be resolved|unresolved|regressed")

    state = "candidate_effective" if repair_eval_result["result"] == "pass" and observed_outcome == "resolved" else "candidate_not_effective"
    record = {
        "artifact_type": "repair_effectiveness_record",
        "schema_version": "1.1.0",
        "record_id": f"fre-eff-{_canonical_digest([repair_candidate['candidate_id'], repair_eval_result['eval_id'], observed_outcome])[:16]}",
        "trace_id": repair_candidate["trace_id"],
        "replay_id": repair_candidate["replay_id"],
        "failure_packet_ref": repair_candidate["failure_packet_ref"],
        "repair_candidate_ref": f"repair_candidate:{repair_candidate['candidate_id']}",
        "repair_eval_result_ref": f"repair_eval_result:{repair_eval_result['eval_id']}",
        "observed_outcome": observed_outcome,
        "effectiveness_state": state,
        "non_authority_assertions": ["effectiveness_record_is_observational_only"],
    }
    validate_artifact(record, "repair_effectiveness_record")
    return record


def build_repair_recurrence_record(*, repair_candidate: Mapping[str, Any], recurrence_count: int, cluster_key: str) -> dict[str, Any]:
    validate_artifact(dict(repair_candidate), "repair_candidate")
    if recurrence_count < 0:
        raise FRERepairFlowError("recurrence_count must be >= 0")
    cluster = _required_str(cluster_key, "cluster_key")
    record = {
        "artifact_type": "repair_recurrence_record",
        "schema_version": "1.1.0",
        "record_id": f"fre-rec-{_canonical_digest([repair_candidate['candidate_id'], recurrence_count, cluster])[:16]}",
        "trace_id": repair_candidate["trace_id"],
        "replay_id": repair_candidate["replay_id"],
        "repair_candidate_ref": f"repair_candidate:{repair_candidate['candidate_id']}",
        "cluster_key": cluster,
        "recurrence_count": recurrence_count,
        "hotspot": recurrence_count >= 3,
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
        "schema_version": "1.1.0",
        "readiness_id": f"fre-ready-{_canonical_digest([repair_candidate['candidate_id'], repair_eval_result['eval_id'], reasons])[:16]}",
        "trace_id": repair_candidate["trace_id"],
        "replay_id": repair_candidate["replay_id"],
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

    if repair_candidate["replay_id"] != repair_eval_result["replay_id"]:
        raise FRERepairFlowError("replay drift detected between candidate and eval")

    bundle = {
        "artifact_type": "repair_bundle",
        "schema_version": "1.1.0",
        "bundle_id": f"fre-bundle-{_canonical_digest([repair_candidate['candidate_id'], repair_eval_result['eval_id']])[:16]}",
        "trace_id": repair_candidate["trace_id"],
        "replay_id": repair_candidate["replay_id"],
        "input_digest": repair_candidate["input_digest"],
        "repair_candidate_ref": f"repair_candidate:{repair_candidate['candidate_id']}",
        "repair_eval_result_ref": f"repair_eval_result:{repair_eval_result['eval_id']}",
        "repair_effectiveness_record_ref": f"repair_effectiveness_record:{repair_effectiveness_record['record_id']}",
        "repair_recurrence_record_ref": f"repair_recurrence_record:{repair_recurrence_record['record_id']}",
        "repair_readiness_candidate_ref": f"repair_readiness_candidate:{repair_readiness_candidate['readiness_id']}",
        "lineage_complete": True,
        "non_authority_assertions": ["bundle_is_candidate_only_non_authoritative"],
    }
    validate_artifact(bundle, "repair_bundle")
    return bundle


def build_repair_template_candidate(*, cluster_key: str, successful_records: Sequence[Mapping[str, Any]], min_successes: int = 2) -> dict[str, Any]:
    refs = sorted({str(r.get("repair_candidate_ref", "")).strip() for r in successful_records if r.get("effectiveness_state") == "candidate_effective"})
    if len(refs) < min_successes:
        raise FRERepairFlowError("template admission blocked: insufficient successful recurrence evidence")
    template = {
        "artifact_type": "repair_template_candidate",
        "schema_version": "1.0.0",
        "template_id": f"fre-tmpl-{_canonical_digest([cluster_key, refs])[:16]}",
        "cluster_key": _required_str(cluster_key, "cluster_key"),
        "version": 1,
        "dedupe_key": _canonical_digest([cluster_key, refs]),
        "successful_repair_refs": refs,
        "admission_state": "candidate_admitted",
        "non_authority_assertions": ["template_is_candidate_only"],
    }
    validate_artifact(template, "repair_template_candidate")
    return template


def apply_repair_scope_policy_gate(*, repair_candidate: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(repair_candidate), "repair_candidate")
    repair_class = _required_str(repair_candidate.get("repair_class"), "repair_class")
    allowed = set(policy.get("allowed_classes", []))
    blocked = set(policy.get("blocked_classes", []))
    review_required = set(policy.get("review_required_classes", []))
    if repair_class in blocked:
        decision, reason = "blocked", "repair_class_blocked"
    elif repair_class in review_required:
        decision, reason = "review_required", "repair_class_requires_review"
    elif repair_class in allowed:
        decision, reason = "allowed", "repair_class_allowed"
    else:
        raise FRERepairFlowError("policy gate fail-closed: unclassified repair class")
    record = {
        "artifact_type": "repair_scope_policy_gate",
        "schema_version": "1.0.0",
        "gate_id": f"fre-gate-{_canonical_digest([repair_candidate['candidate_id'], decision])[:16]}",
        "repair_candidate_ref": f"repair_candidate:{repair_candidate['candidate_id']}",
        "repair_class": repair_class,
        "decision": decision,
        "reason_code": reason,
        "non_authority_assertions": ["gate_result_is_non_executing"],
    }
    validate_artifact(record, "repair_scope_policy_gate")
    return record


def build_review_record(*, repair_candidate: Mapping[str, Any], reviewer_id: str, disposition: str, notes: str) -> dict[str, Any]:
    validate_artifact(dict(repair_candidate), "repair_candidate")
    if disposition not in {"approved", "rejected", "needs_more_evidence"}:
        raise FRERepairFlowError("invalid review disposition")
    record = {
        "artifact_type": "repair_review_record",
        "schema_version": "1.0.0",
        "review_id": f"fre-rvw-{_canonical_digest([repair_candidate['candidate_id'], reviewer_id, disposition])[:16]}",
        "repair_candidate_ref": f"repair_candidate:{repair_candidate['candidate_id']}",
        "reviewer_id": _required_str(reviewer_id, "reviewer_id"),
        "disposition": disposition,
        "review_notes": _required_str(notes, "notes"),
        "reviewed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "non_authority_assertions": ["review_record_is_replayable", "review_not_control_decision"],
    }
    validate_artifact(record, "repair_review_record")
    return record


def build_override_record(*, review_record: Mapping[str, Any], override_by: str, expires_at: str, justification: str) -> dict[str, Any]:
    validate_artifact(dict(review_record), "repair_review_record")
    record = {
        "artifact_type": "repair_override_record",
        "schema_version": "1.0.0",
        "override_id": f"fre-ovr-{_canonical_digest([review_record['review_id'], override_by, expires_at])[:16]}",
        "review_ref": f"repair_review_record:{review_record['review_id']}",
        "override_by": _required_str(override_by, "override_by"),
        "expires_at": _required_str(expires_at, "expires_at"),
        "justification": _required_str(justification, "justification"),
        "non_authority_assertions": ["override_record_is_replayable", "override_not_execution_authority"],
    }
    validate_artifact(record, "repair_override_record")
    return record


def build_repair_budget_signal(
    *,
    effectiveness_records: Sequence[Mapping[str, Any]],
    recurrence_records: Sequence[Mapping[str, Any]],
    override_records: Sequence[Mapping[str, Any]],
    total_latency_ms: int,
    total_cost_units: int,
) -> dict[str, Any]:
    total = len(effectiveness_records)
    success_count = sum(1 for r in effectiveness_records if r.get("effectiveness_state") == "candidate_effective")
    recurrence_hotspots = sum(1 for r in recurrence_records if r.get("hotspot") is True)
    override_count = len(override_records)
    signal = {
        "artifact_type": "repair_budget_signal",
        "schema_version": "1.0.0",
        "signal_id": f"fre-signal-{_canonical_digest([total, success_count, recurrence_hotspots, override_count, total_latency_ms, total_cost_units])[:16]}",
        "sample_size": total,
        "success_rate": 0.0 if total == 0 else round(success_count / total, 4),
        "recurrence_rate": 0.0 if total == 0 else round(recurrence_hotspots / total, 4),
        "override_rate": 0.0 if total == 0 else round(override_count / total, 4),
        "repair_latency_ms": int(total_latency_ms),
        "repair_cost_units": int(total_cost_units),
    }
    validate_artifact(signal, "repair_budget_signal")
    return signal


def build_repair_judgment_slice(
    *,
    candidate_scores: Mapping[str, float],
    eval_refs: Mapping[str, str],
    trace_id: str,
) -> dict[str, Any]:
    if not candidate_scores:
        raise FRERepairFlowError("candidate_scores must not be empty")
    ordered = sorted(candidate_scores.items(), key=lambda item: (-item[1], item[0]))
    selected_candidate_ref = ordered[0][0]
    if selected_candidate_ref not in eval_refs:
        raise FRERepairFlowError("selected candidate missing eval linkage")
    artifact = {
        "artifact_type": "repair_judgment_slice",
        "schema_version": "1.0.0",
        "judgment_id": f"fre-judge-{_canonical_digest([ordered, trace_id])[:16]}",
        "trace_id": _required_str(trace_id, "trace_id"),
        "selected_candidate_ref": selected_candidate_ref,
        "selected_eval_ref": eval_refs[selected_candidate_ref],
        "bounded_outcome": "candidate_selected",
        "rationale_codes": ["highest_score", "deterministic_tie_break"],
        "non_authority_assertions": ["judgment_is_advisory_only", "judgment_not_control_decision"],
    }
    validate_artifact(artifact, "repair_judgment_slice")
    return artifact


def compile_repair_policy_candidate(*, templates: Sequence[Mapping[str, Any]], min_templates: int = 1) -> dict[str, Any]:
    admitted = sorted(
        [str(t.get("template_id")) for t in templates if t.get("admission_state") == "candidate_admitted" and t.get("template_id")]
    )
    if len(admitted) < min_templates:
        raise FRERepairFlowError("policy candidate compilation blocked: insufficient admitted templates")
    artifact = {
        "artifact_type": "repair_policy_candidate",
        "schema_version": "1.0.0",
        "policy_candidate_id": f"fre-pol-{_canonical_digest(admitted)[:16]}",
        "template_refs": [f"repair_template_candidate:{t}" for t in admitted],
        "candidate_policy_primitives": [f"primitive:{i+1}" for i, _ in enumerate(admitted)],
        "compilation_state": "candidate_only",
        "non_authority_assertions": ["policy_candidate_non_authoritative"],
    }
    validate_artifact(artifact, "repair_policy_candidate")
    return artifact


def build_fre_promotion_gate_record(*, bundle: Mapping[str, Any], budget_signal: Mapping[str, Any], policy_gate: Mapping[str, Any], judgment_slice: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(bundle), "repair_bundle")
    validate_artifact(dict(budget_signal), "repair_budget_signal")
    validate_artifact(dict(policy_gate), "repair_scope_policy_gate")
    validate_artifact(dict(judgment_slice), "repair_judgment_slice")

    missing: list[str] = []
    if not bundle.get("lineage_complete"):
        missing.append("lineage_complete")
    if policy_gate.get("decision") == "blocked":
        missing.append("policy_gate_blocked")
    if budget_signal.get("sample_size", 0) <= 0:
        missing.append("observability_sample_missing")

    record = {
        "artifact_type": "fre_promotion_gate_record",
        "schema_version": "1.0.0",
        "gate_record_id": f"fre-prom-{_canonical_digest([bundle['bundle_id'], budget_signal['signal_id'], policy_gate['gate_id'], judgment_slice['judgment_id']])[:16]}",
        "repair_bundle_ref": f"repair_bundle:{bundle['bundle_id']}",
        "budget_signal_ref": f"repair_budget_signal:{budget_signal['signal_id']}",
        "policy_gate_ref": f"repair_scope_policy_gate:{policy_gate['gate_id']}",
        "judgment_slice_ref": f"repair_judgment_slice:{judgment_slice['judgment_id']}",
        "promotion_ready": len(missing) == 0,
        "blocking_reasons": missing,
    }
    validate_artifact(record, "fre_promotion_gate_record")
    return record
