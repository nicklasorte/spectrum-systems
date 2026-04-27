"""SLO error-budget admission gate.

NX-22: A small, fail-closed adjudication seam over existing SLO/error-budget
artifacts. It does NOT redefine SLO authority; it converts an SLO posture
artifact plus a small set of drift signals into a single
``allow|warn|freeze|block`` decision suitable for control inputs.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping


CANONICAL_SLO_REASON_CODES = {
    "SLO_OK",
    "SLO_BUDGET_EXHAUSTED",
    "SLO_DRIFT_RISING",
    "SLO_OVERRIDE_RATE_EXCEEDED",
    "SLO_EVAL_PASS_RATE_DEGRADED",
    "SLO_REPLAY_MISMATCH_RATE_HIGH",
    "SLO_INVALID_POSTURE",
}


class SLOGateError(ValueError):
    """Raised when SLO budget gate cannot be deterministically evaluated."""


def evaluate_slo_budget_gate(
    *,
    posture: Mapping[str, Any],
    thresholds: Mapping[str, float] | None = None,
) -> Dict[str, Any]:
    """Convert an SLO posture into an allow/warn/freeze/block decision.

    ``posture`` is expected to expose:
      - ``budget_remaining`` (float in [0,1])
      - ``drift_rate`` (float, optional)
      - ``override_rate`` (float, optional)
      - ``eval_pass_rate`` (float, optional)
      - ``replay_mismatch_rate`` (float, optional)
      - ``trace_id`` (str)

    ``thresholds`` overrides the default thresholds. Defaults:
      - budget_freeze: 0.05  (≤5% remaining → freeze)
      - budget_block:  0.0   (=0 remaining → block)
      - drift_warn:    0.10
      - drift_freeze:  0.25
      - override_warn: 0.10
      - override_freeze: 0.25
      - eval_pass_warn: 0.95
      - eval_pass_freeze: 0.85
      - replay_mismatch_warn: 0.05
      - replay_mismatch_freeze: 0.10
    """
    if not isinstance(posture, Mapping):
        raise SLOGateError("posture must be a mapping")

    th = {
        "budget_freeze": 0.05,
        "budget_block": 0.0,
        "drift_warn": 0.10,
        "drift_freeze": 0.25,
        "override_warn": 0.10,
        "override_freeze": 0.25,
        "eval_pass_warn": 0.95,
        "eval_pass_freeze": 0.85,
        "replay_mismatch_warn": 0.05,
        "replay_mismatch_freeze": 0.10,
    }
    if thresholds is not None:
        th.update({k: float(v) for k, v in thresholds.items()})

    def _f(key: str) -> float | None:
        v = posture.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            raise SLOGateError(f"posture.{key}={v!r} is not numeric")

    budget_remaining = _f("budget_remaining")
    if budget_remaining is None:
        return {
            "decision": "block",
            "reason_code": "SLO_INVALID_POSTURE",
            "blocking_reasons": ["posture.budget_remaining missing"],
            "trace_id": str(posture.get("trace_id") or ""),
        }
    if budget_remaining < 0.0 or budget_remaining > 1.0:
        return {
            "decision": "block",
            "reason_code": "SLO_INVALID_POSTURE",
            "blocking_reasons": [
                f"posture.budget_remaining out of range: {budget_remaining}"
            ],
            "trace_id": str(posture.get("trace_id") or ""),
        }

    drift_rate = _f("drift_rate") or 0.0
    override_rate = _f("override_rate") or 0.0
    eval_pass_rate = _f("eval_pass_rate")
    replay_mismatch_rate = _f("replay_mismatch_rate") or 0.0

    blocking: list[str] = []
    decision = "allow"
    reason_code = "SLO_OK"

    def _escalate(new_decision: str, new_reason: str, why: str) -> None:
        nonlocal decision, reason_code
        order = {"allow": 0, "warn": 1, "freeze": 2, "block": 3}
        if order[new_decision] > order[decision]:
            decision = new_decision
            reason_code = new_reason
        blocking.append(why)

    # Budget
    if budget_remaining <= th["budget_block"]:
        _escalate("block", "SLO_BUDGET_EXHAUSTED", "error budget exhausted")
    elif budget_remaining <= th["budget_freeze"]:
        _escalate(
            "freeze",
            "SLO_BUDGET_EXHAUSTED",
            f"error budget low: {budget_remaining:.3f}",
        )

    # Drift
    if drift_rate >= th["drift_freeze"]:
        _escalate("freeze", "SLO_DRIFT_RISING", f"drift_rate {drift_rate:.3f} ≥ freeze threshold")
    elif drift_rate >= th["drift_warn"]:
        _escalate("warn", "SLO_DRIFT_RISING", f"drift_rate {drift_rate:.3f} ≥ warn threshold")

    # Override rate
    if override_rate >= th["override_freeze"]:
        _escalate("freeze", "SLO_OVERRIDE_RATE_EXCEEDED", f"override_rate {override_rate:.3f}")
    elif override_rate >= th["override_warn"]:
        _escalate("warn", "SLO_OVERRIDE_RATE_EXCEEDED", f"override_rate {override_rate:.3f}")

    # Eval pass rate
    if eval_pass_rate is not None:
        if eval_pass_rate < th["eval_pass_freeze"]:
            _escalate(
                "freeze",
                "SLO_EVAL_PASS_RATE_DEGRADED",
                f"eval_pass_rate {eval_pass_rate:.3f} < freeze threshold",
            )
        elif eval_pass_rate < th["eval_pass_warn"]:
            _escalate(
                "warn",
                "SLO_EVAL_PASS_RATE_DEGRADED",
                f"eval_pass_rate {eval_pass_rate:.3f} < warn threshold",
            )

    # Replay mismatch rate
    if replay_mismatch_rate >= th["replay_mismatch_freeze"]:
        _escalate(
            "freeze",
            "SLO_REPLAY_MISMATCH_RATE_HIGH",
            f"replay_mismatch_rate {replay_mismatch_rate:.3f} ≥ freeze threshold",
        )
    elif replay_mismatch_rate >= th["replay_mismatch_warn"]:
        _escalate(
            "warn",
            "SLO_REPLAY_MISMATCH_RATE_HIGH",
            f"replay_mismatch_rate {replay_mismatch_rate:.3f} ≥ warn threshold",
        )

    return {
        "decision": decision,
        "reason_code": reason_code,
        "blocking_reasons": blocking,
        "trace_id": str(posture.get("trace_id") or ""),
        "thresholds": th,
    }


__all__ = [
    "CANONICAL_SLO_REASON_CODES",
    "SLOGateError",
    "evaluate_slo_budget_gate",
]
