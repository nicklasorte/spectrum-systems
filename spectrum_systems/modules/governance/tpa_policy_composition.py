"""Deterministic loading and application of TPA policy composition rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class TPAPolicyCompositionError(ValueError):
    """Raised when TPA policy composition cannot be loaded or resolved."""


_DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[3] / "config" / "policy" / "tpa_policy_composition.json"


def _validate_schema(instance: Dict[str, Any], schema_name: str, *, label: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise TPAPolicyCompositionError(f"{label} failed schema validation ({schema_name}): {details}")


def load_tpa_policy_composition(path: str | Path | None = None) -> Dict[str, Any]:
    """Load and schema-validate governed TPA policy composition rules."""
    policy_path = Path(path) if path is not None else _DEFAULT_POLICY_PATH
    if not policy_path.is_file():
        raise TPAPolicyCompositionError(f"tpa_policy_composition file not found: {policy_path}")
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TPAPolicyCompositionError(f"tpa_policy_composition is not valid JSON: {policy_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TPAPolicyCompositionError(f"tpa_policy_composition must be a JSON object: {policy_path}")
    _validate_schema(payload, "tpa_policy_composition", label="tpa_policy_composition")
    return payload


def resolve_tpa_policy_decision(inputs: Dict[str, Any], *, composition: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Resolve TPA policy conflicts via contract-backed precedence rules."""
    resolved = composition if composition is not None else load_tpa_policy_composition()
    if not isinstance(resolved, dict):
        raise TPAPolicyCompositionError("resolved tpa_policy_composition must be an object")

    precedence = list(resolved.get("precedence") or [])
    severity_order = list(resolved.get("severity_order") or [])
    severity_rank = {value: idx for idx, value in enumerate(severity_order)}
    rules = resolved.get("rules") or {}
    if not isinstance(rules, dict):
        raise TPAPolicyCompositionError("tpa_policy_composition.rules must be an object")

    final_decision = "allow"
    reasons: list[str] = []

    def _apply(decision: str, reason: str) -> None:
        nonlocal final_decision
        if decision not in severity_rank:
            raise TPAPolicyCompositionError(f"unknown policy decision value: {decision}")
        if severity_rank[decision] > severity_rank[final_decision]:
            final_decision = decision
        reasons.append(reason)

    for policy_key in precedence:
        if policy_key == "tpa_scope_policy":
            required_scope = bool(inputs.get("required_scope"))
            lineage_present = bool(inputs.get("tpa_lineage_present"))
            if required_scope and not lineage_present:
                decision = str((rules.get(policy_key) or {}).get("required_scope_missing_lineage_decision") or "block")
                _apply(decision, "required_scope_missing_tpa_lineage")
        elif policy_key == "lightweight_mode_constraints":
            requested_mode = str(inputs.get("tpa_mode") or "full")
            lightweight_eligible = bool(inputs.get("lightweight_eligible", True))
            if requested_mode == "lightweight" and not lightweight_eligible:
                decision = str((rules.get(policy_key) or {}).get("requested_without_eligibility_decision") or "block")
                _apply(decision, "lightweight_mode_not_eligible")
        elif policy_key == "cleanup_only_requirements":
            if str(inputs.get("execution_mode") or "") != "cleanup_only":
                continue
            cleanup = inputs.get("cleanup_only_validation")
            cleanup_obj = cleanup if isinstance(cleanup, dict) else {}
            if not bool(cleanup_obj.get("equivalence_proven")):
                decision = str((rules.get(policy_key) or {}).get("missing_equivalence_decision") or "block")
                _apply(decision, "cleanup_only_missing_equivalence")
            replay_ref = str(cleanup_obj.get("replay_ref") or "").strip()
            if not replay_ref:
                decision = str((rules.get(policy_key) or {}).get("missing_replay_ref_decision") or "block")
                _apply(decision, "cleanup_only_missing_replay_ref")
        elif policy_key == "complexity_regression_gate":
            blocked = set((rules.get(policy_key) or {}).get("blocking_decisions") or [])
            decision = str(inputs.get("complexity_decision") or "allow")
            if decision in blocked:
                _apply(decision, f"complexity_regression_gate_{decision}")
        elif policy_key == "simplicity_review":
            blocked = set((rules.get(policy_key) or {}).get("blocking_decisions") or [])
            decision = str(inputs.get("simplicity_decision") or "allow")
            if decision in blocked:
                _apply(decision, f"simplicity_review_{decision}")

    promotion_ready_requested = bool(inputs.get("promotion_ready_requested", False))
    promotion_ready = bool(promotion_ready_requested and final_decision in {"allow", "warn"})

    return {
        "policy_id": str(resolved.get("policy_id") or ""),
        "final_decision": final_decision,
        "promotion_ready": promotion_ready,
        "blocking_reasons": sorted(set(reasons)),
        "applied_precedence": precedence,
    }


__all__ = [
    "TPAPolicyCompositionError",
    "load_tpa_policy_composition",
    "resolve_tpa_policy_decision",
]
