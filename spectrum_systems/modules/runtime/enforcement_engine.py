"""Runtime enforcement engine for evaluation budget decisions.

This module converts control-loop ``evaluation_budget_decision`` artifacts into
schema-valid ``enforcement_result`` artifacts that directly govern whether
execution may proceed.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "enforcement_result.schema.json"
_DECISION_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "evaluation_budget_decision.schema.json"

_ACTION_MAP: Dict[str, Tuple[str, bool, str]] = {
    "allow": ("allow", True, "executed"),
    "warn": ("warn", True, "executed"),
    "freeze": ("freeze", False, "frozen"),
    "block": ("block", False, "blocked"),
}


def _load_schema(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(payload: Any, schema: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    return [
        f"{'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}"
        for err in errors
    ]


def validate_enforcement_result(result: Any) -> List[str]:
    """Validate an enforcement result against its JSON schema."""
    return _validate(result, _load_schema(_SCHEMA_PATH))


def _is_valid_budget_decision_shape(decision: Any) -> Tuple[bool, List[str]]:
    errors = _validate(decision, _load_schema(_DECISION_SCHEMA_PATH))
    return (len(errors) == 0, errors)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return str(uuid.uuid4())


def enforce_budget_decision(decision: dict) -> dict:
    """Convert ``evaluation_budget_decision`` into enforced execution behavior.

    Fail-closed behavior is mandatory. Any malformed input or unknown
    ``system_response`` results in a blocked enforcement artifact.
    """
    default_decision_id = str((decision or {}).get("decision_id") or "unknown-decision")
    default_trace_id = str((decision or {}).get("trace_id") or "unknown-trace")
    reasons: List[str] = []

    action = "block"
    execution_permitted = False
    enforcement_status = "blocked"

    valid_decision, decision_errors = _is_valid_budget_decision_shape(decision)
    if not valid_decision:
        reasons.append("malformed evaluation_budget_decision; fail-closed block applied")
        reasons.extend(decision_errors)
    else:
        system_response = str(decision.get("system_response"))
        mapped = _ACTION_MAP.get(system_response)
        if mapped is None:
            reasons.append(
                f"unknown system_response '{system_response}'; fail-closed block applied"
            )
        else:
            action, execution_permitted, enforcement_status = mapped
            reasons = list(decision.get("reasons") or [])
            if not reasons:
                reasons = [f"system_response={system_response}"]

    result = {
        "enforcement_id": _new_id(),
        "decision_id": default_decision_id,
        "trace_id": default_trace_id,
        "timestamp": _now_iso(),
        "enforcement_action": action,
        "execution_permitted": execution_permitted,
        "enforcement_status": enforcement_status,
        "reasons": reasons,
    }

    schema_errors = validate_enforcement_result(result)
    if schema_errors:
        return {
            "enforcement_id": _new_id(),
            "decision_id": default_decision_id,
            "trace_id": default_trace_id,
            "timestamp": _now_iso(),
            "enforcement_action": "block",
            "execution_permitted": False,
            "enforcement_status": "blocked",
            "reasons": [
                "enforcement_result schema validation failed; fail-closed block applied",
                *schema_errors,
            ],
        }
    return result
