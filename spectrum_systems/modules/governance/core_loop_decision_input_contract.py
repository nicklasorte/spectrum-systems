"""CL-16 / CL-18: CDE control-decision input contract — pure validator.

Restricts CDE inputs to governed artifacts only:

  * AEX admission result;
  * PQX execution envelope;
  * EVL eval summary;
  * TPA policy result;
  * trace / lineage / replay status.

Free-text-only closure, dashboard-only closure, runbook-only closure,
stale proof, and missing TPA result are forbidden. The validator is
non-owning. CDE retains canonical control / closure authority. The
validator surfaces stable canonical reason codes under the
``decision`` precedence class.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "governance"
    / "cde_decision_input_contract.json"
)

REASON_OK = "DECISION_INPUT_OK"
REASON_FREE_TEXT = "DECISION_INPUT_FREE_TEXT_ONLY"
REASON_DASHBOARD = "DECISION_INPUT_DASHBOARD_ONLY"
REASON_RUNBOOK = "DECISION_INPUT_RUNBOOK_ONLY"
REASON_STALE = "DECISION_INPUT_STALE_PROOF"
REASON_MISSING_TPA = "DECISION_INPUT_MISSING_TPA"
REASON_MISSING_EVAL = "DECISION_INPUT_MISSING_EVAL"
REASON_MISSING_EXECUTION = "DECISION_INPUT_MISSING_EXECUTION"
REASON_FREEZE_REQUIRED = "DECISION_FREEZE_REQUIRED"


class DecisionInputContractError(ValueError):
    """Raised only on programmer-misuse."""


def _violation(code: str, **details: Any) -> Dict[str, Any]:
    return {"reason_code": code, **details}


def load_decision_input_contract(path: Optional[Path] = None) -> Dict[str, Any]:
    p = Path(path) if path is not None else CONTRACT_PATH
    if not p.exists():
        raise DecisionInputContractError(f"contract not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def validate_decision_inputs(
    inputs: Mapping[str, Any],
    *,
    contract: Optional[Mapping[str, Any]] = None,
    proof_age_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Validate CDE decision inputs against the contract.

    ``proof_age_seconds`` (when supplied) is compared against the
    contract's ``freshness_rules.max_age_seconds``. A stale input fails
    closed with ``DECISION_INPUT_STALE_PROOF``.
    """
    if not isinstance(inputs, Mapping):
        raise DecisionInputContractError("inputs must be a mapping")

    if contract is None:
        contract = load_decision_input_contract()

    allowed = set(contract.get("allowed_input_keys") or ())
    required = list(contract.get("required_input_keys") or ())
    forbidden = set(contract.get("forbidden_input_keys") or ())
    forbidden_codes = contract.get("forbidden_input_reason_codes") or {}
    missing_codes = contract.get("missing_input_reason_codes") or {}
    freshness = contract.get("freshness_rules") or {}

    violations: List[Dict[str, Any]] = []

    for key in inputs.keys():
        if not isinstance(key, str):
            continue
        if key in forbidden:
            code = forbidden_codes.get(key, REASON_FREE_TEXT)
            violations.append(_violation(code, key=key))
            continue
        if key not in allowed:
            violations.append(_violation(REASON_FREE_TEXT, key=key))

    for key in required:
        v = inputs.get(key)
        if not isinstance(v, str) or not v.strip():
            code = missing_codes.get(key, REASON_MISSING_EXECUTION)
            violations.append(_violation(code, key=key))

    if proof_age_seconds is not None and proof_age_seconds > float(
        freshness.get("max_age_seconds", float("inf"))
    ):
        violations.append(
            _violation(
                freshness.get("stale_reason_code", REASON_STALE),
                age_seconds=proof_age_seconds,
            )
        )

    primary_reason = REASON_OK
    if violations:
        # Decision-class precedence inside the decision stage:
        # missing TPA > missing eval > missing execution > stale > runbook > dashboard > free-text.
        order = (
            REASON_MISSING_TPA,
            REASON_MISSING_EVAL,
            REASON_MISSING_EXECUTION,
            REASON_STALE,
            REASON_RUNBOOK,
            REASON_DASHBOARD,
            REASON_FREE_TEXT,
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


def validate_decision_outcome(outcome: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Validate that a CDE decision artifact carries a recognized outcome.

    Allowed: ``allow | block | freeze | repair_required``. Unknown outcomes
    fail closed.
    """
    if outcome is None or not isinstance(outcome, Mapping):
        return {
            "ok": False,
            "violations": [_violation(REASON_FREEZE_REQUIRED)],
            "primary_reason": REASON_FREEZE_REQUIRED,
        }
    decision = outcome.get("decision") or outcome.get("control_outcome")
    if decision not in ("allow", "block", "freeze", "repair_required"):
        return {
            "ok": False,
            "violations": [_violation(REASON_FREEZE_REQUIRED, got=decision)],
            "primary_reason": REASON_FREEZE_REQUIRED,
        }
    return {"ok": True, "violations": [], "primary_reason": REASON_OK}


__all__ = [
    "CONTRACT_PATH",
    "DecisionInputContractError",
    "REASON_OK",
    "REASON_FREE_TEXT",
    "REASON_DASHBOARD",
    "REASON_RUNBOOK",
    "REASON_STALE",
    "REASON_MISSING_TPA",
    "REASON_MISSING_EVAL",
    "REASON_MISSING_EXECUTION",
    "REASON_FREEZE_REQUIRED",
    "load_decision_input_contract",
    "validate_decision_inputs",
    "validate_decision_outcome",
]
