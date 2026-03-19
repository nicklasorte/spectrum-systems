"""Stage-Aware Decision Gating Engine (BN.3).

Consumes ``slo_enforcement_decision`` artifacts and determines whether a
pipeline step may **proceed**, must **halt**, or may **proceed_with_warning**
based on the enforcement decision status and the stage's governed gating
posture.

This module closes the gap between advisory enforcement (BN.1/BN.2) and
binding runtime control.  An untrustworthy artifact must not silently flow
into a decision-bearing stage.

Design principles
-----------------
- Fail closed:  any unclear, contradictory, or malformed enforcement state
  produces a governed ``halt`` gating decision, never a silent pass.
- Deterministic:  the same inputs always produce the same gating outcome
  (aside from timestamps and generated IDs).
- Crash-proof:  all entry points catch exceptions and return governed failure
  artifacts rather than raising.
- Separation of concerns:

  1. Input normalisation      (:func:`normalize_gating_inputs`)
  2. Input validation         (:func:`validate_enforcement_decision_for_gating`)
  3. Stage posture resolution (:func:`resolve_stage_gating_posture`)
  4. Outcome evaluation       (:func:`evaluate_gating_outcome`)
  5. Reason code derivation   (:func:`derive_gating_reason_code`)
  6. Recommended action       (:func:`derive_gating_recommended_action`)
  7. Artifact construction    (:func:`build_slo_gating_decision`)
  8. Schema validation        (:func:`validate_slo_gating_decision`)
  9. Orchestration            (:func:`run_slo_gating`)

Gating outcomes (distinct from enforcement decision statuses)
-------------------------------------------------------------
proceed
    Enforcement allowed; stage may continue.

proceed_with_warning
    Enforcement warned but the current stage's governed posture permits
    warnings to continue (exploratory / non-decision-bearing stages).

halt
    Enforcement failed, or enforcement warned but the stage's posture
    requires warnings to be blocked (decision-bearing stages).

Default stage-to-posture mapping
---------------------------------
observe    → warnings allowed   (non-decision-bearing)
interpret  → warnings allowed   (non-decision-bearing)
recommend  → warnings halt      (decision-bearing)
synthesis  → warnings halt      (decision-bearing)
export     → warnings halt      (decision-bearing, unless overridden in config)

Gating reason codes
-------------------
enforcement_allow                   – enforcement decision was allow
enforcement_warning_allowed         – warning but stage permits continuation
enforcement_warning_blocked_by_stage – warning and stage requires halt
enforcement_fail                    – enforcement decision was fail
malformed_enforcement_decision      – the decision payload could not be parsed
missing_enforcement_status          – decision_status field absent
unknown_enforcement_status          – decision_status has an unrecognised value
inconsistent_enforcement_payload    – internally contradictory fields detected

Recommended actions
-------------------
proceed                     – continue normally
proceed_with_monitoring     – continue but monitor traceability
halt_and_review             – stop; operator review required
halt_and_repair_lineage     – stop; lineage must be repaired
halt_and_rerun_with_registry – stop; rerun with a lineage registry supplied
halt_and_escalate           – stop; escalate to governance/oversight

Exit codes (CLI)
----------------
0 – proceed
1 – proceed_with_warning
2 – halt
3 – malformed input / schema / execution error
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

# ---------------------------------------------------------------------------
# Schema / data file paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_GATING_DECISION_SCHEMA_PATH = _SCHEMA_DIR / "slo_gating_decision.schema.json"
_GATING_RULES_SCHEMA_PATH = _SCHEMA_DIR / "slo_gating_rules.schema.json"
_GATING_RULES_PATH = _REPO_ROOT / "data" / "policy" / "slo_gating_rules.json"

# ---------------------------------------------------------------------------
# Contract / schema version
# ---------------------------------------------------------------------------

CONTRACT_VERSION: str = "1.0.0"

# ---------------------------------------------------------------------------
# Gating outcome constants
# ---------------------------------------------------------------------------

OUTCOME_PROCEED: str = "proceed"
OUTCOME_PROCEED_WITH_WARNING: str = "proceed_with_warning"
OUTCOME_HALT: str = "halt"

KNOWN_GATING_OUTCOMES: frozenset = frozenset({
    OUTCOME_PROCEED,
    OUTCOME_PROCEED_WITH_WARNING,
    OUTCOME_HALT,
})

# ---------------------------------------------------------------------------
# Enforcement decision status constants (mirrored here for isolation)
# ---------------------------------------------------------------------------

ENFORCEMENT_ALLOW: str = "allow"
ENFORCEMENT_ALLOW_WITH_WARNING: str = "allow_with_warning"
ENFORCEMENT_FAIL: str = "fail"

KNOWN_ENFORCEMENT_STATUSES: frozenset = frozenset({
    ENFORCEMENT_ALLOW,
    ENFORCEMENT_ALLOW_WITH_WARNING,
    ENFORCEMENT_FAIL,
})

# ---------------------------------------------------------------------------
# Stage constants (canonical list; gating rules config is authoritative)
# ---------------------------------------------------------------------------

STAGE_OBSERVE: str = "observe"
STAGE_INTERPRET: str = "interpret"
STAGE_RECOMMEND: str = "recommend"
STAGE_SYNTHESIS: str = "synthesis"
STAGE_EXPORT: str = "export"

KNOWN_STAGES: frozenset = frozenset({
    STAGE_OBSERVE,
    STAGE_INTERPRET,
    STAGE_RECOMMEND,
    STAGE_SYNTHESIS,
    STAGE_EXPORT,
})

# ---------------------------------------------------------------------------
# Gating reason code constants
# ---------------------------------------------------------------------------

REASON_ENFORCEMENT_ALLOW: str = "enforcement_allow"
REASON_ENFORCEMENT_WARNING_ALLOWED: str = "enforcement_warning_allowed"
REASON_ENFORCEMENT_WARNING_BLOCKED_BY_STAGE: str = "enforcement_warning_blocked_by_stage"
REASON_ENFORCEMENT_FAIL: str = "enforcement_fail"
REASON_MALFORMED_ENFORCEMENT_DECISION: str = "malformed_enforcement_decision"
REASON_MISSING_ENFORCEMENT_STATUS: str = "missing_enforcement_status"
REASON_UNKNOWN_ENFORCEMENT_STATUS: str = "unknown_enforcement_status"
REASON_INCONSISTENT_ENFORCEMENT_PAYLOAD: str = "inconsistent_enforcement_payload"

KNOWN_GATING_REASON_CODES: frozenset = frozenset({
    REASON_ENFORCEMENT_ALLOW,
    REASON_ENFORCEMENT_WARNING_ALLOWED,
    REASON_ENFORCEMENT_WARNING_BLOCKED_BY_STAGE,
    REASON_ENFORCEMENT_FAIL,
    REASON_MALFORMED_ENFORCEMENT_DECISION,
    REASON_MISSING_ENFORCEMENT_STATUS,
    REASON_UNKNOWN_ENFORCEMENT_STATUS,
    REASON_INCONSISTENT_ENFORCEMENT_PAYLOAD,
})

# ---------------------------------------------------------------------------
# Recommended action constants
# ---------------------------------------------------------------------------

ACTION_PROCEED: str = "proceed"
ACTION_PROCEED_WITH_MONITORING: str = "proceed_with_monitoring"
ACTION_HALT_AND_REVIEW: str = "halt_and_review"
ACTION_HALT_AND_REPAIR_LINEAGE: str = "halt_and_repair_lineage"
ACTION_HALT_AND_RERUN_WITH_REGISTRY: str = "halt_and_rerun_with_registry"
ACTION_HALT_AND_ESCALATE: str = "halt_and_escalate"

KNOWN_RECOMMENDED_ACTIONS: frozenset = frozenset({
    ACTION_PROCEED,
    ACTION_PROCEED_WITH_MONITORING,
    ACTION_HALT_AND_REVIEW,
    ACTION_HALT_AND_REPAIR_LINEAGE,
    ACTION_HALT_AND_RERUN_WITH_REGISTRY,
    ACTION_HALT_AND_ESCALATE,
})

# ---------------------------------------------------------------------------
# Built-in fallback stage postures (used if config file is unavailable)
# ---------------------------------------------------------------------------

_FALLBACK_STAGE_POSTURES: Dict[str, Dict[str, bool]] = {
    STAGE_OBSERVE:    {"warnings_allowed": True,  "decision_bearing": False},
    STAGE_INTERPRET:  {"warnings_allowed": True,  "decision_bearing": False},
    STAGE_RECOMMEND:  {"warnings_allowed": False, "decision_bearing": True},
    STAGE_SYNTHESIS:  {"warnings_allowed": False, "decision_bearing": True},
    STAGE_EXPORT:     {"warnings_allowed": False, "decision_bearing": True},
}

# ---------------------------------------------------------------------------
# Gating rules cache (loaded once from the JSON config)
# ---------------------------------------------------------------------------

_GATING_RULES_CACHE: Optional[Dict[str, Any]] = None


def _load_gating_rules() -> Dict[str, Any]:
    """Load and cache gating rules from the governed JSON config file.

    Falls back to built-in posture map on any load/validation error so the
    system never fails to gate.
    """
    global _GATING_RULES_CACHE
    if _GATING_RULES_CACHE is not None:
        return _GATING_RULES_CACHE

    try:
        rules_data = json.loads(_GATING_RULES_PATH.read_text(encoding="utf-8"))
        _GATING_RULES_CACHE = rules_data
        return _GATING_RULES_CACHE
    except Exception:  # noqa: BLE001
        return {"stages": _FALLBACK_STAGE_POSTURES}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _gating_decision_id() -> str:
    return "GATE-" + uuid.uuid4().hex[:12].upper()


# ---------------------------------------------------------------------------
# Step 1 — Input normalisation
# ---------------------------------------------------------------------------


def normalize_gating_inputs(raw: Any) -> Dict[str, Any]:
    """Normalise a raw value into a flat dict suitable for gating.

    Handles:
    - Wrapped dicts with an ``enforcement_decision`` key (run_slo_enforcement
      return format)
    - Bare enforcement decision dicts
    - Non-dict values (returned as-is in an error wrapper so later steps can
      detect malformed input)

    Returns a dict that is safe to introspect.  Invalid / missing fields are
    left absent so that validation can surface the correct reason code.
    """
    if not isinstance(raw, dict):
        return {"_malformed": True, "_malformed_reason": f"expected dict, got {type(raw).__name__}"}

    # Unwrap run_slo_enforcement-style wrapper
    if "enforcement_decision" in raw and isinstance(raw["enforcement_decision"], dict):
        return dict(raw["enforcement_decision"])

    return dict(raw)


# ---------------------------------------------------------------------------
# Step 2 — Enforcement decision validation
# ---------------------------------------------------------------------------


def validate_enforcement_decision_for_gating(
    norm: Dict[str, Any],
) -> Tuple[bool, str, List[str]]:
    """Validate a normalised enforcement decision for gating consumption.

    Returns
    -------
    (valid, reason_code, errors)
        valid       – True when the decision is structurally sound enough to
                      evaluate the gating outcome
        reason_code – a REASON_* string identifying the validation result
        errors      – list of human-readable error strings
    """
    errors: List[str] = []

    # Malformed payload (couldn't even parse to dict)
    if norm.get("_malformed"):
        errors.append(f"Malformed enforcement decision: {norm.get('_malformed_reason', 'unknown')}")
        return False, REASON_MALFORMED_ENFORCEMENT_DECISION, errors

    # Missing required fields check
    required_fields = [
        "decision_id",
        "artifact_id",
        "enforcement_policy",
        "decision_status",
        "decision_reason_code",
    ]
    missing = [f for f in required_fields if f not in norm or norm[f] is None]
    if missing:
        errors.append(f"Missing required enforcement decision fields: {missing}")
        # Distinguish missing status vs. other missing fields
        if "decision_status" in missing:
            return False, REASON_MISSING_ENFORCEMENT_STATUS, errors
        return False, REASON_MALFORMED_ENFORCEMENT_DECISION, errors

    # Unknown decision_status
    status = norm.get("decision_status")
    if status not in KNOWN_ENFORCEMENT_STATUSES:
        errors.append(
            f"Unknown enforcement decision_status '{status}'. "
            f"Expected one of: {sorted(KNOWN_ENFORCEMENT_STATUSES)}"
        )
        return False, REASON_UNKNOWN_ENFORCEMENT_STATUS, errors

    # Inconsistency detection: allow with errors populated, or fail with no errors/warnings
    enforcement_errors = norm.get("errors") or []
    enforcement_warnings = norm.get("warnings") or []
    if status == ENFORCEMENT_ALLOW and enforcement_errors:
        errors.append(
            "Inconsistent enforcement payload: decision_status is 'allow' "
            "but errors array is non-empty."
        )
        return False, REASON_INCONSISTENT_ENFORCEMENT_PAYLOAD, errors

    # TI + lineage_mode sanity: if TI is present, must be 0.0/0.5/1.0 or null
    ti = norm.get("traceability_integrity_sli")
    if ti is not None and not isinstance(ti, (int, float)):
        errors.append(
            f"traceability_integrity_sli must be a number or null, got {type(ti).__name__}"
        )
        return False, REASON_INCONSISTENT_ENFORCEMENT_PAYLOAD, errors

    _ = enforcement_warnings  # used implicitly for context; no check needed here

    return True, "", []


# ---------------------------------------------------------------------------
# Step 3 — Stage posture resolution
# ---------------------------------------------------------------------------


def resolve_stage_gating_posture(stage: Optional[str]) -> Dict[str, Any]:
    """Resolve the governed gating posture for *stage*.

    Returns a dict with at least:
    - ``warnings_allowed``: bool
    - ``decision_bearing``: bool
    - ``stage``: the canonical stage name used
    - ``stage_known``: bool

    For unknown or absent stages, ``warnings_allowed`` defaults to ``False``
    (fail-closed) and ``decision_bearing`` defaults to ``True``.
    """
    rules = _load_gating_rules()
    stage_rules = rules.get("stages", {})

    if stage is None or stage not in stage_rules:
        return {
            "stage": stage or "(unknown)",
            "stage_known": False,
            "warnings_allowed": False,
            "decision_bearing": True,
        }

    posture = stage_rules[stage]
    return {
        "stage": stage,
        "stage_known": True,
        "warnings_allowed": bool(posture.get("warnings_allowed", False)),
        "decision_bearing": bool(posture.get("decision_bearing", True)),
    }


# ---------------------------------------------------------------------------
# Step 4 — Gating outcome evaluation
# ---------------------------------------------------------------------------


def evaluate_gating_outcome(
    enforcement_status: str,
    warnings_allowed: bool,
    valid_inputs: bool,
) -> str:
    """Derive the gating outcome from enforcement status and stage posture.

    Parameters
    ----------
    enforcement_status:
        ``allow``, ``allow_with_warning``, or ``fail`` (or unknown).
    warnings_allowed:
        True when the current stage's posture permits warnings to continue.
    valid_inputs:
        False when the enforcement payload was malformed / unreadable.

    Returns
    -------
    One of :data:`KNOWN_GATING_OUTCOMES`.
    """
    if not valid_inputs:
        return OUTCOME_HALT

    if enforcement_status == ENFORCEMENT_ALLOW:
        return OUTCOME_PROCEED

    if enforcement_status == ENFORCEMENT_ALLOW_WITH_WARNING:
        return OUTCOME_PROCEED_WITH_WARNING if warnings_allowed else OUTCOME_HALT

    if enforcement_status == ENFORCEMENT_FAIL:
        return OUTCOME_HALT

    # Unknown status — fail closed
    return OUTCOME_HALT


# ---------------------------------------------------------------------------
# Step 5 — Gating reason code derivation
# ---------------------------------------------------------------------------


def derive_gating_reason_code(
    enforcement_status: str,
    warnings_allowed: bool,
    valid_inputs: bool,
    validation_reason_code: str,
) -> str:
    """Return the appropriate REASON_* constant for this gating decision.

    When ``valid_inputs`` is False, ``validation_reason_code`` (set by
    :func:`validate_enforcement_decision_for_gating`) is returned directly.
    """
    if not valid_inputs:
        return validation_reason_code or REASON_MALFORMED_ENFORCEMENT_DECISION

    if enforcement_status == ENFORCEMENT_ALLOW:
        return REASON_ENFORCEMENT_ALLOW

    if enforcement_status == ENFORCEMENT_ALLOW_WITH_WARNING:
        return (
            REASON_ENFORCEMENT_WARNING_ALLOWED
            if warnings_allowed
            else REASON_ENFORCEMENT_WARNING_BLOCKED_BY_STAGE
        )

    if enforcement_status == ENFORCEMENT_FAIL:
        return REASON_ENFORCEMENT_FAIL

    return REASON_UNKNOWN_ENFORCEMENT_STATUS


# ---------------------------------------------------------------------------
# Step 6 — Recommended action derivation
# ---------------------------------------------------------------------------


def derive_gating_recommended_action(
    gating_outcome: str,
    gating_reason_code: str,
    norm: Dict[str, Any],
) -> str:
    """Derive the recommended operator action deterministically.

    Parameters
    ----------
    gating_outcome:
        One of :data:`KNOWN_GATING_OUTCOMES`.
    gating_reason_code:
        One of :data:`KNOWN_GATING_REASON_CODES`.
    norm:
        Normalised enforcement decision dict (used to inspect lineage fields).
    """
    if gating_outcome == OUTCOME_PROCEED:
        return ACTION_PROCEED

    if gating_outcome == OUTCOME_PROCEED_WITH_WARNING:
        return ACTION_PROCEED_WITH_MONITORING

    # halt cases — differentiate by reason code and lineage context
    if gating_reason_code in (
        REASON_MALFORMED_ENFORCEMENT_DECISION,
        REASON_MISSING_ENFORCEMENT_STATUS,
        REASON_UNKNOWN_ENFORCEMENT_STATUS,
        REASON_INCONSISTENT_ENFORCEMENT_PAYLOAD,
    ):
        return ACTION_HALT_AND_ESCALATE

    lineage_defaulted = norm.get("lineage_defaulted")
    lineage_valid = norm.get("lineage_valid")
    lineage_mode = norm.get("lineage_validation_mode", "")

    # No registry supplied (degraded lineage)
    if lineage_mode == "degraded" or lineage_defaulted is True:
        return ACTION_HALT_AND_RERUN_WITH_REGISTRY

    # Invalid lineage detected
    if lineage_valid is False:
        return ACTION_HALT_AND_REPAIR_LINEAGE

    return ACTION_HALT_AND_REVIEW


# ---------------------------------------------------------------------------
# Step 7 — Gating artifact construction
# ---------------------------------------------------------------------------


def build_slo_gating_decision(
    *,
    source_decision_id: str,
    artifact_id: str,
    stage: Optional[str],
    enforcement_policy: str,
    enforcement_decision_status: str,
    gating_outcome: str,
    gating_reason_code: str,
    ti_value: Any,
    lineage_mode: Optional[str],
    lineage_defaulted: Optional[bool],
    lineage_valid: Optional[Any],
    warnings: List[str],
    errors: List[str],
    recommended_action: str,
    evaluated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct the governed ``slo_gating_decision`` artifact.

    All fields are explicitly set; no implicit defaults are allowed.
    """
    ts = evaluated_at or _now_iso()
    gating_id = _gating_decision_id()

    artifact: Dict[str, Any] = {
        "gating_decision_id": gating_id,
        "source_decision_id": source_decision_id,
        "artifact_id": artifact_id if artifact_id else "(unknown)",
        "stage": stage if stage else "(unknown)",
        "enforcement_policy": enforcement_policy,
        "enforcement_decision_status": enforcement_decision_status,
        "gating_outcome": gating_outcome,
        "gating_reason_code": gating_reason_code,
        "traceability_integrity_sli": ti_value if isinstance(ti_value, (int, float)) else None,
        "lineage_validation_mode": lineage_mode if lineage_mode else "(unknown)",
        "lineage_defaulted": lineage_defaulted if isinstance(lineage_defaulted, bool) else None,
        "lineage_valid": bool(lineage_valid) if lineage_valid is not None else None,
        "warnings": list(warnings),
        "errors": list(errors),
        "recommended_action": recommended_action,
        "evaluated_at": ts,
        "contract_version": CONTRACT_VERSION,
    }
    return artifact


# ---------------------------------------------------------------------------
# Step 8 — Schema validation
# ---------------------------------------------------------------------------


def validate_slo_gating_decision(
    decision: Dict[str, Any],
) -> List[str]:
    """Validate *decision* against the gating decision JSON schema.

    Returns a (possibly empty) list of human-readable error strings.
    """
    try:
        schema = json.loads(_GATING_DECISION_SCHEMA_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [f"Could not load gating decision schema: {exc}"]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(decision), key=lambda e: list(e.absolute_path))
    ]


# ---------------------------------------------------------------------------
# Step 9 — Convenience: run from enforcement decision directly
# ---------------------------------------------------------------------------


def run_slo_gating(
    raw_input: Any,
    stage: Optional[str] = None,
    evaluated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the full SLO gating pipeline.

    This is the primary public entry point.  It is crash-proof: any exception
    during processing is caught and returned as a governed ``halt`` decision
    with reason ``malformed_enforcement_decision``.

    Parameters
    ----------
    raw_input:
        Either an ``slo_enforcement_decision`` dict, or a wrapper dict with
        key ``enforcement_decision`` (as returned by
        :func:`~spectrum_systems.modules.runtime.slo_enforcement.run_slo_enforcement`).
    stage:
        Optional pipeline stage override.  When ``None`` the stage embedded
        in the enforcement decision's ``enforcement_scope`` field is used.
    evaluated_at:
        Optional ISO 8601 timestamp override (for deterministic tests).

    Returns
    -------
    dict with keys:
        ``gating_decision``  – the governed gating artifact
        ``gating_outcome``   – shortcut to ``gating_decision["gating_outcome"]``
        ``schema_errors``    – list of schema validation errors (usually empty)
    """
    try:
        return _run_slo_gating_inner(raw_input, stage=stage, evaluated_at=evaluated_at)
    except Exception as exc:  # noqa: BLE001
        # Crash-proof: return a governed failure artifact
        fallback = build_slo_gating_decision(
            source_decision_id="(unknown)",
            artifact_id="(unknown)",
            stage=stage or "(unknown)",
            enforcement_policy="(unknown)",
            enforcement_decision_status="(unknown)",
            gating_outcome=OUTCOME_HALT,
            gating_reason_code=REASON_MALFORMED_ENFORCEMENT_DECISION,
            ti_value=None,
            lineage_mode=None,
            lineage_defaulted=None,
            lineage_valid=None,
            warnings=[],
            errors=[f"Unhandled exception during gating: {exc}"],
            recommended_action=ACTION_HALT_AND_ESCALATE,
            evaluated_at=evaluated_at,
        )
        return {
            "gating_decision": fallback,
            "gating_outcome": OUTCOME_HALT,
            "schema_errors": [],
        }


def _run_slo_gating_inner(
    raw_input: Any,
    stage: Optional[str],
    evaluated_at: Optional[str],
) -> Dict[str, Any]:
    """Inner gating pipeline — called by :func:`run_slo_gating`."""
    # 1. Normalise inputs
    norm = normalize_gating_inputs(raw_input)

    # 2. Validate enforcement decision
    valid_inputs, validation_reason_code, validation_errors = (
        validate_enforcement_decision_for_gating(norm)
    )

    # Resolve stage: explicit override > enforcement_scope > None
    effective_stage = stage or norm.get("enforcement_scope") or None

    # 3. Resolve stage gating posture
    posture = resolve_stage_gating_posture(effective_stage)
    warnings_allowed = posture["warnings_allowed"]

    # Collect accumulated warnings / errors
    acc_warnings: List[str] = list(norm.get("warnings") or [])
    acc_errors: List[str] = list(validation_errors)

    # Add a warning if stage is unknown (but don't block on it)
    if not posture["stage_known"] and effective_stage is not None:
        acc_warnings.append(
            f"Unrecognised stage '{effective_stage}'; defaulting to fail-closed posture."
        )

    # 4. Derive enforcement status for gating
    enforcement_status: str = norm.get("decision_status", "") if valid_inputs else ""

    # 5. Evaluate gating outcome
    gating_outcome = evaluate_gating_outcome(
        enforcement_status=enforcement_status,
        warnings_allowed=warnings_allowed,
        valid_inputs=valid_inputs,
    )

    # 6. Derive reason code
    gating_reason_code = derive_gating_reason_code(
        enforcement_status=enforcement_status,
        warnings_allowed=warnings_allowed,
        valid_inputs=valid_inputs,
        validation_reason_code=validation_reason_code,
    )

    # 7. Derive recommended action
    recommended_action = derive_gating_recommended_action(
        gating_outcome=gating_outcome,
        gating_reason_code=gating_reason_code,
        norm=norm,
    )

    # 8. Build artifact
    gating_decision = build_slo_gating_decision(
        source_decision_id=norm.get("decision_id") or "(unknown)",
        artifact_id=norm.get("artifact_id") or "(unknown)",
        stage=effective_stage,
        enforcement_policy=norm.get("enforcement_policy") or "(unknown)",
        enforcement_decision_status=norm.get("decision_status") or "(unknown)",
        gating_outcome=gating_outcome,
        gating_reason_code=gating_reason_code,
        ti_value=norm.get("traceability_integrity_sli"),
        lineage_mode=norm.get("lineage_validation_mode"),
        lineage_defaulted=norm.get("lineage_defaulted"),
        lineage_valid=norm.get("lineage_valid"),
        warnings=acc_warnings,
        errors=acc_errors,
        recommended_action=recommended_action,
        evaluated_at=evaluated_at,
    )

    # 9. Schema validation
    schema_errors = validate_slo_gating_decision(gating_decision)

    return {
        "gating_decision": gating_decision,
        "gating_outcome": gating_outcome,
        "schema_errors": schema_errors,
    }


# ---------------------------------------------------------------------------
# Diagnostics / observability helpers
# ---------------------------------------------------------------------------


def summarize_gating_decision(result: Dict[str, Any]) -> str:
    """Return a human-readable multi-line summary of a gating result.

    Parameters
    ----------
    result:
        Dict as returned by :func:`run_slo_gating`.
    """
    gd = result.get("gating_decision", {})
    lines = [
        "SLO Gating Decision",
        "-------------------",
        f"  gating_outcome           : {gd.get('gating_outcome', '(unknown)')}",
        f"  gating_reason_code       : {gd.get('gating_reason_code', '(unknown)')}",
        f"  recommended_action       : {gd.get('recommended_action', '(unknown)')}",
        f"  stage                    : {gd.get('stage', '(unknown)')}",
        f"  enforcement_status       : {gd.get('enforcement_decision_status', '(unknown)')}",
        f"  enforcement_policy       : {gd.get('enforcement_policy', '(unknown)')}",
        f"  traceability_integrity   : {gd.get('traceability_integrity_sli')}",
        f"  lineage_validation_mode  : {gd.get('lineage_validation_mode', '(unknown)')}",
        f"  lineage_defaulted        : {gd.get('lineage_defaulted')}",
        f"  lineage_valid            : {gd.get('lineage_valid')}",
        f"  source_decision_id       : {gd.get('source_decision_id', '(unknown)')}",
        f"  gating_decision_id       : {gd.get('gating_decision_id', '(unknown)')}",
        f"  evaluated_at             : {gd.get('evaluated_at', '(unknown)')}",
    ]
    warnings = gd.get("warnings") or []
    errors = gd.get("errors") or []
    schema_errs = result.get("schema_errors") or []

    if warnings:
        lines.append("  warnings:")
        for w in warnings:
            lines.append(f"    - {w}")
    if errors:
        lines.append("  errors:")
        for e in errors:
            lines.append(f"    - {e}")
    if schema_errs:
        lines.append("  schema_errors:")
        for se in schema_errs:
            lines.append(f"    - {se}")

    return "\n".join(lines)


def describe_stage_gating_posture(stage: Optional[str]) -> Dict[str, Any]:
    """Return a dict describing the gating posture for the given *stage*.

    Useful for diagnostics and operator tooling.
    """
    posture = resolve_stage_gating_posture(stage)
    return {
        "stage": posture["stage"],
        "stage_known": posture["stage_known"],
        "warnings_allowed": posture["warnings_allowed"],
        "decision_bearing": posture["decision_bearing"],
        "gating_posture": (
            "permissive (warnings allowed)"
            if posture["warnings_allowed"]
            else "strict (warnings halt)"
        ),
    }
