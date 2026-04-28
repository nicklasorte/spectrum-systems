"""CL-19 / CL-21: SEL action mapping — pure validator.

Loads the explicit mapping from CDE decision types to permitted SEL
action types (``contracts/governance/sel_action_mapping_policy.json``).
Validates that a given (decision, action) pair is consistent. Detects
the forbidden patterns:

  * promote-on-block
  * no-op-on-freeze
  * retry-on-policy-mismatch
  * mutation-without-allow
  * repair-without-authorization

This module is non-owning. SEL retains canonical enforcement
authority. The validator just makes inconsistencies between CDE
decisions and SEL actions deterministically visible with stable
canonical reason codes under the ``action`` precedence class.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = (
    REPO_ROOT
    / "contracts"
    / "governance"
    / "sel_action_mapping_policy.json"
)

REASON_OK = "ACTION_OK"
REASON_PROMOTE_ON_BLOCK = "ACTION_PROMOTE_ON_BLOCK"
REASON_NOOP_ON_FREEZE = "ACTION_NOOP_ON_FREEZE"
REASON_RETRY_ON_POLICY_MISMATCH = "ACTION_RETRY_ON_POLICY_MISMATCH"
REASON_MUTATION_WITHOUT_ALLOW = "ACTION_MUTATION_WITHOUT_ALLOW"
REASON_REPAIR_WITHOUT_AUTH = "ACTION_REPAIR_WITHOUT_AUTHORIZATION"
REASON_UNKNOWN_DECISION_MAPPING = "ACTION_UNKNOWN_DECISION_MAPPING"


class ActionMappingError(ValueError):
    """Raised only on programmer-misuse."""


def _violation(code: str, **details: Any) -> Dict[str, Any]:
    return {"reason_code": code, **details}


def load_action_mapping_policy(path: Optional[Path] = None) -> Dict[str, Any]:
    p = Path(path) if path is not None else POLICY_PATH
    if not p.exists():
        raise ActionMappingError(f"policy not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def validate_action_for_decision(
    *,
    decision: str,
    action: str,
    policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate a (decision, action) pair against the SEL mapping policy.

    Always returns ``{"ok": bool, "violations": [...], "primary_reason": str}``.
    """
    if not isinstance(decision, str) or not decision.strip():
        return {
            "ok": False,
            "violations": [_violation(REASON_UNKNOWN_DECISION_MAPPING, decision=decision)],
            "primary_reason": REASON_UNKNOWN_DECISION_MAPPING,
        }
    if not isinstance(action, str) or not action.strip():
        return {
            "ok": False,
            "violations": [_violation(REASON_UNKNOWN_DECISION_MAPPING, action=action)],
            "primary_reason": REASON_UNKNOWN_DECISION_MAPPING,
        }

    if policy is None:
        policy = load_action_mapping_policy()

    allowed_map = policy.get("decision_to_allowed_actions") or {}
    forbidden_patterns = policy.get("forbidden_action_patterns") or ()

    if decision not in allowed_map:
        return {
            "ok": False,
            "violations": [
                _violation(REASON_UNKNOWN_DECISION_MAPPING, decision=decision)
            ],
            "primary_reason": REASON_UNKNOWN_DECISION_MAPPING,
        }

    # Forbidden pattern matches first — they expose specific drift names.
    for pat in forbidden_patterns:
        if not isinstance(pat, Mapping):
            continue
        if pat.get("pattern_decision") == decision and pat.get("pattern_action") == action:
            code = pat.get("reason_code", REASON_UNKNOWN_DECISION_MAPPING)
            return {
                "ok": False,
                "violations": [_violation(code, decision=decision, action=action)],
                "primary_reason": code,
            }

    if action not in allowed_map[decision]:
        # Action is not in the allowed set for this decision; choose the
        # most descriptive canonical reason.
        if decision == "block":
            code = REASON_MUTATION_WITHOUT_ALLOW
        elif decision == "freeze":
            code = REASON_NOOP_ON_FREEZE
        elif decision == "allow":
            code = REASON_REPAIR_WITHOUT_AUTH
        else:
            code = REASON_UNKNOWN_DECISION_MAPPING
        return {
            "ok": False,
            "violations": [_violation(code, decision=decision, action=action)],
            "primary_reason": code,
        }

    return {"ok": True, "violations": [], "primary_reason": REASON_OK}


def allowed_actions_for(decision: str, policy: Optional[Mapping[str, Any]] = None) -> List[str]:
    if policy is None:
        policy = load_action_mapping_policy()
    return list((policy.get("decision_to_allowed_actions") or {}).get(decision, ()))


__all__ = [
    "POLICY_PATH",
    "ActionMappingError",
    "REASON_OK",
    "REASON_PROMOTE_ON_BLOCK",
    "REASON_NOOP_ON_FREEZE",
    "REASON_RETRY_ON_POLICY_MISMATCH",
    "REASON_MUTATION_WITHOUT_ALLOW",
    "REASON_REPAIR_WITHOUT_AUTH",
    "REASON_UNKNOWN_DECISION_MAPPING",
    "load_action_mapping_policy",
    "validate_action_for_decision",
    "allowed_actions_for",
]
