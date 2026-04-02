"""Deterministic fail-closed manifest-to-runtime obedience proof evaluator (CON-031)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ControlSurfaceObedienceError(ValueError):
    """Raised when obedience proof cannot be safely evaluated."""


_REQUIRED_SURFACES = [
    "sequence_transition_promotion",
    "done_certification_gate",
    "trust_spine_invariant_validation",
]


def _canonical_hash(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load_json_object(path_value: str, *, label: str) -> Dict[str, Any]:
    path = Path(path_value)
    if not path.is_file():
        raise ControlSurfaceObedienceError(f"{label} file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ControlSurfaceObedienceError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ControlSurfaceObedienceError(f"{label} must be a JSON object")
    return payload


def _validate_schema(instance: Dict[str, Any], schema_name: str, *, label: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        reason = "; ".join(error.message for error in errors)
        raise ControlSurfaceObedienceError(f"{label} failed schema validation ({schema_name}): {reason}")


def _surface_declared(manifest: Dict[str, Any], surface_id: str) -> bool:
    surfaces = manifest.get("surfaces")
    if not isinstance(surfaces, list):
        return False
    for surface in surfaces:
        if isinstance(surface, dict) and surface.get("surface_id") == surface_id:
            return True
    return False


def _surface_required_by_enforcement(enforcement_result: Dict[str, Any], surface_id: str) -> bool:
    evaluated = enforcement_result.get("required_surfaces_evaluated")
    return isinstance(evaluated, list) and surface_id in evaluated


def _as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def evaluate_control_surface_obedience(
    *,
    manifest: Dict[str, Any],
    manifest_ref: str,
    enforcement_result: Dict[str, Any],
    enforcement_result_ref: str,
    invariant_result: Dict[str, Any],
    invariant_result_ref: str,
    done_certification_record: Dict[str, Any],
    done_certification_ref: str,
    promotion_decision: Dict[str, Any],
    promotion_decision_ref: str,
) -> Dict[str, Any]:
    """Evaluate deterministic obedience for narrow governed trust-spine control surfaces."""
    _validate_schema(manifest, "control_surface_manifest", label="control_surface_manifest")
    _validate_schema(enforcement_result, "control_surface_enforcement_result", label="control_surface_enforcement_result")
    _validate_schema(done_certification_record, "done_certification_record", label="done_certification_record")

    passed_value = _as_bool(invariant_result.get("passed"))
    if passed_value is None:
        raise ControlSurfaceObedienceError("trust_spine_invariant_result.passed must be a boolean")
    invariant_blocking_reasons = invariant_result.get("blocking_reasons")
    if not isinstance(invariant_blocking_reasons, list) or any(
        not isinstance(item, str) or not item.strip() for item in invariant_blocking_reasons
    ):
        raise ControlSurfaceObedienceError("trust_spine_invariant_result.blocking_reasons must be an array of strings")

    promotion_allowed = _as_bool(promotion_decision.get("allowed"))
    if promotion_allowed is None:
        raise ControlSurfaceObedienceError("promotion_decision.allowed must be a boolean")

    promotion_target = str(promotion_decision.get("target_state") or "").strip() or "promoted"
    if promotion_target != "promoted":
        raise ControlSurfaceObedienceError("promotion_decision.target_state must be 'promoted'")

    evidence_refs: Dict[str, str] = {
        "manifest_ref": manifest_ref,
        "enforcement_result_ref": enforcement_result_ref,
        "invariant_result_ref": invariant_result_ref,
        "done_certification_ref": done_certification_ref,
        "promotion_decision_ref": promotion_decision_ref,
    }

    surface_results: List[Dict[str, Any]] = []
    missing_obedience_evidence: List[str] = []
    contradictory_obedience_evidence: List[str] = []

    invariant_failed = passed_value is False
    cert_status = str(done_certification_record.get("final_status") or "").strip().upper()
    cert_response = str(done_certification_record.get("system_response") or "").strip().lower()

    # trust_spine_invariant_validation
    trust_missing: List[str] = []
    trust_contradictions: List[str] = []
    if not _surface_declared(manifest, "trust_spine_invariant_validation"):
        trust_missing.append("manifest surface declaration missing")
    if not _surface_required_by_enforcement(enforcement_result, "trust_spine_invariant_validation"):
        trust_missing.append("enforcement required surface mapping missing")
    if invariant_failed and cert_status == "PASSED":
        trust_contradictions.append("invariant failed while done certification passed")
    if invariant_failed and promotion_allowed:
        trust_contradictions.append("invariant failed while promotion decision allowed")

    surface_results.append(
        {
            "surface_id": "trust_spine_invariant_validation",
            "declared_in_manifest": len(trust_missing) == 0 or "manifest surface declaration missing" not in trust_missing,
            "required_by_enforcement": len(trust_missing) == 0 or "enforcement required surface mapping missing" not in trust_missing,
            "runtime_obeyed": len(trust_contradictions) == 0 and len(trust_missing) == 0,
            "status": "PASS" if not trust_missing and not trust_contradictions else "BLOCK",
            "evidence_refs": [
                manifest_ref,
                enforcement_result_ref,
                invariant_result_ref,
                done_certification_ref,
                promotion_decision_ref,
            ],
            "missing_evidence": trust_missing,
            "contradictions": trust_contradictions,
        }
    )
    missing_obedience_evidence.extend([f"trust_spine_invariant_validation:{m}" for m in trust_missing])
    contradictory_obedience_evidence.extend([f"trust_spine_invariant_validation:{c}" for c in trust_contradictions])

    # done_certification_gate
    done_missing: List[str] = []
    done_contradictions: List[str] = []
    checks = done_certification_record.get("check_results")
    trust_check = checks.get("trust_spine_invariants") if isinstance(checks, dict) else None
    trust_check_passed = trust_check.get("passed") if isinstance(trust_check, dict) else None
    if not _surface_declared(manifest, "done_certification_gate"):
        done_missing.append("manifest surface declaration missing")
    if not _surface_required_by_enforcement(enforcement_result, "done_certification_gate"):
        done_missing.append("enforcement required surface mapping missing")
    if not isinstance(trust_check, dict):
        done_missing.append("done certification trust-spine check evidence missing")
    elif not isinstance(trust_check_passed, bool):
        done_missing.append("done certification trust-spine check passed flag missing")
    if invariant_failed and cert_status == "PASSED":
        done_contradictions.append("certification passed despite failed trust-spine invariant")
    if cert_status == "FAILED" and cert_response == "allow":
        done_contradictions.append("certification failed while system_response=allow")

    surface_results.append(
        {
            "surface_id": "done_certification_gate",
            "declared_in_manifest": len(done_missing) == 0 or "manifest surface declaration missing" not in done_missing,
            "required_by_enforcement": len(done_missing) == 0 or "enforcement required surface mapping missing" not in done_missing,
            "runtime_obeyed": len(done_missing) == 0 and len(done_contradictions) == 0,
            "status": "PASS" if not done_missing and not done_contradictions else "BLOCK",
            "evidence_refs": [manifest_ref, enforcement_result_ref, invariant_result_ref, done_certification_ref],
            "missing_evidence": done_missing,
            "contradictions": done_contradictions,
        }
    )
    missing_obedience_evidence.extend([f"done_certification_gate:{m}" for m in done_missing])
    contradictory_obedience_evidence.extend([f"done_certification_gate:{c}" for c in done_contradictions])

    # sequence_transition_promotion
    promo_missing: List[str] = []
    promo_contradictions: List[str] = []
    consumed_signals = promotion_decision.get("consumed_signals")
    if not isinstance(consumed_signals, list) or not all(isinstance(v, str) and v.strip() for v in consumed_signals):
        promo_missing.append("promotion consumed_signals evidence missing")
        consumed_signals = []
    if not _surface_declared(manifest, "sequence_transition_promotion"):
        promo_missing.append("manifest surface declaration missing")
    if not _surface_required_by_enforcement(enforcement_result, "sequence_transition_promotion"):
        promo_missing.append("enforcement required surface mapping missing")
    for required_signal in (
        "trust_spine_invariant_validation",
        "done_certification_gate",
    ):
        if required_signal not in consumed_signals:
            promo_missing.append(f"promotion consumed_signals missing required signal: {required_signal}")
    if invariant_failed and promotion_allowed:
        promo_contradictions.append("promotion allowed despite failed trust-spine invariant")
    if cert_status == "FAILED" and promotion_allowed:
        promo_contradictions.append("promotion allowed despite failed done certification")

    surface_results.append(
        {
            "surface_id": "sequence_transition_promotion",
            "declared_in_manifest": len(promo_missing) == 0 or "manifest surface declaration missing" not in promo_missing,
            "required_by_enforcement": len(promo_missing) == 0 or "enforcement required surface mapping missing" not in promo_missing,
            "runtime_obeyed": len(promo_missing) == 0 and len(promo_contradictions) == 0,
            "status": "PASS" if not promo_missing and not promo_contradictions else "BLOCK",
            "evidence_refs": [manifest_ref, enforcement_result_ref, invariant_result_ref, done_certification_ref, promotion_decision_ref],
            "missing_evidence": promo_missing,
            "contradictions": promo_contradictions,
        }
    )
    missing_obedience_evidence.extend([f"sequence_transition_promotion:{m}" for m in promo_missing])
    contradictory_obedience_evidence.extend([f"sequence_transition_promotion:{c}" for c in promo_contradictions])

    blocking_reasons = sorted(set(missing_obedience_evidence + contradictory_obedience_evidence))
    overall_decision = "ALLOW" if not blocking_reasons else "BLOCK"

    identity_payload = {
        "manifest_identity": manifest.get("deterministic_build_identity"),
        "enforcement_id": enforcement_result.get("deterministic_enforcement_id"),
        "surfaces": [row["surface_id"] + ":" + row["status"] for row in surface_results],
        "overall_decision": overall_decision,
    }
    deterministic_obedience_id = f"cso-{_canonical_hash(identity_payload)[:16]}"

    result = {
        "artifact_type": "control_surface_obedience_result",
        "schema_version": "1.0.0",
        "manifest_ref": manifest_ref,
        "manifest_identity": str(manifest.get("deterministic_build_identity") or ""),
        "enforcement_result_ref": enforcement_result_ref,
        "enforcement_result_id": str(enforcement_result.get("deterministic_enforcement_id") or ""),
        "evaluated_surfaces": list(_REQUIRED_SURFACES),
        "surface_results": surface_results,
        "missing_obedience_evidence": sorted(set(missing_obedience_evidence)),
        "contradictory_obedience_evidence": sorted(set(contradictory_obedience_evidence)),
        "blocking_reasons": blocking_reasons,
        "overall_decision": overall_decision,
        "deterministic_obedience_id": deterministic_obedience_id,
        "trace": {
            "producer": "spectrum_systems.modules.runtime.control_surface_obedience",
            "policy_ref": "CON-031.obedience_proof.v1",
            "evidence_refs": evidence_refs,
        },
    }

    _validate_schema(result, "control_surface_obedience_result", label="control_surface_obedience_result")
    return result


def run_control_surface_obedience(
    *,
    manifest_path: Path,
    enforcement_result_path: Path,
    invariant_result_path: Path,
    done_certification_path: Path,
    promotion_decision_path: Path,
) -> Dict[str, Any]:
    """Load referenced artifacts, evaluate obedience proof, and return the result."""
    manifest = _load_json_object(str(manifest_path), label="control_surface_manifest")
    enforcement_result = _load_json_object(str(enforcement_result_path), label="control_surface_enforcement_result")
    invariant_result = _load_json_object(str(invariant_result_path), label="trust_spine_invariant_result")
    done_certification = _load_json_object(str(done_certification_path), label="done_certification_record")
    promotion_decision = _load_json_object(str(promotion_decision_path), label="promotion_decision")

    return evaluate_control_surface_obedience(
        manifest=manifest,
        manifest_ref=str(manifest_path.as_posix()),
        enforcement_result=enforcement_result,
        enforcement_result_ref=str(enforcement_result_path.as_posix()),
        invariant_result=invariant_result,
        invariant_result_ref=str(invariant_result_path.as_posix()),
        done_certification_record=done_certification,
        done_certification_ref=str(done_certification_path.as_posix()),
        promotion_decision=promotion_decision,
        promotion_decision_ref=str(promotion_decision_path.as_posix()),
    )
