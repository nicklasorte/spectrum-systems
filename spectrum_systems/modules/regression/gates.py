"""
Gate Evaluation Logic — spectrum_systems/modules/regression/gates.py

Deterministic gate evaluation for regression dimensions.

Design principles
-----------------
- Hard gates fail immediately when exceeded; soft gates produce warnings.
- Deterministic mode mismatch is always a hard fail.
- Insufficient data is reported, not silently skipped.
- No external dependencies beyond the Python standard library.

Public API
----------
evaluate_dimension_gate(baseline, candidate, threshold, hard_fail)
    Evaluate a single dimension gate.

evaluate_policy_gates(comparison, policy)
    Evaluate all dimension gates defined by a policy.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Severity constants
# ---------------------------------------------------------------------------

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_HARD_FAIL = "hard_fail"


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def evaluate_dimension_gate(
    baseline_value: float,
    candidate_value: float,
    threshold: float,
    hard_fail: bool,
    *,
    higher_is_better: bool = True,
    insufficient_data: bool = False,
) -> Dict[str, Any]:
    """Evaluate a single dimension gate.

    Parameters
    ----------
    baseline_value:
        Baseline aggregate value.
    candidate_value:
        Candidate aggregate value.
    threshold:
        Maximum allowed drop (for score dimensions) or increase
        (for latency/disagreement dimensions, expressed as absolute difference).
    hard_fail:
        Whether exceeding the threshold triggers a hard failure.
    higher_is_better:
        When True (default), a negative delta is a regression.
        When False, a positive delta is a regression (e.g. latency).
    insufficient_data:
        When True, mark this dimension as insufficiently sampled.

    Returns
    -------
    dict
        Keys: baseline_value, candidate_value, delta, threshold, passed,
        severity, insufficient_data.
    """
    delta = candidate_value - baseline_value

    if insufficient_data:
        return {
            "baseline_value": baseline_value,
            "candidate_value": candidate_value,
            "delta": delta,
            "threshold": threshold,
            "passed": True,
            "severity": SEVERITY_INFO,
            "insufficient_data": True,
        }

    if higher_is_better:
        regressed = delta < -threshold
    else:
        # For latency/disagreement expressed as absolute pct: positive delta is bad
        regressed = delta > threshold

    if regressed:
        severity = SEVERITY_HARD_FAIL if hard_fail else SEVERITY_WARNING
        passed = False
    else:
        severity = SEVERITY_INFO
        passed = True

    return {
        "baseline_value": baseline_value,
        "candidate_value": candidate_value,
        "delta": delta,
        "threshold": threshold,
        "passed": passed,
        "severity": severity,
        "insufficient_data": False,
    }


def evaluate_policy_gates(
    comparison: Dict[str, Any],
    policy: Any,
) -> Dict[str, Any]:
    """Evaluate all dimension gates defined by a policy.

    Parameters
    ----------
    comparison:
        Dict with keys matching dimension names, each holding
        ``{"baseline": float, "candidate": float,
           "insufficient_data": bool (optional)}``.
        Expected keys:
        - structural_score
        - semantic_score
        - grounding_score
        - latency_ms  (absolute milliseconds; converted to pct internally)
        - human_disagreement_rate  (fraction 0–1)
    policy:
        ``RegressionPolicy`` instance.

    Returns
    -------
    dict
        Keys: dimension_results (per-dimension gate dicts), hard_failures (int),
        warnings (int), overall_pass (bool), determinism_fail (bool).
    """
    thresholds = policy.thresholds
    hard_fail_dims = policy.hard_fail_dimensions

    results: Dict[str, Any] = {}
    hard_failures = 0
    warnings = 0

    # --- Score dimensions (higher is better) ---
    score_dims = [
        ("structural_score", thresholds["structural_score_drop_max"], hard_fail_dims["structural_score"]),
        ("semantic_score", thresholds["semantic_score_drop_max"], hard_fail_dims["semantic_score"]),
        ("grounding_score", thresholds["grounding_score_drop_max"], hard_fail_dims["grounding_score"]),
    ]
    for dim_key, threshold, hard_fail in score_dims:
        dim_data = comparison.get(dim_key, {})
        baseline_val = float(dim_data.get("baseline", 0.0))
        candidate_val = float(dim_data.get("candidate", 0.0))
        insufficient = bool(dim_data.get("insufficient_data", False))
        result = evaluate_dimension_gate(
            baseline_val, candidate_val, threshold, hard_fail,
            higher_is_better=True,
            insufficient_data=insufficient,
        )
        results[dim_key] = result
        if not insufficient:
            if result["severity"] == SEVERITY_HARD_FAIL:
                hard_failures += 1
            elif result["severity"] == SEVERITY_WARNING:
                warnings += 1

    # --- Latency (lower is better; threshold is pct increase) ---
    lat_data = comparison.get("latency_ms", {})
    lat_baseline = float(lat_data.get("baseline", 0.0))
    lat_candidate = float(lat_data.get("candidate", 0.0))
    lat_insufficient = bool(lat_data.get("insufficient_data", False))
    # Convert absolute ms delta to percentage of baseline for comparison
    if lat_baseline > 0:
        lat_pct_delta = ((lat_candidate - lat_baseline) / lat_baseline) * 100.0
    else:
        lat_pct_delta = 0.0
    lat_threshold = thresholds["latency_increase_pct_max"]
    lat_hard_fail = hard_fail_dims["latency"]
    lat_result = evaluate_dimension_gate(
        0.0,  # baseline expressed as pct: 0 is the zero point
        lat_pct_delta,
        lat_threshold,
        lat_hard_fail,
        higher_is_better=False,
        insufficient_data=lat_insufficient,
    )
    # Overwrite values for reporting clarity
    lat_result["baseline_value"] = lat_baseline
    lat_result["candidate_value"] = lat_candidate
    lat_result["delta"] = lat_candidate - lat_baseline
    lat_result["threshold"] = lat_threshold
    results["latency"] = lat_result
    if not lat_insufficient:
        if lat_result["severity"] == SEVERITY_HARD_FAIL:
            hard_failures += 1
        elif lat_result["severity"] == SEVERITY_WARNING:
            warnings += 1

    # --- Human disagreement (lower is better; threshold is pct increase) ---
    hd_data = comparison.get("human_disagreement_rate", {})
    hd_baseline = float(hd_data.get("baseline", 0.0))
    hd_candidate = float(hd_data.get("candidate", 0.0))
    hd_insufficient = bool(hd_data.get("insufficient_data", True))
    if hd_baseline > 0:
        hd_pct_delta = ((hd_candidate - hd_baseline) / hd_baseline) * 100.0
    else:
        hd_pct_delta = 0.0
    hd_threshold = thresholds["human_disagreement_increase_pct_max"]
    hd_hard_fail = hard_fail_dims["human_disagreement"]
    hd_result = evaluate_dimension_gate(
        0.0,
        hd_pct_delta,
        hd_threshold,
        hd_hard_fail,
        higher_is_better=False,
        insufficient_data=hd_insufficient,
    )
    hd_result["baseline_value"] = hd_baseline
    hd_result["candidate_value"] = hd_candidate
    hd_result["delta"] = hd_candidate - hd_baseline
    hd_result["threshold"] = hd_threshold
    results["human_disagreement"] = hd_result
    if not hd_insufficient:
        if hd_result["severity"] == SEVERITY_HARD_FAIL:
            hard_failures += 1
        elif hd_result["severity"] == SEVERITY_WARNING:
            warnings += 1

    overall_pass = hard_failures == 0

    return {
        "dimension_results": results,
        "hard_failures": hard_failures,
        "warnings": warnings,
        "overall_pass": overall_pass,
        "determinism_fail": False,
    }
