"""CL-13 / CL-15: TPA policy-input contract — pure validator.

Pins the exact set of inputs that TPA may consume (drawn from
``contracts/governance/tpa_policy_input_contract.json``). Ungoverned
inputs (dashboard-only, narrative-only, hidden state, free text) are
rejected with stable canonical reason codes under the ``policy``
precedence class.

The validator is non-owning: TPA retains canonical trust/policy
authority. The validator is the inspection surface that fails closed
when a TPA call would otherwise consume an undocumented input.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "governance"
    / "tpa_policy_input_contract.json"
)

REASON_OK = "POLICY_INPUT_OK"
REASON_HIDDEN = "POLICY_HIDDEN_INPUT"
REASON_DASHBOARD = "POLICY_DASHBOARD_ONLY_INPUT"
REASON_NARRATIVE = "POLICY_NARRATIVE_ONLY_INPUT"
REASON_UNGOVERNED = "POLICY_UNGOVERNED_INPUT"
REASON_MISSING = "POLICY_INPUT_MISSING"
REASON_STALE = "POLICY_INPUT_STALE"
REASON_RESULT_MISSING = "POLICY_RESULT_MISSING"


class PolicyInputContractError(ValueError):
    """Raised only on programmer-misuse."""


def _violation(code: str, **details: Any) -> Dict[str, Any]:
    return {"reason_code": code, **details}


def load_policy_input_contract(path: Optional[Path] = None) -> Dict[str, Any]:
    p = Path(path) if path is not None else CONTRACT_PATH
    if not p.exists():
        raise PolicyInputContractError(f"contract not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _match_forbidden_pattern(
    key: str, contract: Mapping[str, Any]
) -> Optional[str]:
    for pat in contract.get("forbidden_input_patterns") or ():
        match = pat.get("match") if isinstance(pat, Mapping) else None
        if isinstance(match, str) and fnmatch.fnmatchcase(key, match):
            return pat.get("reason_code")
    return None


def validate_policy_inputs(
    inputs: Mapping[str, Any],
    *,
    contract: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate that ``inputs`` conform to the TPA policy-input contract.

    Returns ``{"ok": bool, "violations": [...], "primary_reason": str}``.
    """
    if not isinstance(inputs, Mapping):
        raise PolicyInputContractError("inputs must be a mapping")

    if contract is None:
        contract = load_policy_input_contract()

    allowed = set(contract.get("allowed_input_keys") or ())
    required = list(contract.get("required_input_keys") or ())
    forbidden_explicit = set(contract.get("forbidden_input_keys") or ())

    violations: List[Dict[str, Any]] = []

    for key, value in inputs.items():
        if not isinstance(key, str):
            continue
        if key in forbidden_explicit:
            mapped = {
                "dashboard_status": REASON_DASHBOARD,
                "dashboard_only_claim": REASON_DASHBOARD,
                "narrative_rationale": REASON_NARRATIVE,
                "free_text_rationale": REASON_NARRATIVE,
                "operator_runbook_text": REASON_NARRATIVE,
                "hidden_state": REASON_HIDDEN,
                "undocumented_input": REASON_UNGOVERNED,
                "raw_text_only": REASON_NARRATIVE,
            }.get(key, REASON_UNGOVERNED)
            violations.append(_violation(mapped, key=key))
            continue
        pat_code = _match_forbidden_pattern(key, contract)
        if pat_code:
            violations.append(_violation(pat_code, key=key))
            continue
        if key not in allowed:
            violations.append(_violation(REASON_UNGOVERNED, key=key))

    for key in required:
        v = inputs.get(key)
        if not isinstance(v, str) or not v.strip():
            violations.append(_violation(REASON_MISSING, key=key))

    primary_reason = REASON_OK
    if violations:
        # Order: hidden > dashboard > narrative > ungoverned > missing > stale
        order = (
            REASON_HIDDEN,
            REASON_DASHBOARD,
            REASON_NARRATIVE,
            REASON_UNGOVERNED,
            REASON_MISSING,
            REASON_STALE,
        )
        for code in order:
            if any(v["reason_code"] == code for v in violations):
                primary_reason = code
                break

    return {
        "ok": not violations,
        "violations": violations,
        "primary_reason": primary_reason,
    }


def validate_policy_result(result: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Validate that a downstream TPA policy result is non-empty and traced.

    Required keys: ``trace_id``, ``policy_result_status`` (one of
    ``allow|block|freeze|repair_required``), ``tpa_policy_result_ref``.
    """
    if result is None or not isinstance(result, Mapping):
        return {
            "ok": False,
            "violations": [_violation(REASON_RESULT_MISSING)],
            "primary_reason": REASON_RESULT_MISSING,
        }

    violations: List[Dict[str, Any]] = []
    for key in ("trace_id", "policy_result_status", "tpa_policy_result_ref"):
        v = result.get(key)
        if not isinstance(v, str) or not v.strip():
            violations.append(_violation(REASON_RESULT_MISSING, key=key))

    status = result.get("policy_result_status")
    if status not in (None, "allow", "block", "freeze", "repair_required"):
        violations.append(_violation(REASON_RESULT_MISSING, status=status))

    primary_reason = REASON_OK if not violations else REASON_RESULT_MISSING
    return {
        "ok": not violations,
        "violations": violations,
        "primary_reason": primary_reason,
    }


__all__ = [
    "CONTRACT_PATH",
    "PolicyInputContractError",
    "REASON_OK",
    "REASON_HIDDEN",
    "REASON_DASHBOARD",
    "REASON_NARRATIVE",
    "REASON_UNGOVERNED",
    "REASON_MISSING",
    "REASON_STALE",
    "REASON_RESULT_MISSING",
    "load_policy_input_contract",
    "validate_policy_inputs",
    "validate_policy_result",
]
