"""Deterministic bounded RIL interpretation foundation (RIL-01..RIL-08E)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from spectrum_systems.contracts import validate_artifact


class RILInterpretationError(ValueError):
    """Raised when RIL boundary rules fail closed."""


_ALLOWED_INPUT_TYPES = {
    "execution_failure_packet",
    "review_findings_artifact",
    "eval_failure_artifact",
    "runtime_anomaly_artifact",
}

_FORBIDDEN_CONTROL_LEAK_FIELDS = {
    "allow",
    "block",
    "freeze",
    "warn",
    "authorize_continuation",
    "execute_repair",
    "repair_candidate",
}

_REASON_BY_CLASS = {
    "missing_artifact": "reason_missing_required_artifact",
    "invalid_artifact_shape": "reason_schema_validation_failure",
    "cross_artifact_mismatch": "reason_cross_artifact_mismatch",
    "authenticity_lineage_mismatch": "reason_provenance_mismatch",
    "slice_contract_mismatch": "reason_slice_contract_violation",
    "runtime_logic_defect": "reason_runtime_logic_defect",
    "policy_blocked": "reason_policy_blocked",
    "retry_budget_exhausted": "reason_retry_budget_exhausted",
}


def _digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _required_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RILInterpretationError(f"{field} must be a non-empty string")
    return value.strip()


def _clean_refs(values: Any, *, field: str, min_items: int = 1) -> list[str]:
    if not isinstance(values, list):
        raise RILInterpretationError(f"{field} must be a list")
    refs = sorted({str(v).strip() for v in values if isinstance(v, str) and v.strip()})
    if len(refs) < min_items:
        raise RILInterpretationError(f"{field} must include at least {min_items} refs")
    return refs


def verify_fre_closeout(
    *,
    repair_bundle: Mapping[str, Any],
    readiness_candidate: Mapping[str, Any],
    effectiveness_record: Mapping[str, Any],
    recurrence_record: Mapping[str, Any],
    promotion_gate_record: Mapping[str, Any],
) -> dict[str, Any]:
    """FRE-16 closeout verification proving FRE seams are operational for RIL downstream use."""

    validate_artifact(dict(repair_bundle), "repair_bundle")
    validate_artifact(dict(readiness_candidate), "repair_readiness_candidate")
    validate_artifact(dict(effectiveness_record), "repair_effectiveness_record")
    validate_artifact(dict(recurrence_record), "repair_recurrence_record")
    validate_artifact(dict(promotion_gate_record), "fre_promotion_gate_record")

    missing: list[str] = []
    if readiness_candidate.get("candidate_ready") is not True:
        missing.append("readiness_not_candidate_ready")
    if effectiveness_record.get("effectiveness_state") != "candidate_effective":
        missing.append("effectiveness_not_candidate_effective")
    if recurrence_record.get("recurrence_state") not in {"not_recurring", "recurring"}:
        missing.append("recurrence_state_invalid")

    status = "closed" if not missing else "blocked"
    artifact = {
        "artifact_type": "fre_closeout_gate_record",
        "schema_version": "1.0.0",
        "gate_id": f"fre-close-{_digest([repair_bundle['bundle_id'], promotion_gate_record['gate_record_id'], missing])[:16]}",
        "repair_bundle_ref": f"repair_bundle:{repair_bundle['bundle_id']}",
        "repair_readiness_candidate_ref": f"repair_readiness_candidate:{readiness_candidate['readiness_id']}",
        "repair_effectiveness_record_ref": f"repair_effectiveness_record:{effectiveness_record['record_id']}",
        "repair_recurrence_record_ref": f"repair_recurrence_record:{recurrence_record['record_id']}",
        "fre_promotion_gate_record_ref": f"fre_promotion_gate_record:{promotion_gate_record['gate_record_id']}",
        "fre_operational": len(missing) == 0,
        "closeout_status": status,
        "blocking_reasons": missing,
        "non_authority_assertions": [
            "fre_non_authoritative",
            "fre_must_not_execute_repairs",
            "fre_must_not_authorize_continuation",
        ],
    }
    validate_artifact(artifact, "fre_closeout_gate_record")
    return artifact


def normalize_failure_packet(*, evidence: Mapping[str, Any], trace_id: str) -> dict[str, Any]:
    """RIL-03 deterministic normalization to bounded failure_packet contract."""

    artifact_type = _required_str(evidence.get("artifact_type"), field="artifact_type")
    if artifact_type not in _ALLOWED_INPUT_TYPES:
        raise RILInterpretationError("RIL upstream boundary rejects non-governed artifact_type")

    failure_class = _required_str(evidence.get("failure_class"), field="failure_class")
    if failure_class not in _REASON_BY_CLASS:
        raise RILInterpretationError("unknown failure_class; fail-closed taxonomy enforcement")

    contradiction_refs = _clean_refs(evidence.get("contradiction_refs", []), field="contradiction_refs", min_items=0)
    ambiguity_refs = _clean_refs(evidence.get("ambiguity_refs", []), field="ambiguity_refs", min_items=0)
    source_evidence_refs = _clean_refs(evidence.get("source_evidence_refs", []), field="source_evidence_refs")

    packet = {
        "artifact_type": "failure_packet",
        "schema_version": "1.0.0",
        "failure_packet_id": f"ril-fp-{_digest([trace_id, artifact_type, failure_class, source_evidence_refs])[:16]}",
        "trace_id": _required_str(trace_id, field="trace_id"),
        "source_artifact_type": artifact_type,
        "source_artifact_ref": _required_str(evidence.get("source_artifact_ref"), field="source_artifact_ref"),
        "failure_class": failure_class,
        "reason_code": _REASON_BY_CLASS[failure_class],
        "owner_surface": _required_str(evidence.get("owner_surface"), field="owner_surface"),
        "source_evidence_refs": source_evidence_refs,
        "ambiguity_markers": ambiguity_refs,
        "contradiction_markers": contradiction_refs,
        "lineage_refs": _clean_refs(evidence.get("lineage_refs", []), field="lineage_refs"),
        "non_authority_assertions": [
            "interpretation_only_not_repair_generation",
            "ril_not_control_authority",
            "ril_not_execution_authority",
        ],
    }
    validate_artifact(packet, "failure_packet")
    return packet


def detect_contradictions(*, failure_packet: Mapping[str, Any], evidence_refs: Sequence[str], material_threshold: int = 1) -> dict[str, Any]:
    validate_artifact(dict(failure_packet), "failure_packet")
    refs = sorted({str(ref).strip() for ref in evidence_refs if str(ref).strip()})
    if not refs:
        raise RILInterpretationError("evidence_refs must not be empty")

    material = len(refs) >= material_threshold
    unresolved = material
    record = {
        "artifact_type": "interpretation_conflict_record",
        "schema_version": "1.0.0",
        "conflict_id": f"ril-conf-{_digest([failure_packet['failure_packet_id'], refs, material])[:16]}",
        "trace_id": failure_packet["trace_id"],
        "failure_packet_ref": f"failure_packet:{failure_packet['failure_packet_id']}",
        "conflict_refs": refs,
        "material_conflict": material,
        "resolved": not unresolved,
        "resolution_state": "resolved" if not unresolved else "unresolved",
        "resolution_notes": "material conflict unresolved" if unresolved else "non-material differences only",
    }
    validate_artifact(record, "interpretation_conflict_record")
    return record


def build_interpretation_record(*, failure_packet: Mapping[str, Any], conflict_record: Mapping[str, Any], interpretation_notes: Sequence[str]) -> dict[str, Any]:
    validate_artifact(dict(failure_packet), "failure_packet")
    validate_artifact(dict(conflict_record), "interpretation_conflict_record")
    notes = sorted({str(n).strip() for n in interpretation_notes if str(n).strip()})
    if not notes:
        raise RILInterpretationError("interpretation_notes must include at least one note")

    artifact = {
        "artifact_type": "interpretation_record",
        "schema_version": "1.0.0",
        "interpretation_id": f"ril-int-{_digest([failure_packet['failure_packet_id'], conflict_record['conflict_id'], notes])[:16]}",
        "trace_id": failure_packet["trace_id"],
        "failure_packet_ref": f"failure_packet:{failure_packet['failure_packet_id']}",
        "conflict_record_ref": f"interpretation_conflict_record:{conflict_record['conflict_id']}",
        "normalized_failure_class": failure_packet["failure_class"],
        "reason_code": failure_packet["reason_code"],
        "interpretation_notes": notes,
        "ambiguity_score": round(min(1.0, len(failure_packet.get("ambiguity_markers", [])) / 3.0), 4),
        "contains_material_conflict": bool(conflict_record.get("material_conflict")),
        "non_authority_assertions": [
            "candidate_only_interpretation",
            "must_not_generate_repair_candidates",
            "must_not_authorize_control_outcomes",
        ],
    }
    validate_artifact(artifact, "interpretation_record")
    return artifact


def evaluate_interpretation(*, interpretation_record: Mapping[str, Any], conflict_record: Mapping[str, Any], evidence_minimum: int = 1) -> dict[str, Any]:
    validate_artifact(dict(interpretation_record), "interpretation_record")
    validate_artifact(dict(conflict_record), "interpretation_conflict_record")

    fail_reasons: list[str] = []
    if len(interpretation_record.get("interpretation_notes", [])) < 1:
        fail_reasons.append("completeness_missing_interpretation_notes")
    if evidence_minimum < 1:
        fail_reasons.append("invalid_evidence_minimum")
    if interpretation_record.get("contains_material_conflict") and conflict_record.get("resolved") is not True:
        fail_reasons.append("material_conflict_unresolved")
    if not interpretation_record.get("reason_code"):
        fail_reasons.append("normalization_reason_missing")

    result = {
        "artifact_type": "interpretation_eval_result",
        "schema_version": "1.0.0",
        "eval_id": f"ril-eval-{_digest([interpretation_record['interpretation_id'], fail_reasons])[:16]}",
        "trace_id": interpretation_record["trace_id"],
        "interpretation_record_ref": f"interpretation_record:{interpretation_record['interpretation_id']}",
        "completeness_passed": "completeness_missing_interpretation_notes" not in fail_reasons,
        "evidence_sufficiency_passed": evidence_minimum >= 1,
        "contradiction_handling_passed": "material_conflict_unresolved" not in fail_reasons,
        "normalization_passed": "normalization_reason_missing" not in fail_reasons,
        "required_field_coverage_passed": len(fail_reasons) == 0,
        "result": "pass" if not fail_reasons else "fail",
        "fail_reasons": sorted(set(fail_reasons)),
    }
    validate_artifact(result, "interpretation_eval_result")
    return result


def build_readiness_record(*, interpretation_record: Mapping[str, Any], eval_result: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(interpretation_record), "interpretation_record")
    validate_artifact(dict(eval_result), "interpretation_eval_result")

    reasons: list[str] = []
    if eval_result.get("result") != "pass":
        reasons.append("eval_not_pass")
    if interpretation_record.get("contains_material_conflict"):
        reasons.append("material_conflict_present")

    artifact = {
        "artifact_type": "interpretation_readiness_record",
        "schema_version": "1.0.0",
        "readiness_id": f"ril-ready-{_digest([interpretation_record['interpretation_id'], eval_result['eval_id'], reasons])[:16]}",
        "trace_id": interpretation_record["trace_id"],
        "interpretation_record_ref": f"interpretation_record:{interpretation_record['interpretation_id']}",
        "interpretation_eval_result_ref": f"interpretation_eval_result:{eval_result['eval_id']}",
        "candidate_ready": len(reasons) == 0,
        "blocking_reasons": sorted(set(reasons)),
        "non_authority_assertions": [
            "candidate_only",
            "cannot_authorize_progression",
            "cannot_issue_control_decisions",
        ],
    }
    validate_artifact(artifact, "interpretation_readiness_record")
    return artifact


def validate_replay(*, source_inputs: Sequence[Mapping[str, Any]], first_outputs: Sequence[Mapping[str, Any]], replay_outputs: Sequence[Mapping[str, Any]], schema_version: str) -> dict[str, Any]:
    if not source_inputs:
        raise RILInterpretationError("replay validation requires source_inputs")
    if not first_outputs or not replay_outputs:
        raise RILInterpretationError("replay validation requires output sets")

    input_fingerprint = _digest(source_inputs)
    first_fingerprint = _digest(first_outputs)
    replay_fingerprint = _digest(replay_outputs)
    deterministic_match = first_fingerprint == replay_fingerprint

    artifact = {
        "artifact_type": "interpretation_replay_validation_record",
        "schema_version": "1.0.0",
        "validation_id": f"ril-replay-{_digest([input_fingerprint, first_fingerprint, replay_fingerprint, schema_version])[:16]}",
        "input_fingerprint": input_fingerprint,
        "first_output_fingerprint": first_fingerprint,
        "replay_output_fingerprint": replay_fingerprint,
        "schema_version_checked": _required_str(schema_version, field="schema_version"),
        "deterministic_match": deterministic_match,
        "result": "pass" if deterministic_match else "fail",
        "fail_reasons": [] if deterministic_match else ["replay_output_mismatch"],
    }
    validate_artifact(artifact, "interpretation_replay_validation_record")
    return artifact


def build_ambiguity_signal(*, interpretation_records: Sequence[Mapping[str, Any]], ambiguity_budget: float) -> dict[str, Any]:
    if ambiguity_budget <= 0 or ambiguity_budget > 1:
        raise RILInterpretationError("ambiguity_budget must be in (0, 1]")
    total = len(interpretation_records)
    if total == 0:
        raise RILInterpretationError("interpretation_records must not be empty")

    ambiguous = sum(1 for record in interpretation_records if float(record.get("ambiguity_score", 0.0)) > 0.0)
    rate = round(ambiguous / total, 4)
    threshold_exceeded = rate > ambiguity_budget

    artifact = {
        "artifact_type": "interpretation_ambiguity_signal",
        "schema_version": "1.0.0",
        "signal_id": f"ril-amb-{_digest([total, ambiguous, ambiguity_budget])[:16]}",
        "sample_size": total,
        "ambiguity_count": ambiguous,
        "ambiguity_rate": rate,
        "ambiguity_budget": round(ambiguity_budget, 4),
        "threshold_exceeded": threshold_exceeded,
        "freeze_ready": threshold_exceeded,
        "policy_signal": "freeze_candidate" if threshold_exceeded else "within_budget",
    }
    validate_artifact(artifact, "interpretation_ambiguity_signal")
    return artifact


def validate_control_signal_integrity(*, interpretation_record: Mapping[str, Any], allowed_fields: Sequence[str]) -> dict[str, Any]:
    validate_artifact(dict(interpretation_record), "interpretation_record")
    allowed = {str(field).strip() for field in allowed_fields if str(field).strip()}
    if not allowed:
        raise RILInterpretationError("allowed_fields must not be empty")

    leaked = sorted(
        field
        for field in interpretation_record.keys()
        if field in _FORBIDDEN_CONTROL_LEAK_FIELDS or (field.startswith("control_") and field not in allowed)
    )

    artifact = {
        "artifact_type": "interpretation_control_signal_validation",
        "schema_version": "1.0.0",
        "validation_id": f"ril-ctrl-{_digest([interpretation_record['interpretation_id'], sorted(allowed), leaked])[:16]}",
        "interpretation_record_ref": f"interpretation_record:{interpretation_record['interpretation_id']}",
        "allowed_influence_fields": sorted(allowed),
        "forbidden_fields_detected": leaked,
        "hidden_authority_detected": bool(leaked),
        "result": "pass" if not leaked else "fail",
    }
    validate_artifact(artifact, "interpretation_control_signal_validation")
    return artifact


def validate_interpretation_repair_alignment(*, interpretation_record: Mapping[str, Any], repair_candidate: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(interpretation_record), "interpretation_record")
    validate_artifact(dict(repair_candidate), "repair_candidate")

    class_to_action = {
        "missing_artifact": "update_artifact:",
        "invalid_artifact_shape": "update_artifact:",
        "cross_artifact_mismatch": "update_artifact:",
        "authenticity_lineage_mismatch": "update_artifact:",
        "slice_contract_mismatch": "update_artifact:",
        "runtime_logic_defect": "update_artifact:",
        "policy_blocked": "update_artifact:",
        "retry_budget_exhausted": "update_artifact:",
    }
    expected_prefix = class_to_action[interpretation_record["normalized_failure_class"]]
    aligned = all(str(action).startswith(expected_prefix) for action in repair_candidate.get("bounded_actions", []))

    artifact = {
        "artifact_type": "interpretation_repair_alignment_record",
        "schema_version": "1.0.0",
        "alignment_id": f"ril-align-{_digest([interpretation_record['interpretation_id'], repair_candidate['candidate_id'], aligned])[:16]}",
        "interpretation_record_ref": f"interpretation_record:{interpretation_record['interpretation_id']}",
        "repair_candidate_ref": f"repair_candidate:{repair_candidate['candidate_id']}",
        "alignment_passed": aligned,
        "expected_action_prefix": expected_prefix,
        "observed_actions": sorted(str(action) for action in repair_candidate.get("bounded_actions", [])),
        "result": "pass" if aligned else "fail",
        "fail_reasons": [] if aligned else ["repair_action_mismatch"],
    }
    validate_artifact(artifact, "interpretation_repair_alignment_record")
    return artifact


def build_effectiveness_record(*, interpretation_record: Mapping[str, Any], alignment_record: Mapping[str, Any], downstream_outcome: str) -> dict[str, Any]:
    validate_artifact(dict(interpretation_record), "interpretation_record")
    validate_artifact(dict(alignment_record), "interpretation_repair_alignment_record")
    if downstream_outcome not in {"improved", "unchanged", "regressed"}:
        raise RILInterpretationError("downstream_outcome must be improved|unchanged|regressed")

    effective = downstream_outcome == "improved" and alignment_record.get("alignment_passed") is True
    artifact = {
        "artifact_type": "interpretation_effectiveness_record",
        "schema_version": "1.0.0",
        "record_id": f"ril-eff-{_digest([interpretation_record['interpretation_id'], alignment_record['alignment_id'], downstream_outcome])[:16]}",
        "interpretation_record_ref": f"interpretation_record:{interpretation_record['interpretation_id']}",
        "alignment_record_ref": f"interpretation_repair_alignment_record:{alignment_record['alignment_id']}",
        "downstream_outcome": downstream_outcome,
        "effective": effective,
        "effectiveness_state": "effective" if effective else "not_effective",
    }
    validate_artifact(artifact, "interpretation_effectiveness_record")
    return artifact


def validate_required_coverage(*, required_failure_classes: Sequence[str], covered_failure_classes: Sequence[str], fail_closed: bool = True) -> dict[str, Any]:
    required = sorted({str(x).strip() for x in required_failure_classes if str(x).strip()})
    covered = sorted({str(x).strip() for x in covered_failure_classes if str(x).strip()})
    if not required:
        raise RILInterpretationError("required_failure_classes must not be empty")

    missing = sorted(set(required) - set(covered))
    artifact = {
        "artifact_type": "interpretation_coverage_report",
        "schema_version": "1.0.0",
        "report_id": f"ril-cov-{_digest([required, covered, fail_closed])[:16]}",
        "required_failure_classes": required,
        "covered_failure_classes": covered,
        "missing_failure_classes": missing,
        "coverage_complete": len(missing) == 0,
        "fail_closed_triggered": bool(missing) and bool(fail_closed),
        "result": "pass" if not missing else "fail",
    }
    validate_artifact(artifact, "interpretation_coverage_report")
    return artifact


def monitor_failure_class_drift(*, baseline_distribution: Mapping[str, int], observed_distribution: Mapping[str, int], novelty_threshold: float = 0.2) -> dict[str, Any]:
    if novelty_threshold <= 0 or novelty_threshold > 1:
        raise RILInterpretationError("novelty_threshold must be in (0,1]")

    baseline_keys = set(baseline_distribution.keys())
    observed_keys = set(observed_distribution.keys())
    novel = sorted(observed_keys - baseline_keys)
    total_observed = sum(max(0, int(v)) for v in observed_distribution.values())
    novel_count = sum(max(0, int(observed_distribution.get(k, 0))) for k in novel)
    novel_rate = 0.0 if total_observed == 0 else round(novel_count / total_observed, 4)

    artifact = {
        "artifact_type": "failure_class_drift_record",
        "schema_version": "1.0.0",
        "record_id": f"ril-drift-{_digest([sorted(baseline_distribution.items()), sorted(observed_distribution.items()), novelty_threshold])[:16]}",
        "baseline_classes": sorted(baseline_keys),
        "observed_classes": sorted(observed_keys),
        "novel_classes": novel,
        "novel_rate": novel_rate,
        "novelty_threshold": round(novelty_threshold, 4),
        "drift_detected": novel_rate >= novelty_threshold,
        "result": "pass" if novel_rate < novelty_threshold else "fail",
    }
    validate_artifact(artifact, "failure_class_drift_record")
    return artifact


def build_interpretation_bundle(
    *,
    failure_packet: Mapping[str, Any],
    interpretation_record: Mapping[str, Any],
    eval_result: Mapping[str, Any],
    readiness_record: Mapping[str, Any],
    conflict_record: Mapping[str, Any],
) -> dict[str, Any]:
    validate_artifact(dict(failure_packet), "failure_packet")
    validate_artifact(dict(interpretation_record), "interpretation_record")
    validate_artifact(dict(eval_result), "interpretation_eval_result")
    validate_artifact(dict(readiness_record), "interpretation_readiness_record")
    validate_artifact(dict(conflict_record), "interpretation_conflict_record")

    artifact = {
        "artifact_type": "interpretation_bundle",
        "schema_version": "1.0.0",
        "bundle_id": f"ril-bundle-{_digest([failure_packet['failure_packet_id'], interpretation_record['interpretation_id'], eval_result['eval_id']])[:16]}",
        "trace_id": failure_packet["trace_id"],
        "failure_packet_ref": f"failure_packet:{failure_packet['failure_packet_id']}",
        "interpretation_record_ref": f"interpretation_record:{interpretation_record['interpretation_id']}",
        "interpretation_eval_result_ref": f"interpretation_eval_result:{eval_result['eval_id']}",
        "interpretation_readiness_record_ref": f"interpretation_readiness_record:{readiness_record['readiness_id']}",
        "interpretation_conflict_record_ref": f"interpretation_conflict_record:{conflict_record['conflict_id']}",
        "lineage_complete": True,
        "non_authority_assertions": [
            "bundle_not_repair_authority",
            "bundle_not_control_authority",
        ],
    }
    validate_artifact(artifact, "interpretation_bundle")
    return artifact
