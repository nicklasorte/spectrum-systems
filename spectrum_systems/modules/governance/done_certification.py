"""Deterministic fail-closed Done Certification Gate (DONE-01)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


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
    return refs


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


def run_done_certification(input_refs: dict) -> dict:
    """Run deterministic fail-closed done certification and return governed artifact."""
    refs = _require_refs(input_refs)

    replay = _load_json(refs["replay_result_ref"], label="replay_result")
    regression = _load_json(refs["regression_result_ref"], label="regression_result")
    certification_pack = _load_json(refs["certification_pack_ref"], label="control_loop_certification_pack")
    error_budget = _load_json(refs["error_budget_ref"], label="error_budget_status")
    control_decision = _load_json(refs["policy_ref"], label="evaluation_control_decision")

    failure_injection: Optional[Dict[str, Any]] = None
    if "failure_injection_ref" in refs:
        failure_injection = _load_json(refs["failure_injection_ref"], label="governed_failure_injection_summary")

    _validate_schema(replay, "replay_result", label="replay_result")
    _validate_schema(regression, "regression_run_result", label="regression_result")
    _validate_schema(certification_pack, "control_loop_certification_pack", label="control_loop_certification_pack")
    _validate_schema(error_budget, "error_budget_status", label="error_budget_status")
    _validate_schema(control_decision, "evaluation_control_decision", label="evaluation_control_decision")
    if failure_injection is not None:
        _validate_schema(failure_injection, "governed_failure_injection_summary", label="governed_failure_injection_summary")

    blocking_reasons: List[str] = []

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

    final_status = "PASSED" if not blocking_reasons else "FAILED"
    system_response = "allow" if final_status == "PASSED" else "block"

    deterministic_context = {
        "input_refs": refs,
        "replay_id": replay.get("replay_id"),
        "regression_run_id": regression.get("run_id"),
        "certification_id": certification_pack.get("certification_id"),
        "error_budget_id": error_budget.get("artifact_id"),
        "control_decision_id": control_decision.get("decision_id"),
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
        },
        "final_status": final_status,
        "system_response": system_response,
        "blocking_reasons": blocking_reasons,
        "trace_id": trace_id,
    }

    _validate_schema(artifact, "done_certification_record", label="done_certification_record")
    return artifact
