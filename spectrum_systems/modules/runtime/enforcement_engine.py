"""Runtime enforcement engine for deterministic governed decisions.

BAF single-path surface
-----------------------
``enforce_control_decision`` is the canonical enforcement mapper for
``evaluation_control_decision`` artifacts and emits schema-valid
``enforcement_result`` artifacts.

Legacy compatibility surface
----------------------------
``enforce_budget_decision`` remains available for existing run-bundle and replay
flows that still consume ``evaluation_budget_decision`` artifacts.
"""

from __future__ import annotations

import uuid
import warnings
import hashlib
import json
from inspect import stack
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


_ACTION_MAP: Dict[str, str] = {
    "allow": "allow_execution",
    "deny": "deny_execution",
    "require_review": "require_manual_review",
}

_STATUS_MAP: Dict[str, str] = {
    "allow_execution": "allow",
    "deny_execution": "deny",
    "require_manual_review": "require_review",
}


class EnforcementError(Exception):
    """Raised when enforcement mapping cannot produce a valid governed result."""


def _validate(payload: Any, schema_name: str) -> List[str]:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    return [
        f"{'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}"
        for err in errors
    ]


def validate_enforcement_result(result: Any) -> List[str]:
    """Validate an enforcement result against ``enforcement_result`` schema."""
    return _validate(result, "enforcement_result")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _deterministic_id(prefix: str, payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def enforce_control_decision(decision_artifact: dict, *, timestamp: str | None = None) -> dict:
    """Map ``evaluation_control_decision`` to deterministic ``enforcement_result``.

    Fail-closed behavior:
    - malformed decision artifact -> ``EnforcementError``
    - missing/unknown decision value -> ``EnforcementError``
    - invalid output artifact shape -> ``EnforcementError``
    """
    if not isinstance(decision_artifact, dict):
        raise EnforcementError("decision_artifact must be a dict")

    decision_errors = _validate(decision_artifact, "evaluation_control_decision")
    if decision_errors:
        raise EnforcementError(
            "evaluation_control_decision failed validation: " + "; ".join(decision_errors)
        )

    decision_label = decision_artifact.get("decision")
    if not isinstance(decision_label, str) or not decision_label:
        raise EnforcementError("missing decision in evaluation_control_decision")

    enforcement_action = _ACTION_MAP.get(decision_label)
    if enforcement_action is None:
        raise EnforcementError(f"unsupported decision value: {decision_label}")

    final_status = _STATUS_MAP[enforcement_action]
    source_decision_id = str(decision_artifact.get("decision_id") or "")
    if not source_decision_id:
        raise EnforcementError("evaluation_control_decision missing decision_id")
    trace_id = str(decision_artifact.get("trace_id") or "")
    if not trace_id:
        raise EnforcementError("evaluation_control_decision missing trace_id")
    run_id = str(decision_artifact.get("run_id") or "")
    if not run_id:
        raise EnforcementError("evaluation_control_decision missing run_id")
    rationale_code = str(decision_artifact.get("rationale_code") or "")
    if not rationale_code:
        raise EnforcementError("evaluation_control_decision missing rationale_code")

    fail_closed = final_status in {"deny", "require_review"}
    deterministic_identity_payload = {
        "artifact_type": "enforcement_result",
        "schema_version": "1.1.0",
        "source_decision_id": source_decision_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "decision": decision_label,
        "enforcement_action": enforcement_action,
        "final_status": final_status,
        "rationale_code": rationale_code,
        "fail_closed": fail_closed,
        "enforcement_path": "baf_single_path",
    }

    if timestamp is not None and (not isinstance(timestamp, str) or not timestamp.strip()):
        raise EnforcementError("timestamp override must be a non-empty string when provided")

    result = {
        "artifact_type": "enforcement_result",
        "schema_version": "1.1.0",
        "enforcement_result_id": _deterministic_id("ENF", deterministic_identity_payload),
        "timestamp": timestamp.strip() if isinstance(timestamp, str) else _now_iso(),
        "trace_id": trace_id,
        "run_id": run_id,
        "input_decision_reference": source_decision_id,
        "enforcement_action": enforcement_action,
        "final_status": final_status,
        "rationale_code": rationale_code,
        "fail_closed": fail_closed,
        "enforcement_path": "baf_single_path",
        "provenance": {
            "source_artifact_type": "evaluation_control_decision",
            "source_artifact_id": source_decision_id,
        },
    }

    result_errors = validate_enforcement_result(result)
    if result_errors:
        raise EnforcementError(
            "enforcement_result failed validation: " + "; ".join(result_errors)
        )
    return result


# ---------------------------------------------------------------------------
# Legacy compatibility path (used by existing budget/replay entry points)
# ---------------------------------------------------------------------------

_LEGACY_ACTION_MAP: Dict[str, Tuple[str, bool, str]] = {
    "allow": ("allow", True, "executed"),
    "warn": ("warn", True, "executed"),
    "freeze": ("freeze", False, "frozen"),
    "block": ("block", False, "blocked"),
}

_LEGACY_CALLER_ALLOWLIST = (
    "spectrum_systems.modules.runtime.control_executor",
    "tests.",
)


def _legacy_caller_is_allowed() -> bool:
    for frame in stack(context=0):
        module_name = frame.frame.f_globals.get("__name__")
        if not isinstance(module_name, str):
            continue
        if module_name == __name__:
            continue
        if module_name.startswith("test_"):
            return True
        return any(
            module_name == allowed or module_name.startswith(allowed)
            for allowed in _LEGACY_CALLER_ALLOWLIST
        )
    return False


def _validate_budget_decision_shape(decision: Any) -> Tuple[bool, List[str]]:
    errors = _validate(decision, "evaluation_budget_decision")
    return (len(errors) == 0, errors)


def enforce_budget_decision(decision: dict) -> dict:
    """Legacy budget-decision mapper retained for backward compatibility."""
    if not _legacy_caller_is_allowed():
        raise EnforcementError(
            "enforce_budget_decision is restricted to explicitly approved legacy callers"
        )
    warnings.warn(
        "enforce_budget_decision is deprecated; use enforce_control_decision for canonical BAF enforcement.",
        DeprecationWarning,
        stacklevel=2,
    )
    default_decision_id = str((decision or {}).get("decision_id") or "unknown-decision")
    default_trace_id = str((decision or {}).get("trace_id") or "unknown-trace")
    reasons: List[str] = []

    action = "block"
    execution_permitted = False
    enforcement_status = "blocked"

    valid_decision, decision_errors = _validate_budget_decision_shape(decision)
    if not valid_decision:
        reasons.append("malformed evaluation_budget_decision; fail-closed block applied")
        reasons.extend(decision_errors)
    else:
        system_response = str(decision.get("system_response"))
        mapped = _LEGACY_ACTION_MAP.get(system_response)
        if mapped is None:
            reasons.append(f"unknown system_response '{system_response}'; fail-closed block applied")
        else:
            action, execution_permitted, enforcement_status = mapped
            reasons = list(decision.get("reasons") or []) or [f"system_response={system_response}"]

    return {
        "enforcement_id": _new_id("enf"),
        "decision_id": default_decision_id,
        "trace_id": default_trace_id,
        "timestamp": _now_iso(),
        "enforcement_action": action,
        "execution_permitted": execution_permitted,
        "enforcement_status": enforcement_status,
        "reasons": reasons,
    }
