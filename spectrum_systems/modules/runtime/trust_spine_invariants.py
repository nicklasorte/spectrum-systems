"""Centralized trust-spine cross-seam invariant validation helpers.

These checks are deterministic and fail-closed. They validate that replay,
control, enforcement, coverage, gate-proof, and closure artifacts remain
semantically aligned on authority-bearing promotion/certification paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


_BLOCK_VALUES = frozenset({"deny", "block", "blocked", "freeze", "frozen", "hold", "require_review", "warn"})
_ALLOW_VALUES = frozenset({"allow", "pass", "passed", "certified"})


@dataclass(frozen=True)
class TrustSpineInvariantResult:
    passed: bool
    categories_checked: List[str]
    violations: List[str]
    blocking_reasons: List[str]
    evaluated_surfaces: Dict[str, str]


@dataclass(frozen=True)
class TrustSpineEvidenceCompletenessResult:
    passed: bool
    categories_checked: List[str]
    blocking_reasons: List[str]
    missing_refs: List[str]
    evaluated_surfaces: Dict[str, str]
    authority_path_mode: str
    promotable: bool
    certifiable: bool


_DEF_CATEGORIES = [
    "threshold_context_consistency",
    "policy_authority_consistency",
    "replay_enforcement_promotion_alignment",
    "coverage_promotion_alignment",
    "gate_proof_truthfulness",
    "certification_closure_coherence",
]

_COMPLETENESS_CATEGORIES = [
    "required_authority_refs_present",
    "enforcement_evidence_present",
    "coverage_evidence_present",
    "certification_supporting_refs_present",
    "promotion_supporting_refs_present",
    "active_path_vs_legacy_mode_consistency",
]


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_blocking(value: Any) -> bool:
    return _norm(value) in _BLOCK_VALUES


def _is_allow_like(value: Any) -> bool:
    return _norm(value) in _ALLOW_VALUES


def _coverage_has_required_gap(coverage_payload: Dict[str, Any]) -> bool:
    required_gaps = coverage_payload.get("required_slice_gaps")
    if isinstance(required_gaps, list) and required_gaps:
        return True

    uncovered = coverage_payload.get("uncovered_required_slices")
    if isinstance(uncovered, list) and uncovered:
        return True

    gaps = coverage_payload.get("coverage_gaps")
    if not isinstance(gaps, list):
        return False
    for entry in gaps:
        if not isinstance(entry, dict):
            continue
        required = entry.get("required") is True or "required" in _norm(entry.get("gap_type"))
        if not required:
            continue
        severity = _norm(entry.get("severity"))
        status = _norm(entry.get("status"))
        if severity in {"high", "critical"}:
            return True
        if status in {"missing", "uncovered", "gap"}:
            return True
    return False


def validate_trust_spine_evidence_completeness(
    *,
    refs: Dict[str, Any],
    target_surface: str,
    authority_path_mode: str,
) -> TrustSpineEvidenceCompletenessResult:
    """Validate trust-spine evidence completeness for active/legacy authority modes."""
    missing_refs: List[str] = []
    blocking_reasons: List[str] = []
    normalized_mode = _norm(authority_path_mode) or "active_runtime"
    normalized_surface = _norm(target_surface)
    is_active_authority = normalized_mode == "active_runtime"
    is_legacy_mode = normalized_mode in {"legacy_compatibility", "reduced_depth_non_authority"}

    required_base_refs = ("replay_result_ref", "policy_ref")
    required_active_refs = ("enforcement_result_ref", "eval_coverage_summary_ref")
    required_promotion_refs = ("certification_pack_ref", "gate_proof_ref", "closure_bundle_ref")
    required_certification_refs = ("certification_pack_ref", "gate_proof_ref", "closure_bundle_ref")

    def _present(ref_key: str) -> bool:
        value = refs.get(ref_key)
        return isinstance(value, str) and bool(value.strip())

    for key in required_base_refs:
        if not _present(key):
            missing_refs.append(key)
            blocking_reasons.append("TRUST_SPINE_REQUIRED_REF_MISSING")

    if is_active_authority:
        for key in required_active_refs:
            if not _present(key):
                missing_refs.append(key)
                reason = "TRUST_SPINE_ENFORCEMENT_REF_MISSING" if key == "enforcement_result_ref" else "TRUST_SPINE_COVERAGE_REF_MISSING"
                blocking_reasons.append(reason)

        if normalized_surface == "promotion":
            for key in required_promotion_refs:
                if not _present(key):
                    missing_refs.append(key)
                    blocking_reasons.append("TRUST_SPINE_REQUIRED_REF_MISSING")
        if normalized_surface == "certification":
            for key in required_certification_refs:
                if not _present(key):
                    missing_refs.append(key)
                    blocking_reasons.append("TRUST_SPINE_REQUIRED_REF_MISSING")

        if missing_refs:
            blocking_reasons.append("TRUST_SPINE_ACTIVE_PATH_INCOMPLETE")
            if normalized_surface == "certification":
                blocking_reasons.append("TRUST_SPINE_CERTIFICATION_EVIDENCE_INCOMPLETE")

    if is_legacy_mode and normalized_surface == "promotion":
        blocking_reasons.append("TRUST_SPINE_LEGACY_PATH_NOT_PROMOTABLE")

    unique_missing_refs = sorted(set(missing_refs))
    unique_reasons = sorted(set(blocking_reasons))
    passed = len(unique_reasons) == 0
    evaluated_surfaces = {
        "target_surface": normalized_surface or "unknown",
        "authority_path_mode": normalized_mode,
        "refs_count": str(len(refs)),
    }
    promotable = passed and is_active_authority and normalized_surface == "promotion"
    certifiable = passed and is_active_authority and normalized_surface == "certification"
    return TrustSpineEvidenceCompletenessResult(
        passed=passed,
        categories_checked=list(_COMPLETENESS_CATEGORIES),
        blocking_reasons=unique_reasons,
        missing_refs=unique_missing_refs,
        evaluated_surfaces=evaluated_surfaces,
        authority_path_mode=normalized_mode,
        promotable=promotable,
        certifiable=certifiable,
    )


def validate_trust_spine_invariants(
    *,
    replay_result: Dict[str, Any],
    evaluation_control_decision: Dict[str, Any],
    enforcement_result: Dict[str, Any],
    eval_coverage_summary: Dict[str, Any],
    gate_proof_evidence: Dict[str, Any] | None,
    done_certification_record: Dict[str, Any] | None,
    target_surface: str,
) -> TrustSpineInvariantResult:
    """Validate cross-seam trust invariants for promotion/certification paths."""
    violations: List[str] = []
    reasons: List[str] = []
    evaluated_surfaces = {
        "target_surface": target_surface,
        "replay_result": str(replay_result.get("artifact_type") or "replay_result"),
        "evaluation_control_decision": str(evaluation_control_decision.get("artifact_type") or "evaluation_control_decision"),
        "enforcement_result": str(enforcement_result.get("artifact_type") or "enforcement_result"),
        "eval_coverage_summary": str(eval_coverage_summary.get("artifact_type") or "eval_coverage_summary"),
        "gate_proof": "embedded" if isinstance(gate_proof_evidence, dict) else "missing",
        "done_certification": "present" if isinstance(done_certification_record, dict) else "absent",
    }

    threshold_context = _norm(evaluation_control_decision.get("threshold_context"))
    if not threshold_context and str(evaluation_control_decision.get("schema_version") or "") == "1.1.0":
        threshold_context = "active_runtime"
    if target_surface in {"promotion", "certification"} and threshold_context != "active_runtime":
        violations.append(
            "threshold_context_consistency: promotion/certification authority requires threshold_context=active_runtime"
        )
        reasons.append("TRUST_SPINE_THRESHOLD_CONTEXT_MISMATCH")

    decision = _norm(evaluation_control_decision.get("decision"))
    system_response = _norm(evaluation_control_decision.get("system_response"))
    final_status = _norm(enforcement_result.get("final_status") or enforcement_result.get("enforcement_status"))

    contradictory_pairs = {
        ("allow", "block"),
        ("allow", "freeze"),
        ("allow", "deny"),
        ("require_review", "allow"),
        ("deny", "allow"),
    }
    if (decision, system_response) in contradictory_pairs:
        violations.append("policy_authority_consistency: control decision/system_response authority is contradictory")
        reasons.append("TRUST_SPINE_POLICY_AUTHORITY_CONTRADICTION")

    if _is_blocking(decision) and _is_allow_like(final_status):
        violations.append("policy_authority_consistency: blocking control decision cannot map to permissive enforcement")
        reasons.append("TRUST_SPINE_POLICY_ENFORCEMENT_CONTRADICTION")

    replay_status = _norm(replay_result.get("status"))
    replay_final_status = _norm(replay_result.get("replay_final_status"))
    replay_prereq_valid = replay_result.get("prerequisites_valid")
    replay_blocked = replay_status == "blocked" or replay_prereq_valid is False or _is_blocking(replay_final_status)
    if replay_blocked:
        if _is_allow_like(decision) or _is_allow_like(system_response) or _is_allow_like(final_status):
            violations.append("replay_enforcement_promotion_alignment: blocked/invalid replay cannot yield permissive authority")
            reasons.append("TRUST_SPINE_REPLAY_PROMOTION_MISMATCH")

    if _is_allow_like(system_response) and _is_blocking(final_status):
        violations.append("replay_enforcement_promotion_alignment: permissive control decision conflicts with blocking enforcement")
        reasons.append("TRUST_SPINE_CONTROL_ENFORCEMENT_MISMATCH")

    required_gap = _coverage_has_required_gap(eval_coverage_summary)
    if required_gap and (_is_allow_like(decision) or _is_allow_like(system_response) or _is_allow_like(final_status)):
        violations.append("coverage_promotion_alignment: required coverage gaps cannot coexist with promotable authority")
        reasons.append("TRUST_SPINE_COVERAGE_PROMOTION_CONTRADICTION")

    if isinstance(gate_proof_evidence, dict):
        required_true = (
            "severity_linkage_complete",
            "deterministic_transition_consumption",
            "policy_caused_action_observed",
            "recurrence_prevention_linked",
            "failure_binding_required_for_progression",
            "missing_binding_blocks_progression",
            "advisory_only_learning_rejected",
            "transition_policy_consumes_binding_deterministically",
        )
        for field in required_true:
            if gate_proof_evidence.get(field) is not True:
                violations.append(f"gate_proof_truthfulness: {field} must be true")
                reasons.append("TRUST_SPINE_GATE_PROOF_MISMATCH")

        refs_by_group = {
            "severity_linkage_refs": gate_proof_evidence.get("severity_linkage_refs"),
            "transition_consumption_refs": gate_proof_evidence.get("transition_consumption_refs"),
            "policy_action_refs": gate_proof_evidence.get("policy_action_refs"),
            "recurrence_prevention_refs": gate_proof_evidence.get("recurrence_prevention_refs"),
        }
        for key, refs in refs_by_group.items():
            if not isinstance(refs, list) or not refs:
                violations.append(f"gate_proof_truthfulness: {key} must include at least one evidence ref")
                reasons.append("TRUST_SPINE_GATE_PROOF_MISMATCH")

    if isinstance(done_certification_record, dict):
        done_status = _norm(done_certification_record.get("final_status"))
        done_response = _norm(done_certification_record.get("system_response"))
        if done_status == "passed":
            if _is_blocking(final_status) or _is_blocking(system_response) or _is_blocking(decision):
                violations.append("certification_closure_coherence: done certification passed while upstream authority is blocking")
                reasons.append("TRUST_SPINE_CERTIFICATION_CLOSURE_CONTRADICTION")
            if required_gap:
                violations.append("certification_closure_coherence: done certification passed with required coverage gaps")
                reasons.append("TRUST_SPINE_CERTIFICATION_CLOSURE_CONTRADICTION")
        if done_status == "failed" and (done_response == "allow" or _is_allow_like(final_status)):
            violations.append("certification_closure_coherence: failed done certification cannot coexist with permissive authority")
            reasons.append("TRUST_SPINE_CERTIFICATION_CLOSURE_CONTRADICTION")

    unique_reasons = sorted(set(reasons))
    return TrustSpineInvariantResult(
        passed=not violations,
        categories_checked=list(_DEF_CATEGORIES),
        violations=violations,
        blocking_reasons=unique_reasons,
        evaluated_surfaces=evaluated_surfaces,
    )
