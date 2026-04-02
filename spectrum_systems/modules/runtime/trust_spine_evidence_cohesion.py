"""Deterministic fail-closed trust-spine evidence cohesion evaluator (CON-033)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class TrustSpineEvidenceCohesionError(ValueError):
    """Raised when trust-spine evidence cohesion cannot be evaluated safely."""


_CONTRADICTION_BY_REASON = {
    "surface": "surface_set_mismatch",
    "policy": "policy_context_mismatch",
    "enforcement_obedience": "enforcement_obedience_contradiction",
    "invariant_certification": "invariant_certification_contradiction",
    "promotion_certification": "promotion_certification_contradiction",
    "missing": "missing_required_evidence",
    "reference": "artifact_reference_mismatch",
}


def _canonical_hash(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _as_required_dict(payload: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise TrustSpineEvidenceCohesionError(f"{key} must be an object")
    return value


def _require_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TrustSpineEvidenceCohesionError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_schema(instance: Dict[str, Any], schema_name: str, *, label: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise TrustSpineEvidenceCohesionError(f"{label} failed schema validation ({schema_name}): {details}")


def _ref_or_missing(refs: Dict[str, str], key: str) -> str:
    value = refs.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return f"missing:{key}"


def evaluate_trust_spine_evidence_cohesion(*, artifacts: Dict[str, Dict[str, Any]], refs: Dict[str, str]) -> Dict[str, Any]:
    """Evaluate trust-spine evidence cohesion across active governed artifacts."""
    manifest = _as_required_dict(artifacts, "manifest")
    enforcement = _as_required_dict(artifacts, "enforcement_result")
    obedience = _as_required_dict(artifacts, "obedience_result")
    invariant_result = _as_required_dict(artifacts, "invariant_result")
    done_certification = _as_required_dict(artifacts, "done_certification_record")

    promotion_decision = artifacts.get("promotion_decision")
    if promotion_decision is not None and not isinstance(promotion_decision, dict):
        raise TrustSpineEvidenceCohesionError("promotion_decision must be an object when provided")

    contract_preflight = artifacts.get("contract_preflight_result")
    if contract_preflight is not None and not isinstance(contract_preflight, dict):
        raise TrustSpineEvidenceCohesionError("contract_preflight_result must be an object when provided")

    _validate_schema(manifest, "control_surface_manifest", label="control_surface_manifest")
    _validate_schema(enforcement, "control_surface_enforcement_result", label="control_surface_enforcement_result")
    _validate_schema(obedience, "control_surface_obedience_result", label="control_surface_obedience_result")
    _validate_schema(done_certification, "done_certification_record", label="done_certification_record")

    passed = invariant_result.get("passed")
    if not isinstance(passed, bool):
        raise TrustSpineEvidenceCohesionError("trust_spine_invariant_result.passed must be a boolean")
    invariant_reasons = invariant_result.get("blocking_reasons")
    if not isinstance(invariant_reasons, list) or any(not isinstance(item, str) or not item.strip() for item in invariant_reasons):
        raise TrustSpineEvidenceCohesionError("trust_spine_invariant_result.blocking_reasons must be an array of strings")

    refs_required = {
        "manifest_ref",
        "enforcement_result_ref",
        "obedience_result_ref",
        "invariant_result_ref",
        "done_certification_ref",
    }
    missing_required_evidence_refs: list[str] = []
    for key in sorted(refs_required):
        value = refs.get(key)
        if not isinstance(value, str) or not value.strip():
            missing_required_evidence_refs.append(key)

    blocking_reasons: list[str] = []
    mismatched_artifact_references: list[dict[str, str]] = []
    inconsistent_truth_context_fields: list[dict[str, str]] = []
    contradiction_categories: set[str] = set()

    if missing_required_evidence_refs:
        contradiction_categories.add("missing_required_evidence")
        for key in missing_required_evidence_refs:
            blocking_reasons.append(f"MISSING_REQUIRED_EVIDENCE:{key}")

    manifest_surfaces = {
        surface.get("surface_id")
        for surface in manifest.get("surfaces", [])
        if isinstance(surface, dict) and isinstance(surface.get("surface_id"), str)
    }
    enforcement_surfaces = {
        value for value in enforcement.get("required_surfaces_evaluated", []) if isinstance(value, str) and value
    }
    obedience_surfaces = {
        value for value in obedience.get("evaluated_surfaces", []) if isinstance(value, str) and value
    }
    required_surface_subset = {
        "sequence_transition_promotion",
        "done_certification_gate",
        "trust_spine_invariant_validation",
    }
    if not required_surface_subset.issubset(manifest_surfaces):
        contradiction_categories.add("surface_set_mismatch")
        blocking_reasons.append("SURFACE_SET_MISMATCH:manifest_missing_required_trust_spine_surfaces")
    if not required_surface_subset.issubset(enforcement_surfaces):
        contradiction_categories.add("surface_set_mismatch")
        blocking_reasons.append("SURFACE_SET_MISMATCH:enforcement_missing_required_trust_spine_surfaces")
    if obedience_surfaces != required_surface_subset:
        contradiction_categories.add("surface_set_mismatch")
        blocking_reasons.append("SURFACE_SET_MISMATCH:obedience_evaluated_surfaces_not_equal_required_trust_spine_subset")

    if _norm(enforcement.get("enforcement_status")) == "block" and _norm(obedience.get("overall_decision")) == "allow":
        contradiction_categories.add("enforcement_obedience_contradiction")
        blocking_reasons.append("ENFORCEMENT_OBEDIENCE_CONTRADICTION:enforcement_block_with_obedience_allow")

    done_status = _norm(done_certification.get("final_status"))
    done_response = _norm(done_certification.get("system_response"))
    if passed is False and done_status == "passed":
        contradiction_categories.add("invariant_certification_contradiction")
        blocking_reasons.append("INVARIANT_CERTIFICATION_CONTRADICTION:invariant_failed_with_done_certification_passed")
    if passed is False and done_response == "allow":
        contradiction_categories.add("invariant_certification_contradiction")
        blocking_reasons.append("INVARIANT_CERTIFICATION_CONTRADICTION:invariant_failed_with_done_system_response_allow")

    if promotion_decision is not None:
        if not isinstance(promotion_decision.get("allowed"), bool):
            raise TrustSpineEvidenceCohesionError("promotion_decision.allowed must be a boolean when promotion_decision is provided")
        if promotion_decision.get("allowed") and done_status == "failed":
            contradiction_categories.add("promotion_certification_contradiction")
            blocking_reasons.append("PROMOTION_CERTIFICATION_CONTRADICTION:promotion_allowed_with_failed_done_certification")
        if promotion_decision.get("allowed") and _norm(obedience.get("overall_decision")) == "block":
            contradiction_categories.add("promotion_certification_contradiction")
            blocking_reasons.append("PROMOTION_CERTIFICATION_CONTRADICTION:promotion_allowed_with_obedience_block")

    manifest_authority_mode = _norm(manifest.get("authority_path_mode") or "active_runtime")
    done_mode = _norm((done_certification.get("trust_spine_evidence_completeness_result") or {}).get("authority_path_mode"))
    if done_mode and manifest_authority_mode and done_mode != manifest_authority_mode:
        contradiction_categories.add("policy_context_mismatch")
        blocking_reasons.append("POLICY_CONTEXT_MISMATCH:authority_path_mode")
        inconsistent_truth_context_fields.append(
            {
                "field": "authority_path_mode",
                "expected": manifest_authority_mode,
                "observed": done_mode,
                "artifact": "done_certification_record",
            }
        )

    manifest_policy_ref = _norm((manifest.get("control_loop_gate_proof") or {}).get("policy_ref"))
    enforcement_policy_ref = _norm((enforcement.get("trace") or {}).get("policy_ref"))
    if manifest_policy_ref and enforcement_policy_ref and manifest_policy_ref != enforcement_policy_ref:
        contradiction_categories.add("policy_context_mismatch")
        blocking_reasons.append("POLICY_CONTEXT_MISMATCH:manifest_vs_enforcement_policy_ref")
        inconsistent_truth_context_fields.append(
            {
                "field": "policy_ref",
                "expected": manifest_policy_ref,
                "observed": enforcement_policy_ref,
                "artifact": "control_surface_enforcement_result",
            }
        )

    expected_manifest_ref = _require_string(refs.get("manifest_ref"), field="refs.manifest_ref")
    observed_manifest_ref = _require_string(enforcement.get("manifest_ref"), field="control_surface_enforcement_result.manifest_ref")
    if observed_manifest_ref != expected_manifest_ref:
        contradiction_categories.add("artifact_reference_mismatch")
        blocking_reasons.append("ARTIFACT_REFERENCE_MISMATCH:manifest_to_enforcement")
        mismatched_artifact_references.append(
            {
                "chain_link": "manifest->enforcement",
                "expected_ref": expected_manifest_ref,
                "observed_ref": observed_manifest_ref,
            }
        )

    observed_obedience_manifest_ref = _require_string(obedience.get("manifest_ref"), field="control_surface_obedience_result.manifest_ref")
    if observed_obedience_manifest_ref != expected_manifest_ref:
        contradiction_categories.add("artifact_reference_mismatch")
        blocking_reasons.append("ARTIFACT_REFERENCE_MISMATCH:manifest_to_obedience")
        mismatched_artifact_references.append(
            {
                "chain_link": "manifest->obedience",
                "expected_ref": expected_manifest_ref,
                "observed_ref": observed_obedience_manifest_ref,
            }
        )

    expected_enforcement_ref = _require_string(refs.get("enforcement_result_ref"), field="refs.enforcement_result_ref")
    observed_obedience_enforcement_ref = _require_string(
        obedience.get("enforcement_result_ref"), field="control_surface_obedience_result.enforcement_result_ref"
    )
    if observed_obedience_enforcement_ref != expected_enforcement_ref:
        contradiction_categories.add("artifact_reference_mismatch")
        blocking_reasons.append("ARTIFACT_REFERENCE_MISMATCH:enforcement_to_obedience")
        mismatched_artifact_references.append(
            {
                "chain_link": "enforcement->obedience",
                "expected_ref": expected_enforcement_ref,
                "observed_ref": observed_obedience_enforcement_ref,
            }
        )

    if contract_preflight is not None:
        signal = _as_required_dict(contract_preflight, "control_signal")
        decision = _norm(signal.get("strategy_gate_decision"))
        if decision in {"allow", "warn"} and bool(blocking_reasons):
            contradiction_categories.add("promotion_certification_contradiction")
            blocking_reasons.append("PROMOTION_CERTIFICATION_CONTRADICTION:preflight_allow_warn_with_cohesion_block")

    evaluated_surfaces = [
        "control_surface_manifest",
        "control_surface_enforcement_result",
        "control_surface_obedience_result",
        "trust_spine_invariant_result",
        "done_certification_record",
    ]
    artifact_refs = {
        "manifest_ref": _ref_or_missing(refs, "manifest_ref"),
        "enforcement_result_ref": _ref_or_missing(refs, "enforcement_result_ref"),
        "obedience_result_ref": _ref_or_missing(refs, "obedience_result_ref"),
        "invariant_result_ref": _ref_or_missing(refs, "invariant_result_ref"),
        "done_certification_ref": _ref_or_missing(refs, "done_certification_ref"),
    }
    if "promotion_decision_ref" in refs and isinstance(refs["promotion_decision_ref"], str) and refs["promotion_decision_ref"].strip():
        artifact_refs["promotion_decision_ref"] = refs["promotion_decision_ref"].strip()
        evaluated_surfaces.append("sequence_transition_promotion")
    if "contract_preflight_ref" in refs and isinstance(refs["contract_preflight_ref"], str) and refs["contract_preflight_ref"].strip():
        artifact_refs["contract_preflight_ref"] = refs["contract_preflight_ref"].strip()
        evaluated_surfaces.append("contract_preflight_gate")

    contradiction_list = sorted(contradiction_categories)
    blocking_list = sorted(set(blocking_reasons))
    result = {
        "artifact_type": "trust_spine_evidence_cohesion_result",
        "schema_version": "1.0.0",
        "deterministic_cohesion_id": "",
        "overall_decision": "BLOCK" if blocking_list else "ALLOW",
        "evaluated_surfaces": evaluated_surfaces,
        "artifact_refs": artifact_refs,
        "contradiction_categories": contradiction_list,
        "blocking_reasons": blocking_list,
        "missing_required_evidence_refs": sorted(set(missing_required_evidence_refs)),
        "mismatched_artifact_references": sorted(
            mismatched_artifact_references,
            key=lambda item: (item["chain_link"], item["expected_ref"], item["observed_ref"]),
        ),
        "inconsistent_truth_context_fields": sorted(
            inconsistent_truth_context_fields,
            key=lambda item: (item["field"], item["artifact"], item["expected"], item["observed"]),
        ),
        "trace": {
            "producer": "spectrum_systems.modules.runtime.trust_spine_evidence_cohesion",
            "policy_ref": "CON-033.trust_spine_evidence_cohesion.v1",
        },
    }

    identity_payload = {
        "artifact_refs": result["artifact_refs"],
        "contradiction_categories": result["contradiction_categories"],
        "blocking_reasons": result["blocking_reasons"],
        "inconsistent_truth_context_fields": result["inconsistent_truth_context_fields"],
        "mismatched_artifact_references": result["mismatched_artifact_references"],
    }
    result["deterministic_cohesion_id"] = f"tsec-{_canonical_hash(identity_payload)[:16]}"

    _validate_schema(result, "trust_spine_evidence_cohesion_result", label="trust_spine_evidence_cohesion_result")
    return result
