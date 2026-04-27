"""SLO error-budget admission gate.

NX-22: A small, fail-closed adjudication seam over existing SLO/error-budget
artifacts. It does NOT redefine SLO authority; it converts an SLO posture
artifact plus a small set of drift signals into a single
``allow|warn|freeze|block`` decision suitable for control inputs.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional


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


# NS-22: SLO Signal Diet — only a small set of hard trust signals can drive
# freeze/block. Other metrics may be reported as observations but never gate
# promotion unless explicitly promoted by policy.

HARD_TRUST_SIGNALS = (
    "required_eval_pass_status",          # pass | fail
    "replay_match_status",                # match | mismatch | indeterminate
    "lineage_completeness_status",        # healthy | blocked
    "context_admissibility_status",       # allow | block
    "authority_shape_preflight_status",   # pass | fail
    "registry_validation_status",         # pass | fail
    "certification_evidence_index_status",  # ready | blocked | frozen
)


SIGNAL_DIET_REASON_CODES = {
    "SLO_DIET_OK",
    "SLO_DIET_EVAL_FAILURE",
    "SLO_DIET_REPLAY_MISMATCH",
    "SLO_DIET_LINEAGE_GAP",
    "SLO_DIET_CONTEXT_ADMISSION_FAILURE",
    "SLO_DIET_AUTHORITY_SHAPE_VIOLATION",
    "SLO_DIET_REGISTRY_VIOLATION",
    "SLO_DIET_CERTIFICATION_GAP",
    "SLO_DIET_OBSERVATION_ONLY",
    "SLO_DIET_INVALID_SIGNAL",
}


def evaluate_slo_signal_diet(
    *,
    signals: Mapping[str, Any],
    observation_only: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert a small set of hard trust signals into an allow/warn/freeze/block.

    ``signals`` is a flat mapping with the keys in ``HARD_TRUST_SIGNALS``.
    Any other key in ``signals`` is rejected — other metrics belong in
    ``observation_only`` and never freeze/block.

    Returns:
      {"decision": allow|warn|freeze|block,
       "reason_code": canonical (SLO_DIET_*),
       "canonical_category": canonical reason category from the canon mapping,
       "blocking_reasons": [str,...],
       "observed": {key: value, ...},
       "ignored_observations": [str, ...]}
    """
    if not isinstance(signals, Mapping):
        raise SLOGateError("signals must be a mapping")

    unknown = [k for k in signals if k not in HARD_TRUST_SIGNALS]
    if unknown:
        raise SLOGateError(
            f"hard-signal slot received non-hard signals: {sorted(unknown)}; "
            "move them to observation_only or promote them via policy."
        )

    blocking: list[str] = []
    decision = "allow"
    reason_code = "SLO_DIET_OK"
    canonical_category = None

    def _block(reason: str, why: str, category: str) -> None:
        nonlocal decision, reason_code, canonical_category
        decision = "block"
        if reason_code == "SLO_DIET_OK":
            reason_code = reason
            canonical_category = category
        blocking.append(why)

    def _str(name: str) -> str:
        v = signals.get(name)
        if v is None:
            return ""
        if not isinstance(v, str):
            raise SLOGateError(
                f"hard signal {name!r} must be a string (got {type(v).__name__})"
            )
        return v.strip().lower()

    eval_status = _str("required_eval_pass_status")
    replay_status = _str("replay_match_status")
    lineage_status = _str("lineage_completeness_status")
    ctx_status = _str("context_admissibility_status")
    auth_status = _str("authority_shape_preflight_status")
    reg_status = _str("registry_validation_status")
    cert_status = _str("certification_evidence_index_status")

    if eval_status == "fail":
        _block("SLO_DIET_EVAL_FAILURE", "required eval pass status: fail", "EVAL_FAILURE")
    if replay_status == "mismatch":
        _block("SLO_DIET_REPLAY_MISMATCH", "replay match status: mismatch", "REPLAY_MISMATCH")
    if replay_status == "indeterminate":
        _block(
            "SLO_DIET_REPLAY_MISMATCH",
            "replay match status: indeterminate",
            "REPLAY_MISMATCH",
        )
    if lineage_status == "blocked":
        _block("SLO_DIET_LINEAGE_GAP", "lineage completeness: blocked", "LINEAGE_GAP")
    if ctx_status == "block":
        _block(
            "SLO_DIET_CONTEXT_ADMISSION_FAILURE",
            "context admissibility: block",
            "CONTEXT_ADMISSION_FAILURE",
        )
    if auth_status == "fail":
        _block(
            "SLO_DIET_AUTHORITY_SHAPE_VIOLATION",
            "authority-shape preflight: fail",
            "AUTHORITY_SHAPE_VIOLATION",
        )
    if reg_status == "fail":
        _block("SLO_DIET_REGISTRY_VIOLATION", "registry validation: fail", "POLICY_MISMATCH")
    if cert_status == "blocked":
        _block(
            "SLO_DIET_CERTIFICATION_GAP",
            "certification evidence index: blocked",
            "CERTIFICATION_GAP",
        )
    elif cert_status == "frozen":
        decision = "freeze"
        if reason_code == "SLO_DIET_OK":
            reason_code = "SLO_DIET_CERTIFICATION_GAP"
            canonical_category = "CERTIFICATION_GAP"
        blocking.append("certification evidence index: frozen")

    return {
        "decision": decision,
        "reason_code": reason_code,
        "canonical_category": canonical_category,
        "blocking_reasons": blocking,
        "observed": dict(signals),
        "ignored_observations": sorted(list((observation_only or {}).keys())),
    }


__all__ = [
    "CANONICAL_SLO_REASON_CODES",
    "HARD_TRUST_SIGNALS",
    "SIGNAL_DIET_REASON_CODES",
    "SLOGateError",
    "evaluate_slo_budget_gate",
    "evaluate_slo_signal_diet",
]
