"""SLO Enforcement Layer (Prompt 11B).

Turns ``traceability_integrity_sli`` (TI) from a passive metric into an
**active runtime control**.  Downstream pipeline stages call
:func:`run_slo_enforcement` to obtain a governed
``slo_enforcement_decision`` artifact that specifies whether execution may
proceed (``allow``), should proceed with warnings (``allow_with_warning``),
or must stop (``fail``).

Design principles
-----------------
- Policy-first: enforcement behaviour is driven by named policy profiles, not
  inline branching.
- Crash-proof: malformed or missing inputs produce a governed ``fail``
  decision, never an uncaught exception.
- Deterministic: the same inputs always produce the same decision (aside from
  timestamps and generated IDs).
- Separation of concerns:

  1. Input normalisation   (:func:`normalize_enforcement_inputs`)
  2. Consistency checks    (:func:`detect_lineage_state_inconsistencies`)
  3. Input validation      (:func:`validate_enforcement_inputs`)
  4. Policy evaluation     (:func:`evaluate_traceability_policy`)
  5. Decision construction (:func:`build_slo_enforcement_decision`)
  6. Schema validation     (:func:`validate_slo_enforcement_decision`)
  7. Orchestration         (:func:`run_slo_enforcement`)

Supported policy profiles
-------------------------
permissive
    TI 1.0 → allow  /  TI 0.5 → allow_with_warning  /  TI 0.0 → fail

decision_grade
    TI 1.0 → allow  /  TI 0.5 → fail  /  TI 0.0 → fail

exploratory
    TI 1.0 → allow  /  TI 0.5 → allow_with_warning  /  TI 0.0 → fail

The default policy is ``permissive``.  Per-stage overrides are supported via
:data:`STAGE_DEFAULT_POLICIES`.

Reason codes
------------
strict_valid_lineage          – TI 1.0 in strict mode, all lineage valid
strict_invalid_lineage        – TI 0.0 in strict mode, lineage errors detected
degraded_no_registry          – TI 0.5, no lineage registry supplied
missing_traceability_integrity – TI field absent from input
malformed_traceability_integrity – TI value is not a recognised float
missing_lineage_mode          – lineage_validation_mode absent from input
malformed_lineage_mode        – lineage_validation_mode is not an allowed value
inconsistent_lineage_state    – internally contradictory combination of fields
policy_resolution_failed      – explicit policy/stage resolution failed closed

Exit codes (CLI)
----------------
0 – allow
1 – allow_with_warning
2 – fail
3 – malformed input / schema / execution error
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

# ---------------------------------------------------------------------------
# Schema path
# ---------------------------------------------------------------------------

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "contracts" / "schemas"
_ENFORCEMENT_SCHEMA_PATH = _SCHEMA_DIR / "slo_enforcement_decision.schema.json"

# ---------------------------------------------------------------------------
# Contract / schema version
# ---------------------------------------------------------------------------

CONTRACT_VERSION: str = "1.0.0"

# ---------------------------------------------------------------------------
# Policy profile names, stage identifiers, and stage bindings
# are now owned by the policy registry (BN.2).  They are imported here
# for backward compatibility with existing callers.
# ---------------------------------------------------------------------------

from spectrum_systems.modules.runtime.policy_registry import (  # noqa: E402
    DEFAULT_POLICY,
    KNOWN_POLICIES,
    KNOWN_STAGES,
    POLICY_DECISION_GRADE,
    POLICY_EXPLORATORY,
    POLICY_PERMISSIVE,
    PolicyRegistryError,
    STAGE_DEFAULT_POLICIES,
    STAGE_EXPORT,
    STAGE_INTERPRET,
    STAGE_OBSERVE,
    STAGE_RECOMMEND,
    STAGE_SYNTHESIS,
    get_policy_profile,
    load_slo_policy_registry,
    resolve_effective_slo_policy,
)

# ---------------------------------------------------------------------------
# Decision statuses
# ---------------------------------------------------------------------------

DECISION_ALLOW: str = "allow"
DECISION_ALLOW_WITH_WARNING: str = "allow_with_warning"
DECISION_FAIL: str = "fail"

KNOWN_DECISION_STATUSES: frozenset = frozenset({
    DECISION_ALLOW,
    DECISION_ALLOW_WITH_WARNING,
    DECISION_FAIL,
})

# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

REASON_STRICT_VALID_LINEAGE: str = "strict_valid_lineage"
REASON_STRICT_INVALID_LINEAGE: str = "strict_invalid_lineage"
REASON_DEGRADED_NO_REGISTRY: str = "degraded_no_registry"
REASON_MISSING_TI: str = "missing_traceability_integrity"
REASON_MALFORMED_TI: str = "malformed_traceability_integrity"
REASON_MISSING_LINEAGE_MODE: str = "missing_lineage_mode"
REASON_MALFORMED_LINEAGE_MODE: str = "malformed_lineage_mode"
REASON_INCONSISTENT_LINEAGE_STATE: str = "inconsistent_lineage_state"
REASON_POLICY_RESOLUTION_FAILED: str = "policy_resolution_failed"

KNOWN_REASON_CODES: frozenset = frozenset({
    REASON_STRICT_VALID_LINEAGE,
    REASON_STRICT_INVALID_LINEAGE,
    REASON_DEGRADED_NO_REGISTRY,
    REASON_MISSING_TI,
    REASON_MALFORMED_TI,
    REASON_MISSING_LINEAGE_MODE,
    REASON_MALFORMED_LINEAGE_MODE,
    REASON_INCONSISTENT_LINEAGE_STATE,
    REASON_POLICY_RESOLUTION_FAILED,
})

# ---------------------------------------------------------------------------
# Recommended actions
# ---------------------------------------------------------------------------

ACTION_PROCEED: str = "proceed"
ACTION_PROCEED_WITH_CAUTION: str = "proceed_with_caution"
ACTION_HALT_AND_REVIEW: str = "halt_and_review"
ACTION_HALT_INVALID_LINEAGE: str = "halt_invalid_lineage"
ACTION_HALT_DEGRADED_LINEAGE: str = "halt_degraded_lineage"
ACTION_INVESTIGATE_INCONSISTENCY: str = "investigate_inconsistency"
ACTION_FIX_INPUT: str = "fix_input"

KNOWN_RECOMMENDED_ACTIONS: frozenset = frozenset({
    ACTION_PROCEED,
    ACTION_PROCEED_WITH_CAUTION,
    ACTION_HALT_AND_REVIEW,
    ACTION_HALT_INVALID_LINEAGE,
    ACTION_HALT_DEGRADED_LINEAGE,
    ACTION_INVESTIGATE_INCONSISTENCY,
    ACTION_FIX_INPUT,
})

# ---------------------------------------------------------------------------
# TI value constants (must match slo_control._TI_* values)
# ---------------------------------------------------------------------------

_TI_STRICT_VALID: float = 1.0
_TI_DEGRADED: float = 0.5
_TI_STRICT_INVALID: float = 0.0

_VALID_TI_VALUES: frozenset = frozenset({_TI_STRICT_VALID, _TI_DEGRADED, _TI_STRICT_INVALID})

_VALID_LINEAGE_MODES: frozenset = frozenset({"strict", "degraded"})

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _decision_id() -> str:
    """Generate a unique, short decision identifier."""
    return "ENF-" + uuid.uuid4().hex[:12].upper()


def _load_enforcement_schema() -> Dict[str, Any]:
    """Load the governed slo_enforcement_decision JSON Schema."""
    return json.loads(_ENFORCEMENT_SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Step 1 — Input normalisation
# ---------------------------------------------------------------------------


def normalize_enforcement_inputs(raw: Any) -> Dict[str, Any]:
    """Normalise *raw* into a flat dict of enforcement-relevant fields.

    Accepts either:
    - a full artifact dict (any shape that contains the relevant keys), or
    - a pre-extracted dict of normalised inputs.

    Missing fields are recorded as ``None``.  This function never raises.

    Parameters
    ----------
    raw:
        Raw input — typically an artifact dict loaded from JSON.

    Returns
    -------
    dict with keys:
        artifact_id, artifact_type, traceability_integrity_sli,
        lineage_validation_mode, lineage_defaulted, lineage_valid,
        parent_artifact_ids, _raw_ok (bool)
    """
    if not isinstance(raw, dict):
        return {
            "artifact_id": None,
            "artifact_type": None,
            "traceability_integrity_sli": None,
            "lineage_validation_mode": None,
            "lineage_defaulted": None,
            "lineage_valid": None,
            "parent_artifact_ids": None,
            "_raw_ok": False,
        }

    # TI may be nested inside slos.slis.traceability_integrity or at top level.
    ti_value: Any = raw.get("traceability_integrity_sli")
    if ti_value is None:
        # Also accept the flat key name used in some call sites.
        ti_value = raw.get("traceability_integrity")
    if ti_value is None:
        # Check directly nested slis dict (e.g. slo_evaluation artifact's own slis)
        ti_value = (raw.get("slis") or {}).get("traceability_integrity")
    if ti_value is None:
        # Check nested location: outer dict wrapping slo_evaluation artifact
        slo_eval = raw.get("slo_evaluation") or {}
        ti_value = (slo_eval.get("slis") or {}).get("traceability_integrity")

    return {
        "artifact_id": raw.get("artifact_id"),
        "artifact_type": raw.get("artifact_type"),
        "traceability_integrity_sli": ti_value,
        "lineage_validation_mode": raw.get("lineage_validation_mode"),
        "lineage_defaulted": raw.get("lineage_defaulted"),
        "lineage_valid": raw.get("lineage_valid"),
        "parent_artifact_ids": raw.get("parent_artifact_ids"),
        "_raw_ok": True,
    }


# ---------------------------------------------------------------------------
# Step 2 — Consistency checks
# ---------------------------------------------------------------------------


def detect_lineage_state_inconsistencies(norm: Dict[str, Any]) -> List[str]:
    """Detect internally contradictory combinations of lineage fields.

    Checked contradictions:
    - TI 1.0 with lineage_validation_mode == "degraded"
    - TI 0.5 with lineage_defaulted == False
    - TI 0.0 with lineage_valid == True
    - strict mode with lineage_valid absent (None) when TI is 1.0 or 0.0

    Returns a list of human-readable inconsistency descriptions (empty = ok).
    """
    issues: List[str] = []
    ti: Any = norm.get("traceability_integrity_sli")
    mode: Any = norm.get("lineage_validation_mode")
    defaulted: Any = norm.get("lineage_defaulted")
    valid: Any = norm.get("lineage_valid")

    if not isinstance(ti, float):
        # Can't perform consistency checks without a numeric TI value.
        return issues

    if ti == _TI_STRICT_VALID and mode == "degraded":
        issues.append(
            "TI is 1.0 (strict_valid) but lineage_validation_mode is 'degraded'; "
            "strict-valid lineage requires strict mode"
        )

    if ti == _TI_DEGRADED and defaulted is False:
        issues.append(
            "TI is 0.5 (degraded) but lineage_defaulted is False; "
            "degraded TI implies lineage_defaulted should be True"
        )

    if ti == _TI_STRICT_INVALID and valid is True:
        issues.append(
            "TI is 0.0 (strict_invalid) but lineage_valid is True; "
            "invalid lineage cannot also be valid"
        )

    if mode == "strict" and ti in (_TI_STRICT_VALID, _TI_STRICT_INVALID) and valid is None:
        issues.append(
            "lineage_validation_mode is 'strict' but lineage_valid is absent; "
            "strict mode must record lineage_valid"
        )

    return issues


# ---------------------------------------------------------------------------
# Step 3 — Input validation
# ---------------------------------------------------------------------------


def validate_enforcement_inputs(
    norm: Dict[str, Any],
) -> Tuple[bool, str, List[str]]:
    """Validate normalised inputs for enforcement.

    Returns
    -------
    (valid, reason_code, errors)
        valid       – True when inputs are sufficient for policy evaluation
        reason_code – one of the REASON_* constants describing the initial
                      classification (may be updated after policy evaluation)
        errors      – list of human-readable validation error strings
    """
    errors: List[str] = []

    if not norm.get("_raw_ok", True):
        errors.append("Input was not a dict; cannot perform enforcement.")
        return False, REASON_MALFORMED_TI, errors

    # --- traceability_integrity_sli ---
    ti: Any = norm.get("traceability_integrity_sli")
    if ti is None:
        errors.append("traceability_integrity_sli is missing from input artifact.")
        return False, REASON_MISSING_TI, errors

    try:
        ti_float = float(ti)
    except (TypeError, ValueError):
        errors.append(
            f"traceability_integrity_sli is not a valid number: {ti!r}"
        )
        return False, REASON_MALFORMED_TI, errors

    if ti_float not in _VALID_TI_VALUES:
        errors.append(
            f"traceability_integrity_sli value {ti_float!r} is not a governed TI band "
            f"(expected one of {sorted(_VALID_TI_VALUES)})"
        )
        return False, REASON_MALFORMED_TI, errors

    # --- lineage_validation_mode ---
    mode: Any = norm.get("lineage_validation_mode")
    if mode is None:
        errors.append("lineage_validation_mode is missing from input artifact.")
        return False, REASON_MISSING_LINEAGE_MODE, errors

    if mode not in _VALID_LINEAGE_MODES:
        errors.append(
            f"lineage_validation_mode value {mode!r} is not a governed value "
            f"(expected one of {sorted(_VALID_LINEAGE_MODES)})"
        )
        return False, REASON_MALFORMED_LINEAGE_MODE, errors

    # Derive initial reason code from TI value + mode
    if ti_float == _TI_STRICT_VALID:
        reason = REASON_STRICT_VALID_LINEAGE
    elif ti_float == _TI_STRICT_INVALID:
        reason = REASON_STRICT_INVALID_LINEAGE
    else:
        reason = REASON_DEGRADED_NO_REGISTRY

    return True, reason, errors


# ---------------------------------------------------------------------------
# Step 4 — Policy resolution
# ---------------------------------------------------------------------------


def resolve_enforcement_policy(
    requested_policy: Optional[str],
    stage: Optional[str],
) -> str:
    """Resolve the effective enforcement policy.

    Delegates to the governed policy registry (BN.2) for authoritative
    fail-closed resolution.

    Parameters
    ----------
    requested_policy:
        Explicit policy name requested by the caller, or ``None``.
    stage:
        Pipeline stage identifier, or ``None``.

    Returns
    -------
    One of the POLICY_* constants.

    Raises
    ------
    PolicyRegistryError
        If policy resolution fails (unknown policy/stage or missing
        policy+stage inputs).
    """
    effective_policy, _ = resolve_effective_slo_policy(requested_policy, stage)
    return effective_policy


# ---------------------------------------------------------------------------
# Step 5 — Policy evaluation
# ---------------------------------------------------------------------------


def evaluate_traceability_policy(
    ti_value: float,
    policy: str,
) -> str:
    """Evaluate *ti_value* against *policy* and return a decision status.

    Delegates to the governed policy registry (BN.2) for the TI-band
    decision mapping defined in each policy profile.

    Parameters
    ----------
    ti_value:
        The governed TI band value (1.0, 0.5, or 0.0).
    policy:
        One of the POLICY_* constants.

    Returns
    -------
    One of ``DECISION_ALLOW``, ``DECISION_ALLOW_WITH_WARNING``,
    ``DECISION_FAIL``.
    """
    from spectrum_systems.modules.runtime.policy_registry import (  # noqa: PLC0415
        UnknownPolicyError,
    )
    try:
        profile = get_policy_profile(policy)
        if ti_value == _TI_STRICT_VALID:
            return profile["ti_1_0_decision"]
        if ti_value == _TI_DEGRADED:
            return profile["ti_0_5_decision"]
        if ti_value == _TI_STRICT_INVALID:
            return profile["ti_0_0_decision"]
    except UnknownPolicyError:
        # Unknown policy — fail conservatively (same behaviour as before).
        pass
    except (KeyError, TypeError):
        # Malformed profile data — fail conservatively.
        pass

    # Unrecognised policy or out-of-band TI value — fail conservatively.
    return DECISION_FAIL


# ---------------------------------------------------------------------------
# Step 6 — Reason code derivation
# ---------------------------------------------------------------------------


def derive_decision_reason_code(
    valid_inputs: bool,
    input_reason: str,
    inconsistency_issues: List[str],
    ti_value: Optional[float],
    decision_status: str,
) -> str:
    """Derive the final reason code for the enforcement decision.

    Parameters
    ----------
    valid_inputs:
        True when input validation passed.
    input_reason:
        Reason code from :func:`validate_enforcement_inputs`.
    inconsistency_issues:
        List of inconsistency descriptions from
        :func:`detect_lineage_state_inconsistencies`.
    ti_value:
        Normalised float TI value, or ``None``.
    decision_status:
        The decision status derived from policy evaluation.

    Returns
    -------
    One of the REASON_* constants.
    """
    if not valid_inputs:
        return input_reason

    if inconsistency_issues:
        return REASON_INCONSISTENT_LINEAGE_STATE

    # When valid and consistent, reason code is fully determined by input_reason
    # (which was already derived from TI value + mode in validate_enforcement_inputs).
    return input_reason


# ---------------------------------------------------------------------------
# Step 7 — Recommended action derivation
# ---------------------------------------------------------------------------


def derive_recommended_action(
    decision_status: str,
    reason_code: str,
    valid_inputs: bool,
) -> str:
    """Derive the recommended action string from the decision outcome.

    Parameters
    ----------
    decision_status:
        One of the DECISION_* constants.
    reason_code:
        One of the REASON_* constants.
    valid_inputs:
        True when input validation passed.

    Returns
    -------
    One of the ACTION_* constants.
    """
    if not valid_inputs:
        return ACTION_FIX_INPUT

    if reason_code == REASON_INCONSISTENT_LINEAGE_STATE:
        return ACTION_INVESTIGATE_INCONSISTENCY

    if decision_status == DECISION_ALLOW:
        return ACTION_PROCEED

    if decision_status == DECISION_ALLOW_WITH_WARNING:
        if reason_code == REASON_DEGRADED_NO_REGISTRY:
            return ACTION_PROCEED_WITH_CAUTION
        return ACTION_HALT_DEGRADED_LINEAGE

    # DECISION_FAIL
    if reason_code == REASON_STRICT_INVALID_LINEAGE:
        return ACTION_HALT_INVALID_LINEAGE
    if reason_code == REASON_DEGRADED_NO_REGISTRY:
        return ACTION_HALT_DEGRADED_LINEAGE
    return ACTION_HALT_AND_REVIEW


# ---------------------------------------------------------------------------
# Step 8 — Decision artifact construction
# ---------------------------------------------------------------------------


def build_slo_enforcement_decision(
    *,
    artifact_id: Optional[str],
    policy: str,
    stage: Optional[str],
    decision_status: str,
    reason_code: str,
    ti_value: Optional[float],
    lineage_mode: Optional[str],
    lineage_defaulted: Optional[bool],
    lineage_valid: Optional[Any],
    recommended_action: str,
    warnings: List[str],
    errors: List[str],
    evaluated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct the governed ``slo_enforcement_decision`` artifact.

    All fields are explicitly set; no implicit defaults are allowed.

    Returns
    -------
    A dict ready for schema validation.
    """
    ts = evaluated_at or _now_iso()
    decision_id = _decision_id()

    artifact: Dict[str, Any] = {
        "artifact_id": artifact_id if artifact_id else "(unknown)",
        "enforcement_policy": policy,
        "decision_status": decision_status,
        "decision_reason_code": reason_code,
        "traceability_integrity_sli": ti_value if ti_value is not None else None,
        "lineage_validation_mode": lineage_mode if lineage_mode else "(unknown)",
        "lineage_defaulted": lineage_defaulted if lineage_defaulted is not None else None,
        "recommended_action": recommended_action,
        "warnings": list(warnings),
        "errors": list(errors),
        "evaluated_at": ts,
        "contract_version": CONTRACT_VERSION,
        "decision_id": decision_id,
    }

    # Optional fields included only when present
    if stage is not None:
        artifact["enforcement_scope"] = stage

    # lineage_valid: include always, as null when unknown
    if lineage_valid is not None:
        artifact["lineage_valid"] = bool(lineage_valid)
    else:
        artifact["lineage_valid"] = None

    return artifact


# ---------------------------------------------------------------------------
# Step 9 — Schema validation
# ---------------------------------------------------------------------------


def validate_slo_enforcement_decision(
    decision: Dict[str, Any],
) -> List[str]:
    """Validate *decision* against the governed JSON Schema.

    Returns a list of error strings (empty = valid).
    """
    errors: List[str] = []
    try:
        schema = _load_enforcement_schema()
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        ve = sorted(validator.iter_errors(decision), key=lambda e: e.path)
        for err in ve:
            errors.append(f"slo_enforcement_decision schema error: {err.message}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"schema load/validation error: {exc}")
    return errors


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_slo_enforcement(
    raw_input: Any,
    policy: Optional[str] = None,
    stage: Optional[str] = None,
    evaluated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the full SLO enforcement pipeline.

    This is the primary public entry point.  It is crash-proof: any exception
    during processing is caught and returned as a governed ``fail`` decision.

    Parameters
    ----------
    raw_input:
        Artifact dict (or any value) to evaluate.  Accepts full artifact dicts
        or pre-normalised input dicts.
    policy:
        Explicit policy name (one of the POLICY_* constants), or ``None``.
        If omitted, a valid stage binding must resolve; otherwise resolution
        fails closed.
    stage:
        Optional pipeline stage identifier (e.g. ``"synthesis"``).
    evaluated_at:
        Optional ISO 8601 timestamp override for deterministic tests.

    Returns
    -------
    dict with keys:
        ``enforcement_decision``  – the governed decision artifact
        ``decision_status``       – one of the DECISION_* constants
        ``decision_reason_code``  – one of the REASON_* constants
        ``schema_errors``         – list of schema validation errors
        ``warnings``              – list of warning strings
        ``errors``                – list of error strings
    """
    try:
        return _run_slo_enforcement_inner(
            raw_input=raw_input,
            policy=policy,
            stage=stage,
            evaluated_at=evaluated_at,
        )
    except PolicyRegistryError as exc:
        err_msg = f"Policy resolution error: {exc}"
        decision = build_slo_enforcement_decision(
            artifact_id=None,
            policy=policy or "policy_resolution_failed",
            stage=stage,
            decision_status=DECISION_FAIL,
            reason_code=REASON_POLICY_RESOLUTION_FAILED,
            ti_value=None,
            lineage_mode=None,
            lineage_defaulted=None,
            lineage_valid=None,
            recommended_action=ACTION_FIX_INPUT,
            warnings=[],
            errors=[err_msg],
            evaluated_at=evaluated_at,
        )
        return {
            "enforcement_decision": decision,
            "decision_status": DECISION_FAIL,
            "decision_reason_code": REASON_POLICY_RESOLUTION_FAILED,
            "schema_errors": [],
            "warnings": [],
            "errors": [err_msg],
        }
    except Exception as exc:  # noqa: BLE001
        # Last-resort crash protection: if the inner pipeline itself fails,
        # return a governed fail decision.
        err_msg = f"Internal enforcement error: {exc}"
        fallback_policy = policy
        if fallback_policy is None:
            fallback_policy = "policy_resolution_failed"
        decision = build_slo_enforcement_decision(
            artifact_id=None,
            policy=fallback_policy,
            stage=stage,
            decision_status=DECISION_FAIL,
            reason_code=REASON_MALFORMED_TI,
            ti_value=None,
            lineage_mode=None,
            lineage_defaulted=None,
            lineage_valid=None,
            recommended_action=ACTION_FIX_INPUT,
            warnings=[],
            errors=[err_msg],
            evaluated_at=evaluated_at,
        )
        return {
            "enforcement_decision": decision,
            "decision_status": DECISION_FAIL,
            "decision_reason_code": REASON_MALFORMED_TI,
            "schema_errors": [],
            "warnings": [],
            "errors": [err_msg],
        }


def _run_slo_enforcement_inner(
    raw_input: Any,
    policy: Optional[str],
    stage: Optional[str],
    evaluated_at: Optional[str],
) -> Dict[str, Any]:
    """Inner pipeline — called by :func:`run_slo_enforcement`."""
    warnings: List[str] = []
    errors: List[str] = []

    # 1. Normalise inputs
    norm = normalize_enforcement_inputs(raw_input)

    # 2. Detect consistency issues (before validation so we can still flag them)
    inconsistency_issues = detect_lineage_state_inconsistencies(norm)
    if inconsistency_issues:
        warnings.extend(inconsistency_issues)

    # 3. Validate inputs
    valid_inputs, input_reason, validation_errors = validate_enforcement_inputs(norm)
    if validation_errors:
        errors.extend(validation_errors)

    # 4. Resolve effective policy
    effective_policy = resolve_enforcement_policy(policy, stage)

    # 5. Evaluate policy (or fail if inputs are invalid)
    ti_value: Optional[float] = norm.get("traceability_integrity_sli")
    if isinstance(ti_value, (int, float)):
        ti_value = float(ti_value)
    else:
        ti_value = None

    if not valid_inputs or inconsistency_issues:
        # Inconsistency or invalid inputs → fail regardless of policy
        decision_status = DECISION_FAIL
    elif ti_value is None:
        # Should not happen when valid_inputs is True, but guard defensively.
        decision_status = DECISION_FAIL
        errors.append("Internal: ti_value is None despite valid_inputs=True")
    else:
        decision_status = evaluate_traceability_policy(ti_value, effective_policy)

    # 6. Derive reason code
    reason_code = derive_decision_reason_code(
        valid_inputs=valid_inputs,
        input_reason=input_reason,
        inconsistency_issues=inconsistency_issues,
        ti_value=ti_value,
        decision_status=decision_status,
    )

    # 7. Derive recommended action
    recommended_action = derive_recommended_action(
        decision_status=decision_status,
        reason_code=reason_code,
        valid_inputs=valid_inputs,
    )

    # 8. Build artifact
    decision = build_slo_enforcement_decision(
        artifact_id=norm.get("artifact_id"),
        policy=effective_policy,
        stage=stage,
        decision_status=decision_status,
        reason_code=reason_code,
        ti_value=ti_value,
        lineage_mode=norm.get("lineage_validation_mode"),
        lineage_defaulted=norm.get("lineage_defaulted"),
        lineage_valid=norm.get("lineage_valid"),
        recommended_action=recommended_action,
        warnings=warnings,
        errors=errors,
        evaluated_at=evaluated_at,
    )

    # 9. Schema validation
    schema_errors = validate_slo_enforcement_decision(decision)

    return {
        "enforcement_decision": decision,
        "decision_status": decision_status,
        "decision_reason_code": reason_code,
        "schema_errors": schema_errors,
        "warnings": warnings,
        "errors": errors,
    }
