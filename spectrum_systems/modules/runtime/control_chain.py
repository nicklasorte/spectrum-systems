"""Control-Chain Orchestrator (BN.4).

Implements the **single canonical execution path** for decision-bearing pipeline
stages.  Enforcement and gating are non-optional: any stage in
{recommend, synthesis, export} **must** pass through the full control chain
before continuation is allowed.

Design principles
-----------------
- Single entry point:  :func:`run_control_chain` is the **only** public API.
  Calling enforcement or gating directly for decision-bearing stages bypasses
  this module; such misuse is detectable via the `blocking_layer` field in the
  produced artifact.
- Fail closed:  any malformed, missing, or contradictory input produces a
  governed ``continuation_allowed = False`` artifact, never a silent pass.
- Deterministic:  the same inputs always produce the same decision (aside from
  timestamps and generated IDs).
- Crash-proof:  all code paths catch exceptions and return governed failure
  artifacts rather than raising.
- Non-bypassable:  decision-bearing stages CANNOT continue without a
  ``gating_outcome != halt`` from a completed gating step.

Supported input kinds
---------------------
evaluation
    An ``slo_evaluation`` artifact.  The chain runs enforcement then gating.

enforcement
    An ``slo_enforcement_decision`` artifact.  The chain runs gating only.

gating
    An ``slo_gating_decision`` artifact.  The chain validates and returns
    (audit / replay mode).

Canonical execution path
------------------------
evaluation → enforcement → gating → control decision

For evaluation input:
    1. run_slo_enforcement  (mandatory)
    2. run_slo_gating       (mandatory)
    3. build control-chain artifact

For enforcement input:
    1. run_slo_gating       (mandatory)
    2. build control-chain artifact

For gating input:
    1. validate gating artifact
    2. build control-chain artifact (audit mode)

Continuation rules (non-negotiable)
------------------------------------
- IF stage ∈ {recommend, synthesis, export}
  AND gating has NOT been executed → HARD FAIL (blocking_layer = orchestration)
- IF gating_outcome == halt          → continuation_allowed = False
                                       (blocking_layer = gating)
- IF enforcement alone fails at a decision-bearing stage without gating
  → continuation_allowed = False      (blocking_layer = orchestration)
- IF gating cannot be evaluated      → HARD FAIL (fail closed)

Control-chain reason codes
--------------------------
control_chain_continue                   – full chain passed; continue
control_chain_continue_with_warning      – chain passed with warnings
control_chain_blocked_by_gating          – gating outcome was halt
control_chain_blocked_by_missing_gating  – gating was not executed for a
                                           decision-bearing stage
control_chain_blocked_by_malformed_input – input could not be parsed
control_chain_blocked_by_inconsistent_state – internally contradictory state

Recommended actions
-------------------
continue                        – proceed normally
continue_with_monitoring        – proceed but monitor
stop_and_review                 – stop; operator review required
stop_and_repair_lineage         – stop; lineage must be repaired
stop_and_rerun_with_registry    – stop; rerun with lineage registry
stop_and_escalate               – stop; escalate to governance

Exit codes (CLI)
----------------
0 – continue
1 – continue_with_warning
2 – blocked (halt)
3 – execution / malformed error

WARNING FOR CALLERS
-------------------
Do NOT call ``run_slo_enforcement`` or ``run_slo_gating`` directly for
decision-bearing stages (recommend, synthesis, export) and treat the result
as authoritative.  Those are lower-level tools.  **This module is the
required entry point for decision-grade operation.**
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker
from spectrum_systems.modules.runtime.contract_runtime import (  # noqa: E402
    ContractRuntimeError,
    ensure_contract_runtime_available,
    format_contract_runtime_error,
    get_contract_runtime_status,
)

# ---------------------------------------------------------------------------
# Schema / data paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_CONTROL_CHAIN_SCHEMA_PATH = _SCHEMA_DIR / "slo_control_chain_decision.schema.json"

# ---------------------------------------------------------------------------
# Contract / schema version
# ---------------------------------------------------------------------------

CONTRACT_VERSION: str = "1.0.0"

# ---------------------------------------------------------------------------
# Import lower-level modules (not to be called directly for decision stages)
# ---------------------------------------------------------------------------

from spectrum_systems.modules.runtime.slo_enforcement import (  # noqa: E402
    DECISION_ALLOW,
    DECISION_ALLOW_WITH_WARNING,
    DECISION_FAIL,
    run_slo_enforcement,
)
from spectrum_systems.modules.runtime.decision_gating import (  # noqa: E402
    OUTCOME_HALT,
    OUTCOME_PROCEED,
    OUTCOME_PROCEED_WITH_WARNING,
    STAGE_EXPORT,
    STAGE_RECOMMEND,
    STAGE_SYNTHESIS,
    run_slo_gating,
)
from spectrum_systems.modules.runtime.policy_registry import (  # noqa: E402
    DEFAULT_POLICY,
    KNOWN_STAGES,
    resolve_effective_slo_policy,
)
from spectrum_systems.modules.runtime.control_signals import (  # noqa: E402
    derive_control_signals,
    summarize_control_signals,
    explain_blocking_requirements,
    list_required_followups,
    validate_control_signals,
    KNOWN_CONTINUATION_MODES,
    KNOWN_CS_REASON_CODES,
    KNOWN_VALIDATORS,
    KNOWN_REPAIR_ACTIONS,
)
from spectrum_systems.modules.runtime.control_executor import (  # noqa: E402
    execute_control_signals,
)
from spectrum_systems.modules.runtime.replay_governance import (  # noqa: E402
    SYSTEM_RESPONSE_ALLOW,
    SYSTEM_RESPONSE_BLOCK,
    SYSTEM_RESPONSE_QUARANTINE,
    SYSTEM_RESPONSE_REQUIRE_REVIEW,
    build_replay_governance_decision,
    merge_system_responses,
    should_block_from_replay_governance,
    should_quarantine_from_replay_governance,
    should_require_review_from_replay_governance,
    summarize_replay_governance_decision,
)
from spectrum_systems.modules.runtime.trace_engine import (  # noqa: E402
    SPAN_STATUS_BLOCKED,
    SPAN_STATUS_OK,
    SpanNotFoundError,
    TraceNotFoundError,
    attach_artifact,
    end_span,
    record_event,
    start_span,
    start_trace,
    summarize_trace,
)

# ---------------------------------------------------------------------------
# Decision-bearing stages (mandatory gating required)
# ---------------------------------------------------------------------------

DECISION_BEARING_STAGES: frozenset = frozenset({
    STAGE_RECOMMEND,
    STAGE_SYNTHESIS,
    STAGE_EXPORT,
})

# ---------------------------------------------------------------------------
# Input kind constants
# ---------------------------------------------------------------------------

INPUT_KIND_EVALUATION: str = "evaluation"
INPUT_KIND_ENFORCEMENT: str = "enforcement"
INPUT_KIND_GATING: str = "gating"

KNOWN_INPUT_KINDS: frozenset = frozenset({
    INPUT_KIND_EVALUATION,
    INPUT_KIND_ENFORCEMENT,
    INPUT_KIND_GATING,
})

# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

REASON_CONTINUE: str = "control_chain_continue"
REASON_CONTINUE_WITH_WARNING: str = "control_chain_continue_with_warning"
REASON_BLOCKED_BY_GATING: str = "control_chain_blocked_by_gating"
REASON_BLOCKED_BY_MISSING_GATING: str = "control_chain_blocked_by_missing_gating"
REASON_BLOCKED_BY_MALFORMED_INPUT: str = "control_chain_blocked_by_malformed_input"
REASON_BLOCKED_BY_INCONSISTENT_STATE: str = "control_chain_blocked_by_inconsistent_state"

KNOWN_REASON_CODES: frozenset = frozenset({
    REASON_CONTINUE,
    REASON_CONTINUE_WITH_WARNING,
    REASON_BLOCKED_BY_GATING,
    REASON_BLOCKED_BY_MISSING_GATING,
    REASON_BLOCKED_BY_MALFORMED_INPUT,
    REASON_BLOCKED_BY_INCONSISTENT_STATE,
})

# ---------------------------------------------------------------------------
# Blocking layer constants
# ---------------------------------------------------------------------------

BLOCKING_NONE: str = "none"
BLOCKING_ENFORCEMENT: str = "enforcement"
BLOCKING_GATING: str = "gating"
BLOCKING_ORCHESTRATION: str = "orchestration"

KNOWN_BLOCKING_LAYERS: frozenset = frozenset({
    BLOCKING_NONE,
    BLOCKING_ENFORCEMENT,
    BLOCKING_GATING,
    BLOCKING_ORCHESTRATION,
})

# ---------------------------------------------------------------------------
# Recommended action constants
# ---------------------------------------------------------------------------

ACTION_CONTINUE: str = "continue"
ACTION_CONTINUE_WITH_MONITORING: str = "continue_with_monitoring"
ACTION_STOP_AND_REVIEW: str = "stop_and_review"
ACTION_STOP_AND_REPAIR_LINEAGE: str = "stop_and_repair_lineage"
ACTION_STOP_AND_RERUN_WITH_REGISTRY: str = "stop_and_rerun_with_registry"
ACTION_STOP_AND_ESCALATE: str = "stop_and_escalate"

KNOWN_RECOMMENDED_ACTIONS: frozenset = frozenset({
    ACTION_CONTINUE,
    ACTION_CONTINUE_WITH_MONITORING,
    ACTION_STOP_AND_REVIEW,
    ACTION_STOP_AND_REPAIR_LINEAGE,
    ACTION_STOP_AND_RERUN_WITH_REGISTRY,
    ACTION_STOP_AND_ESCALATE,
})

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _control_chain_id() -> str:
    """Generate a unique control-chain decision identifier with format CC-{12-char-hex}."""
    return "CC-" + uuid.uuid4().hex[:12].upper()


def _load_control_chain_schema() -> Dict[str, Any]:
    """Load the governed slo_control_chain_decision JSON Schema."""
    return json.loads(_CONTROL_CHAIN_SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Step 1 — Input normalisation and kind detection
# ---------------------------------------------------------------------------


def normalize_control_chain_inputs(
    raw: Any,
    explicit_input_kind: Optional[str] = None,
) -> Tuple[Optional[str], Dict[str, Any], List[str]]:
    """Normalise *raw* and detect its input kind.

    Parameters
    ----------
    raw:
        Raw input — typically a JSON-loaded dict.
    explicit_input_kind:
        If provided, override auto-detection.  Must be one of
        :data:`KNOWN_INPUT_KINDS`.

    Returns
    -------
    (input_kind, norm, errors)
        - ``input_kind``: detected or overridden kind, or ``None`` on failure
        - ``norm``: flat normalised field dict
        - ``errors``: list of error strings (empty on success)
    """
    errors: List[str] = []

    if not isinstance(raw, dict):
        errors.append(
            f"Expected dict input; got {type(raw).__name__}. "
            "Input must be a JSON artifact dict."
        )
        return None, {}, errors

    # Override takes priority
    if explicit_input_kind is not None:
        if explicit_input_kind not in KNOWN_INPUT_KINDS:
            errors.append(
                f"Unknown explicit input_kind '{explicit_input_kind}'. "
                f"Must be one of: {sorted(KNOWN_INPUT_KINDS)}"
            )
            return None, {}, errors
        return explicit_input_kind, raw, errors

    # Auto-detect: gating decision (or wrapped gating result)
    if "gating_decision_id" in raw or "gating_outcome" in raw:
        return INPUT_KIND_GATING, raw, errors
    # Wrapped gating result: {"gating_decision": {...}, "gating_outcome": ..., ...}
    if "gating_decision" in raw and "gating_outcome" in raw:
        return INPUT_KIND_GATING, raw.get("gating_decision", raw), errors

    # Auto-detect: enforcement decision (bare or wrapped)
    # Bare enforcement decision artifact
    if "decision_id" in raw or (
        "decision_status" in raw and "enforcement_policy" in raw
    ):
        return INPUT_KIND_ENFORCEMENT, raw, errors
    # Wrapped enforcement result: {"enforcement_decision": {...}, "decision_status": ..., ...}
    if "enforcement_decision" in raw and "decision_status" in raw:
        return INPUT_KIND_ENFORCEMENT, raw.get("enforcement_decision", raw), errors

    # Auto-detect: evaluation artifact
    if "evaluation_id" in raw or "slo_status" in raw or "slis" in raw:
        return INPUT_KIND_EVALUATION, raw, errors

    # Could not detect
    errors.append(
        "Could not auto-detect input kind. "
        "Artifact must contain 'gating_decision_id', 'decision_id', or 'evaluation_id'. "
        "Use --input-kind to override."
    )
    return None, raw, errors


# ---------------------------------------------------------------------------
# Step 2 — Stage resolution
# ---------------------------------------------------------------------------


def resolve_control_chain_stage(
    raw: Dict[str, Any],
    input_kind: str,
    stage_override: Optional[str] = None,
) -> Tuple[Optional[str], str]:
    """Resolve the effective stage from the artifact or override.

    Returns
    -------
    (stage, stage_source)
        - ``stage``: resolved stage name, or ``None`` if unknown
        - ``stage_source``: ``"override"`` or ``"original"``
    """
    if stage_override is not None:
        return stage_override, "override"

    # Try to extract stage from various artifact shapes
    if input_kind == INPUT_KIND_GATING:
        stage = raw.get("stage")
    elif input_kind == INPUT_KIND_ENFORCEMENT:
        stage = raw.get("enforcement_scope")
        if stage is None:
            # May be wrapped
            inner = raw.get("enforcement_decision") or {}
            stage = inner.get("enforcement_scope")
    else:
        # evaluation — stage is not reliably present; caller must provide it
        stage = raw.get("stage") or raw.get("enforcement_scope")

    return (stage or None), "original"


# ---------------------------------------------------------------------------
# Step 3 — Mandatory gating check for decision-bearing stages
# ---------------------------------------------------------------------------


def check_mandatory_gating(
    stage: Optional[str],
    gating_executed: bool,
    gating_outcome: Optional[str],
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Enforce the mandatory gating rule for decision-bearing stages.

    Parameters
    ----------
    stage:
        Resolved stage name (may be ``None`` for unknown stages).
    gating_executed:
        True when gating was actually run in this chain.
    gating_outcome:
        The gating outcome string (e.g. ``"halt"``, ``"proceed"``), or
        ``None`` when gating was not executed.

    Returns
    -------
    (continuation_allowed, blocking_layer, reason_code)
    """
    is_decision_bearing = stage in DECISION_BEARING_STAGES

    if is_decision_bearing and not gating_executed:
        return (
            False,
            BLOCKING_ORCHESTRATION,
            REASON_BLOCKED_BY_MISSING_GATING,
        )

    if gating_outcome == OUTCOME_HALT:
        return (
            False,
            BLOCKING_GATING,
            REASON_BLOCKED_BY_GATING,
        )

    return True, None, None


# ---------------------------------------------------------------------------
# Step 4 — Derive final reason code
# ---------------------------------------------------------------------------


def derive_control_chain_reason_code(
    continuation_allowed: bool,
    blocking_layer: Optional[str],
    override_reason: Optional[str],
    gating_outcome: Optional[str],
    enforcement_status: Optional[str],
    has_warnings: bool,
) -> str:
    """Derive the primary reason code for the control-chain decision.

    Parameters
    ----------
    continuation_allowed:
        Whether continuation is permitted.
    blocking_layer:
        The layer that blocked, or ``None`` / ``"none"`` when allowed.
    override_reason:
        A reason code that was pre-determined (e.g. from malformed input).
    gating_outcome:
        The gating outcome string, or ``None``.
    enforcement_status:
        The enforcement decision status, or ``None``.
    has_warnings:
        True when warnings were accumulated in the chain.
    """
    if override_reason is not None and override_reason in KNOWN_REASON_CODES:
        return override_reason

    if not continuation_allowed:
        if blocking_layer == BLOCKING_ORCHESTRATION:
            return REASON_BLOCKED_BY_MISSING_GATING
        if blocking_layer == BLOCKING_GATING:
            return REASON_BLOCKED_BY_GATING
        if blocking_layer == BLOCKING_ENFORCEMENT:
            # enforcement-only block should not reach here for decision stages
            # (gating is mandatory), but handle it defensively
            return REASON_BLOCKED_BY_INCONSISTENT_STATE
        return REASON_BLOCKED_BY_INCONSISTENT_STATE

    if has_warnings or gating_outcome == OUTCOME_PROCEED_WITH_WARNING:
        return REASON_CONTINUE_WITH_WARNING

    return REASON_CONTINUE


# ---------------------------------------------------------------------------
# Step 5 — Derive recommended action
# ---------------------------------------------------------------------------


def derive_control_chain_recommended_action(
    reason_code: str,
    enforcement_status: Optional[str],
    gating_outcome: Optional[str],
) -> str:
    """Map a reason code to a recommended action.

    Deterministic mapping — same inputs always produce the same output.
    """
    _MAP: Dict[str, str] = {
        REASON_CONTINUE: ACTION_CONTINUE,
        REASON_CONTINUE_WITH_WARNING: ACTION_CONTINUE_WITH_MONITORING,
        REASON_BLOCKED_BY_GATING: ACTION_STOP_AND_REVIEW,
        REASON_BLOCKED_BY_MISSING_GATING: ACTION_STOP_AND_ESCALATE,
        REASON_BLOCKED_BY_MALFORMED_INPUT: ACTION_STOP_AND_REVIEW,
        REASON_BLOCKED_BY_INCONSISTENT_STATE: ACTION_STOP_AND_ESCALATE,
    }
    action = _MAP.get(reason_code, ACTION_STOP_AND_ESCALATE)

    # Refine for lineage-specific cases
    if reason_code == REASON_BLOCKED_BY_GATING:
        if enforcement_status == DECISION_ALLOW_WITH_WARNING:
            action = ACTION_STOP_AND_REPAIR_LINEAGE
        elif gating_outcome == OUTCOME_HALT and enforcement_status == DECISION_FAIL:
            action = ACTION_STOP_AND_REVIEW

    return action


# ---------------------------------------------------------------------------
# Step 6 — Build governed artifact
# ---------------------------------------------------------------------------


def build_control_chain_decision(
    *,
    artifact_id: str,
    stage: Optional[str],
    input_kind: str,
    enforcement_decision_id: str,
    gating_decision_id: str,
    enforcement_policy: str,
    enforcement_decision_status: str,
    gating_outcome: str,
    continuation_allowed: bool,
    blocking_layer: str,
    primary_reason_code: str,
    ti_value: Any,
    lineage_mode: Optional[str],
    lineage_defaulted: Optional[Any],
    lineage_valid: Optional[Any],
    warnings: List[str],
    errors: List[str],
    recommended_action: str,
    control_signals: Optional[Dict[str, Any]] = None,
    stage_source: Optional[str] = None,
    evaluated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct the governed ``slo_control_chain_decision`` artifact.

    All fields are explicitly set; no implicit defaults are allowed.
    """
    ts = evaluated_at or _now_iso()
    cc_id = _control_chain_id()

    artifact: Dict[str, Any] = {
        "control_chain_decision_id": cc_id,
        "artifact_id": artifact_id if artifact_id else "missing_artifact_id",
        "stage": stage if stage else "unspecified_stage",
        "input_kind": input_kind,
        "enforcement_decision_id": enforcement_decision_id,
        "gating_decision_id": gating_decision_id,
        "enforcement_policy": enforcement_policy,
        "enforcement_decision_status": enforcement_decision_status,
        "gating_outcome": gating_outcome,
        "continuation_allowed": bool(continuation_allowed),
        "blocking_layer": blocking_layer,
        "primary_reason_code": primary_reason_code,
        "traceability_integrity_sli": (
            ti_value if isinstance(ti_value, (int, float)) else None
        ),
        "lineage_validation_mode": lineage_mode if lineage_mode else "unspecified_lineage_mode",
        "lineage_defaulted": (
            lineage_defaulted if isinstance(lineage_defaulted, bool) else None
        ),
        "lineage_valid": (
            bool(lineage_valid) if lineage_valid is not None else None
        ),
        "warnings": list(warnings),
        "errors": list(errors),
        "recommended_action": recommended_action,
        "control_signals": control_signals if control_signals is not None else {},
        "evaluated_at": ts,
        "schema_version": CONTRACT_VERSION,
    }

    if stage_source is not None:
        artifact["stage_source"] = stage_source

    return artifact


# ---------------------------------------------------------------------------
# Step 7 — Schema validation
# ---------------------------------------------------------------------------


def validate_control_chain_decision(
    decision: Dict[str, Any],
) -> List[str]:
    """Validate *decision* against the control-chain decision JSON Schema.

    Returns a (possibly empty) list of human-readable error strings.
    """
    try:
        schema = _load_control_chain_schema()
    except Exception as exc:  # noqa: BLE001
        return [f"Could not load control-chain decision schema: {exc}"]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(decision), key=lambda e: list(e.absolute_path))
    ]


# ---------------------------------------------------------------------------
# Step 8 — Operator-readable summary
# ---------------------------------------------------------------------------


def summarize_control_chain_decision(result: Dict[str, Any]) -> str:
    """Return a human-readable multi-line summary of a control-chain result."""
    cd = result.get("control_chain_decision") or {}
    lines = [
        "SLO Control-Chain Decision (BN.4 / BN.5)",
        "-----------------------------------------",
        f"  continuation_allowed     : {cd.get('continuation_allowed')}",
        f"  primary_reason_code      : {cd.get('primary_reason_code', '(unknown)')}",
        f"  recommended_action       : {cd.get('recommended_action', '(unknown)')}",
        f"  blocking_layer           : {cd.get('blocking_layer', '(unknown)')}",
        f"  stage                    : {cd.get('stage', '(unknown)')}",
        f"  input_kind               : {cd.get('input_kind', '(unknown)')}",
        f"  enforcement_policy       : {cd.get('enforcement_policy', '(unknown)')}",
        f"  enforcement_status       : {cd.get('enforcement_decision_status', '(unknown)')}",
        f"  gating_outcome           : {cd.get('gating_outcome', '(unknown)')}",
        f"  traceability_integrity   : {cd.get('traceability_integrity_sli')}",
        f"  lineage_validation_mode  : {cd.get('lineage_validation_mode', '(unknown)')}",
        f"  lineage_defaulted        : {cd.get('lineage_defaulted')}",
        f"  lineage_valid            : {cd.get('lineage_valid')}",
        f"  enforcement_decision_id  : {cd.get('enforcement_decision_id', '(none)')}",
        f"  gating_decision_id       : {cd.get('gating_decision_id', '(none)')}",
        f"  control_chain_decision_id: {cd.get('control_chain_decision_id', '(unknown)')}",
        f"  evaluated_at             : {cd.get('evaluated_at', '(unknown)')}",
    ]
    warnings = cd.get("warnings") or []
    errors = cd.get("errors") or []
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

    # BN.5 control signals summary
    cs = cd.get("control_signals") or {}
    if cs:
        lines.append("")
        lines.append(summarize_control_signals(cs))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 9 — Canonical orchestration
# ---------------------------------------------------------------------------


def _run_control_chain_inner(
    raw_input: Any,
    stage_override: Optional[str],
    policy_override: Optional[str],
    input_kind_override: Optional[str],
    evaluated_at: Optional[str],
    execute: bool,
    replay_governance_artifact: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Inner control-chain pipeline — called by :func:`run_control_chain`."""

    acc_warnings: List[str] = []
    acc_errors: List[str] = []

    # ------------------------------------------------------------------ #
    # BK–BM: Start trace for this control chain run
    # ------------------------------------------------------------------ #
    trace_id = start_trace({"source": "control_chain"})
    root_span_id: Optional[str] = None
    enforcement_span_id: Optional[str] = None
    gating_span_id: Optional[str] = None
    try:
        root_span_id = start_span(trace_id, "control_chain")
    except (TraceNotFoundError, SpanNotFoundError):
        root_span_id = None

    # ------------------------------------------------------------------ #
    # 1. Normalise inputs and detect kind
    # ------------------------------------------------------------------ #
    input_kind, norm, detect_errors = normalize_control_chain_inputs(
        raw_input, explicit_input_kind=input_kind_override
    )
    acc_errors.extend(detect_errors)

    if input_kind is None:
        # Malformed / undetectable input — fail closed immediately
        if root_span_id:
            try:
                record_event(root_span_id, "chain_blocked", {"reason": "malformed_input"})
                end_span(root_span_id, SPAN_STATUS_BLOCKED)
            except (TraceNotFoundError, SpanNotFoundError):
                pass
        return _make_error_artifact(
            acc_warnings=acc_warnings,
            acc_errors=acc_errors,
            reason_code=REASON_BLOCKED_BY_MALFORMED_INPUT,
            evaluated_at=evaluated_at,
            execute=execute,
            trace_id=trace_id,
        )

    # ------------------------------------------------------------------ #
    # 2. Resolve stage
    # ------------------------------------------------------------------ #
    stage, stage_source = resolve_control_chain_stage(
        norm, input_kind, stage_override=stage_override
    )

    if stage_override is not None and stage_override != stage:
        acc_warnings.append(
            f"Stage override '{stage_override}' applied; "
            f"artifact stage may differ."
        )

    # ------------------------------------------------------------------ #
    # 3. Route through the canonical chain
    # ------------------------------------------------------------------ #

    enforcement_result: Optional[Dict[str, Any]] = None
    gating_result: Optional[Dict[str, Any]] = None
    gating_executed: bool = False

    if input_kind == INPUT_KIND_EVALUATION:
        # Must run enforcement then gating.
        policy = policy_override or _resolve_policy_for_stage(stage)
        try:
            # BK–BM: span for enforcement
            try:
                enforcement_span_id = start_span(trace_id, "enforcement", root_span_id)
            except (TraceNotFoundError, SpanNotFoundError):
                enforcement_span_id = None
            enforcement_result = run_slo_enforcement(
                norm, policy=policy, stage=stage
            )
            if enforcement_span_id:
                try:
                    enf_status = (enforcement_result.get("enforcement_decision") or {}).get("decision_status", "unknown")
                    record_event(enforcement_span_id, "enforcement_complete", {"decision_status": enf_status})
                    end_span(enforcement_span_id, SPAN_STATUS_OK)
                except (TraceNotFoundError, SpanNotFoundError):
                    pass
        except Exception as exc:  # noqa: BLE001
            if enforcement_span_id:
                try:
                    end_span(enforcement_span_id, SPAN_STATUS_ERROR)
                except (TraceNotFoundError, SpanNotFoundError):
                    pass
            acc_errors.append(f"Enforcement step raised unexpectedly: {exc}")
            if root_span_id:
                try:
                    record_event(root_span_id, "chain_blocked", {"reason": "enforcement_exception"})
                    end_span(root_span_id, SPAN_STATUS_BLOCKED)
                except (TraceNotFoundError, SpanNotFoundError):
                    pass
            return _make_error_artifact(
                acc_warnings=acc_warnings,
                acc_errors=acc_errors,
                reason_code=REASON_BLOCKED_BY_MALFORMED_INPUT,
                evaluated_at=evaluated_at,
                execute=execute,
                trace_id=trace_id,
            )

        # Accumulate any enforcement warnings
        enf_artifact = enforcement_result.get("enforcement_decision") or enforcement_result
        acc_warnings.extend(enf_artifact.get("warnings") or [])
        acc_errors.extend(enforcement_result.get("schema_errors") or [])

        # Now run gating on the enforcement result
        try:
            # BK–BM: span for gating
            try:
                gating_span_id = start_span(trace_id, "gating", root_span_id)
            except (TraceNotFoundError, SpanNotFoundError):
                gating_span_id = None
            gating_result = run_slo_gating(
                enforcement_result, stage=stage, evaluated_at=evaluated_at
            )
            gating_executed = True
            if gating_span_id:
                try:
                    g_outcome = gating_result.get("gating_outcome") or "(unknown)"
                    record_event(gating_span_id, "gating_complete", {"gating_outcome": g_outcome})
                    g_span_st = SPAN_STATUS_OK if g_outcome != "halt" else SPAN_STATUS_BLOCKED
                    end_span(gating_span_id, g_span_st)
                except (TraceNotFoundError, SpanNotFoundError):
                    pass
        except Exception as exc:  # noqa: BLE001
            if gating_span_id:
                try:
                    end_span(gating_span_id, SPAN_STATUS_ERROR)
                except (TraceNotFoundError, SpanNotFoundError):
                    pass
            acc_errors.append(f"Gating step raised unexpectedly: {exc}")
            if root_span_id:
                try:
                    record_event(root_span_id, "chain_blocked", {"reason": "gating_exception"})
                    end_span(root_span_id, SPAN_STATUS_BLOCKED)
                except (TraceNotFoundError, SpanNotFoundError):
                    pass
            return _make_error_artifact(
                acc_warnings=acc_warnings,
                acc_errors=acc_errors,
                reason_code=REASON_BLOCKED_BY_MISSING_GATING,
                stage=stage,
                stage_source=stage_source,
                evaluated_at=evaluated_at,
                execute=execute,
                trace_id=trace_id,
            )

    elif input_kind == INPUT_KIND_ENFORCEMENT:
        # Must run gating only.
        if policy_override is not None:
            acc_warnings.append(
                f"policy_override '{policy_override}' is ignored for enforcement input "
                "(policy is already embedded in the enforcement artifact)."
            )
        try:
            # BK–BM: span for gating
            try:
                gating_span_id = start_span(trace_id, "gating", root_span_id)
            except (TraceNotFoundError, SpanNotFoundError):
                gating_span_id = None
            gating_result = run_slo_gating(
                norm, stage=stage_override or stage, evaluated_at=evaluated_at
            )
            gating_executed = True
            if gating_span_id:
                try:
                    g_outcome = gating_result.get("gating_outcome") or "(unknown)"
                    record_event(gating_span_id, "gating_complete", {"gating_outcome": g_outcome})
                    g_span_st = SPAN_STATUS_OK if g_outcome != "halt" else SPAN_STATUS_BLOCKED
                    end_span(gating_span_id, g_span_st)
                except (TraceNotFoundError, SpanNotFoundError):
                    pass
        except Exception as exc:  # noqa: BLE001
            if gating_span_id:
                try:
                    end_span(gating_span_id, SPAN_STATUS_ERROR)
                except (TraceNotFoundError, SpanNotFoundError):
                    pass
            acc_errors.append(f"Gating step raised unexpectedly: {exc}")
            if root_span_id:
                try:
                    record_event(root_span_id, "chain_blocked", {"reason": "gating_exception"})
                    end_span(root_span_id, SPAN_STATUS_BLOCKED)
                except (TraceNotFoundError, SpanNotFoundError):
                    pass
            return _make_error_artifact(
                acc_warnings=acc_warnings,
                acc_errors=acc_errors,
                reason_code=REASON_BLOCKED_BY_MISSING_GATING,
                stage=stage,
                stage_source=stage_source,
                evaluated_at=evaluated_at,
                execute=execute,
                trace_id=trace_id,
            )

    elif input_kind == INPUT_KIND_GATING:
        # Audit / replay mode — validate and return.
        gating_result = {"gating_decision": norm, "gating_outcome": norm.get("gating_outcome"), "schema_errors": []}
        gating_executed = True
        acc_warnings.append(
            "Control chain running in audit mode (gating input). "
            "No enforcement was run; this result is for replay/audit only."
        )

    # ------------------------------------------------------------------ #
    # 4. Extract gating fields
    # ------------------------------------------------------------------ #
    gating_decision_artifact: Dict[str, Any] = {}
    gating_outcome_str: str = "(none)"
    gating_decision_id_str: str = "(none)"

    if gating_result is not None:
        gating_decision_artifact = gating_result.get("gating_decision") or {}
        gating_outcome_str = gating_result.get("gating_outcome") or gating_decision_artifact.get("gating_outcome") or "(unknown)"
        gating_decision_id_str = gating_decision_artifact.get("gating_decision_id") or "(unknown)"
        acc_warnings.extend(gating_decision_artifact.get("warnings") or [])
        acc_errors.extend(gating_decision_artifact.get("errors") or [])
        acc_errors.extend(gating_result.get("schema_errors") or [])
        # Add a synthesized warning if gating outcome is proceed_with_warning
        if gating_outcome_str == OUTCOME_PROCEED_WITH_WARNING:
            acc_warnings.append(
                "Gating outcome is proceed_with_warning: lineage or enforcement state "
                "is degraded. Continuation is permitted at this stage but requires monitoring."
            )

    # ------------------------------------------------------------------ #
    # 5. Extract enforcement fields
    # ------------------------------------------------------------------ #
    enforcement_decision_artifact: Dict[str, Any] = {}
    enforcement_decision_id_str: str = "(none)"
    enforcement_decision_status_str: str = "(unknown)"
    enforcement_policy_str: str = "(unknown)"
    ti_value: Any = None
    lineage_mode: Optional[str] = None
    lineage_defaulted: Optional[Any] = None
    lineage_valid: Optional[Any] = None

    if enforcement_result is not None:
        enforcement_decision_artifact = (
            enforcement_result.get("enforcement_decision") or enforcement_result
        )
        enforcement_decision_id_str = enforcement_decision_artifact.get("decision_id") or "(unknown)"
        enforcement_decision_status_str = enforcement_decision_artifact.get("decision_status") or "(unknown)"
        enforcement_policy_str = enforcement_decision_artifact.get("enforcement_policy") or "(unknown)"
        ti_value = enforcement_decision_artifact.get("traceability_integrity_sli")
        lineage_mode = enforcement_decision_artifact.get("lineage_validation_mode")
        lineage_defaulted = enforcement_decision_artifact.get("lineage_defaulted")
        lineage_valid = enforcement_decision_artifact.get("lineage_valid")
    elif input_kind == INPUT_KIND_ENFORCEMENT:
        # Enforcement artifact is the input itself
        enforcement_decision_id_str = norm.get("decision_id") or "(unknown)"
        enforcement_decision_status_str = norm.get("decision_status") or "(unknown)"
        enforcement_policy_str = norm.get("enforcement_policy") or "(unknown)"
        ti_value = norm.get("traceability_integrity_sli")
        lineage_mode = norm.get("lineage_validation_mode")
        lineage_defaulted = norm.get("lineage_defaulted")
        lineage_valid = norm.get("lineage_valid")
    elif input_kind == INPUT_KIND_GATING:
        # Extract from gating artifact (pass-through)
        enforcement_decision_id_str = norm.get("source_decision_id") or "(unknown)"
        enforcement_decision_status_str = norm.get("enforcement_decision_status") or "(unknown)"
        enforcement_policy_str = norm.get("enforcement_policy") or "(unknown)"
        ti_value = norm.get("traceability_integrity_sli")
        lineage_mode = norm.get("lineage_validation_mode")
        lineage_defaulted = norm.get("lineage_defaulted")
        lineage_valid = norm.get("lineage_valid")

    # ------------------------------------------------------------------ #
    # 6. Resolve artifact_id
    # ------------------------------------------------------------------ #
    artifact_id_str: str = (
        enforcement_decision_artifact.get("artifact_id")
        or gating_decision_artifact.get("artifact_id")
        or norm.get("artifact_id")
        or "(unknown)"
    )

    # Fail closed: governed producer paths must not emit placeholder policy linkage.
    if enforcement_policy_str in {"(unknown)", ""}:
        acc_errors.append(
            "Missing enforcement policy linkage: enforcement_policy must be explicit."
        )
        return _make_error_artifact(
            acc_warnings=acc_warnings,
            acc_errors=acc_errors,
            reason_code=REASON_BLOCKED_BY_INCONSISTENT_STATE,
            stage=stage,
            stage_source=stage_source,
            evaluated_at=evaluated_at,
            execute=execute,
            trace_id=trace_id,
        )

    if enforcement_decision_status_str in {"(unknown)", ""}:
        acc_errors.append(
            "Missing enforcement decision status: enforcement_decision_status must be explicit."
        )
        return _make_error_artifact(
            acc_warnings=acc_warnings,
            acc_errors=acc_errors,
            reason_code=REASON_BLOCKED_BY_INCONSISTENT_STATE,
            stage=stage,
            stage_source=stage_source,
            evaluated_at=evaluated_at,
            execute=execute,
            trace_id=trace_id,
        )

    # ------------------------------------------------------------------ #
    # 7. Mandatory gating enforcement
    # ------------------------------------------------------------------ #
    continuation_allowed, blocking_layer_val, mandatory_reason = check_mandatory_gating(
        stage=stage,
        gating_executed=gating_executed,
        gating_outcome=gating_outcome_str if gating_executed else None,
    )

    if blocking_layer_val is None:
        blocking_layer_val = BLOCKING_NONE

    # ------------------------------------------------------------------ #
    # 8. Derive reason code and recommended action
    # ------------------------------------------------------------------ #
    reason_code = derive_control_chain_reason_code(
        continuation_allowed=continuation_allowed,
        blocking_layer=blocking_layer_val,
        override_reason=mandatory_reason,
        gating_outcome=gating_outcome_str,
        enforcement_status=enforcement_decision_status_str,
        has_warnings=bool(acc_warnings),
    )

    recommended_action = derive_control_chain_recommended_action(
        reason_code=reason_code,
        enforcement_status=enforcement_decision_status_str,
        gating_outcome=gating_outcome_str,
    )

    # ------------------------------------------------------------------ #
    # 9. Derive control signals (BN.5)
    # ------------------------------------------------------------------ #
    cs = derive_control_signals(
        continuation_allowed=continuation_allowed,
        primary_reason_code=reason_code,
        gating_outcome=gating_outcome_str,
        enforcement_status=enforcement_decision_status_str,
        lineage_defaulted=lineage_defaulted if isinstance(lineage_defaulted, bool) else None,
        lineage_valid=lineage_valid if isinstance(lineage_valid, bool) else None,
        stage=stage,
        has_schema_errors=False,  # schema errors discovered in step 10; pre-flight clean
        required_inputs=None,
        traceability_integrity_sli=ti_value if isinstance(ti_value, (int, float)) else None,
    )

    # ------------------------------------------------------------------ #
    # 10. Build artifact
    # ------------------------------------------------------------------ #
    control_chain_decision = build_control_chain_decision(
        artifact_id=artifact_id_str,
        stage=stage,
        input_kind=input_kind,
        enforcement_decision_id=enforcement_decision_id_str,
        gating_decision_id=gating_decision_id_str,
        enforcement_policy=enforcement_policy_str,
        enforcement_decision_status=enforcement_decision_status_str,
        gating_outcome=gating_outcome_str,
        continuation_allowed=continuation_allowed,
        blocking_layer=blocking_layer_val,
        primary_reason_code=reason_code,
        ti_value=ti_value,
        lineage_mode=lineage_mode,
        lineage_defaulted=lineage_defaulted,
        lineage_valid=lineage_valid,
        warnings=acc_warnings,
        errors=acc_errors,
        recommended_action=recommended_action,
        control_signals=cs,
        stage_source=stage_source,
        evaluated_at=evaluated_at,
    )

    # ------------------------------------------------------------------ #
    # 11. Schema validation
    # ------------------------------------------------------------------ #
    schema_errors = validate_control_chain_decision(control_chain_decision)

    # BK–BM: attach trace_id to the decision artifact and close the root span
    control_chain_decision["trace_id"] = trace_id
    decision_id = control_chain_decision.get("decision_id") or "(unknown)"

    # ------------------------------------------------------------------ #
    # 11.5  BY — Replay governance gate
    # Apply the replay governance artifact (if provided) and merge its
    # system_response with the existing continuation decision using
    # strict-precedence merging.  block > quarantine > require_review > allow.
    # ------------------------------------------------------------------ #
    replay_gov_result: Optional[Dict[str, Any]] = replay_governance_artifact
    replay_gov_summary: Optional[Dict[str, Any]] = None

    if replay_gov_result is not None:
        try:
            replay_gov_summary = summarize_replay_governance_decision(replay_gov_result)
            rg_response = (replay_gov_result.get("decision") or {}).get("system_response", SYSTEM_RESPONSE_ALLOW)

            # Map current continuation_allowed to a system_response for merging
            current_response = SYSTEM_RESPONSE_ALLOW if continuation_allowed else SYSTEM_RESPONSE_BLOCK

            merged = merge_system_responses([current_response, rg_response])
            if merged == SYSTEM_RESPONSE_BLOCK:
                continuation_allowed = False
                if blocking_layer_val == BLOCKING_NONE:
                    blocking_layer_val = "replay_governance"
                acc_warnings.append(
                    f"Replay governance blocked execution: "
                    f"rationale_code={replay_gov_summary.get('replay_governance_rationale_code')}"
                )
            elif merged in {SYSTEM_RESPONSE_QUARANTINE, SYSTEM_RESPONSE_REQUIRE_REVIEW}:
                # Execution must not proceed automatically; downgrade to not allowed
                continuation_allowed = False
                if blocking_layer_val == BLOCKING_NONE:
                    blocking_layer_val = "replay_governance"
                acc_warnings.append(
                    f"Replay governance escalated to {merged}: "
                    f"rationale_code={replay_gov_summary.get('replay_governance_rationale_code')}"
                )

            # BZ/BAA: Propagate replay governance into the formally declared schema shape.
            # Ad-hoc flat fields replaced by the nested replay_governance object.
            replay_governed_val = bool(
                replay_gov_summary.get("replay_governance_replay_governed", True)
            )
            rg_obj: Dict[str, Any] = {
                "present": True,
                "replay_governed": replay_governed_val,
                "system_response": rg_response,
                "severity": replay_gov_summary.get("replay_governance_severity"),
                "rationale_code": replay_gov_summary.get("replay_governance_rationale_code"),
                "status": replay_gov_summary.get("artifact_status"),
                "escalated_final_decision": replay_gov_summary.get(
                    "replay_governance_escalated_final_decision", False
                ),
            }
            if replay_gov_summary.get("replay_status") is not None:
                rg_obj["replay_status"] = replay_gov_summary["replay_status"]
            if replay_gov_summary.get("replay_consistency_sli") is not None:
                rg_obj["replay_consistency_sli"] = replay_gov_summary["replay_consistency_sli"]
            # BAA: Propagate replay_decision_status from governance artifact
            rds = replay_gov_result.get("replay_decision_status")
            if rds is not None:
                rg_obj["replay_decision_status"] = rds
            control_chain_decision["replay_governance"] = rg_obj
            # Update continuation_allowed and blocking_layer in the artifact to reflect merged decision
            control_chain_decision["continuation_allowed"] = continuation_allowed
            control_chain_decision["blocking_layer"] = blocking_layer_val

            # Emit trace event for replay governance decision
            if root_span_id:
                try:
                    record_event(root_span_id, "replay_governance_applied", {
                        "replay_governance_response": rg_response,
                        "merged_response": merged,
                        "continuation_allowed": continuation_allowed,
                        "rationale_code": replay_gov_summary.get("replay_governance_rationale_code"),
                        "replay_decision_status": rds,
                    })
                except (TraceNotFoundError, SpanNotFoundError):
                    pass

        except Exception as exc:  # noqa: BLE001
            # Fail closed: governance integration error must not silently allow
            continuation_allowed = False
            acc_errors.append(
                f"Replay governance integration raised unexpectedly: {exc}"
            )
            control_chain_decision["continuation_allowed"] = False

    if root_span_id:
        try:
            cc_span_st = SPAN_STATUS_OK if continuation_allowed else SPAN_STATUS_BLOCKED
            record_event(root_span_id, "chain_complete", {
                "continuation_allowed": continuation_allowed,
                "primary_reason_code": reason_code,
                "decision_id": decision_id,
            })
            end_span(root_span_id, cc_span_st)
            attach_artifact(trace_id, decision_id, "control_chain_decision", root_span_id)
        except (TraceNotFoundError, SpanNotFoundError):
            pass

    result = {
        "control_chain_decision": control_chain_decision,
        "continuation_allowed": continuation_allowed,
        "primary_reason_code": reason_code,
        "schema_errors": schema_errors,
        # Surface intermediate artifacts for caller inspection
        "enforcement_result": enforcement_result,
        "gating_result": gating_result,
        "trace_id": trace_id,
        "replay_governance_result": replay_gov_result,
        "replay_governance_summary": replay_gov_summary,
    }
    if execute:
        result["execution_result"] = execute_control_signals(
            cs,
            context={
                "artifact": control_chain_decision,
                "stage": stage,
                "runtime_environment": "control_chain",
                "trace_id": trace_id,
                "parent_span_id": root_span_id,
            },
        )
    return result


def _resolve_policy_for_stage(stage: Optional[str]) -> str:
    """Return the default policy for *stage*, or the global default."""
    if stage is None:
        return DEFAULT_POLICY
    try:
        return resolve_effective_slo_policy(stage=stage, policy_override=None)
    except Exception:  # noqa: BLE001
        return DEFAULT_POLICY


def _make_error_artifact(
    *,
    acc_warnings: List[str],
    acc_errors: List[str],
    reason_code: str,
    stage: Optional[str] = None,
    stage_source: Optional[str] = None,
    evaluated_at: Optional[str] = None,
    execute: bool = False,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct a governed fail-closed control-chain result."""
    cs = derive_control_signals(
        continuation_allowed=False,
        primary_reason_code=reason_code,
        gating_outcome=None,
        enforcement_status=None,
        lineage_defaulted=None,
        lineage_valid=None,
        stage=stage,
        has_schema_errors=False,
        required_inputs=None,
        traceability_integrity_sli=None,
    )
    decision = build_control_chain_decision(
        artifact_id="missing_artifact_id",
        stage=stage,
        input_kind=INPUT_KIND_EVALUATION,  # best guess for error paths
        enforcement_decision_id="(none)",
        gating_decision_id="(none)",
        enforcement_policy="missing_enforcement_policy",
        enforcement_decision_status="missing_enforcement_decision_status",
        gating_outcome="(none)",
        continuation_allowed=False,
        blocking_layer=BLOCKING_ORCHESTRATION,
        primary_reason_code=reason_code,
        ti_value=None,
        lineage_mode=None,
        lineage_defaulted=None,
        lineage_valid=None,
        warnings=acc_warnings,
        errors=acc_errors,
        recommended_action=derive_control_chain_recommended_action(
            reason_code=reason_code,
            enforcement_status=None,
            gating_outcome=None,
        ),
        control_signals=cs,
        stage_source=stage_source,
        evaluated_at=evaluated_at,
    )
    if trace_id:
        decision["trace_id"] = trace_id
    schema_errors = validate_control_chain_decision(decision)
    result = {
        "control_chain_decision": decision,
        "continuation_allowed": False,
        "primary_reason_code": reason_code,
        "schema_errors": schema_errors,
        "enforcement_result": None,
        "gating_result": None,
        "trace_id": trace_id,
        "replay_governance_result": None,
        "replay_governance_summary": None,
    }
    if execute:
        result["execution_result"] = execute_control_signals(
            cs,
            context={
                "artifact": decision,
                "stage": stage,
                "runtime_environment": "control_chain_error",
                "trace_id": trace_id,
            },
        )
    return result


# ---------------------------------------------------------------------------
# Public API — REQUIRED entry point for decision-grade operation
# ---------------------------------------------------------------------------


def run_control_chain(
    raw_input: Any,
    stage: Optional[str] = None,
    policy: Optional[str] = None,
    input_kind: Optional[str] = None,
    evaluated_at: Optional[str] = None,
    execute: bool = False,
    replay_governance_decision: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the full SLO control chain.

    **This is the REQUIRED entry point for decision-grade operation.**
    Decision-bearing stages (recommend, synthesis, export) MUST use this
    function.  Calling ``run_slo_enforcement`` or ``run_slo_gating`` directly
    does not constitute passing the control chain.

    Parameters
    ----------
    raw_input:
        A JSON-loaded artifact dict.  Auto-detected as evaluation,
        enforcement, or gating input.
    stage:
        Override the pipeline stage.  When ``None``, the stage is extracted
        from the artifact.
    policy:
        Override the enforcement policy profile.  When ``None``, the default
        stage-based policy is used.
    input_kind:
        Override the detected input kind.  One of ``"evaluation"``,
        ``"enforcement"``, ``"gating"``.  Use the safer explicit form when
        the input shape is ambiguous.
    evaluated_at:
        Override the evaluation timestamp.  Defaults to now.
    execute:
        When true, executes BN.6 control-signal consumption and returns an
        ``execution_result`` field alongside the decision artifact.
    replay_governance_decision:
        Optional ``replay_governance_decision`` artifact from the BY Replay
        Governance Gate.  When provided, its ``system_response`` is merged
        with the control-chain decision using strict-precedence merging
        (block > quarantine > require_review > allow).  A quarantine or
        require_review response prevents automatic continuation.  A block
        response halts execution entirely.

    Returns
    -------
    dict with keys:
        ``control_chain_decision``   – governed artifact
        ``continuation_allowed``     – bool shortcut
        ``primary_reason_code``      – shortcut
        ``schema_errors``            – list of schema validation errors
        ``enforcement_result``       – enforcement step result (may be None)
        ``gating_result``            – gating step result (may be None)
        ``execution_result``         – present only when ``execute=True``
        ``replay_governance_result`` – replay governance artifact (may be None)
        ``replay_governance_summary`` – concise replay governance summary (may be None)
    """
    # BN.6.1: Fail closed if the contract-validation runtime is unavailable.
    # This check must run before any schema enforcement logic.
    # ContractRuntimeError is intentionally NOT caught below — it propagates
    # to the caller so the CLI can exit with code 3.
    ensure_contract_runtime_available()

    try:
        return _run_control_chain_inner(
            raw_input=raw_input,
            stage_override=stage,
            policy_override=policy,
            input_kind_override=input_kind,
            evaluated_at=evaluated_at,
            execute=execute,
            replay_governance_artifact=replay_governance_decision,
        )
    except ContractRuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001
        return _make_error_artifact(
            acc_warnings=[],
            acc_errors=[f"Control chain raised unexpectedly: {exc}"],
            reason_code=REASON_BLOCKED_BY_MALFORMED_INPUT,
            evaluated_at=evaluated_at,
            execute=execute,
        )
