"""Validator Execution Engine (BN.8).

Centralises validator registration, name resolution, canonical ordering,
structured execution, and result aggregation.  This module is the single
authoritative source of validator logic for the spectrum-systems control
plane.

No downstream module may maintain its own validator resolution logic.

Design principles
-----------------
- Fail closed:  unknown, missing, malformed, or excepting validators produce
  ``blocked`` status, never a silent pass.
- Deterministic ordering:  validators always run in the canonical order
  defined here, regardless of the order the caller requests them.
- Governed metadata:  every validator entry carries a structured registry
  record so operators and automation can inspect capabilities without
  executing.
- Structured results:  every execution emits a schema-validated
  ``ValidatorExecutionResult`` dict.

Canonical validator order (BN.8)
---------------------------------
1. validate_runtime_compatibility
2. validate_bundle_contract
3. validate_schema_conformance
4. validate_traceability_integrity
5. validate_artifact_completeness
6. validate_cross_artifact_consistency

Public API
----------
get_validator_registry()            – canonical registry dict
list_registered_validators()        – deterministic ordered name list
resolve_validator(name)             – (callable, metadata) or raises
run_validators(names, context)      – canonical execution entry point
validate_validator_result(result)   – structural integrity check
summarize_validator_execution(res)  – operator-readable summary string
"""

from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.trace_engine import (
    SPAN_STATUS_BLOCKED,
    SPAN_STATUS_ERROR,
    SPAN_STATUS_OK,
    SpanNotFoundError,
    TraceNotFoundError,
    attach_artifact,
    end_span,
    record_event,
    start_span,
    start_trace,
    validate_trace_context,
)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ValidatorCallable = Callable[[str, Any, Dict[str, Any]], Dict[str, Any]]

ValidatorRegistryEntry = Dict[str, Any]
# Required keys per entry:
#   validator_name   : str
#   callable_ref     : ValidatorCallable
#   description      : str
#   stage_applicability : List[str]   ("*" = all stages)
#   blocking_by_default : bool
#   output_schema    : Optional[str]

ValidatorResult = Dict[str, Any]
# Required keys per result (governed by validator_execution_result schema):
#   validator_name, status, blocking, reason_codes, warnings, errors, details

ValidatorExecutionResult = Dict[str, Any]
# Governed by contracts/schemas/validator_execution_result.schema.json

# ---------------------------------------------------------------------------
# Canonical validator order
# ---------------------------------------------------------------------------

CANONICAL_VALIDATOR_ORDER: List[str] = [
    "validate_runtime_compatibility",
    "validate_bundle_contract",
    "validate_schema_conformance",
    "validate_traceability_integrity",
    "validate_artifact_completeness",
    "validate_cross_artifact_consistency",
]

SCHEMA_VERSION: str = "1.0.0"

# ---------------------------------------------------------------------------
# Built-in validator callables
# ---------------------------------------------------------------------------


def _stub_not_implemented(name: str, _artifact: Any, _context: Dict[str, Any]) -> ValidatorResult:
    """Governed stub for validators that are registered but not yet fully
    implemented.  Returns a *blocked* (not silently-passing) result."""
    return {
        "validator_name": name,
        "status": "blocked",
        "blocking": True,
        "reason_codes": ["not_implemented"],
        "warnings": [],
        "errors": [f"Validator '{name}' is registered but not yet implemented; failing closed."],
        "details": {"mode": "stub"},
    }


def _validate_runtime_compatibility(name: str, _artifact: Any, context: Dict[str, Any]) -> ValidatorResult:
    """Check that required runtime environment fields are present."""
    env = context.get("runtime_environment")
    if not env:
        return {
            "validator_name": name,
            "status": "fail",
            "blocking": True,
            "reason_codes": ["runtime_environment_missing"],
            "warnings": [],
            "errors": ["runtime_environment not present in context"],
            "details": {"runtime_environment": None},
        }
    return {
        "validator_name": name,
        "status": "pass",
        "blocking": True,
        "reason_codes": [],
        "warnings": [],
        "errors": [],
        "details": {"runtime_environment": str(env)},
    }


def _validate_bundle_contract(name: str, artifact: Any, _context: Dict[str, Any]) -> ValidatorResult:
    """Check that the artifact conforms to a minimal bundle contract."""
    if not isinstance(artifact, dict):
        return {
            "validator_name": name,
            "status": "fail",
            "blocking": True,
            "reason_codes": ["artifact_not_object"],
            "warnings": [],
            "errors": ["artifact must be a dict to satisfy bundle contract"],
            "details": {"artifact_type": type(artifact).__name__},
        }
    return {
        "validator_name": name,
        "status": "pass",
        "blocking": True,
        "reason_codes": [],
        "warnings": [],
        "errors": [],
        "details": {"artifact_is_object": True},
    }


def _validate_schema_conformance(name: str, artifact: Any, _context: Dict[str, Any]) -> ValidatorResult:
    """Check that the artifact is a structured object (schema-conformant shape)."""
    is_dict = isinstance(artifact, dict)
    if not is_dict:
        return {
            "validator_name": name,
            "status": "fail",
            "blocking": True,
            "reason_codes": ["artifact_not_object"],
            "warnings": [],
            "errors": ["artifact must be an object for schema conformance"],
            "details": {"artifact_is_object": False},
        }
    return {
        "validator_name": name,
        "status": "pass",
        "blocking": True,
        "reason_codes": [],
        "warnings": [],
        "errors": [],
        "details": {"artifact_is_object": True},
    }


def _validate_traceability_integrity(name: str, artifact: Any, _context: Dict[str, Any]) -> ValidatorResult:
    """Check that the artifact carries a non-empty artifact_id for traceability."""
    ok = isinstance(artifact, dict) and bool(artifact.get("artifact_id"))
    if not ok:
        return {
            "validator_name": name,
            "status": "fail",
            "blocking": True,
            "reason_codes": ["artifact_id_missing"],
            "warnings": [],
            "errors": ["artifact_id missing; traceability integrity cannot be confirmed"],
            "details": {"artifact_id_present": False},
        }
    return {
        "validator_name": name,
        "status": "pass",
        "blocking": True,
        "reason_codes": [],
        "warnings": [],
        "errors": [],
        "details": {"artifact_id_present": True},
    }


def _validate_artifact_completeness(name: str, artifact: Any, _context: Dict[str, Any]) -> ValidatorResult:
    """Check that the artifact has a non-empty payload field."""
    complete = isinstance(artifact, dict) and bool(artifact.get("payload") is not None)
    if not complete:
        return {
            "validator_name": name,
            "status": "fail",
            "blocking": True,
            "reason_codes": ["artifact_payload_missing"],
            "warnings": [],
            "errors": ["artifact payload field is missing or None"],
            "details": {"payload_present": False},
        }
    return {
        "validator_name": name,
        "status": "pass",
        "blocking": True,
        "reason_codes": [],
        "warnings": [],
        "errors": [],
        "details": {"payload_present": True},
    }


def _validate_cross_artifact_consistency(name: str, artifact: Any, context: Dict[str, Any]) -> ValidatorResult:
    """Check cross-artifact consistency using parent_artifact_ids from context."""
    parent_ids = context.get("parent_artifact_ids") or []
    artifact_id = (artifact or {}).get("artifact_id") if isinstance(artifact, dict) else None
    if artifact_id and parent_ids and artifact_id in parent_ids:
        return {
            "validator_name": name,
            "status": "fail",
            "blocking": True,
            "reason_codes": ["artifact_self_reference"],
            "warnings": [],
            "errors": [f"artifact_id '{artifact_id}' appears in its own parent_artifact_ids"],
            "details": {"artifact_id": artifact_id, "parent_artifact_ids": parent_ids},
        }
    return {
        "validator_name": name,
        "status": "pass",
        "blocking": True,
        "reason_codes": [],
        "warnings": [],
        "errors": [],
        "details": {"cross_artifact_consistency": "ok"},
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, ValidatorRegistryEntry] = {
    "validate_runtime_compatibility": {
        "validator_name": "validate_runtime_compatibility",
        "callable_ref": _validate_runtime_compatibility,
        "description": "Verifies that the runtime execution environment is present and accessible.",
        "stage_applicability": ["*"],
        "blocking_by_default": True,
        "output_schema": "validator_execution_result",
    },
    "validate_bundle_contract": {
        "validator_name": "validate_bundle_contract",
        "callable_ref": _validate_bundle_contract,
        "description": "Verifies that the artifact satisfies the minimal bundle contract (dict shape).",
        "stage_applicability": ["*"],
        "blocking_by_default": True,
        "output_schema": "validator_execution_result",
    },
    "validate_schema_conformance": {
        "validator_name": "validate_schema_conformance",
        "callable_ref": _validate_schema_conformance,
        "description": "Verifies that the artifact is a structured object conforming to schema expectations.",
        "stage_applicability": ["*"],
        "blocking_by_default": True,
        "output_schema": "validator_execution_result",
    },
    "validate_traceability_integrity": {
        "validator_name": "validate_traceability_integrity",
        "callable_ref": _validate_traceability_integrity,
        "description": "Verifies that the artifact carries a non-empty artifact_id enabling traceability.",
        "stage_applicability": ["*"],
        "blocking_by_default": True,
        "output_schema": "validator_execution_result",
    },
    "validate_artifact_completeness": {
        "validator_name": "validate_artifact_completeness",
        "callable_ref": _validate_artifact_completeness,
        "description": "Verifies that the artifact payload field is present and non-null.",
        "stage_applicability": ["*"],
        "blocking_by_default": True,
        "output_schema": "validator_execution_result",
    },
    "validate_cross_artifact_consistency": {
        "validator_name": "validate_cross_artifact_consistency",
        "callable_ref": _validate_cross_artifact_consistency,
        "description": "Verifies cross-artifact consistency (e.g. no self-reference in parent lineage).",
        "stage_applicability": ["*"],
        "blocking_by_default": True,
        "output_schema": "validator_execution_result",
    },
}


# ---------------------------------------------------------------------------
# Schema loader
# ---------------------------------------------------------------------------

def _load_validator_execution_result_schema() -> Dict[str, Any]:
    return load_schema("validator_execution_result")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_validator_registry() -> Dict[str, ValidatorRegistryEntry]:
    """Return the canonical validator registry (read-only copy)."""
    return dict(_REGISTRY)


def list_registered_validators() -> List[str]:
    """Return a deterministic ordered list of registered validator names.

    Names appear in canonical execution order first, then any additional
    registered validators in sorted order.
    """
    canonical = [n for n in CANONICAL_VALIDATOR_ORDER if n in _REGISTRY]
    extras = sorted(n for n in _REGISTRY if n not in CANONICAL_VALIDATOR_ORDER)
    return canonical + extras


def resolve_validator(name: str) -> Tuple[ValidatorCallable, ValidatorRegistryEntry]:
    """Resolve a validator name to its (callable, metadata) entry.

    Raises
    ------
    KeyError
        If *name* is not registered.  Callers must treat unknown validators
        as blocked (fail-closed).
    """
    entry = _REGISTRY.get(name)
    if entry is None:
        raise KeyError(f"Unknown validator '{name}'; not registered in canonical registry.")
    return entry["callable_ref"], entry


def validate_validator_result(result: Any, *, validator_name: str = "<unknown>") -> List[str]:
    """Return a list of structural error strings for *result*.

    An empty list means the result is well-formed.
    """
    errors: List[str] = []
    if not isinstance(result, dict):
        return [f"Validator '{validator_name}' returned non-dict result: {type(result).__name__}"]
    for required_key in ("validator_name", "status", "blocking", "reason_codes", "warnings", "errors", "details"):
        if required_key not in result:
            errors.append(f"Validator '{validator_name}' result missing required key: '{required_key}'")
    status = result.get("status")
    if status not in ("pass", "fail", "blocked", "error"):
        errors.append(f"Validator '{validator_name}' result has invalid status: '{status}'")
    return errors


def _make_blocked_result(name: str, reason_codes: List[str], errors: List[str], blocking: bool = True) -> ValidatorResult:
    return {
        "validator_name": name,
        "status": "blocked",
        "blocking": blocking,
        "reason_codes": reason_codes,
        "warnings": [],
        "errors": errors,
        "details": {},
    }


def run_validators(
    required_validators: List[str],
    context: Optional[Dict[str, Any]] = None,
) -> ValidatorExecutionResult:
    """Canonical entry point for validator execution (BN.8).

    Executes *required_validators* in deterministic canonical order.
    Caller-provided order is ignored; canonical order always applies.

    Parameters
    ----------
    required_validators:
        Validator names requested by the caller.
    context:
        Execution context dict.  Recognised keys: ``artifact``,
        ``stage``, ``runtime_environment``, ``parent_artifact_ids``,
        ``trace_id``, ``parent_span_id``.

    Returns
    -------
    ValidatorExecutionResult
        Schema-validated structured result dict.
    """
    context = dict(context or {})
    artifact = context.get("artifact")

    # BK–BM: resolve trace context; auto-start trace if absent (backward-compat)
    trace_id: Optional[str] = context.get("trace_id")
    parent_span_id: Optional[str] = context.get("parent_span_id")
    _trace_auto_started = False
    if not trace_id:
        trace_id = start_trace({"source": "validator_engine", "auto_started": True})
        _trace_auto_started = True

    # Validate trace context — fail closed on malformed trace
    _trace_errors = validate_trace_context(trace_id)
    if _trace_errors:
        # Malformed trace: return a blocked result immediately
        blocked_result: ValidatorExecutionResult = {
            "execution_id": str(uuid.uuid4()),
            "validators_requested": list(required_validators or []),
            "validators_run": [],
            "validators_passed": [],
            "validators_failed": ["<trace_engine>"],
            "validator_results": [
                _make_blocked_result(
                    "<trace_engine>",
                    reason_codes=["malformed_trace_context"],
                    errors=_trace_errors,
                )
            ],
            "overall_status": "blocked",
            "failure_reason_codes": ["malformed_trace_context"],
            "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
            "schema_version": SCHEMA_VERSION,
            "trace_id": trace_id,
            "parent_span_id": parent_span_id,
        }
        return blocked_result

    # Create a span for the validator execution batch
    try:
        ve_span_id = start_span(trace_id, "validator_execution", parent_span_id)
    except (TraceNotFoundError, SpanNotFoundError):
        ve_span_id = None

    validators_requested = list(required_validators or [])

    # Normalise to canonical order: canonical-order first, then unknowns.
    canonical_requested = [n for n in CANONICAL_VALIDATOR_ORDER if n in validators_requested]
    extra_requested = [n for n in validators_requested if n not in CANONICAL_VALIDATOR_ORDER]
    ordered_validators = canonical_requested + sorted(extra_requested)

    validators_run: List[str] = []
    validators_passed: List[str] = []
    validators_failed: List[str] = []
    validator_results: List[ValidatorResult] = []
    all_reason_codes: List[str] = []

    for name in ordered_validators:
        # BK–BM: create per-validator span
        v_span_id: Optional[str] = None
        try:
            if ve_span_id is not None:
                v_span_id = start_span(trace_id, f"validator:{name}", ve_span_id)
        except (TraceNotFoundError, SpanNotFoundError):
            v_span_id = None

        # --- Resolve ---
        try:
            fn, entry = resolve_validator(name)
        except KeyError:
            vr = _make_blocked_result(
                name,
                reason_codes=["unknown_validator"],
                errors=[f"Validator '{name}' is not registered; failing closed."],
            )
            validators_failed.append(name)
            all_reason_codes.append("unknown_validator")
            validator_results.append(vr)
            if v_span_id:
                try:
                    record_event(v_span_id, "validator_result", {"status": "blocked", "reason": "unknown_validator"})
                    end_span(v_span_id, SPAN_STATUS_BLOCKED)
                except (TraceNotFoundError, SpanNotFoundError):
                    pass
            continue

        # --- Execute ---
        try:
            raw_result = fn(name, artifact, context)
        except Exception as exc:
            vr = _make_blocked_result(
                name,
                reason_codes=["validator_exception"],
                errors=[f"Validator '{name}' raised an exception: {exc}", traceback.format_exc()],
                blocking=entry.get("blocking_by_default", True),
            )
            validators_failed.append(name)
            all_reason_codes.append("validator_exception")
            validator_results.append(vr)
            if v_span_id:
                try:
                    record_event(v_span_id, "validator_result", {"status": "blocked", "reason": "validator_exception"})
                    end_span(v_span_id, SPAN_STATUS_BLOCKED)
                except (TraceNotFoundError, SpanNotFoundError):
                    pass
            continue

        # --- Validate result structure ---
        struct_errors = validate_validator_result(raw_result, validator_name=name)
        if struct_errors:
            vr = _make_blocked_result(
                name,
                reason_codes=["malformed_validator_result"],
                errors=struct_errors,
                blocking=entry.get("blocking_by_default", True),
            )
            validators_failed.append(name)
            all_reason_codes.append("malformed_validator_result")
            validator_results.append(vr)
            if v_span_id:
                try:
                    record_event(v_span_id, "validator_result", {"status": "blocked", "reason": "malformed_validator_result"})
                    end_span(v_span_id, SPAN_STATUS_BLOCKED)
                except (TraceNotFoundError, SpanNotFoundError):
                    pass
            continue

        validators_run.append(name)
        vr = raw_result
        if vr["status"] == "pass":
            validators_passed.append(name)
        else:
            validators_failed.append(name)
            all_reason_codes.extend(vr.get("reason_codes") or [])

        validator_results.append(vr)

        # BK–BM: record validator result event and close span
        if v_span_id:
            try:
                v_status = vr.get("status", "blocked")
                record_event(v_span_id, "validator_result", {
                    "validator_name": name,
                    "status": v_status,
                    "reason_codes": vr.get("reason_codes") or [],
                })
                span_status = SPAN_STATUS_OK if v_status == "pass" else SPAN_STATUS_BLOCKED
                end_span(v_span_id, span_status)
            except (TraceNotFoundError, SpanNotFoundError):
                pass

    # --- Compute overall status ---
    if any(
        vr["status"] in ("blocked", "error")
        for vr in validator_results
    ):
        overall_status = "blocked"
    elif validators_failed:
        overall_status = "fail"
    else:
        overall_status = "pass"

    result: ValidatorExecutionResult = {
        "execution_id": str(uuid.uuid4()),
        "validators_requested": validators_requested,
        "validators_run": validators_run,
        "validators_passed": validators_passed,
        "validators_failed": validators_failed,
        "validator_results": validator_results,
        "overall_status": overall_status,
        "failure_reason_codes": list(dict.fromkeys(all_reason_codes)),
        "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
    }

    # --- Validate against governed schema ---
    try:
        schema = _load_validator_execution_result_schema()
        schema_validator = Draft202012Validator(schema)
        schema_errors = [
            f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in sorted(schema_validator.iter_errors(result), key=lambda e: list(e.absolute_path))
        ]
    except Exception as exc:
        schema_errors = [f"Schema validation unavailable: {exc}"]

    if schema_errors:
        result["overall_status"] = "blocked"
        result["failure_reason_codes"] = list(dict.fromkeys(result["failure_reason_codes"] + ["schema_validation_failed"]))
        result["validator_results"].append(
            _make_blocked_result(
                "<validator_engine>",
                reason_codes=["schema_validation_failed"],
                errors=schema_errors,
            )
        )

    # BK–BM: close the validator execution batch span and attach the artifact
    if ve_span_id:
        try:
            ve_span_status = SPAN_STATUS_OK if overall_status == "pass" else SPAN_STATUS_BLOCKED
            record_event(ve_span_id, "validator_execution_complete", {
                "overall_status": result["overall_status"],
                "validators_run": validators_run,
                "validators_failed": validators_failed,
            })
            end_span(ve_span_id, ve_span_status)
            attach_artifact(trace_id, result["execution_id"], "validator_execution_result", ve_span_id)
        except (TraceNotFoundError, SpanNotFoundError):
            pass

    return result


def summarize_validator_execution(execution_result: ValidatorExecutionResult) -> str:
    """Return a deterministic operator-readable summary of a validator execution result."""
    lines = [
        "Validator Execution Result (BN.8)",
        "----------------------------------",
        f"  overall_status         : {execution_result.get('overall_status')}",
        f"  validators_requested   : {execution_result.get('validators_requested')}",
        f"  validators_run         : {execution_result.get('validators_run')}",
        f"  validators_passed      : {execution_result.get('validators_passed')}",
        f"  validators_failed      : {execution_result.get('validators_failed')}",
        f"  failure_reason_codes   : {execution_result.get('failure_reason_codes')}",
        f"  evaluated_at           : {execution_result.get('evaluated_at')}",
    ]
    # First blocking validator
    first_blocked = next(
        (vr["validator_name"] for vr in (execution_result.get("validator_results") or []) if vr.get("blocking") and vr.get("status") != "pass"),
        None,
    )
    lines.append(f"  first_blocking_failure : {first_blocked}")
    return "\n".join(lines)
