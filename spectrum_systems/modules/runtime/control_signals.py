"""Control-Signal Emission Layer (BN.5).

Derives structured, machine-consumable control signals from control-chain
outcomes and embeds them in the canonical control-chain decision artifact.

This module closes the gap between *reactive blocking* (BN.4) and
*actionable closed-loop control*: a blocked or degraded run now says not
just "no" but *what is missing*, *what must be repaired*, *what validators
are required*, and *whether rerun or escalation is appropriate*.

Design principles
-----------------
- Deterministic:  the same inputs always produce the same signal set
  (no random or time-based variation).
- Machine-consumable:  every field is a boolean, enum value, or array of
  controlled-vocabulary strings — no ad-hoc prose.
- Fail closed:  malformed or contradictory inputs produce
  ``continuation_mode = stop_and_escalate`` with ``escalation_required``.
- Additive:  this module extends BN.4 without breaking any existing
  callers.  All new fields are added alongside existing fields.

Public API
----------
derive_control_signals(...)      – main entry point; returns the full dict
summarize_control_signals(...)   – operator-readable summary string
explain_blocking_requirements(...)  – operator-readable explanation
list_required_followups(...)     – deterministic follow-up list
validate_control_signals(...)    – JSON-Schema validation helper

Internal helpers (called from derive_control_signals):
  derive_continuation_mode(...)
  derive_required_validators(...)
  derive_repair_actions(...)
  derive_publication_permissions(...)
  derive_control_signal_reason_codes(...)
  build_control_signals(...)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------

# -- Continuation modes -------------------------------------------------------

CONTINUATION_MODE_CONTINUE: str = "continue"
CONTINUATION_MODE_CONTINUE_WITH_MONITORING: str = "continue_with_monitoring"
CONTINUATION_MODE_STOP: str = "stop"
CONTINUATION_MODE_STOP_AND_REPAIR: str = "stop_and_repair"
CONTINUATION_MODE_STOP_AND_RERUN: str = "stop_and_rerun"
CONTINUATION_MODE_STOP_AND_ESCALATE: str = "stop_and_escalate"

KNOWN_CONTINUATION_MODES: frozenset = frozenset({
    CONTINUATION_MODE_CONTINUE,
    CONTINUATION_MODE_CONTINUE_WITH_MONITORING,
    CONTINUATION_MODE_STOP,
    CONTINUATION_MODE_STOP_AND_REPAIR,
    CONTINUATION_MODE_STOP_AND_RERUN,
    CONTINUATION_MODE_STOP_AND_ESCALATE,
})

# -- Control-signal reason codes ----------------------------------------------

CS_REASON_MISSING_REQUIRED_INPUT: str = "missing_required_input"
CS_REASON_MISSING_TRACEABILITY: str = "missing_traceability"
CS_REASON_DEGRADED_LINEAGE_NOT_ALLOWED: str = "degraded_lineage_not_allowed"
CS_REASON_INVALID_LINEAGE: str = "invalid_lineage"
CS_REASON_MALFORMED_CONTROL_INPUT: str = "malformed_control_input"
CS_REASON_SCHEMA_NONCONFORMANCE: str = "schema_nonconformance"
CS_REASON_GATING_HALT: str = "gating_halt"
CS_REASON_DECISION_STAGE_REQUIRES_STRICT_VALIDATION: str = (
    "decision_stage_requires_strict_validation"
)
CS_REASON_RERUN_POSSIBLE_AFTER_REPAIR: str = "rerun_possible_after_repair"
CS_REASON_ESCALATION_REQUIRED_FOR_DECISION_STAGE: str = (
    "escalation_required_for_decision_stage"
)
CS_REASON_HUMAN_REVIEW_REQUIRED_FOR_WARNING_STATE: str = (
    "human_review_required_for_warning_state"
)

KNOWN_CS_REASON_CODES: frozenset = frozenset({
    CS_REASON_MISSING_REQUIRED_INPUT,
    CS_REASON_MISSING_TRACEABILITY,
    CS_REASON_DEGRADED_LINEAGE_NOT_ALLOWED,
    CS_REASON_INVALID_LINEAGE,
    CS_REASON_MALFORMED_CONTROL_INPUT,
    CS_REASON_SCHEMA_NONCONFORMANCE,
    CS_REASON_GATING_HALT,
    CS_REASON_DECISION_STAGE_REQUIRES_STRICT_VALIDATION,
    CS_REASON_RERUN_POSSIBLE_AFTER_REPAIR,
    CS_REASON_ESCALATION_REQUIRED_FOR_DECISION_STAGE,
    CS_REASON_HUMAN_REVIEW_REQUIRED_FOR_WARNING_STATE,
})

# -- Validator names ----------------------------------------------------------

VALIDATOR_RUNTIME_COMPATIBILITY: str = "validate_runtime_compatibility"
VALIDATOR_BUNDLE_CONTRACT: str = "validate_bundle_contract"
VALIDATOR_TRACEABILITY_INTEGRITY: str = "validate_traceability_integrity"
VALIDATOR_SCHEMA_CONFORMANCE: str = "validate_schema_conformance"
VALIDATOR_ARTIFACT_COMPLETENESS: str = "validate_artifact_completeness"
VALIDATOR_CROSS_ARTIFACT_CONSISTENCY: str = "validate_cross_artifact_consistency"

KNOWN_VALIDATORS: frozenset = frozenset({
    VALIDATOR_RUNTIME_COMPATIBILITY,
    VALIDATOR_BUNDLE_CONTRACT,
    VALIDATOR_TRACEABILITY_INTEGRITY,
    VALIDATOR_SCHEMA_CONFORMANCE,
    VALIDATOR_ARTIFACT_COMPLETENESS,
    VALIDATOR_CROSS_ARTIFACT_CONSISTENCY,
})

# -- Repair action names ------------------------------------------------------

REPAIR_REBUILD_WITH_REGISTRY: str = "rebuild_with_registry"
REPAIR_RESTORE_MISSING_LINEAGE: str = "restore_missing_lineage"
REPAIR_RERUN_WITH_STRICT_VALIDATION: str = "rerun_with_strict_validation"
REPAIR_SCHEMA_ERRORS: str = "repair_schema_errors"
REPAIR_MISSING_INPUTS: str = "repair_missing_inputs"
REPAIR_ESCALATE_FOR_MANUAL_REVIEW: str = "escalate_for_manual_review"

KNOWN_REPAIR_ACTIONS: frozenset = frozenset({
    REPAIR_REBUILD_WITH_REGISTRY,
    REPAIR_RESTORE_MISSING_LINEAGE,
    REPAIR_RERUN_WITH_STRICT_VALIDATION,
    REPAIR_SCHEMA_ERRORS,
    REPAIR_MISSING_INPUTS,
    REPAIR_ESCALATE_FOR_MANUAL_REVIEW,
})

# -- Decision-bearing stages (duplicated here for independence) ---------------

_DECISION_BEARING_STAGES: frozenset = frozenset({
    "recommend",
    "synthesis",
    "export",
})

# -- BN.4 reason-code constants (imported by value to avoid circular imports) -

_CC_REASON_CONTINUE: str = "control_chain_continue"
_CC_REASON_CONTINUE_WITH_WARNING: str = "control_chain_continue_with_warning"
_CC_REASON_BLOCKED_BY_GATING: str = "control_chain_blocked_by_gating"
_CC_REASON_BLOCKED_BY_MISSING_GATING: str = "control_chain_blocked_by_missing_gating"
_CC_REASON_BLOCKED_BY_MALFORMED_INPUT: str = "control_chain_blocked_by_malformed_input"
_CC_REASON_BLOCKED_BY_INCONSISTENT_STATE: str = "control_chain_blocked_by_inconsistent_state"

# -- BN.4 gating / enforcement outcome constants (values copied) --------------

_GATING_HALT: str = "halt"
_GATING_PROCEED: str = "proceed"
_GATING_PROCEED_WITH_WARNING: str = "proceed_with_warning"

_ENF_ALLOW: str = "allow"
_ENF_ALLOW_WITH_WARNING: str = "allow_with_warning"
_ENF_FAIL: str = "fail"


# ---------------------------------------------------------------------------
# Step 1 — Derive continuation mode
# ---------------------------------------------------------------------------


def derive_continuation_mode(
    *,
    continuation_allowed: bool,
    primary_reason_code: str,
    gating_outcome: Optional[str],
    enforcement_status: Optional[str],
    lineage_defaulted: Optional[bool],
    lineage_valid: Optional[bool],
) -> str:
    """Map control-chain state to a :data:`KNOWN_CONTINUATION_MODES` value.

    Rules (applied in priority order):
    1. Malformed / inconsistent input → stop_and_escalate
    2. continuation_allowed = False, gating halted with degraded lineage
       → stop_and_repair (or stop_and_rerun if rerun makes sense)
    3. continuation_allowed = False, malformed/inconsistent → stop_and_escalate
    4. continuation_allowed = False, any other halt → stop
    5. continuation_allowed = True, warning state → continue_with_monitoring
    6. continuation_allowed = True, clean → continue
    """
    if primary_reason_code in {
        _CC_REASON_BLOCKED_BY_MALFORMED_INPUT,
        _CC_REASON_BLOCKED_BY_INCONSISTENT_STATE,
    }:
        return CONTINUATION_MODE_STOP_AND_ESCALATE

    if not continuation_allowed:
        if primary_reason_code == _CC_REASON_BLOCKED_BY_MISSING_GATING:
            return CONTINUATION_MODE_STOP_AND_ESCALATE

        # Lineage-repairable states
        if lineage_defaulted or lineage_valid is False:
            # If enforcement warned (degraded lineage), rerun may help
            if enforcement_status == _ENF_ALLOW_WITH_WARNING:
                return CONTINUATION_MODE_STOP_AND_RERUN
            return CONTINUATION_MODE_STOP_AND_REPAIR

        if gating_outcome == _GATING_HALT:
            return CONTINUATION_MODE_STOP_AND_REPAIR

        return CONTINUATION_MODE_STOP

    # continuation allowed
    if primary_reason_code == _CC_REASON_CONTINUE_WITH_WARNING:
        return CONTINUATION_MODE_CONTINUE_WITH_MONITORING

    return CONTINUATION_MODE_CONTINUE


# ---------------------------------------------------------------------------
# Step 2 — Derive required validators
# ---------------------------------------------------------------------------


def derive_required_validators(
    *,
    continuation_mode: str,
    primary_reason_code: str,
    lineage_defaulted: Optional[bool],
    lineage_valid: Optional[bool],
    has_schema_errors: bool,
    stage: Optional[str],
) -> List[str]:
    """Return an ordered list of validator names that must run before
    continuation or rerun.

    The list is deterministic: same inputs → same output.
    """
    validators: List[str] = []

    if continuation_mode == CONTINUATION_MODE_CONTINUE:
        # Clean pass — no mandatory validators beyond what already ran
        return validators

    # Always require traceability check when anything is degraded
    if lineage_defaulted or lineage_valid is False or (
        primary_reason_code in {
            _CC_REASON_BLOCKED_BY_GATING,
            _CC_REASON_BLOCKED_BY_MISSING_GATING,
        }
    ):
        validators.append(VALIDATOR_TRACEABILITY_INTEGRITY)

    # Schema errors → schema conformance validator needed
    if has_schema_errors or primary_reason_code in {
        _CC_REASON_BLOCKED_BY_MALFORMED_INPUT,
        _CC_REASON_BLOCKED_BY_INCONSISTENT_STATE,
    }:
        validators.append(VALIDATOR_SCHEMA_CONFORMANCE)

    # Decision-bearing stages always require artifact completeness
    if stage in _DECISION_BEARING_STAGES and continuation_mode != CONTINUATION_MODE_CONTINUE:
        if VALIDATOR_ARTIFACT_COMPLETENESS not in validators:
            validators.append(VALIDATOR_ARTIFACT_COMPLETENESS)
        if VALIDATOR_CROSS_ARTIFACT_CONSISTENCY not in validators:
            validators.append(VALIDATOR_CROSS_ARTIFACT_CONSISTENCY)

    # Rerun / repair states need runtime compatibility checked
    if continuation_mode in {
        CONTINUATION_MODE_STOP_AND_RERUN,
        CONTINUATION_MODE_STOP_AND_REPAIR,
    }:
        if VALIDATOR_RUNTIME_COMPATIBILITY not in validators:
            validators.append(VALIDATOR_RUNTIME_COMPATIBILITY)

    # Escalate states need bundle contract checked
    if continuation_mode == CONTINUATION_MODE_STOP_AND_ESCALATE:
        if VALIDATOR_BUNDLE_CONTRACT not in validators:
            validators.append(VALIDATOR_BUNDLE_CONTRACT)

    # continue_with_monitoring at warning states
    if continuation_mode == CONTINUATION_MODE_CONTINUE_WITH_MONITORING:
        if VALIDATOR_TRACEABILITY_INTEGRITY not in validators:
            validators.append(VALIDATOR_TRACEABILITY_INTEGRITY)

    return validators


# ---------------------------------------------------------------------------
# Step 3 — Derive repair actions
# ---------------------------------------------------------------------------


def derive_repair_actions(
    *,
    continuation_mode: str,
    primary_reason_code: str,
    lineage_defaulted: Optional[bool],
    lineage_valid: Optional[bool],
    has_schema_errors: bool,
    enforcement_status: Optional[str],
) -> List[str]:
    """Return an ordered list of governed repair action names.

    The list is deterministic: same inputs → same output.
    """
    actions: List[str] = []

    if continuation_mode == CONTINUATION_MODE_CONTINUE:
        return actions

    if continuation_mode == CONTINUATION_MODE_CONTINUE_WITH_MONITORING:
        # Warning but allowed — no mandatory repair, but schema repair if needed
        if has_schema_errors:
            actions.append(REPAIR_SCHEMA_ERRORS)
        return actions

    # --- Blocked states -------------------------------------------------------

    if has_schema_errors:
        actions.append(REPAIR_SCHEMA_ERRORS)

    if lineage_defaulted:
        actions.append(REPAIR_RESTORE_MISSING_LINEAGE)

    if lineage_valid is False and not lineage_defaulted:
        actions.append(REPAIR_RESTORE_MISSING_LINEAGE)

    if continuation_mode == CONTINUATION_MODE_STOP_AND_RERUN:
        if REPAIR_REBUILD_WITH_REGISTRY not in actions:
            actions.append(REPAIR_REBUILD_WITH_REGISTRY)
        if REPAIR_RERUN_WITH_STRICT_VALIDATION not in actions:
            actions.append(REPAIR_RERUN_WITH_STRICT_VALIDATION)

    if primary_reason_code == _CC_REASON_BLOCKED_BY_MISSING_GATING:
        if REPAIR_MISSING_INPUTS not in actions:
            actions.append(REPAIR_MISSING_INPUTS)

    if continuation_mode == CONTINUATION_MODE_STOP_AND_ESCALATE:
        if REPAIR_ESCALATE_FOR_MANUAL_REVIEW not in actions:
            actions.append(REPAIR_ESCALATE_FOR_MANUAL_REVIEW)

    return actions


# ---------------------------------------------------------------------------
# Step 4 — Derive publication / decision permissions
# ---------------------------------------------------------------------------


def derive_publication_permissions(
    *,
    continuation_mode: str,
    stage: Optional[str],
    primary_reason_code: str,
    gating_outcome: Optional[str],
) -> Dict[str, bool]:
    """Return a dict with ``publication_allowed`` and ``decision_grade_allowed``.

    Decision rules (all fail-closed):
    - publication_allowed = True only when:
        continuation_mode = continue AND
        (stage is non-decision-bearing OR gating_outcome = proceed)
    - decision_grade_allowed = True only when:
        continuation_mode = continue AND
        stage is not blocked AND
        for decision-bearing stages: gating_outcome must be proceed (not warning)
    """
    is_clean = continuation_mode == CONTINUATION_MODE_CONTINUE
    is_decision_bearing = stage in _DECISION_BEARING_STAGES

    # Anything not a clean continue: no publication
    if not is_clean:
        return {
            "publication_allowed": False,
            "decision_grade_allowed": False,
        }

    # Clean continue: publication allowed unless decision-bearing with warning
    gating_clean = gating_outcome == _GATING_PROCEED

    if is_decision_bearing:
        # Decision-bearing stages require a clean gating proceed, not just warning
        publication_allowed = gating_clean
        decision_grade_allowed = gating_clean
    else:
        # Non-decision-bearing: allow publication on clean continue
        publication_allowed = True
        decision_grade_allowed = True

    return {
        "publication_allowed": publication_allowed,
        "decision_grade_allowed": decision_grade_allowed,
    }


# ---------------------------------------------------------------------------
# Step 5 — Derive control-signal reason codes
# ---------------------------------------------------------------------------


def derive_control_signal_reason_codes(
    *,
    continuation_mode: str,
    primary_reason_code: str,
    lineage_defaulted: Optional[bool],
    lineage_valid: Optional[bool],
    has_schema_errors: bool,
    stage: Optional[str],
    required_inputs_missing: bool,
    traceability_integrity_sli: Optional[float],
) -> List[str]:
    """Return an ordered list of governed control-signal reason codes.

    Deterministic: same inputs always produce the same codes.
    """
    codes: List[str] = []

    # Malformed / escalation state
    if primary_reason_code in {
        _CC_REASON_BLOCKED_BY_MALFORMED_INPUT,
        _CC_REASON_BLOCKED_BY_INCONSISTENT_STATE,
        _CC_REASON_BLOCKED_BY_MISSING_GATING,
    }:
        codes.append(CS_REASON_MALFORMED_CONTROL_INPUT)
        if continuation_mode == CONTINUATION_MODE_STOP_AND_ESCALATE:
            codes.append(CS_REASON_ESCALATION_REQUIRED_FOR_DECISION_STAGE)

    # Gating halt
    if primary_reason_code == _CC_REASON_BLOCKED_BY_GATING:
        codes.append(CS_REASON_GATING_HALT)

    # Lineage / traceability issues
    if lineage_defaulted:
        codes.append(CS_REASON_MISSING_TRACEABILITY)
    if lineage_valid is False:
        codes.append(CS_REASON_INVALID_LINEAGE)
    if (
        traceability_integrity_sli is not None
        and traceability_integrity_sli < 1.0
        and continuation_mode != CONTINUATION_MODE_CONTINUE
    ):
        if CS_REASON_MISSING_TRACEABILITY not in codes:
            codes.append(CS_REASON_MISSING_TRACEABILITY)

    # Degraded lineage at decision-bearing stage
    if (
        lineage_defaulted
        and stage in _DECISION_BEARING_STAGES
        and continuation_mode != CONTINUATION_MODE_CONTINUE
    ):
        if CS_REASON_DEGRADED_LINEAGE_NOT_ALLOWED not in codes:
            codes.append(CS_REASON_DEGRADED_LINEAGE_NOT_ALLOWED)

    # Schema errors
    if has_schema_errors:
        codes.append(CS_REASON_SCHEMA_NONCONFORMANCE)

    # Missing inputs
    if required_inputs_missing:
        codes.append(CS_REASON_MISSING_REQUIRED_INPUT)

    # Decision stage requires strict validation
    if stage in _DECISION_BEARING_STAGES and continuation_mode not in {
        CONTINUATION_MODE_CONTINUE,
        CONTINUATION_MODE_CONTINUE_WITH_MONITORING,
    }:
        if CS_REASON_DECISION_STAGE_REQUIRES_STRICT_VALIDATION not in codes:
            codes.append(CS_REASON_DECISION_STAGE_REQUIRES_STRICT_VALIDATION)

    # Rerun possible after repair
    if continuation_mode == CONTINUATION_MODE_STOP_AND_RERUN:
        codes.append(CS_REASON_RERUN_POSSIBLE_AFTER_REPAIR)

    # Human review for warning states
    if continuation_mode == CONTINUATION_MODE_CONTINUE_WITH_MONITORING:
        codes.append(CS_REASON_HUMAN_REVIEW_REQUIRED_FOR_WARNING_STATE)

    return codes


# ---------------------------------------------------------------------------
# Step 6 — Derive boolean flags
# ---------------------------------------------------------------------------


def _derive_boolean_flags(
    *,
    continuation_mode: str,
    primary_reason_code: str,
    stage: Optional[str],
    lineage_defaulted: Optional[bool],
    lineage_valid: Optional[bool],
    has_schema_errors: bool,
) -> Dict[str, bool]:
    """Return the boolean control-signal flags."""
    is_blocked = continuation_mode not in {
        CONTINUATION_MODE_CONTINUE,
        CONTINUATION_MODE_CONTINUE_WITH_MONITORING,
    }

    rerun_recommended = continuation_mode == CONTINUATION_MODE_STOP_AND_RERUN

    # Human review required when:
    # - warning state at a decision-bearing stage
    # - any escalation state
    human_review_required = (
        continuation_mode == CONTINUATION_MODE_CONTINUE_WITH_MONITORING
        and stage in _DECISION_BEARING_STAGES
    ) or continuation_mode == CONTINUATION_MODE_STOP_AND_ESCALATE

    # Escalation required for inconsistent/malformed states at decision stages,
    # or whenever missing gating is detected
    escalation_required = primary_reason_code in {
        _CC_REASON_BLOCKED_BY_MISSING_GATING,
        _CC_REASON_BLOCKED_BY_MALFORMED_INPUT,
        _CC_REASON_BLOCKED_BY_INCONSISTENT_STATE,
    } or continuation_mode == CONTINUATION_MODE_STOP_AND_ESCALATE

    # Traceability required when lineage was defaulted or invalid
    traceability_required = bool(lineage_defaulted) or (lineage_valid is False)

    return {
        "rerun_recommended": rerun_recommended,
        "human_review_required": human_review_required,
        "escalation_required": escalation_required,
        "traceability_required": traceability_required,
    }


# ---------------------------------------------------------------------------
# Step 7 — Build the control_signals dict
# ---------------------------------------------------------------------------


def build_control_signals(
    *,
    continuation_mode: str,
    required_inputs: List[str],
    required_validators: List[str],
    repair_actions: List[str],
    rerun_recommended: bool,
    human_review_required: bool,
    escalation_required: bool,
    publication_allowed: bool,
    decision_grade_allowed: bool,
    traceability_required: bool,
    control_signal_reason_codes: List[str],
) -> Dict[str, Any]:
    """Assemble the governed ``control_signals`` artifact sub-object.

    All fields are explicitly set.  No implicit defaults.
    """
    return {
        "continuation_mode": continuation_mode,
        "required_inputs": list(required_inputs),
        "required_validators": list(required_validators),
        "repair_actions": list(repair_actions),
        "rerun_recommended": bool(rerun_recommended),
        "human_review_required": bool(human_review_required),
        "escalation_required": bool(escalation_required),
        "publication_allowed": bool(publication_allowed),
        "decision_grade_allowed": bool(decision_grade_allowed),
        "traceability_required": bool(traceability_required),
        "control_signal_reason_codes": list(control_signal_reason_codes),
    }


# ---------------------------------------------------------------------------
# Step 8 — Main derivation entry point
# ---------------------------------------------------------------------------


def derive_control_signals(
    *,
    continuation_allowed: bool,
    primary_reason_code: str,
    gating_outcome: Optional[str],
    enforcement_status: Optional[str],
    lineage_defaulted: Optional[bool],
    lineage_valid: Optional[bool],
    stage: Optional[str],
    has_schema_errors: bool = False,
    required_inputs: Optional[List[str]] = None,
    traceability_integrity_sli: Optional[float] = None,
) -> Dict[str, Any]:
    """Derive the full ``control_signals`` dict from control-chain state.

    This is the primary public entry point.  All derivation is deterministic.

    Parameters
    ----------
    continuation_allowed:
        Whether the control chain permitted continuation.
    primary_reason_code:
        The BN.4 reason code (e.g. ``"control_chain_continue"``).
    gating_outcome:
        The gating outcome string (``"proceed"``, ``"proceed_with_warning"``,
        ``"halt"``), or ``None``/``"(none)"`` when gating was not executed.
    enforcement_status:
        The enforcement decision status (``"allow"``, ``"allow_with_warning"``,
        ``"fail"``), or ``None``/``"(unknown)"`` when not determinable.
    lineage_defaulted:
        True when lineage was populated via fail-safe defaults.
    lineage_valid:
        Whether the artifact lineage was validated without errors.
    stage:
        Pipeline stage name (e.g. ``"synthesis"``), or ``None``.
    has_schema_errors:
        True when schema validation errors were found in the chain.
    required_inputs:
        Caller-supplied list of missing/required input identifiers.
    traceability_integrity_sli:
        Traceability integrity SLI value (0.0–1.0), or ``None``.

    Returns
    -------
    dict
        Governed ``control_signals`` sub-object ready to embed in the
        control-chain artifact.
    """
    _required_inputs = required_inputs or []
    required_inputs_missing = bool(_required_inputs)

    # Normalize sentinel strings to None for boolean comparisons
    _gating_outcome = gating_outcome if gating_outcome not in {None, "(none)", "(unknown)"} else None
    _enforcement_status = (
        enforcement_status if enforcement_status not in {None, "(unknown)"} else None
    )
    _lineage_defaulted = lineage_defaulted if isinstance(lineage_defaulted, bool) else None
    _lineage_valid = lineage_valid if isinstance(lineage_valid, bool) else None

    continuation_mode = derive_continuation_mode(
        continuation_allowed=continuation_allowed,
        primary_reason_code=primary_reason_code,
        gating_outcome=_gating_outcome,
        enforcement_status=_enforcement_status,
        lineage_defaulted=_lineage_defaulted,
        lineage_valid=_lineage_valid,
    )

    required_validators = derive_required_validators(
        continuation_mode=continuation_mode,
        primary_reason_code=primary_reason_code,
        lineage_defaulted=_lineage_defaulted,
        lineage_valid=_lineage_valid,
        has_schema_errors=has_schema_errors,
        stage=stage,
    )

    repair_actions = derive_repair_actions(
        continuation_mode=continuation_mode,
        primary_reason_code=primary_reason_code,
        lineage_defaulted=_lineage_defaulted,
        lineage_valid=_lineage_valid,
        has_schema_errors=has_schema_errors,
        enforcement_status=_enforcement_status,
    )

    pub_permissions = derive_publication_permissions(
        continuation_mode=continuation_mode,
        stage=stage,
        primary_reason_code=primary_reason_code,
        gating_outcome=_gating_outcome,
    )

    reason_codes = derive_control_signal_reason_codes(
        continuation_mode=continuation_mode,
        primary_reason_code=primary_reason_code,
        lineage_defaulted=_lineage_defaulted,
        lineage_valid=_lineage_valid,
        has_schema_errors=has_schema_errors,
        stage=stage,
        required_inputs_missing=required_inputs_missing,
        traceability_integrity_sli=traceability_integrity_sli,
    )

    bool_flags = _derive_boolean_flags(
        continuation_mode=continuation_mode,
        primary_reason_code=primary_reason_code,
        stage=stage,
        lineage_defaulted=_lineage_defaulted,
        lineage_valid=_lineage_valid,
        has_schema_errors=has_schema_errors,
    )

    return build_control_signals(
        continuation_mode=continuation_mode,
        required_inputs=_required_inputs,
        required_validators=required_validators,
        repair_actions=repair_actions,
        rerun_recommended=bool_flags["rerun_recommended"],
        human_review_required=bool_flags["human_review_required"],
        escalation_required=bool_flags["escalation_required"],
        publication_allowed=pub_permissions["publication_allowed"],
        decision_grade_allowed=pub_permissions["decision_grade_allowed"],
        traceability_required=bool_flags["traceability_required"],
        control_signal_reason_codes=reason_codes,
    )


# ---------------------------------------------------------------------------
# Schema validation helper
# ---------------------------------------------------------------------------


def validate_control_signals(signals: Any) -> List[str]:
    """Return a list of validation error strings for *signals*.

    Checks structural requirements without requiring jsonschema.  The full
    schema validation is performed at the control-chain artifact level.
    """
    errors: List[str] = []
    if not isinstance(signals, dict):
        return [f"control_signals must be a dict; got {type(signals).__name__}"]

    # Required fields
    required = {
        "continuation_mode",
        "required_inputs",
        "required_validators",
        "repair_actions",
        "rerun_recommended",
        "human_review_required",
        "escalation_required",
        "publication_allowed",
        "decision_grade_allowed",
        "traceability_required",
        "control_signal_reason_codes",
    }
    missing = required - signals.keys()
    if missing:
        errors.append(f"control_signals missing required fields: {sorted(missing)}")

    # Enum check
    mode = signals.get("continuation_mode")
    if mode is not None and mode not in KNOWN_CONTINUATION_MODES:
        errors.append(
            f"control_signals.continuation_mode '{mode}' not in "
            f"KNOWN_CONTINUATION_MODES"
        )

    # Array fields
    for arr_field in ("required_inputs", "required_validators", "repair_actions",
                      "control_signal_reason_codes"):
        val = signals.get(arr_field)
        if val is not None and not isinstance(val, list):
            errors.append(f"control_signals.{arr_field} must be a list")

    # Boolean fields
    for bool_field in ("rerun_recommended", "human_review_required", "escalation_required",
                       "publication_allowed", "decision_grade_allowed", "traceability_required"):
        val = signals.get(bool_field)
        if val is not None and not isinstance(val, bool):
            errors.append(f"control_signals.{bool_field} must be a boolean")

    # Reason codes must be in vocabulary
    codes = signals.get("control_signal_reason_codes")
    if isinstance(codes, list):
        unknown = [c for c in codes if c not in KNOWN_CS_REASON_CODES]
        if unknown:
            errors.append(
                f"control_signals.control_signal_reason_codes contains unknown "
                f"codes: {unknown}"
            )

    # Consistency checks
    mode = signals.get("continuation_mode")
    if mode in {
        CONTINUATION_MODE_STOP,
        CONTINUATION_MODE_STOP_AND_REPAIR,
        CONTINUATION_MODE_STOP_AND_RERUN,
        CONTINUATION_MODE_STOP_AND_ESCALATE,
    }:
        if signals.get("publication_allowed") is True:
            errors.append(
                "control_signals: publication_allowed=True is contradictory "
                f"when continuation_mode={mode}"
            )
        if signals.get("decision_grade_allowed") is True:
            errors.append(
                "control_signals: decision_grade_allowed=True is contradictory "
                f"when continuation_mode={mode}"
            )

    return errors


# ---------------------------------------------------------------------------
# Diagnostic helpers
# ---------------------------------------------------------------------------


def summarize_control_signals(signals: Dict[str, Any]) -> str:
    """Return a deterministic, operator-readable multi-line summary.

    Derived entirely from structured state — no ad-hoc prose.
    """
    if not isinstance(signals, dict):
        return "control_signals: (invalid — not a dict)"

    lines = [
        "Control Signals (BN.5)",
        "----------------------",
        f"  continuation_mode        : {signals.get('continuation_mode', '(unknown)')}",
        f"  publication_allowed      : {signals.get('publication_allowed')}",
        f"  decision_grade_allowed   : {signals.get('decision_grade_allowed')}",
        f"  human_review_required    : {signals.get('human_review_required')}",
        f"  escalation_required      : {signals.get('escalation_required')}",
        f"  rerun_recommended        : {signals.get('rerun_recommended')}",
        f"  traceability_required    : {signals.get('traceability_required')}",
    ]

    required_validators = signals.get("required_validators") or []
    if required_validators:
        lines.append("  required_validators:")
        for v in required_validators:
            lines.append(f"    - {v}")
    else:
        lines.append("  required_validators      : (none)")

    repair_actions = signals.get("repair_actions") or []
    if repair_actions:
        lines.append("  repair_actions:")
        for a in repair_actions:
            lines.append(f"    - {a}")
    else:
        lines.append("  repair_actions           : (none)")

    required_inputs = signals.get("required_inputs") or []
    if required_inputs:
        lines.append("  required_inputs:")
        for i in required_inputs:
            lines.append(f"    - {i}")

    reason_codes = signals.get("control_signal_reason_codes") or []
    if reason_codes:
        lines.append("  reason_codes:")
        for c in reason_codes:
            lines.append(f"    - {c}")
    else:
        lines.append("  reason_codes             : (none)")

    return "\n".join(lines)


def explain_blocking_requirements(signals: Dict[str, Any]) -> str:
    """Return a deterministic operator-readable explanation of what must be done
    before continuation is possible.

    Empty string when continuation is already allowed (mode = continue or
    continue_with_monitoring).
    """
    if not isinstance(signals, dict):
        return "control_signals: (invalid — not a dict)"

    mode = signals.get("continuation_mode", "")
    if mode in {CONTINUATION_MODE_CONTINUE, CONTINUATION_MODE_CONTINUE_WITH_MONITORING}:
        return ""

    parts: List[str] = [f"Blocking requirements for continuation_mode={mode}:"]

    repair_actions = signals.get("repair_actions") or []
    if repair_actions:
        parts.append("  Required repair actions:")
        for a in repair_actions:
            parts.append(f"    - {a}")

    required_validators = signals.get("required_validators") or []
    if required_validators:
        parts.append("  Required validators before rerun/continuation:")
        for v in required_validators:
            parts.append(f"    - {v}")

    required_inputs = signals.get("required_inputs") or []
    if required_inputs:
        parts.append("  Missing required inputs:")
        for i in required_inputs:
            parts.append(f"    - {i}")

    codes = signals.get("control_signal_reason_codes") or []
    if codes:
        parts.append("  Reason codes:")
        for c in codes:
            parts.append(f"    - {c}")

    if signals.get("escalation_required"):
        parts.append("  ACTION: Escalation to governance/oversight is required.")
    if signals.get("human_review_required"):
        parts.append("  ACTION: Human review is required before proceeding.")

    return "\n".join(parts)


def list_required_followups(signals: Dict[str, Any]) -> List[str]:
    """Return a deterministic ordered list of required follow-up actions.

    Each entry is a short controlled-vocabulary string.
    Empty list when no follow-ups are required.
    """
    if not isinstance(signals, dict):
        return ["invalid_control_signals"]

    followups: List[str] = []

    repair_actions = signals.get("repair_actions") or []
    followups.extend(repair_actions)

    required_validators = signals.get("required_validators") or []
    for v in required_validators:
        entry = f"run:{v}"
        if entry not in followups:
            followups.append(entry)

    if signals.get("human_review_required") and "human_review" not in followups:
        followups.append("human_review")

    if signals.get("escalation_required") and "escalate_to_governance" not in followups:
        followups.append("escalate_to_governance")

    if signals.get("rerun_recommended") and "rerun_after_repair" not in followups:
        followups.append("rerun_after_repair")

    return followups
