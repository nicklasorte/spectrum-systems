"""Governor Enforcement Bridge (Prompt BU).

Consumes evaluation_budget_decision artifacts produced by the BT Evaluation
Budget Governor and converts them into governed evaluation_enforcement_action
artifacts that promotion/release/change workflows must honor.

Design principles
-----------------
- Fail closed:  any invalid or missing input raises an error immediately.
- No silent overrides:  review/override requires an explicit structured
  override artifact present in the call context.
- Schema-governed:  every enforcement action artifact is validated before return.
- Deterministic:  the same inputs always produce the same outputs.
- Auditable:  all reasons and required human actions are recorded.

Policy
------
    allow              → advisory,  action_type=allow,          allowed_to_proceed=True
    allow_with_warning → advisory,  action_type=warn,           allowed_to_proceed=True
    require_review     → enforced,  action_type=require_review, allowed_to_proceed=False
                         (True only if an explicit override artifact is present)
    freeze_changes     → enforced,  action_type=freeze_changes, allowed_to_proceed=False
    block_release      → enforced,  action_type=block_release,  allowed_to_proceed=False

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
    build_enforcement_action(...)
                │  validate_enforcement_action(action)
                ▼
    evaluation_enforcement_action (schema-validated)

Public API
----------
load_budget_decision(path)                           → decision dict
validate_budget_decision(decision)                   → list[str]  (empty = valid)
determine_enforcement_scope(decision, context)       → scope str
build_enforcement_action(...)                        → action dict
validate_enforcement_action(action)                  → list[str]  (empty = valid)
enforce_budget_decision(decision, context)           → action dict
run_enforcement_bridge(path, context)                → action dict
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

SCHEMA_VERSION = "1.0.0"
GENERATOR = "spectrum_systems.modules.runtime.evaluation_enforcement_bridge"

# Valid system_response values from evaluation_budget_decision (used for
# validation in build_enforcement_action)
_VALID_SYSTEM_RESPONSES = frozenset(
    {"allow", "allow_with_warning", "require_review", "freeze_changes", "block_release"}
)

# system_response values that block downstream workflows absent an override
_BLOCKING_RESPONSES = frozenset({"freeze_changes", "block_release"})

# system_response values that block unless an explicit override is present
_REVIEW_RESPONSES = frozenset({"require_review"})

# Default enforcement scope when not provided or determinable from context
_DEFAULT_SCOPE = "release"

# Context key for an explicit human override artifact
_OVERRIDE_KEY = "override_artifact"

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
        "Loaded evaluation_budget_decision decision_id=%s system_response=%s",
        decision.get("decision_id"),
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

    if system_response == "allow_with_warning":
        actions.append("Review warning signals before proceeding.")
        for reason in decision.get("required_actions", []):
            actions.append(reason)
        return actions

    if system_response == "require_review":
        actions.append(
            "A human reviewer must inspect the evaluation_budget_decision and "
            "provide an explicit override artifact before this workflow may proceed."
        )
        actions.append("Escalate to on-call engineer for immediate review.")
        for reason in decision.get("required_actions", []):
            actions.append(reason)
        return actions

    if system_response == "freeze_changes":
        actions.append(
            "All changes are frozen. No deployment or release activity is permitted "
            "until the evaluation budget is restored."
        )
        for reason in decision.get("required_actions", []):
            actions.append(reason)
        return actions

    if system_response == "block_release":
        actions.append(
            "Release is blocked. No release activity is permitted. "
            "Escalate to engineering leadership immediately."
        )
        for reason in decision.get("required_actions", []):
            actions.append(reason)
        return actions

    # Fail-closed: unknown system_response
    actions.append(
        "Unknown system response; all activity blocked pending engineering review."
    )
    return actions


def _resolve_allow_to_proceed(
    system_response: str,
    context: Optional[Dict[str, Any]],
) -> bool:
    """Determine whether the downstream workflow is allowed to proceed.

    - allow / allow_with_warning  → True (no override required)
    - freeze_changes / block_release → False (no override available)
    - require_review → False unless an explicit override artifact is present
      in context[_OVERRIDE_KEY].  Override absence → fail closed.
    """
    if system_response in ("allow", "allow_with_warning"):
        return True

    if system_response in _BLOCKING_RESPONSES:
        return False

    if system_response in _REVIEW_RESPONSES:
        if context and context.get(_OVERRIDE_KEY):
            logger.info(
                "Explicit override artifact present for require_review; "
                "allowing to proceed."
            )
            return True
        # No override present → fail closed
        return False

    # Unknown system_response → fail closed
    return False


def build_enforcement_action(
    decision_id: str,
    summary_id: str,
    system_response: str,
    enforcement_scope: str,
    reasons: List[str],
    required_human_actions: List[str],
    allowed_to_proceed: bool,
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

    Returns
    -------
    dict
        Schema-validated evaluation_enforcement_action artifact.

    Raises
    ------
    EnforcementBridgeError
        If the produced artifact fails schema validation.
    """
    # Map system_response → action_type and enforcement status
    _response_to_action_type = {
        "allow": "allow",
        "allow_with_warning": "warn",
        "require_review": "require_review",
        "freeze_changes": "freeze_changes",
        "block_release": "block_release",
    }
    _response_to_status = {
        "allow": "advisory",
        "allow_with_warning": "advisory",
        "require_review": "enforced",
        "freeze_changes": "enforced",
        "block_release": "enforced",
    }

    if system_response not in _VALID_SYSTEM_RESPONSES:
        raise EnforcementBridgeError(
            f"Unknown system_response '{system_response}'; cannot build enforcement action."
        )

    action_type = _response_to_action_type[system_response]
    status = _response_to_status[system_response]

    action: Dict[str, Any] = {
        "action_id": _new_id(),
        "decision_id": decision_id,
        "summary_id": summary_id,
        "status": status,
        "action_type": action_type,
        "enforcement_scope": enforcement_scope,
        "allowed_to_proceed": allowed_to_proceed,
        "reasons": reasons,
        "required_human_actions": required_human_actions,
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
        - ``override_artifact`` (dict): explicit human override for
          ``require_review`` decisions.

    Returns
    -------
    dict
        Schema-validated evaluation_enforcement_action artifact.

    Raises
    ------
    EnforcementBridgeError
        On any enforcement failure.
    InvalidDecisionError
        If *decision* fails schema validation.
    """
    errors = validate_budget_decision(decision)
    if errors:
        raise InvalidDecisionError(
            "evaluation_budget_decision failed schema validation: "
            + "; ".join(errors)
        )

    system_response: str = decision["system_response"]
    enforcement_scope = determine_enforcement_scope(decision, context)
    allowed_to_proceed = _resolve_allow_to_proceed(system_response, context)
    required_human_actions = _build_required_human_actions(system_response, decision)

    reasons: List[str] = list(decision.get("reasons", []))

    return build_enforcement_action(
        decision_id=decision["decision_id"],
        summary_id=decision["summary_id"],
        system_response=system_response,
        enforcement_scope=enforcement_scope,
        reasons=reasons,
        required_human_actions=required_human_actions,
        allowed_to_proceed=allowed_to_proceed,
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
