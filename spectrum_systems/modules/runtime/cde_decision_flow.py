"""CDE bounded decision foundation (CDE-01..CDE-09).

CDE consumes governed evidence and emits decision artifacts only.
CDE never executes repairs, enforces decisions, or mutates downstream state.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from spectrum_systems.contracts import validate_artifact


class CDEDecisionFlowError(ValueError):
    """Raised when CDE boundary rules fail closed."""


_ALLOWED_UPSTREAM_TYPES = {
    "interpretation_bundle",
    "repair_bundle",
    "interpretation_conflict_record",
    "interpretation_replay_validation_record",
    "fre_promotion_gate_record",
}
_FORBIDDEN_EXECUTION_FIELDS = {"execute", "apply", "write_path", "shell_command", "enforcement_action"}


def _digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _required_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CDEDecisionFlowError(f"{field} must be a non-empty string")
    return value.strip()


def _clean_refs(values: Any, *, field: str, min_items: int = 1) -> list[str]:
    if not isinstance(values, list):
        raise CDEDecisionFlowError(f"{field} must be a list")
    refs = sorted({str(v).strip() for v in values if isinstance(v, str) and v.strip()})
    if len(refs) < min_items:
        raise CDEDecisionFlowError(f"{field} must include at least {min_items} refs")
    return refs


def build_decision_evidence_pack(
    *,
    trace_id: str,
    interpretation_bundle: Mapping[str, Any],
    repair_bundle: Mapping[str, Any],
    policy_constraints_ref: str,
    provenance_refs: Sequence[str],
    replay_refs: Sequence[str],
    evidence_refs: Sequence[str],
) -> dict[str, Any]:
    validate_artifact(dict(interpretation_bundle), "interpretation_bundle")
    validate_artifact(dict(repair_bundle), "repair_bundle")

    pack = {
        "artifact_type": "decision_evidence_pack",
        "schema_version": "1.0.0",
        "evidence_pack_id": f"cde-ep-{_digest([trace_id, interpretation_bundle['bundle_id'], repair_bundle['bundle_id']])[:16]}",
        "trace_id": _required_str(trace_id, field="trace_id"),
        "interpretation_bundle_ref": f"interpretation_bundle:{interpretation_bundle['bundle_id']}",
        "repair_bundle_ref": f"repair_bundle:{repair_bundle['bundle_id']}",
        "policy_constraints_ref": _required_str(policy_constraints_ref, field="policy_constraints_ref"),
        "provenance_refs": _clean_refs(list(provenance_refs), field="provenance_refs"),
        "replay_refs": _clean_refs(list(replay_refs), field="replay_refs"),
        "evidence_refs": _clean_refs(list(evidence_refs), field="evidence_refs"),
        "input_fingerprint": _digest(
            {
                "trace_id": trace_id,
                "interpretation_bundle_ref": interpretation_bundle["bundle_id"],
                "repair_bundle_ref": repair_bundle["bundle_id"],
                "policy_constraints_ref": policy_constraints_ref,
                "provenance_refs": sorted(provenance_refs),
                "replay_refs": sorted(replay_refs),
                "evidence_refs": sorted(evidence_refs),
            }
        ),
    }
    validate_artifact(pack, "decision_evidence_pack")
    return pack


def detect_decision_conflicts(*, evidence_pack: Mapping[str, Any], conflict_refs: Sequence[str], material_threshold: int = 1) -> dict[str, Any]:
    validate_artifact(dict(evidence_pack), "decision_evidence_pack")
    refs = _clean_refs(list(conflict_refs), field="conflict_refs")

    material = len(refs) >= material_threshold
    unresolved = material
    record = {
        "artifact_type": "decision_conflict_record",
        "schema_version": "1.0.0",
        "conflict_id": f"cde-conf-{_digest([evidence_pack['evidence_pack_id'], refs, material])[:16]}",
        "trace_id": evidence_pack["trace_id"],
        "decision_evidence_pack_ref": f"decision_evidence_pack:{evidence_pack['evidence_pack_id']}",
        "conflict_refs": refs,
        "material_conflict": material,
        "resolved": not unresolved,
        "resolution_state": "resolved" if not unresolved else "unresolved",
        "resolution_notes": "material conflict unresolved" if unresolved else "non-material differences only",
    }
    validate_artifact(record, "decision_conflict_record")
    return record


def make_continuation_decision(
    *,
    evidence_pack: Mapping[str, Any],
    conflict_record: Mapping[str, Any],
    evidence_budget_min: int = 3,
    ambiguity_rate: float = 0.0,
    ambiguity_budget: float = 0.3,
) -> dict[str, Any]:
    validate_artifact(dict(evidence_pack), "decision_evidence_pack")
    validate_artifact(dict(conflict_record), "decision_conflict_record")

    if ambiguity_budget <= 0 or ambiguity_budget > 1:
        raise CDEDecisionFlowError("ambiguity_budget must be in (0,1]")
    if evidence_budget_min < 1:
        raise CDEDecisionFlowError("evidence_budget_min must be >= 1")

    reason_codes: list[str] = []
    change_conditions: list[str] = []

    evidence_count = len(evidence_pack.get("evidence_refs", []))
    material_conflict = bool(conflict_record.get("material_conflict")) and conflict_record.get("resolved") is not True
    ambiguity_exceeded = ambiguity_rate > ambiguity_budget

    if material_conflict:
        outcome = "human_review_required"
        reason_codes.append("material_conflict_unresolved")
    elif evidence_count < evidence_budget_min:
        outcome = "block"
        reason_codes.append("evidence_budget_insufficient")
    elif ambiguity_exceeded:
        outcome = "human_review_required"
        reason_codes.append("ambiguity_budget_exceeded")
    else:
        outcome = "continue_repair_bounded"
        reason_codes.append("bounded_continue_permitted")

    change_conditions.extend(
        [
            "material_conflict_unresolved",
            "evidence_budget_insufficient",
            "ambiguity_budget_exceeded",
            "policy_constraints_changed",
        ]
    )

    decision = {
        "artifact_type": "continuation_decision_record",
        "schema_version": "1.0.0",
        "decision_id": f"cde-dec-{_digest([evidence_pack['evidence_pack_id'], outcome, reason_codes])[:16]}",
        "trace_id": evidence_pack["trace_id"],
        "evidence_pack_ref": f"decision_evidence_pack:{evidence_pack['evidence_pack_id']}",
        "decision_outcome": outcome,
        "reason_codes": sorted(set(reason_codes)),
        "evidence_refs": sorted(evidence_pack["evidence_refs"]),
        "change_conditions": sorted(set(change_conditions)),
        "non_authority_assertions": [
            "decision_artifact_only",
            "cde_must_not_execute",
            "cde_must_not_enforce",
            "cde_must_not_mutate_downstream_state",
        ],
    }
    validate_artifact(decision, "continuation_decision_record")
    return decision


def evaluate_decision(*, decision_record: Mapping[str, Any], conflict_record: Mapping[str, Any], evidence_pack: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(decision_record), "continuation_decision_record")
    validate_artifact(dict(conflict_record), "decision_conflict_record")
    validate_artifact(dict(evidence_pack), "decision_evidence_pack")

    fail_reasons: list[str] = []
    if len(decision_record.get("evidence_refs", [])) < 1:
        fail_reasons.append("evidence_missing")
    if len(decision_record.get("reason_codes", [])) < 1:
        fail_reasons.append("reason_codes_missing")
    if conflict_record.get("material_conflict") and conflict_record.get("resolved") is not True and decision_record.get("decision_outcome") == "continue_repair_bounded":
        fail_reasons.append("contradiction_handling_incorrect")
    if not str(evidence_pack.get("policy_constraints_ref", "")).startswith("policy:"):
        fail_reasons.append("policy_alignment_missing")

    result = {
        "artifact_type": "decision_eval_result",
        "schema_version": "1.0.0",
        "eval_id": f"cde-eval-{_digest([decision_record['decision_id'], fail_reasons])[:16]}",
        "trace_id": decision_record["trace_id"],
        "continuation_decision_record_ref": f"continuation_decision_record:{decision_record['decision_id']}",
        "evidence_sufficiency_passed": "evidence_missing" not in fail_reasons,
        "policy_alignment_passed": "policy_alignment_missing" not in fail_reasons,
        "contradiction_handling_passed": "contradiction_handling_incorrect" not in fail_reasons,
        "decision_completeness_passed": "reason_codes_missing" not in fail_reasons,
        "required_field_coverage_passed": len(fail_reasons) == 0,
        "result": "pass" if not fail_reasons else "fail",
        "fail_reasons": sorted(set(fail_reasons)),
    }
    validate_artifact(result, "decision_eval_result")
    return result


def build_decision_readiness(*, decision_record: Mapping[str, Any], eval_result: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(decision_record), "continuation_decision_record")
    validate_artifact(dict(eval_result), "decision_eval_result")

    reasons: list[str] = []
    if eval_result.get("result") != "pass":
        reasons.append("decision_eval_not_pass")
    if decision_record.get("decision_outcome") == "human_review_required":
        reasons.append("human_review_required")

    readiness = {
        "artifact_type": "decision_readiness_record",
        "schema_version": "1.0.0",
        "readiness_id": f"cde-ready-{_digest([decision_record['decision_id'], eval_result['eval_id'], reasons])[:16]}",
        "trace_id": decision_record["trace_id"],
        "continuation_decision_record_ref": f"continuation_decision_record:{decision_record['decision_id']}",
        "decision_eval_result_ref": f"decision_eval_result:{eval_result['eval_id']}",
        "candidate_ready": len(reasons) == 0,
        "blocking_reasons": sorted(set(reasons)),
        "non_authority_assertions": [
            "candidate_only",
            "cannot_trigger_execution",
            "cannot_trigger_enforcement",
        ],
    }
    validate_artifact(readiness, "decision_readiness_record")
    return readiness


def build_decision_bundle(
    *,
    evidence_pack: Mapping[str, Any],
    decision_record: Mapping[str, Any],
    eval_result: Mapping[str, Any],
    readiness_record: Mapping[str, Any],
    conflict_record: Mapping[str, Any],
) -> dict[str, Any]:
    validate_artifact(dict(evidence_pack), "decision_evidence_pack")
    validate_artifact(dict(decision_record), "continuation_decision_record")
    validate_artifact(dict(eval_result), "decision_eval_result")
    validate_artifact(dict(readiness_record), "decision_readiness_record")
    validate_artifact(dict(conflict_record), "decision_conflict_record")

    bundle = {
        "artifact_type": "decision_bundle",
        "schema_version": "1.0.0",
        "bundle_id": f"cde-bundle-{_digest([evidence_pack['evidence_pack_id'], decision_record['decision_id'], eval_result['eval_id']])[:16]}",
        "trace_id": decision_record["trace_id"],
        "decision_evidence_pack_ref": f"decision_evidence_pack:{evidence_pack['evidence_pack_id']}",
        "continuation_decision_record_ref": f"continuation_decision_record:{decision_record['decision_id']}",
        "decision_eval_result_ref": f"decision_eval_result:{eval_result['eval_id']}",
        "decision_readiness_record_ref": f"decision_readiness_record:{readiness_record['readiness_id']}",
        "decision_conflict_record_ref": f"decision_conflict_record:{conflict_record['conflict_id']}",
        "lineage_complete": True,
        "non_authority_assertions": [
            "bundle_is_decision_only",
            "bundle_not_execution_authority",
            "bundle_not_enforcement_authority",
        ],
    }
    validate_artifact(bundle, "decision_bundle")
    return bundle


def validate_decision_replay(*, evidence_pack: Mapping[str, Any], first_decision: Mapping[str, Any], replay_decision: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(evidence_pack), "decision_evidence_pack")
    validate_artifact(dict(first_decision), "continuation_decision_record")
    validate_artifact(dict(replay_decision), "continuation_decision_record")

    input_fp = evidence_pack["input_fingerprint"]
    first_fp = _digest(first_decision)
    replay_fp = _digest(replay_decision)
    deterministic_match = first_fp == replay_fp

    record = {
        "artifact_type": "decision_replay_validation_record",
        "schema_version": "1.0.0",
        "validation_id": f"cde-replay-{_digest([input_fp, first_fp, replay_fp])[:16]}",
        "input_fingerprint": input_fp,
        "first_decision_fingerprint": first_fp,
        "replay_decision_fingerprint": replay_fp,
        "deterministic_match": deterministic_match,
        "result": "pass" if deterministic_match else "fail",
        "fail_reasons": [] if deterministic_match else ["decision_replay_mismatch"],
    }
    validate_artifact(record, "decision_replay_validation_record")
    return record


def build_decision_effectiveness_record(*, decision_record: Mapping[str, Any], downstream_outcome_ref: str, downstream_outcome: str) -> dict[str, Any]:
    validate_artifact(dict(decision_record), "continuation_decision_record")
    outcome = _required_str(downstream_outcome, field="downstream_outcome")

    mapping = {
        ("continue_repair_bounded", "improved"): ("effective", 0.9, 0.6),
        ("continue_repair_bounded", "regressed"): ("too_permissive", 0.2, 0.1),
        ("block", "improved"): ("too_strict", 0.4, 0.95),
        ("human_review_required", "unchanged"): ("noisy", 0.5, 0.8),
    }
    state, precision, strictness = mapping.get((decision_record["decision_outcome"], outcome), ("effective", 0.7, 0.7))

    record = {
        "artifact_type": "decision_effectiveness_record",
        "schema_version": "1.0.0",
        "record_id": f"cde-eff-{_digest([decision_record['decision_id'], downstream_outcome_ref, outcome])[:16]}",
        "trace_id": decision_record["trace_id"],
        "continuation_decision_record_ref": f"continuation_decision_record:{decision_record['decision_id']}",
        "downstream_outcome_ref": _required_str(downstream_outcome_ref, field="downstream_outcome_ref"),
        "effectiveness_state": state,
        "precision_proxy": precision,
        "strictness_proxy": strictness,
    }
    validate_artifact(record, "decision_effectiveness_record")
    return record


def verify_cde_boundary_inputs(*, upstream_artifacts: Sequence[Mapping[str, Any]]) -> None:
    if not upstream_artifacts:
        raise CDEDecisionFlowError("upstream_artifacts must not be empty")
    for artifact in upstream_artifacts:
        artifact_type = _required_str(artifact.get("artifact_type"), field="artifact_type")
        if artifact_type not in _ALLOWED_UPSTREAM_TYPES:
            raise CDEDecisionFlowError("CDE upstream boundary rejected non-governed artifact")
        if any(field in artifact for field in _FORBIDDEN_EXECUTION_FIELDS):
            raise CDEDecisionFlowError("CDE fail-closed: execution/enforcement fields are forbidden")
