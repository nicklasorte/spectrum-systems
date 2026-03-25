"""TRUST-01 Context admission gate.

Fail-closed pre-execution admission boundary that consumes a context bundle,
verifies policy/trust/source governance constraints, and emits deterministic
artifactized outcomes.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.context_bundle import (
    ALLOWED_SOURCE_CLASSIFICATIONS,
    ALLOWED_TRUST_LEVELS,
    BUNDLE_SCHEMA_VERSION,
    ContextBundleValidationError,
    validate_context_bundle,
)
from spectrum_systems.modules.runtime.policy_registry import (
    CONTRACT_VERSION as POLICY_CONTRACT_VERSION,
    REGISTRY_VERSION as POLICY_REGISTRY_VERSION,
    PolicyRegistryError,
    get_policy_profile,
    resolve_effective_slo_policy,
)
from spectrum_systems.utils.deterministic_id import deterministic_id

VALIDATION_ARTIFACT_TYPE = "context_validation_result"
VALIDATION_SCHEMA_VERSION = "1.0.0"
ADMISSION_ARTIFACT_TYPE = "context_admission_decision"
ADMISSION_SCHEMA_VERSION = "1.0.0"
ADMISSION_STAGE = "observe"

DECISION_ALLOW = "allow"
DECISION_BLOCK = "block"

_ALLOWED_SCHEMA_VERSIONS: Tuple[str, ...] = (BUNDLE_SCHEMA_VERSION,)
_ALLOWED_SOURCES: Tuple[str, ...] = tuple(ALLOWED_SOURCE_CLASSIFICATIONS)
_ALLOWED_TRUST: Tuple[str, ...] = tuple(ALLOWED_TRUST_LEVELS)

_POLICY_DISALLOWED_TRUST_SOURCE: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "decision_grade": (
        ("external", "low"),
        ("inferred", "low"),
        ("inferred", "untrusted"),
        ("user_provided", "untrusted"),
    ),
    "permissive": (("inferred", "untrusted"),),
    "exploratory": (("inferred", "untrusted"),),
}


class ContextAdmissionError(RuntimeError):
    """Fail-closed context admission boundary error."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _deterministic_timestamp(seed_payload: Dict[str, Any]) -> str:
    """Produce deterministic RFC3339 timestamp for same canonical seed payload."""
    seed = deterministic_id(prefix="ts", namespace="context_admission_timestamp", payload=seed_payload)
    y = 2026
    month = (int(seed[-2:], 16) % 12) + 1
    day = (int(seed[-4:-2], 16) % 28) + 1
    hour = int(seed[-6:-4], 16) % 24
    minute = int(seed[-8:-6], 16) % 60
    second = int(seed[-10:-8], 16) % 60
    return f"{y:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z"


def _validate_contract(payload: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    except ValidationError as exc:
        raise ContextAdmissionError(f"{schema_name} contract validation failed: {exc.message}") from exc


def _validate_bundle_or_error(bundle: Dict[str, Any]) -> Optional[str]:
    try:
        validate_context_bundle(bundle)
        return None
    except ContextBundleValidationError as exc:
        return str(exc)


def _scan_item_constraints(context_items: Sequence[Dict[str, Any]], policy_id: str) -> Tuple[List[str], List[Dict[str, str]]]:
    reasons: List[str] = []
    blocked_pairs: List[Dict[str, str]] = []
    disallowed = set(_POLICY_DISALLOWED_TRUST_SOURCE.get(policy_id, ()))

    for item in context_items:
        source = str(item.get("source_classification") or "")
        trust = str(item.get("trust_level") or "")

        if source not in _ALLOWED_SOURCES:
            reasons.append(f"missing_or_invalid_source_classification:{source or 'missing'}")
        if trust not in _ALLOWED_TRUST:
            reasons.append(f"missing_or_invalid_trust_level:{trust or 'missing'}")

        if (source, trust) in disallowed:
            blocked_pairs.append({"source_classification": source, "trust_level": trust})

    if blocked_pairs:
        reasons.append("disallowed_trust_source_combination")

    return sorted(set(reasons)), sorted(
        blocked_pairs,
        key=lambda entry: (entry["source_classification"], entry["trust_level"]),
    )


def run_context_admission(
    *,
    context_bundle: Optional[Dict[str, Any]],
    requested_policy: Optional[str] = None,
    stage: str = ADMISSION_STAGE,
) -> Dict[str, Dict[str, Any]]:
    """Run fail-closed context admission and emit governed artifacts."""

    validation_reasons: List[str] = []
    policy_id: Optional[str] = None
    policy_source: Optional[str] = None
    policy_profile: Dict[str, Any] = {}
    blocked_pairs: List[Dict[str, str]] = []

    if context_bundle is None:
        validation_reasons.append("missing_context_bundle")
        bundle: Dict[str, Any] = {}
    elif not isinstance(context_bundle, dict):
        validation_reasons.append("context_bundle_not_object")
        bundle = {}
    else:
        bundle = dict(context_bundle)

    bundle_trace = bundle.get("trace") if isinstance(bundle.get("trace"), dict) else {}
    trace_id = str(bundle_trace.get("trace_id") or "")
    run_id = str(bundle_trace.get("run_id") or "")
    context_bundle_id = str(bundle.get("context_bundle_id") or bundle.get("context_id") or "")

    bundle_schema_version = str(bundle.get("schema_version") or "")
    schema_version_accepted = bundle_schema_version in _ALLOWED_SCHEMA_VERSIONS
    if bundle and not schema_version_accepted:
        validation_reasons.append("unsupported_context_bundle_schema_version")

    if bundle:
        bundle_error = _validate_bundle_or_error(bundle)
        if bundle_error:
            validation_reasons.append(f"context_bundle_validation_failed:{bundle_error}")

    if bundle and isinstance(bundle.get("context_items"), list):
        item_reasons, blocked_pairs = _scan_item_constraints(bundle["context_items"], policy_id="permissive")
        validation_reasons.extend(item_reasons)

    try:
        policy_id, policy_source = resolve_effective_slo_policy(requested_policy=requested_policy, stage=stage)
        policy_profile = get_policy_profile(policy_id)
    except PolicyRegistryError as exc:
        validation_reasons.append(f"policy_resolution_failed:{exc}")

    if bundle and isinstance(bundle.get("context_items"), list) and policy_id:
        item_reasons, blocked_pairs = _scan_item_constraints(bundle["context_items"], policy_id=policy_id)
        validation_reasons.extend(item_reasons)

    unique_reasons = sorted(set(validation_reasons))
    validation_passed = len(unique_reasons) == 0

    validation_identity = {
        "context_bundle_id": context_bundle_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "stage": stage,
        "requested_policy": requested_policy,
        "resolved_policy": policy_id,
        "schema_version": bundle_schema_version,
        "reasons": unique_reasons,
        "blocked_pairs": blocked_pairs,
        "policy_registry_version": POLICY_REGISTRY_VERSION,
    }
    created_at = _deterministic_timestamp(validation_identity)
    validation_result = {
        "artifact_type": VALIDATION_ARTIFACT_TYPE,
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_id": deterministic_id(
            prefix="ctxv",
            namespace="context_validation_result",
            payload=validation_identity,
        ),
        "context_bundle_id": context_bundle_id,
        "trace": {
            "trace_id": trace_id,
            "run_id": run_id,
        },
        "admission_stage": stage,
        "policy_resolution": {
            "requested_policy": requested_policy,
            "resolved_policy": policy_id,
            "resolution_source": policy_source,
            "policy_registry_version": POLICY_REGISTRY_VERSION,
            "policy_contract_version": POLICY_CONTRACT_VERSION,
        },
        "checks": {
            "bundle_present": bool(bundle),
            "bundle_schema_version_accepted": schema_version_accepted,
            "bundle_contract_valid": not any(r.startswith("context_bundle_validation_failed") for r in unique_reasons),
            "trust_levels_valid": not any("trust_level" in r for r in unique_reasons),
            "source_classifications_valid": not any("source_classification" in r for r in unique_reasons),
            "policy_resolution_succeeded": policy_id is not None,
            "disallowed_trust_source_combinations": blocked_pairs,
        },
        "validation_status": "pass" if validation_passed else "fail",
        "reason_codes": unique_reasons,
        "created_at": created_at,
    }
    _validate_contract(validation_result, "context_validation_result")

    decision_status = DECISION_ALLOW if validation_passed else DECISION_BLOCK
    decision_identity = {
        "validation_id": validation_result["validation_id"],
        "context_bundle_id": context_bundle_id,
        "decision_status": decision_status,
        "policy_id": policy_id,
        "reason_codes": unique_reasons,
        "checks": validation_result["checks"],
    }
    decision = {
        "artifact_type": ADMISSION_ARTIFACT_TYPE,
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "admission_decision_id": deterministic_id(
            prefix="ctxa",
            namespace="context_admission_decision",
            payload=decision_identity,
        ),
        "context_bundle_id": context_bundle_id,
        "trace": {
            "trace_id": trace_id,
            "run_id": run_id,
        },
        "admission_stage": stage,
        "policy_id": policy_id,
        "policy_registry_version": POLICY_REGISTRY_VERSION,
        "decision_status": decision_status,
        "allow_execution": validation_passed,
        "reason_codes": unique_reasons,
        "blocked_trust_source_pairs": blocked_pairs,
        "validation_ref": validation_result["validation_id"],
        "created_at": _deterministic_timestamp(decision_identity),
    }
    _validate_contract(decision, "context_admission_decision")

    return {
        "context_validation_result": validation_result,
        "context_admission_decision": decision,
        "resolved_policy_profile": policy_profile,
    }


__all__ = [
    "ADMISSION_ARTIFACT_TYPE",
    "ADMISSION_SCHEMA_VERSION",
    "ContextAdmissionError",
    "DECISION_ALLOW",
    "DECISION_BLOCK",
    "VALIDATION_ARTIFACT_TYPE",
    "VALIDATION_SCHEMA_VERSION",
    "run_context_admission",
]
