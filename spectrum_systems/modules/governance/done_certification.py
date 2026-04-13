"""Deterministic fail-closed Done Certification Gate (DONE-01)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.provenance_verification import (
    ProvenanceVerificationError,
    assert_linked_identity_consistency,
    validate_required_identity,
)
from spectrum_systems.modules.runtime.trust_spine_invariants import (
    validate_trust_spine_evidence_completeness,
    validate_trust_spine_invariants,
)
from spectrum_systems.modules.governance.tpa_scope_policy import (
    TPAScopePolicyError,
    is_tpa_required,
    load_tpa_scope_policy,
)


class DoneCertificationError(ValueError):
    """Raised when done certification cannot be deterministically computed."""


_REQUIRED_REFS = (
    "replay_result_ref",
    "regression_result_ref",
    "certification_pack_ref",
    "error_budget_ref",
    "policy_ref",
)


def _load_json(path_value: str, *, label: str) -> Dict[str, Any]:
    path = Path(path_value)
    if not path.is_file():
        raise DoneCertificationError(f"{label} file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DoneCertificationError(f"{label} is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DoneCertificationError(f"{label} must be a JSON object: {path}")
    return payload


def _validate_schema(instance: Dict[str, Any], schema_name: str, *, label: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise DoneCertificationError(f"{label} failed schema validation ({schema_name}): {details}")


def _stable_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()




def _resolve_run_id(*, replay: Dict[str, Any], regression: Dict[str, Any], certification_pack: Dict[str, Any]) -> str:
    for candidate in (
        certification_pack.get("run_id"),
        replay.get("run_id"),
        regression.get("run_id"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    raise DoneCertificationError("run_id cannot be derived from certification/replay/regression inputs")

def _deterministic_timestamp(*, replay: Dict[str, Any], regression: Dict[str, Any], certification: Dict[str, Any]) -> str:
    for candidate in (
        certification.get("generated_at"),
        replay.get("timestamp"),
        regression.get("created_at"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    raise DoneCertificationError("deterministic timestamp cannot be derived from input artifacts")


def _require_refs(input_refs: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(input_refs, dict):
        raise DoneCertificationError("input_refs must be an object")
    refs: Dict[str, str] = {}
    for key in _REQUIRED_REFS:
        value = input_refs.get(key)
        if not isinstance(value, str) or not value.strip():
            raise DoneCertificationError(f"missing required input ref: {key}")
        refs[key] = value
    optional_value = input_refs.get("failure_injection_ref")
    if optional_value is not None:
        if not isinstance(optional_value, str) or not optional_value.strip():
            raise DoneCertificationError("failure_injection_ref must be a non-empty string when provided")
        refs["failure_injection_ref"] = optional_value
    for optional_key in (
        "enforcement_result_ref",
        "tpa_certification_envelope_ref",
        "tax_decision_ref",
        "bax_decision_ref",
        "cax_arbitration_ref",
        "cde_decision_ref",
        "eval_coverage_summary_ref",
        "repo_review_snapshot_ref",
        "repo_health_eval_summary_ref",
        "tpa_plan_artifact",
        "tpa_build_artifact",
        "tpa_simplify_artifact",
        "tpa_gate_artifact",
        "tpa_scope_policy_path",
        "scope_file_path",
        "scope_module",
        "scope_artifact_type",
    ):
        optional = input_refs.get(optional_key)
        if optional is None:
            continue
        if not isinstance(optional, str) or not optional.strip():
            raise DoneCertificationError(f"{optional_key} must be a non-empty string when provided")
        refs[optional_key] = optional
    cohesion_ref = input_refs.get("trust_spine_evidence_cohesion_result_ref")
    if cohesion_ref is not None:
        if not isinstance(cohesion_ref, str) or not cohesion_ref.strip():
            raise DoneCertificationError("trust_spine_evidence_cohesion_result_ref must be a non-empty string when provided")
        refs["trust_spine_evidence_cohesion_result_ref"] = cohesion_ref
    return refs


def _identity_policy(input_refs: Dict[str, Any]) -> Dict[str, bool]:
    policy = input_refs.get("identity_policy")
    if policy is None:
        return {"allow_cross_run_reference": False}
    if not isinstance(policy, dict):
        raise DoneCertificationError("identity_policy must be an object when provided")
    allow_cross_run = bool(policy.get("allow_cross_run_reference", False))
    return {"allow_cross_run_reference": allow_cross_run}


def _is_governed_strict_certification_mode(*, input_refs: Dict[str, Any], authority_path_mode: str) -> bool:
    explicit_profile = str(input_refs.get("execution_profile") or "").strip().lower()
    if explicit_profile in {"governed_spine", "authoritative_spine"}:
        return True
    return authority_path_mode in {"active_runtime", "governed_spine"}


def _certification_policy(input_refs: Dict[str, Any], *, authority_path_mode: str) -> Dict[str, bool]:
    strict_mode = _is_governed_strict_certification_mode(input_refs=input_refs, authority_path_mode=authority_path_mode)
    default_allow_warn_as_pass = not strict_mode
    default_require_system_readiness = strict_mode
    policy = input_refs.get("certification_policy")
    if policy is None:
        return {
            "allow_warn_as_pass": default_allow_warn_as_pass,
            "allow_warn_promotion": False,
            "require_system_readiness": default_require_system_readiness,
        }
    if not isinstance(policy, dict):
        raise DoneCertificationError("certification_policy must be an object when provided")
    return {
        "allow_warn_as_pass": bool(policy.get("allow_warn_as_pass", default_allow_warn_as_pass)),
        "allow_warn_promotion": bool(policy.get("allow_warn_promotion", False)),
        "require_system_readiness": bool(policy.get("require_system_readiness", default_require_system_readiness)),
    }


def _normalize_trace(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    return value.strip()


def _extend_trace_candidates(candidates: List[str], values: List[str]) -> None:
    for value in values:
        normalized = _normalize_trace(value)
        if normalized:
            candidates.append(normalized)


def _validate_trace_linkage(
    *,
    replay: Dict[str, Any],
    regression: Dict[str, Any],
    error_budget: Dict[str, Any],
    control_decision: Dict[str, Any],
    certification_pack: Dict[str, Any],
    failure_injection: Optional[Dict[str, Any]],
) -> tuple[bool, List[str], str]:
    details: List[str] = []

    replay_trace = _normalize_trace(replay.get("trace_id"))
    if not replay_trace:
        details.append("TRACE_LINKAGE_MISSING: replay_result.trace_id is required")

    reference_trace = replay_trace
    def _require_exact(label: str, value: Any) -> None:
        normalized = _normalize_trace(value)
        if not normalized:
            details.append(f"TRACE_LINKAGE_MISSING: {label} is required")
            return
        if reference_trace and normalized != reference_trace:
            details.append(
                f"TRACE_LINKAGE_MISMATCH: {label}={normalized!r} does not match replay_result.trace_id={reference_trace!r}"
            )

    _require_exact("error_budget_status.trace_refs.trace_id", (error_budget.get("trace_refs") or {}).get("trace_id"))
    _require_exact("evaluation_control_decision.trace_id", control_decision.get("trace_id"))

    regression_trace_ids: List[str] = []
    for idx, result in enumerate(regression.get("results") or []):
        trace_id = _normalize_trace(result.get("trace_id"))
        if not trace_id:
            details.append(f"TRACE_LINKAGE_MISSING: regression_result.results[{idx}].trace_id is required")
            continue
        regression_trace_ids.append(trace_id)
        if reference_trace and trace_id != reference_trace:
            details.append(
                "TRACE_LINKAGE_MISMATCH: "
                f"regression_result.results[{idx}].trace_id={trace_id!r} "
                f"does not match replay_result.trace_id={reference_trace!r}"
            )
    certification_trace_ids: List[str] = []
    _extend_trace_candidates(
        certification_trace_ids,
        list((certification_pack.get("provenance_trace_refs") or {}).get("trace_refs") or []),
    )
    if not certification_trace_ids:
        details.append("TRACE_LINKAGE_MISSING: control_loop_certification_pack provenance trace_refs are required")
    if len(set(certification_trace_ids)) > 1:
        details.append("TRACE_LINKAGE_AMBIGUOUS: control_loop_certification_pack has multiple trace_refs values")
    for trace_id in certification_trace_ids:
        if reference_trace and trace_id != reference_trace:
            details.append(
                "TRACE_LINKAGE_MISMATCH: "
                f"control_loop_certification_pack.provenance_trace_refs.trace_refs contains {trace_id!r} "
                f"which does not match replay_result.trace_id={reference_trace!r}"
            )

    if failure_injection is not None:
        fi_summary_primary = _normalize_trace((failure_injection.get("trace_refs") or {}).get("primary"))
        if not fi_summary_primary:
            details.append("TRACE_LINKAGE_MISSING: governed_failure_injection_summary.trace_refs.primary is required")
        elif reference_trace and fi_summary_primary != reference_trace:
            details.append(
                "TRACE_LINKAGE_MISMATCH: "
                f"governed_failure_injection_summary.trace_refs.primary={fi_summary_primary!r} "
                f"does not match replay_result.trace_id={reference_trace!r}"
            )

        for idx, result in enumerate(failure_injection.get("results") or []):
            primary = _normalize_trace((result.get("trace_refs") or {}).get("primary"))
            if not primary:
                details.append(
                    f"TRACE_LINKAGE_MISSING: governed_failure_injection_summary.results[{idx}].trace_refs.primary is required"
                )
            elif reference_trace and primary != reference_trace:
                details.append(
                    "TRACE_LINKAGE_MISMATCH: "
                    f"governed_failure_injection_summary.results[{idx}].trace_refs.primary={primary!r} "
                    f"does not match replay_result.trace_id={reference_trace!r}"
                )

    passed = len(details) == 0
    resolved_trace = reference_trace
    if not resolved_trace and passed:
        raise DoneCertificationError("TRACE_LINKAGE_MISSING: replay_result.trace_id is required")
    return passed, details, resolved_trace


def _load_tpa_artifact(path_value: str, *, expected_phase: str) -> Dict[str, Any]:
    artifact = _load_json(path_value, label=f"tpa_{expected_phase}_artifact")
    _validate_schema(artifact, "tpa_slice_artifact", label=f"tpa_{expected_phase}_artifact")
    if artifact.get("phase") != expected_phase:
        raise DoneCertificationError(
            f"tpa_{expected_phase}_artifact phase mismatch: expected {expected_phase!r} got {artifact.get('phase')!r}"
        )
    return artifact


def _load_tpa_certification_envelope(path_value: str) -> Dict[str, Any]:
    envelope = _load_json(path_value, label="tpa_certification_envelope")
    _validate_schema(envelope, "tpa_certification_envelope", label="tpa_certification_envelope")
    return envelope


def _evaluate_tpa_compliance(*, refs: Dict[str, str], input_refs: Dict[str, Any]) -> tuple[bool, str, List[str], List[str]]:
    scope_context = {
        "file_path": refs.get("scope_file_path", ""),
        "module": refs.get("scope_module", ""),
        "artifact_type": refs.get("scope_artifact_type", ""),
        "pqx_step_metadata": input_refs.get("pqx_step_metadata") if isinstance(input_refs.get("pqx_step_metadata"), dict) else {},
    }

    policy_path = refs.get("tpa_scope_policy_path")
    try:
        policy = load_tpa_scope_policy(policy_path)
        required = is_tpa_required(scope_context, policy=policy)
    except TPAScopePolicyError as exc:
        raise DoneCertificationError(f"TPA scope policy evaluation failed: {exc}") from exc

    if not required:
        optional_refs = [
            refs[key]
            for key in ("tpa_certification_envelope_ref", "tpa_plan_artifact", "tpa_build_artifact", "tpa_simplify_artifact", "tpa_gate_artifact")
            if key in refs
        ]
        return False, "NOT_REQUIRED", [], optional_refs

    details: List[str] = []
    envelope_ref = refs.get("tpa_certification_envelope_ref")
    if not envelope_ref:
        details.append("missing required TPA certification envelope ref: tpa_certification_envelope_ref")
        return True, "FAIL", details, []

    envelope = _load_tpa_certification_envelope(envelope_ref)
    evidence_refs = dict(envelope.get("evidence_refs") or {})
    tpa_artifact_refs = [
        str(evidence_refs.get("tpa_plan_artifact_ref") or ""),
        str(evidence_refs.get("tpa_build_artifact_ref") or ""),
        str(evidence_refs.get("tpa_simplify_artifact_ref") or ""),
        str(evidence_refs.get("tpa_gate_artifact_ref") or ""),
    ]
    if any(not ref for ref in tpa_artifact_refs):
        details.append("TPA certification envelope missing required artifact refs")

    if str(envelope.get("certification_decision") or "") != "certified":
        details.append("TPA certification envelope decision must be certified")
    gate_decision = dict(envelope.get("gate_decision") or {})
    if not bool(gate_decision.get("promotion_ready")):
        details.append("TPA certification envelope gate_decision.promotion_ready must be true")
    if str(gate_decision.get("complexity_regression_decision") or "") in {"freeze", "block"}:
        details.append("TPA certification envelope complexity decision blocks promotion")
    if str(gate_decision.get("simplicity_decision") or "") in {"freeze", "block"}:
        details.append("TPA certification envelope simplicity decision blocks promotion")

    if str(envelope.get("execution_mode") or "") == "cleanup_only":
        cleanup = envelope.get("cleanup_only_validation")
        if not isinstance(cleanup, dict):
            details.append("TPA cleanup-only envelope missing cleanup_only_validation")
        else:
            if not bool(cleanup.get("mode_enabled")):
                details.append("TPA cleanup-only envelope requires mode_enabled=true")
            if not bool(cleanup.get("equivalence_proven")):
                details.append("TPA cleanup-only envelope requires equivalence_proven=true")
            if not str(cleanup.get("replay_ref") or "").strip():
                details.append("TPA cleanup-only envelope requires replay_ref")

    return True, ("PASS" if not details else "FAIL"), details, [envelope_ref, *[ref for ref in tpa_artifact_refs if ref]]


def run_done_certification(input_refs: dict) -> dict:
    """Run deterministic fail-closed done certification and return governed artifact."""
    refs = _require_refs(input_refs)
    authority_path_mode = str(input_refs.get("authority_path_mode") or "").strip()
    if not authority_path_mode:
        authority_path_mode = (
            "active_runtime"
            if "enforcement_result_ref" in refs and "eval_coverage_summary_ref" in refs
            else "reduced_depth_non_authority"
        )
    identity_policy = _identity_policy(input_refs)
    certification_policy = _certification_policy(input_refs, authority_path_mode=authority_path_mode)

    replay = _load_json(refs["replay_result_ref"], label="replay_result")
    regression = _load_json(refs["regression_result_ref"], label="regression_result")
    certification_pack = _load_json(refs["certification_pack_ref"], label="control_loop_certification_pack")
    error_budget = _load_json(refs["error_budget_ref"], label="error_budget_status")
    control_decision = _load_json(refs["policy_ref"], label="evaluation_control_decision")
    repo_review_snapshot: Dict[str, Any] | None = None
    repo_health_eval_summary: Dict[str, Any] | None = None
    if "repo_review_snapshot_ref" in refs:
        repo_review_snapshot = _load_json(refs["repo_review_snapshot_ref"], label="repo_review_snapshot")
    if "repo_health_eval_summary_ref" in refs:
        repo_health_eval_summary = _load_json(refs["repo_health_eval_summary_ref"], label="repo_health_eval_summary")
    enforcement_result: Dict[str, Any] | None = None
    eval_coverage_summary: Dict[str, Any] | None = None
    if "enforcement_result_ref" in refs:
        enforcement_result = _load_json(refs["enforcement_result_ref"], label="enforcement_result")
    if "eval_coverage_summary_ref" in refs:
        eval_coverage_summary = _load_json(refs["eval_coverage_summary_ref"], label="eval_coverage_summary")
    trust_spine_cohesion_result: Dict[str, Any] | None = None
    if "trust_spine_evidence_cohesion_result_ref" in refs:
        trust_spine_cohesion_result = _load_json(
            refs["trust_spine_evidence_cohesion_result_ref"], label="trust_spine_evidence_cohesion_result"
        )

    failure_injection: Optional[Dict[str, Any]] = None
    if "failure_injection_ref" in refs:
        failure_injection = _load_json(refs["failure_injection_ref"], label="governed_failure_injection_summary")

    _validate_schema(replay, "replay_result", label="replay_result")
    _validate_schema(regression, "regression_run_result", label="regression_result")
    _validate_schema(certification_pack, "control_loop_certification_pack", label="control_loop_certification_pack")
    _validate_schema(error_budget, "error_budget_status", label="error_budget_status")
    _validate_schema(control_decision, "evaluation_control_decision", label="evaluation_control_decision")
    if repo_review_snapshot is not None:
        _validate_schema(repo_review_snapshot, "repo_review_snapshot", label="repo_review_snapshot")
    if repo_health_eval_summary is not None:
        _validate_schema(repo_health_eval_summary, "eval_summary", label="repo_health_eval_summary")
    if enforcement_result is not None:
        _validate_schema(enforcement_result, "enforcement_result", label="enforcement_result")
    if eval_coverage_summary is not None:
        _validate_schema(eval_coverage_summary, "eval_coverage_summary", label="eval_coverage_summary")
    if trust_spine_cohesion_result is not None:
        _validate_schema(
            trust_spine_cohesion_result,
            "trust_spine_evidence_cohesion_result",
            label="trust_spine_evidence_cohesion_result",
        )
    if failure_injection is not None:
        _validate_schema(failure_injection, "governed_failure_injection_summary", label="governed_failure_injection_summary")

    replay_trace_id = replay.get("trace_id")
    replay_run_id = replay.get("replay_run_id") or replay.get("original_run_id")
    try:
        validate_required_identity(
            {"run_id": replay_run_id, "trace_id": replay_trace_id},
            label="replay_result",
        )
        assert_linked_identity_consistency(
            {"run_id": replay_run_id, "trace_id": replay_trace_id},
            {"run_id": regression.get("run_id"), "trace_id": replay_trace_id},
            upstream_label="replay_result",
            linked_label="regression_result",
            require_same_run=True,
            allow_cross_run_reference=identity_policy["allow_cross_run_reference"],
            allow_trace_override=False,
        )
        assert_linked_identity_consistency(
            {"run_id": replay_run_id, "trace_id": replay_trace_id},
            {"run_id": certification_pack.get("run_id"), "trace_id": replay_trace_id},
            upstream_label="replay_result",
            linked_label="control_loop_certification_pack",
            require_same_run=True,
            allow_cross_run_reference=identity_policy["allow_cross_run_reference"],
            allow_trace_override=False,
        )
        assert_linked_identity_consistency(
            {"run_id": replay_run_id, "trace_id": replay_trace_id},
            {"run_id": control_decision.get("run_id"), "trace_id": control_decision.get("trace_id")},
            upstream_label="replay_result",
            linked_label="evaluation_control_decision",
            require_same_run=True,
            allow_cross_run_reference=identity_policy["allow_cross_run_reference"],
            allow_trace_override=False,
        )
    except ProvenanceVerificationError as exc:
        raise DoneCertificationError(str(exc)) from exc

    blocking_reasons: List[str] = []
    readiness_warnings: List[str] = []

    replay_pass = True
    replay_details: List[str] = []
    if replay.get("consistency_status") != "match":
        replay_pass = False
        replay_details.append("replay consistency_status must be 'match'")
    if bool(replay.get("drift_detected")):
        replay_pass = False
        replay_details.append("replay drift_detected must be false")
    failure_reason = replay.get("failure_reason")
    if failure_reason not in (None, ""):
        replay_pass = False
        replay_details.append("replay failure_reason must be null/empty")
    if not replay_pass:
        blocking_reasons.extend(replay_details)

    regression_pass = True
    regression_details: List[str] = []
    if bool(regression.get("blocked")):
        regression_pass = False
        regression_details.append("regression blocked must be false")
    if regression.get("overall_status") != "pass" or regression.get("regression_status") != "pass":
        regression_pass = False
        regression_details.append("regression overall_status/regression_status must be pass")
    if int(regression.get("failed_traces", 0)) != 0:
        regression_pass = False
        regression_details.append("regression failed_traces must be 0")
    for result in regression.get("results", []):
        if not bool(result.get("passed")):
            regression_pass = False
            regression_details.append(f"trace {result.get('trace_id', '<unknown>')} did not pass regression")
        if result.get("mismatch_summary"):
            regression_pass = False
            regression_details.append(f"trace {result.get('trace_id', '<unknown>')} has mismatch_summary violations")
        digest = str(result.get("comparison_digest") or "")
        if len(digest) != 64:
            regression_pass = False
            regression_details.append(f"trace {result.get('trace_id', '<unknown>')} has invalid comparison_digest")
    if not regression_pass:
        blocking_reasons.extend(regression_details)

    contracts_pass = True
    contracts_details: List[str] = []
    if certification_pack.get("certification_status") != "certified" or certification_pack.get("decision") != "pass":
        contracts_pass = False
        contracts_details.append("control_loop_certification_pack must be certified/pass")
    if not contracts_pass:
        blocking_reasons.extend(contracts_details)

    reliability_pass = True
    reliability_details: List[str] = []
    if error_budget.get("budget_status") in {"exhausted", "invalid"}:
        reliability_pass = False
        reliability_details.append("error budget status is exhausted/invalid")
    if control_decision.get("system_status") in {"exhausted", "blocked", "fail"}:
        reliability_pass = False
        reliability_details.append("evaluation control system_status indicates exhausted/fail")
    if not reliability_pass:
        blocking_reasons.extend(reliability_details)

    fail_closed_pass = True
    fail_closed_details: List[str] = []
    if failure_injection is not None:
        if int(failure_injection.get("fail_count", 0)) != 0:
            fail_closed_pass = False
            fail_closed_details.append("failure injection fail_count must be 0")
        for result in failure_injection.get("results", []):
            if not bool(result.get("passed")):
                fail_closed_pass = False
                fail_closed_details.append(f"failure injection case failed: {result.get('injection_case_id', '<unknown>')}")
            observed = str(result.get("observed_outcome") or "").lower()
            expected = str(result.get("expected_outcome") or "").lower()
            if "allow" in observed and "allow" not in expected:
                fail_closed_pass = False
                fail_closed_details.append(
                    f"unexpected allow path in failure injection case: {result.get('injection_case_id', '<unknown>')}"
                )
            if result.get("invariant_violations"):
                fail_closed_pass = False
                fail_closed_details.append(
                    f"invariant violations present in failure injection case: {result.get('injection_case_id', '<unknown>')}"
                )
    if not fail_closed_pass:
        blocking_reasons.extend(fail_closed_details)

    control_consistency_pass = True
    control_consistency_details: List[str] = []
    response = str(control_decision.get("system_response") or "")
    decision_label = str(control_decision.get("decision") or "")
    expected_decision = {
        "allow": "allow",
        "warn": "require_review",
        "freeze": "deny",
        "block": "deny",
    }.get(response)
    if expected_decision is None:
        control_consistency_pass = False
        control_consistency_details.append(f"unknown system_response for control consistency: {response!r}")
    elif decision_label != expected_decision:
        control_consistency_pass = False
        control_consistency_details.append(
            f"control decision mismatch: system_response={response!r} requires decision={expected_decision!r}"
        )
    if not control_consistency_pass:
        blocking_reasons.extend(control_consistency_details)

    completeness_result = validate_trust_spine_evidence_completeness(
        refs={
            "replay_result_ref": refs.get("replay_result_ref"),
            "policy_ref": refs.get("policy_ref"),
            "enforcement_result_ref": refs.get("enforcement_result_ref"),
            "eval_coverage_summary_ref": refs.get("eval_coverage_summary_ref"),
            "certification_pack_ref": refs.get("certification_pack_ref"),
            "gate_proof_ref": "embedded" if isinstance(certification_pack.get("gate_proof_evidence"), dict) else "",
            "closure_bundle_ref": refs.get("certification_pack_ref"),
        },
        target_surface="certification",
        authority_path_mode=authority_path_mode,
    )
    if not completeness_result.passed:
        blocking_reasons.extend(completeness_result.blocking_reasons)
        if completeness_result.missing_refs:
            blocking_reasons.append("missing trust-spine refs: " + ",".join(completeness_result.missing_refs))

    if enforcement_result is not None and eval_coverage_summary is not None:
        trust_spine_result = validate_trust_spine_invariants(
            replay_result=replay,
            evaluation_control_decision=control_decision,
            enforcement_result=enforcement_result,
            eval_coverage_summary=eval_coverage_summary,
            gate_proof_evidence=certification_pack.get("gate_proof_evidence"),
            done_certification_record=None,
            target_surface="certification",
        )
        if not trust_spine_result.passed:
            downgraded: List[str] = []
            for violation in trust_spine_result.violations:
                if (
                    isinstance(violation, str)
                    and violation == "policy_authority_consistency: blocking control decision cannot map to permissive enforcement"
                    and str(control_decision.get("system_response") or "").strip().lower() == "warn"
                ):
                    downgraded.append(f"warning:{violation}")
                    continue
                blocking_reasons.append(violation)
            if downgraded:
                readiness_warnings.extend(downgraded)
    else:
        trust_spine_result = validate_trust_spine_invariants(
            replay_result=replay,
            evaluation_control_decision=control_decision,
            enforcement_result={"artifact_type": "enforcement_result", "final_status": "allow"},
            eval_coverage_summary={"artifact_type": "eval_coverage_summary", "coverage_gaps": []},
            gate_proof_evidence=certification_pack.get("gate_proof_evidence"),
            done_certification_record=None,
            target_surface="certification",
        )

    trace_linkage_pass, trace_linkage_details, resolved_trace_id = _validate_trace_linkage(
        replay=replay,
        regression=regression,
        error_budget=error_budget,
        control_decision=control_decision,
        certification_pack=certification_pack,
        failure_injection=failure_injection,
    )
    if not trace_linkage_pass:
        blocking_reasons.extend(trace_linkage_details)

    cohesion_details: List[str] = []
    cohesion_pass = True
    if authority_path_mode == "active_runtime":
        if trust_spine_cohesion_result is None:
            cohesion_pass = False
            cohesion_details.append("trust_spine_evidence_cohesion_result_ref is required on active_runtime path")
        elif trust_spine_cohesion_result.get("overall_decision") != "ALLOW":
            cohesion_pass = False
            cohesion_details.extend(
                [f"cohesion:{reason}" for reason in trust_spine_cohesion_result.get("blocking_reasons", []) if isinstance(reason, str)]
            )
    elif trust_spine_cohesion_result is not None and trust_spine_cohesion_result.get("overall_decision") == "BLOCK":
        cohesion_pass = False
        cohesion_details.extend(
            [f"cohesion:{reason}" for reason in trust_spine_cohesion_result.get("blocking_reasons", []) if isinstance(reason, str)]
        )
    if not cohesion_pass and not cohesion_details:
        cohesion_details.append("trust-spine evidence cohesion is blocking")
    if not cohesion_pass:
        blocking_reasons.extend(cohesion_details)

    tpa_required, tpa_status, tpa_details, tpa_artifact_refs = _evaluate_tpa_compliance(refs=refs, input_refs=input_refs)
    tpa_compliance_pass = tpa_status == "PASS"
    if tpa_required and not tpa_compliance_pass:
        blocking_reasons.extend(tpa_details or ["TPA compliance failed for required scope"])

    authority_lineage_details: List[str] = []
    authority_lineage_pass = True
    lineage_refs_present = all(
        required_ref in refs for required_ref in ("tax_decision_ref", "bax_decision_ref", "cax_arbitration_ref", "cde_decision_ref")
    )
    strict_authority_lineage = bool(input_refs.get("require_authority_lineage", False)) or lineage_refs_present
    if authority_path_mode == "active_runtime" and strict_authority_lineage:
        required_lineage_refs = ("tax_decision_ref", "bax_decision_ref", "cax_arbitration_ref", "cde_decision_ref")
        for required_ref in required_lineage_refs:
            if required_ref not in refs:
                authority_lineage_pass = False
                authority_lineage_details.append(f"missing required authority lineage ref: {required_ref}")
        if authority_lineage_pass:
            tax_decision = _load_json(refs["tax_decision_ref"], label="termination_decision")
            bax_decision = _load_json(refs["bax_decision_ref"], label="budget_control_decision")
            cax_record = _load_json(refs["cax_arbitration_ref"], label="control_arbitration_record")
            cde_decision = _load_json(refs["cde_decision_ref"], label="closure_decision_artifact")
            _validate_schema(tax_decision, "termination_decision", label="termination_decision")
            _validate_schema(bax_decision, "budget_control_decision", label="budget_control_decision")
            _validate_schema(cax_record, "control_arbitration_record", label="control_arbitration_record")
            _validate_schema(cde_decision, "closure_decision_artifact", label="closure_decision_artifact")
            if str(tax_decision.get("decision") or "") != "complete":
                authority_lineage_pass = False
                authority_lineage_details.append("TAX decision must be complete for promotion readiness")
            if str(bax_decision.get("decision") or "") not in {"allow", "warn"}:
                authority_lineage_pass = False
                authority_lineage_details.append("BAX decision must be allow or warn for promotion readiness")
            if str(cax_record.get("outcome") or "") not in {"complete", "warn_complete_candidate"}:
                authority_lineage_pass = False
                authority_lineage_details.append("CAX outcome must be complete or warn_complete_candidate")
            if str(cde_decision.get("decision_type") or "") != "lock":
                authority_lineage_pass = False
                authority_lineage_details.append("CDE decision_type must remain lock for promotion readiness")
    elif authority_path_mode == "active_runtime":
        authority_lineage_details.append("authority lineage strict mode not requested; compatibility path active")
    if not authority_lineage_pass:
        blocking_reasons.extend(authority_lineage_details)

    readiness_details: List[str] = []
    readiness_pass = True
    readiness_response = "allow"
    control_response = str(control_decision.get("system_response") or "").strip().lower()
    if control_response not in {"allow", "warn", "freeze", "block"}:
        readiness_pass = False
        readiness_response = "block"
        readiness_details.append("control decision system_response must be one of allow|warn|freeze|block")
    require_system_readiness = certification_policy["require_system_readiness"]
    if repo_review_snapshot is None and require_system_readiness:
        readiness_pass = False
        readiness_response = "block"
        readiness_details.append("repo_review_snapshot_ref is required for system readiness certification")
        findings_summary: Dict[str, Any] = {}
    elif repo_review_snapshot is None:
        findings_summary = {}
    else:
        findings_summary = repo_review_snapshot.get("findings_summary") or {}
    drift_findings = int(findings_summary.get("drift_findings", 0))
    redundancy_findings = int(findings_summary.get("redundancy_findings", 0))
    eval_coverage_gaps = int(findings_summary.get("eval_coverage_gaps", 0))
    control_bypass_findings = int(findings_summary.get("control_bypass_findings", 0))
    if repo_health_eval_summary is None and require_system_readiness:
        readiness_pass = False
        readiness_response = "block"
        readiness_details.append("repo_health_eval_summary_ref is required for system readiness certification")
        eval_system_status = ""
    elif repo_health_eval_summary is None:
        eval_system_status = ""
    else:
        eval_system_status = str(repo_health_eval_summary.get("system_status") or "").strip().lower()

    if control_response == "block":
        readiness_pass = False
        readiness_response = "block"
        readiness_details.append("control decision is block")
    if control_bypass_findings > 0:
        readiness_pass = False
        readiness_response = "block"
        readiness_details.append("control bypass findings exceed block threshold")
    if eval_system_status == "failing":
        readiness_pass = False
        readiness_response = "block"
        readiness_details.append("repo health eval indicates failing status")
    if eval_coverage_gaps > 0:
        readiness_pass = False
        readiness_response = "block"
        readiness_details.append("eval coverage gaps exceed block threshold")

    if readiness_pass:
        if control_response == "freeze" or drift_findings >= 2 or redundancy_findings >= 2:
            readiness_response = "freeze"
            readiness_details.append("system-level drift/redundancy risk requires freeze")
        elif control_response == "warn" or drift_findings == 1 or redundancy_findings == 1 or eval_system_status == "degraded":
            readiness_response = "warn"
            readiness_warnings.append("minor degradation detected but acceptable under policy")
        else:
            readiness_response = "allow"

    if readiness_response == "warn" and control_response == "warn" and not certification_policy["allow_warn_as_pass"]:
        readiness_pass = False
        readiness_response = "block"
        readiness_details.append("control decision warn requires certification_policy.allow_warn_as_pass=true")

    if not readiness_pass:
        blocking_reasons.extend(readiness_details)

    if blocking_reasons:
        final_status = "FAILED"
        system_response = "block"
    elif readiness_response == "freeze":
        final_status = "FROZEN"
        system_response = "freeze"
        if not blocking_reasons:
            blocking_reasons.extend(readiness_details or ["system-level risk freeze"])
    elif readiness_response == "warn":
        final_status = "WARNED"
        system_response = "warn"
    else:
        final_status = "PASSED"
        system_response = "allow"

    deterministic_context = {
        "input_refs": refs,
        "replay_id": replay.get("replay_id"),
        "regression_run_id": regression.get("run_id"),
        "certification_id": certification_pack.get("certification_id"),
        "error_budget_id": error_budget.get("artifact_id"),
        "control_decision_id": control_decision.get("decision_id"),
        "tpa_required": tpa_required,
        "tpa_status": tpa_status,
        "tpa_artifact_refs": tpa_artifact_refs,
        "final_status": final_status,
        "blocking_reasons": blocking_reasons,
    }
    certification_id = _stable_hash(deterministic_context)

    trace_id = resolved_trace_id
    if not trace_id:
        raise DoneCertificationError("trace_id cannot be derived from replay/error_budget/control_decision inputs")

    run_id = _resolve_run_id(
        replay=replay,
        regression=regression,
        certification_pack=certification_pack,
    )

    artifact = {
        "certification_id": certification_id,
        "run_id": run_id,
        "timestamp": _deterministic_timestamp(
            replay=replay,
            regression=regression,
            certification=certification_pack,
        ),
        "input_refs": refs,
        "check_results": {
            "replay": {"passed": replay_pass, "details": replay_details},
            "regression": {"passed": regression_pass, "details": regression_details},
            "contracts": {"passed": contracts_pass, "details": contracts_details},
            "reliability": {"passed": reliability_pass, "details": reliability_details},
            "fail_closed": {"passed": fail_closed_pass, "details": fail_closed_details},
            "control_consistency": {
                "passed": control_consistency_pass,
                "details": control_consistency_details,
            },
            "trace_linkage": {
                "passed": trace_linkage_pass,
                "details": trace_linkage_details,
            },
            "trust_spine_invariants": {
                "passed": trust_spine_result.passed,
                "details": trust_spine_result.violations,
            },
            "trust_spine_evidence_completeness": {
                "passed": completeness_result.passed,
                "details": [
                    *completeness_result.blocking_reasons,
                    *[f"missing_ref:{ref}" for ref in completeness_result.missing_refs],
                ],
            },
            "trust_spine_evidence_cohesion": {
                "passed": cohesion_pass,
                "details": cohesion_details,
            },
            "tpa_compliance": {
                "passed": (tpa_compliance_pass if tpa_required else True),
                "details": tpa_details,
            },
            "authority_lineage": {
                "passed": authority_lineage_pass,
                "details": authority_lineage_details,
            },
            "system_readiness": {
                "passed": readiness_pass and readiness_response in {"allow", "warn"},
                "details": readiness_details,
            },
        },
        "trust_spine_invariant_result": {
            "passed": trust_spine_result.passed,
            "categories_checked": trust_spine_result.categories_checked,
            "blocking_reasons": trust_spine_result.blocking_reasons,
            "evaluated_surfaces": trust_spine_result.evaluated_surfaces,
        },
        "trust_spine_evidence_completeness_result": {
            "passed": completeness_result.passed,
            "categories_checked": completeness_result.categories_checked,
            "blocking_reasons": completeness_result.blocking_reasons,
            "missing_refs": completeness_result.missing_refs,
            "evaluated_surfaces": completeness_result.evaluated_surfaces,
            "authority_path_mode": completeness_result.authority_path_mode,
            "promotable": completeness_result.promotable,
            "certifiable": completeness_result.certifiable,
        },
        "trust_spine_evidence_cohesion_result": {
            "passed": cohesion_pass,
            "overall_decision": (
                trust_spine_cohesion_result.get("overall_decision")
                if isinstance(trust_spine_cohesion_result, dict)
                else ("ALLOW" if cohesion_pass else "BLOCK")
            ),
            "deterministic_cohesion_id": (
                trust_spine_cohesion_result.get("deterministic_cohesion_id")
                if isinstance(trust_spine_cohesion_result, dict)
                else ""
            ),
            "contradiction_categories": (
                trust_spine_cohesion_result.get("contradiction_categories")
                if isinstance(trust_spine_cohesion_result, dict)
                else []
            ),
            "blocking_reasons": (
                trust_spine_cohesion_result.get("blocking_reasons")
                if isinstance(trust_spine_cohesion_result, dict)
                else cohesion_details
            ),
            "evidence_ref": refs.get("trust_spine_evidence_cohesion_result_ref", ""),
        },
        "tpa_required": tpa_required,
        "tpa_status": tpa_status,
        "tpa_artifact_refs": tpa_artifact_refs,
        "final_status": final_status,
        "system_response": system_response,
        "blocking_reasons": blocking_reasons,
        "warnings": readiness_warnings,
        "certification_policy": certification_policy,
        "trace_id": trace_id,
    }

    _validate_schema(artifact, "done_certification_record", label="done_certification_record")
    return artifact
