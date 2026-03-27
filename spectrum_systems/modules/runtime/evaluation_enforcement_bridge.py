"""Governor Enforcement Bridge (Prompt BU).

Consumes evaluation_budget_decision artifacts produced by the BT Evaluation
Budget Governor and converts them into governed evaluation_enforcement_action
artifacts that promotion/release/change workflows must honor.

Design principles
-----------------
- Fail closed: any invalid or missing input raises an error immediately.
- Canonical-only runtime vocabulary: enforcement accepts/produces only
  allow|warn|freeze|block values.
- Schema-governed: every enforcement action artifact is validated before return.
- Deterministic: the same inputs always produce the same outputs.
- Auditable: all reasons and required human actions are recorded.

Policy
------
    allow  → advisory, action_type=allow,  allowed_to_proceed=True
    warn   → advisory, action_type=warn,   allowed_to_proceed=True
    freeze → enforced, action_type=freeze, allowed_to_proceed=False
    block  → enforced, action_type=block,  allowed_to_proceed=False

Data-flow
---------
    evaluation_budget_decision (JSON file)
                │  load_budget_decision(path)
                ▼
    decision dict  ──► validate_budget_decision(decision)
                │
                ▼
    determine_enforcement_scope(decision, context)
                │
                ▼
    [optional] load_override_authorization(path)
                │  validate_override_authorization(override)
                │  verify_override_applicability(override, decision, action)
                ▼
    build_enforcement_action(...)
                │  validate_enforcement_action(action)
                ▼
    evaluation_enforcement_action (schema-validated)

Public API
----------
load_budget_decision(path)                              → decision dict
validate_budget_decision(decision)                      → list[str]  (empty = valid)
determine_enforcement_scope(decision, context)          → scope str
load_override_authorization(path)                       → override dict
validate_override_authorization(override)               → list[str]  (empty = valid)
verify_override_applicability(override, decision, action) → None  (raises on failure)
build_enforcement_action(...)                           → action dict
validate_enforcement_action(action)                     → list[str]  (empty = valid)
enforce_budget_decision(decision, context)              → action dict
run_enforcement_bridge(path, context)                   → action dict
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_BUDGET_DECISION_SCHEMA_PATH = _SCHEMA_DIR / "evaluation_budget_decision.schema.json"
_ENFORCEMENT_ACTION_SCHEMA_PATH = _SCHEMA_DIR / "evaluation_enforcement_action.schema.json"
_OVERRIDE_AUTHORIZATION_SCHEMA_PATH = _SCHEMA_DIR / "evaluation_override_authorization.schema.json"
_CONTROL_LOOP_CERTIFICATION_SCHEMA_PATH = _SCHEMA_DIR / "control_loop_certification_pack.schema.json"

SCHEMA_VERSION = "1.0.0"
GENERATOR = "spectrum_systems.modules.runtime.evaluation_enforcement_bridge"

# Canonical control-loop system_response values used by enforcement action construction.
_VALID_SYSTEM_RESPONSES = frozenset({"allow", "warn", "freeze", "block"})

# system_response values that block downstream workflows
_BLOCKING_RESPONSES = frozenset({"freeze", "block"})

# Default enforcement scope when not provided or determinable from context
_DEFAULT_SCOPE = "release"

# Context key for a governed override authorization artifact
_OVERRIDE_AUTHORIZATION_KEY = "override_authorization"
_CONTROL_LOOP_CERTIFICATION_PATH_KEY = "control_loop_certification_path"

# Module-level mapping of system_response → action_type (used in multiple places)
_RESPONSE_TO_ACTION_TYPE: Dict[str, str] = {
    "allow": "allow",
    "warn": "warn",
    "freeze": "freeze",
    "block": "block",
}

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class EnforcementBridgeError(Exception):
    """Raised for any enforcement bridge failure. Fail-closed."""


class InvalidDecisionError(EnforcementBridgeError):
    """Raised when an evaluation_budget_decision fails schema validation."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return str(uuid.uuid4())


def _load_schema(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise EnforcementBridgeError(f"Schema file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _validate_against_schema(artifact: Any, schema: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(artifact), key=lambda e: list(e.absolute_path)
    )
    return [e.message for e in errors]


def _parse_iso_timestamp(timestamp_str: str) -> datetime:
    """Parse an ISO-8601 timestamp string, normalising the 'Z' suffix."""
    return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))


def _canonical_response_for_enforcement(decision: Dict[str, Any]) -> str:
    """Return canonical enforcement response for a validated control-loop decision."""
    decision_dialect = str(decision.get("decision_dialect") or "")
    system_response = str(decision.get("system_response") or "")
    if decision_dialect != "control_loop":
        raise EnforcementBridgeError(
            "Unsupported decision_dialect "
            f"'{decision_dialect}'; enforcement requires 'control_loop'."
        )
    if system_response not in _VALID_SYSTEM_RESPONSES:
        raise EnforcementBridgeError(
            "Unsupported canonical system_response "
            f"'{system_response}' for decision_dialect '{decision_dialect}'."
        )
    return system_response


def _default_certification_gate(enforcement_scope: str) -> Dict[str, Any]:
    if enforcement_scope != "promotion":
        return {
            "artifact_reference": "not_applicable",
            "certification_decision": "not_applicable",
            "certification_status": "not_applicable",
            "block_reason": None,
            "gate_passed": True,
        }
    return {
        "artifact_reference": "missing",
        "certification_decision": "missing",
        "certification_status": "missing",
        "block_reason": "control_loop_certification_pack is required for promotion scope.",
        "gate_passed": False,
    }


def _evaluate_certification_gate(
    context: Optional[Dict[str, Any]],
    enforcement_scope: str,
) -> Dict[str, Any]:
    """Evaluate promotion certification requirements with fail-closed behavior."""
    gate = _default_certification_gate(enforcement_scope)
    if enforcement_scope != "promotion":
        return gate

    path_value: Optional[str] = None
    if context:
        raw = context.get(_CONTROL_LOOP_CERTIFICATION_PATH_KEY)
        if raw is not None:
            path_value = str(raw)

    if not path_value:
        return gate

    artifact_path = Path(path_value)
    gate["artifact_reference"] = str(artifact_path)
    if not artifact_path.is_file():
        gate["certification_decision"] = "missing"
        gate["certification_status"] = "missing"
        gate["block_reason"] = (
            "control_loop_certification_pack file not found: "
            f"{artifact_path}"
        )
        gate["gate_passed"] = False
        return gate

    try:
        with artifact_path.open(encoding="utf-8") as fh:
            artifact = json.load(fh)
    except json.JSONDecodeError as exc:
        gate["certification_decision"] = "malformed"
        gate["certification_status"] = "malformed"
        gate["block_reason"] = (
            "control_loop_certification_pack is not valid JSON: "
            f"{exc}"
        )
        gate["gate_passed"] = False
        return gate

    schema = _load_schema(_CONTROL_LOOP_CERTIFICATION_SCHEMA_PATH)
    errors = _validate_against_schema(artifact, schema)
    if errors:
        gate["certification_decision"] = "malformed"
        gate["certification_status"] = "malformed"
        gate["block_reason"] = (
            "control_loop_certification_pack failed schema validation: "
            + "; ".join(errors)
        )
        gate["gate_passed"] = False
        return gate

    certification_id = str(artifact.get("certification_id") or "")
    if certification_id:
        gate["artifact_reference"] = f"{artifact_path}#{certification_id}"
    gate["certification_decision"] = str(artifact.get("decision") or "")
    gate["certification_status"] = str(artifact.get("certification_status") or "")

    if gate["certification_status"] != "certified":
        gate["block_reason"] = (
            "control_loop_certification_pack must have "
            "certification_status='certified' for promotion."
        )
        gate["gate_passed"] = False
        return gate

    if gate["certification_decision"] != "pass":
        gate["block_reason"] = (
            "control_loop_certification_pack must have decision='pass' "
            "for promotion."
        )
        gate["gate_passed"] = False
        return gate

    gate["block_reason"] = None
    gate["gate_passed"] = True
    return gate


# ---------------------------------------------------------------------------
# Public API — loading and validation
# ---------------------------------------------------------------------------


def load_budget_decision(path: str | Path) -> Dict[str, Any]:
    """Load and return an evaluation_budget_decision from *path*.

    Parameters
    ----------
    path:
        Path to an evaluation_budget_decision JSON file.

    Returns
    -------
    dict
        The parsed decision.

    Raises
    ------
    EnforcementBridgeError
        If the file is missing or cannot be parsed.
    InvalidDecisionError
        If the loaded JSON fails schema validation.
    """
    path = Path(path)
    if not path.is_file():
        raise EnforcementBridgeError(
            f"evaluation_budget_decision file not found: {path}"
        )
    try:
        with path.open(encoding="utf-8") as fh:
            decision = json.load(fh)
    except json.JSONDecodeError as exc:
        raise EnforcementBridgeError(
            f"Failed to parse evaluation_budget_decision JSON at '{path}': {exc}"
        ) from exc

    validation_errors = validate_budget_decision(decision)
    if validation_errors:
        raise InvalidDecisionError(
            "evaluation_budget_decision failed schema validation: "
            + "; ".join(validation_errors)
        )

    logger.info(
        "Loaded evaluation_budget_decision decision_id=%s decision_dialect=%s system_response=%s",
        decision.get("decision_id"),
        decision.get("decision_dialect"),
        decision.get("system_response"),
    )
    return decision


def validate_budget_decision(decision: Any) -> List[str]:
    """Validate *decision* against the evaluation_budget_decision JSON Schema.

    Parameters
    ----------
    decision:
        Object to validate.

    Returns
    -------
    list[str]
        Validation error messages. Empty list means the decision is valid.
    """
    schema = _load_schema(_BUDGET_DECISION_SCHEMA_PATH)
    return _validate_against_schema(decision, schema)


def validate_enforcement_action(action: Any) -> List[str]:
    """Validate *action* against the evaluation_enforcement_action JSON Schema.

    Parameters
    ----------
    action:
        Object to validate.

    Returns
    -------
    list[str]
        Validation error messages. Empty list means the action is valid.
    """
    schema = _load_schema(_ENFORCEMENT_ACTION_SCHEMA_PATH)
    return _validate_against_schema(action, schema)


def load_override_authorization(path: str | Path) -> Dict[str, Any]:
    """Load and return an evaluation_override_authorization from *path*.

    Parameters
    ----------
    path:
        Path to an evaluation_override_authorization JSON file.

    Returns
    -------
    dict
        The parsed and schema-validated override authorization.

    Raises
    ------
    EnforcementBridgeError
        If the file is missing, cannot be parsed, or fails schema validation.
    """
    path = Path(path)
    if not path.is_file():
        raise EnforcementBridgeError(
            f"override_authorization file not found: {path}"
        )
    try:
        with path.open(encoding="utf-8") as fh:
            override = json.load(fh)
    except json.JSONDecodeError as exc:
        raise EnforcementBridgeError(
            f"Failed to parse override_authorization JSON at '{path}': {exc}"
        ) from exc

    errors = validate_override_authorization(override)
    if errors:
        raise EnforcementBridgeError(
            "override_authorization failed schema validation: "
            + "; ".join(errors)
        )

    logger.info(
        "Loaded override_authorization override_id=%s decision_id=%s",
        override.get("override_id"),
        override.get("decision_id"),
    )
    return override


def validate_override_authorization(override: Any) -> List[str]:
    """Validate *override* against the evaluation_override_authorization JSON Schema.

    Parameters
    ----------
    override:
        Object to validate.

    Returns
    -------
    list[str]
        Validation error messages. Empty list means the override is valid.
    """
    schema = _load_schema(_OVERRIDE_AUTHORIZATION_SCHEMA_PATH)
    return _validate_against_schema(override, schema)


def verify_override_applicability(
    override: Dict[str, Any],
    decision: Dict[str, Any],
    action: Dict[str, Any],
) -> None:
    """Verify that *override* is applicable to *decision* and *action*.

    All checks are strict.  If ANY check fails the function raises
    :class:`EnforcementBridgeError` (fail closed).

    Checks performed
    ----------------
    1. ``override["decision_id"]`` must equal ``decision["decision_id"]``.
    2. ``override["summary_id"]`` must equal ``decision["summary_id"]``.
    3. ``override["action_id"]`` must equal ``action["action_id"]``.
    4. ``override["scope"]`` must equal ``action["enforcement_scope"]``.
    5. Current UTC time must be strictly before ``override["expires_at"]``.
    6. ``action["action_type"]`` must be in ``override["allowed_actions"]``.

    Parameters
    ----------
    override:
        A schema-validated evaluation_override_authorization dict.
    decision:
        The evaluation_budget_decision being enforced.
    action:
        The evaluation_enforcement_action being produced (or a proto-action
        dict with at least ``action_id``, ``action_type``, and
        ``enforcement_scope`` fields).

    Raises
    ------
    EnforcementBridgeError
        If any applicability check fails.
    """
    failures: List[str] = []

    if override.get("decision_id") != decision.get("decision_id"):
        failures.append(
            f"override decision_id '{override.get('decision_id')}' "
            f"does not match decision decision_id '{decision.get('decision_id')}'"
        )

    if override.get("summary_id") != decision.get("summary_id"):
        failures.append(
            f"override summary_id '{override.get('summary_id')}' "
            f"does not match decision summary_id '{decision.get('summary_id')}'"
        )

    if override.get("action_id") != action.get("action_id"):
        failures.append(
            f"override action_id '{override.get('action_id')}' "
            f"does not match enforcement action action_id '{action.get('action_id')}'"
        )

    if override.get("scope") != action.get("enforcement_scope"):
        failures.append(
            f"override scope '{override.get('scope')}' "
            f"does not match enforcement_scope '{action.get('enforcement_scope')}'"
        )

    try:
        expires_at = _parse_iso_timestamp(str(override.get("expires_at", "")))
        now = datetime.now(tz=timezone.utc)
        if now >= expires_at:
            failures.append(
                f"override has expired (expires_at={override.get('expires_at')}, "
                f"now={now.strftime('%Y-%m-%dT%H:%M:%SZ')})"
            )
    except (ValueError, TypeError):
        failures.append(
            f"override expires_at '{override.get('expires_at')}' is not a valid ISO timestamp"
        )

    action_type = action.get("action_type")
    if action_type not in override.get("allowed_actions", []):
        failures.append(
            f"action_type '{action_type}' is not in override allowed_actions "
            f"{override.get('allowed_actions')}"
        )

    if failures:
        raise EnforcementBridgeError(
            "override_authorization applicability check failed: "
            + "; ".join(failures)
        )


# ---------------------------------------------------------------------------
# Public API — enforcement policy
# ---------------------------------------------------------------------------


def determine_enforcement_scope(
    decision: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Determine the enforcement scope for this decision.

    The scope is read from ``context["enforcement_scope"]`` when present and
    valid.  Otherwise the default scope (``"release"``) is used.

    Parameters
    ----------
    decision:
        A validated evaluation_budget_decision dict.
    context:
        Optional caller-supplied context dict.

    Returns
    -------
    str
        One of ``"promotion" | "release" | "schema_change" | "prompt_change" |
        "pipeline_change"``.
    """
    valid_scopes = {
        "promotion", "release", "schema_change", "prompt_change", "pipeline_change"
    }

    if context:
        scope = context.get("enforcement_scope")
        if scope in valid_scopes:
            return scope
        if scope is not None:
            logger.warning(
                "Unknown enforcement_scope '%s' in context; falling back to default '%s'",
                scope,
                _DEFAULT_SCOPE,
            )

    return _DEFAULT_SCOPE


def _build_required_human_actions(
    system_response: str,
    decision: Dict[str, Any],
) -> List[str]:
    """Derive required human actions from the system response."""
    actions: List[str] = []

    if system_response == "allow":
        return actions

    if system_response == "warn":
        actions.append("Review warning signals before proceeding.")
        for reason in decision.get("required_actions", []):
            actions.append(reason)
        return actions

    if system_response == "freeze":
        actions.append(
            "All changes are frozen. No deployment or release activity is permitted "
            "until the evaluation budget is restored."
        )
        for reason in decision.get("required_actions", []):
            actions.append(reason)
        return actions

    if system_response == "block":
        actions.append(
            "Release is blocked. No release activity is permitted. "
            "Escalate to engineering leadership immediately."
        )
        for reason in decision.get("required_actions", []):
            actions.append(reason)
        return actions

    raise EnforcementBridgeError(
        f"Unknown system_response '{system_response}' while building required_human_actions."
    )


def build_enforcement_action(
    decision_id: str,
    summary_id: str,
    system_response: str,
    enforcement_scope: str,
    reasons: List[str],
    required_human_actions: List[str],
    allowed_to_proceed: bool,
    certification_gate: Dict[str, Any],
    action_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble and schema-validate an evaluation_enforcement_action artifact.

    Parameters
    ----------
    decision_id:
        ``decision_id`` of the source evaluation_budget_decision.
    summary_id:
        ``summary_id`` of the originating evaluation_monitor_summary.
    system_response:
        Governed system response from the budget decision.
    enforcement_scope:
        The workflow scope to enforce against.
    reasons:
        Human-readable explanation list.
    required_human_actions:
        Actions that a human must take.
    allowed_to_proceed:
        Whether the downstream workflow may proceed.
    action_id:
        Optional explicit action_id to assign.  When an override_authorization
        is present the override's ``action_id`` must be supplied here so the
        produced artifact carries the pre-authorized ID.  If *None* a new
        UUID is generated.

    Returns
    -------
    dict
        Schema-validated evaluation_enforcement_action artifact.

    Raises
    ------
    EnforcementBridgeError
        If the produced artifact fails schema validation.
    """
    if system_response not in _VALID_SYSTEM_RESPONSES:
        raise EnforcementBridgeError(
            f"Unknown system_response '{system_response}'; cannot build enforcement action."
        )
    expected_allowed_to_proceed = system_response in {"allow", "warn"}
    if allowed_to_proceed != expected_allowed_to_proceed:
        raise EnforcementBridgeError(
            "Invalid enforcement action invariant: "
            f"system_response '{system_response}' requires "
            f"allowed_to_proceed={expected_allowed_to_proceed}."
        )

    _response_to_status = {
        "allow": "advisory",
        "warn": "advisory",
        "freeze": "enforced",
        "block": "enforced",
    }

    action_type = _RESPONSE_TO_ACTION_TYPE[system_response]
    status = _response_to_status[system_response]

    action: Dict[str, Any] = {
        "action_id": action_id if action_id is not None else _new_id(),
        "decision_id": decision_id,
        "summary_id": summary_id,
        "status": status,
        "action_type": action_type,
        "enforcement_scope": enforcement_scope,
        "allowed_to_proceed": allowed_to_proceed,
        "reasons": reasons,
        "required_human_actions": required_human_actions,
        "certification_gate": certification_gate,
        "created_at": _now_iso(),
    }

    errors = validate_enforcement_action(action)
    if errors:
        raise EnforcementBridgeError(
            "Produced enforcement action failed schema validation: "
            + "; ".join(errors)
        )

    logger.info(
        "Enforcement action built decision_id=%s action_type=%s "
        "allowed_to_proceed=%s scope=%s",
        decision_id,
        action_type,
        allowed_to_proceed,
        enforcement_scope,
    )
    return action


def enforce_budget_decision(
    decision: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert a validated budget decision into an enforcement action.

    Parameters
    ----------
    decision:
        A schema-validated evaluation_budget_decision dict.
    context:
        Optional caller-supplied context.  May contain:
        - ``enforcement_scope`` (str): workflow scope override.
        - ``override_authorization`` (dict): reserved for callers that need to
          provide override context. Canonical runtime responses have no override
          pathway and invalid/mismatched values fail closed.

    Returns
    -------
    dict
        Schema-validated evaluation_enforcement_action artifact.

    Raises
    ------
    EnforcementBridgeError
        On any enforcement failure, including override validation/verification
        failures.
    InvalidDecisionError
        If *decision* fails schema validation.
    """
    errors = validate_budget_decision(decision)
    if errors:
        raise InvalidDecisionError(
            "evaluation_budget_decision failed schema validation: "
            + "; ".join(errors)
        )

    system_response = _canonical_response_for_enforcement(decision)
    enforcement_scope = determine_enforcement_scope(decision, context)
    required_human_actions = _build_required_human_actions(system_response, decision)
    reasons: List[str] = list(decision.get("reasons", []))
    certification_gate = _evaluate_certification_gate(context, enforcement_scope)

    if context and _OVERRIDE_AUTHORIZATION_KEY in context:
        raise EnforcementBridgeError(
            "override_authorization is not supported for canonical enforcement responses."
        )

    if not certification_gate["gate_passed"]:
        gate_reason = str(certification_gate.get("block_reason") or "Certification gate blocked promotion.")
        if gate_reason not in reasons:
            reasons.append(gate_reason)
        if gate_reason not in required_human_actions:
            required_human_actions.append(gate_reason)
        system_response = "block"

    if system_response in {"allow", "warn"}:
        allowed_to_proceed = True
    elif system_response in _BLOCKING_RESPONSES:
        allowed_to_proceed = False
    else:
        raise EnforcementBridgeError(
            f"Unknown system_response '{system_response}' in enforce_budget_decision."
        )

    return build_enforcement_action(
        decision_id=decision["decision_id"],
        summary_id=decision["summary_id"],
        system_response=system_response,
        enforcement_scope=enforcement_scope,
        reasons=reasons,
        required_human_actions=required_human_actions,
        allowed_to_proceed=allowed_to_proceed,
        certification_gate={
            "artifact_reference": certification_gate["artifact_reference"],
            "certification_decision": certification_gate["certification_decision"],
            "certification_status": certification_gate["certification_status"],
            "block_reason": certification_gate["block_reason"],
        },
        action_id=None,
    )


# ---------------------------------------------------------------------------
# Public API — batch entry point
# ---------------------------------------------------------------------------


def run_enforcement_bridge(
    path: str | Path,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Load a budget decision from *path* and produce a governed enforcement action.

    This is the primary entry point.  It is fail-closed: any invalid or
    missing input raises an exception rather than returning a partial result.

    Parameters
    ----------
    path:
        Path to an evaluation_budget_decision JSON file.
    context:
        Optional caller-supplied context dict.

    Returns
    -------
    dict
        Schema-validated evaluation_enforcement_action artifact.

    Raises
    ------
    EnforcementBridgeError
        If the file is missing, cannot be parsed, or the produced action
        fails schema validation.
    InvalidDecisionError
        If the loaded decision fails schema validation.
    """
    decision = load_budget_decision(path)
    action = enforce_budget_decision(decision, context)

    logger.info(
        "Enforcement bridge complete decision_id=%s action_type=%s "
        "allowed_to_proceed=%s",
        action["decision_id"],
        action["action_type"],
        action["allowed_to_proceed"],
    )
    return action
