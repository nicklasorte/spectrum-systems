"""
Simulation Compare — spectrum_systems/modules/improvement/simulation_compare.py

Baseline vs candidate comparison logic for AW2 simulation results.

Reuses vocabulary from the AN evaluation framework, AP observability output,
and AR regression harness (referenced via structural conventions; adapts to
whatever eval/observability infrastructure is available).

Public API
----------
compare_baseline_candidate(baseline_summary, candidate_summary)
    -> score_deltas_dict

summarize_targeted_effect(proposed_action, deltas, action_type)
    -> targeted_effect_dict

check_regression(baseline_summary, candidate_summary, *, hard_threshold, warn_threshold)
    -> regression_check_dict

determine_promotion_recommendation(
    simulation_fidelity,
    targeted_effect,
    regression_check,
    deltas,
    *,
    candidate_summary=None,
    baseline_available=True,
)
    -> Dict[str, Any]  # {"recommendation", "gating_decision_reason", "gating_flags"}
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# A delta larger than this in the negative direction is a hard regression.
_HARD_REGRESSION_THRESHOLD: float = -0.10

# A delta between hard threshold and this is a warning.
_WARN_REGRESSION_THRESHOLD: float = -0.03

# Minimum targeted metric improvement to recommend promotion.
_MIN_IMPROVEMENT_FOR_PROMOTE: float = 0.01

# Latency regression thresholds (ms increase = bad).
_HARD_LATENCY_REGRESSION_MS: float = 50.0
_WARN_LATENCY_REGRESSION_MS: float = 20.0

# ---------------------------------------------------------------------------
# AR Hard Gating constants (Prompt AZ)
# ---------------------------------------------------------------------------

# Minimum semantic_score_delta required to recommend promotion.
_MIN_SEMANTIC_IMPROVEMENT: float = 0.05

# Maximum allowed regression in any score metric before promotion is blocked.
# Changes beyond this tolerance in the negative direction → REJECT.
_MAX_REGRESSION_TOLERANCE: float = 0.01

# Whether a zero structural score in the candidate is a hard reject gate.
_REQUIRE_STRUCTURAL_SCORE: bool = True

# ---------------------------------------------------------------------------
# Metric target mappings per action_type
# ---------------------------------------------------------------------------

_ACTION_TYPE_TARGET_METRIC: Dict[str, str] = {
    "prompt_change": "structural_score",
    "grounding_rule_change": "grounding_score",
    "schema_change": "structural_score",
    "input_quality_rule_change": "structural_score",
    "retrieval_change": "semantic_score",
    "observability_change": "latency_ms",
    "no_action": "structural_score",
}

# Whether the target metric should increase or decrease for improvement.
# latency_ms improvement = decrease; all scores improvement = increase.
_ACTION_TYPE_EXPECTED_DIRECTION: Dict[str, str] = {
    "prompt_change": "increase",
    "grounding_rule_change": "increase",
    "schema_change": "increase",
    "input_quality_rule_change": "increase",
    "retrieval_change": "increase",
    "observability_change": "decrease",
    "no_action": "increase",
}

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def compare_baseline_candidate(
    baseline_summary: Dict[str, Any],
    candidate_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute score deltas between candidate and baseline.

    Parameters
    ----------
    baseline_summary:
        Eval summary dict for the baseline configuration.
    candidate_summary:
        Eval summary dict for the candidate configuration.

    Returns
    -------
    Dict[str, Any]
        Deltas dict matching the ``score_deltas`` schema definition.
    """
    def _delta(key: str) -> float:
        b = float(baseline_summary.get(key, 0.0))
        c = float(candidate_summary.get(key, 0.0))
        return round(c - b, 6)

    return {
        "structural_score_delta": _delta("structural_score"),
        "semantic_score_delta": _delta("semantic_score"),
        "grounding_score_delta": _delta("grounding_score"),
        "latency_ms_delta": _delta("latency_ms"),
    }


def summarize_targeted_effect(
    proposed_action: Dict[str, Any],
    deltas: Dict[str, Any],
    action_type: str,
) -> Dict[str, Any]:
    """Determine whether the simulation produced the expected targeted effect.

    Parameters
    ----------
    proposed_action:
        The proposed action dict from the RemediationPlan.
    deltas:
        Score deltas from ``compare_baseline_candidate``.
    action_type:
        The action_type string.

    Returns
    -------
    Dict[str, Any]
        ``targeted_effect`` dict matching the schema definition.
    """
    target_component = proposed_action.get("target_component", "unknown")
    target_metric = _ACTION_TYPE_TARGET_METRIC.get(action_type, "structural_score")
    expected_direction = _ACTION_TYPE_EXPECTED_DIRECTION.get(action_type, "increase")

    # Determine observed direction
    delta_key = f"{target_metric}_delta"
    delta_value = float(deltas.get(delta_key, 0.0))

    if target_metric == "latency_ms":
        # For latency, lower is better; negative delta = improvement = "decrease"
        if delta_value < -0.001:
            observed_direction = "decrease"
        elif delta_value > 0.001:
            observed_direction = "increase"
        else:
            observed_direction = "none"
    else:
        # For scores, higher is better; positive delta = improvement = "increase"
        if delta_value > 0.001:
            observed_direction = "increase"
        elif delta_value < -0.001:
            observed_direction = "decrease"
        else:
            observed_direction = "none"

    return {
        "target_component": target_component,
        "target_metric": target_metric,
        "expected_direction": expected_direction,
        "observed_direction": observed_direction,
    }


def check_regression(
    baseline_summary: Dict[str, Any],
    candidate_summary: Dict[str, Any],
    *,
    hard_threshold: float = _HARD_REGRESSION_THRESHOLD,
    warn_threshold: float = _WARN_REGRESSION_THRESHOLD,
) -> Dict[str, Any]:
    """Check for regressions in the candidate configuration.

    A regression occurs when a candidate metric is significantly lower than
    its baseline.

    Parameters
    ----------
    baseline_summary:
        Eval summary dict for the baseline.
    candidate_summary:
        Eval summary dict for the candidate.
    hard_threshold:
        Delta below which a metric change is a hard failure (default -0.10).
    warn_threshold:
        Delta below which a metric change is a warning (default -0.03).

    Returns
    -------
    Dict[str, Any]
        ``regression_check`` dict matching the schema definition.
    """
    score_metrics = ["structural_score", "semantic_score", "grounding_score"]
    hard_failures = 0
    warnings = 0

    for metric in score_metrics:
        b = float(baseline_summary.get(metric, 0.0))
        c = float(candidate_summary.get(metric, 0.0))
        delta = c - b
        if delta < hard_threshold:
            hard_failures += 1
        elif delta < warn_threshold:
            warnings += 1

    # Check latency regression (an increase in latency_ms is a regression).
    b_latency = float(baseline_summary.get("latency_ms", 0.0))
    c_latency = float(candidate_summary.get("latency_ms", 0.0))
    latency_delta = c_latency - b_latency
    if latency_delta > _HARD_LATENCY_REGRESSION_MS:
        hard_failures += 1
    elif latency_delta > _WARN_LATENCY_REGRESSION_MS:
        warnings += 1

    return {
        "overall_pass": hard_failures == 0,
        "hard_failures": hard_failures,
        "warnings": warnings,
    }


def determine_promotion_recommendation(
    simulation_fidelity: str,
    targeted_effect: Dict[str, Any],
    regression_check: Dict[str, Any],
    deltas: Dict[str, Any],
    *,
    candidate_summary: Optional[Dict[str, Any]] = None,
    baseline_available: bool = True,
) -> Dict[str, Any]:
    """Determine the promotion recommendation from simulation results.

    AR Hard Gating (Prompt AZ) — fail-closed enforcement
    -----------------------------------------------------
    The system defaults to HOLD or REJECT unless ALL strict criteria are met.

    Returns "promote" only when ALL of the following are true:
    - ``baseline_available`` is True
    - ``simulation_fidelity`` is "high" or "medium"
    - ``semantic_score_delta`` >= ``_MIN_SEMANTIC_IMPROVEMENT`` (0.05)
    - ``structural_score`` of candidate > 0 (when candidate_summary provided)
    - No regressions beyond ``_MAX_REGRESSION_TOLERANCE`` in any metric
    - No hard regression failures from ``check_regression``
    - No regression warnings from ``check_regression``
    - ``targeted_effect.observed_direction`` matches ``expected_direction``
    - Grounding score is sensitive to output changes

    Parameters
    ----------
    simulation_fidelity:
        "high", "medium", "low", or "none".
    targeted_effect:
        Dict from ``summarize_targeted_effect``.
    regression_check:
        Dict from ``check_regression``.
    deltas:
        Score deltas from ``compare_baseline_candidate``.
    candidate_summary:
        Optional candidate eval summary; used for structural validity hard gate.
    baseline_available:
        False when no real baseline was available for comparison → HOLD.

    Returns
    -------
    Dict[str, Any]
        ``{"recommendation": str, "gating_decision_reason": str, "gating_flags": List[str]}``
        where recommendation is "promote", "hold", or "reject".
    """
    gating_flags: List[str] = []

    def _result(rec: str, reason: str) -> Dict[str, Any]:
        return {
            "recommendation": rec,
            "gating_decision_reason": reason,
            "gating_flags": list(gating_flags),
        }

    # F. DEFAULT FAIL-CLOSED: missing baseline signal → HOLD
    if not baseline_available:
        gating_flags.append("insufficient_signal")
        return _result("hold", "insufficient_signal")

    # Hard reject: simulation could not be run (fidelity=none)
    if simulation_fidelity == "none":
        gating_flags.append("insufficient_signal")
        return _result("reject", "insufficient_signal")

    # B. STRUCTURAL VALIDITY HARD GATE: candidate structural_score == 0.0 → REJECT
    if _REQUIRE_STRUCTURAL_SCORE and candidate_summary is not None:
        structural = float(candidate_summary.get("structural_score", 1.0))
        if structural == 0.0:
            gating_flags.append("structural_failure")
            return _result("reject", "structural_failure")

    # C/D. REGRESSION BLOCK: check hard failures from check_regression
    hard_failures = regression_check.get("hard_failures", 0)
    if hard_failures > 0:
        gating_flags.append("regression_detected")
        return _result("reject", "regression_detected")

    # C/D. REGRESSION BLOCK: check per-metric deltas beyond tolerance
    semantic_delta = float(deltas.get("semantic_score_delta", 0.0))
    structural_delta = float(deltas.get("structural_score_delta", 0.0))
    grounding_delta = float(deltas.get("grounding_score_delta", 0.0))
    latency_delta = float(deltas.get("latency_ms_delta", 0.0))

    if semantic_delta < -_MAX_REGRESSION_TOLERANCE:
        gating_flags.append("regression_detected")
        return _result("reject", "regression_detected")
    if structural_delta < -_MAX_REGRESSION_TOLERANCE:
        gating_flags.append("regression_detected")
        return _result("reject", "regression_detected")
    if grounding_delta < -_MAX_REGRESSION_TOLERANCE:
        gating_flags.append("regression_detected")
        return _result("reject", "regression_detected")
    if latency_delta > _HARD_LATENCY_REGRESSION_MS:
        gating_flags.append("regression_detected")
        return _result("reject", "regression_detected")

    # Check if target metric moved opposite to expected direction
    expected_direction = targeted_effect.get("expected_direction", "increase")
    observed_direction = targeted_effect.get("observed_direction", "none")
    _opposites = {"increase": "decrease", "decrease": "increase"}
    if observed_direction == _opposites.get(expected_direction):
        gating_flags.append("regression_detected")
        return _result("reject", "regression_detected")

    # A. MINIMUM SEMANTIC IMPROVEMENT: semantic_score_delta must meet threshold
    if semantic_delta < _MIN_SEMANTIC_IMPROVEMENT:
        gating_flags.append("low_semantic_improvement")
        return _result("hold", "low_semantic_improvement")

    # Require fidelity of high or medium for promotion
    if simulation_fidelity not in ("high", "medium"):
        gating_flags.append("low_fidelity")
        return _result("hold", "low_fidelity")

    # Block promotion when regression warnings exist
    warnings = regression_check.get("warnings", 0)
    if warnings > 0:
        gating_flags.append("regression_warning")
        return _result("hold", "regression_warning")

    # Require observed direction to match expected
    if observed_direction != expected_direction:
        gating_flags.append("insufficient_signal")
        return _result("hold", "insufficient_signal")

    # E. MEANINGFUL CHANGE CHECK: require minimum improvement in target metric
    target_metric = targeted_effect.get("target_metric", "structural_score")
    delta_key = f"{target_metric}_delta"
    delta_magnitude = abs(float(deltas.get(delta_key, 0.0)))
    if delta_magnitude < _MIN_IMPROVEMENT_FOR_PROMOTE:
        gating_flags.append("insufficient_target_improvement")
        return _result("hold", "insufficient_target_improvement")

    # E. GROUNDING CONSISTENCY CHECK: grounding unchanged while other outputs changed
    # Use _MIN_IMPROVEMENT_FOR_PROMOTE as the threshold for "meaningful output change"
    # (distinct from _MAX_REGRESSION_TOLERANCE which guards against regressions).
    grounding_unchanged = abs(grounding_delta) <= _MAX_REGRESSION_TOLERANCE
    outputs_changed = (
        abs(semantic_delta) > _MIN_IMPROVEMENT_FOR_PROMOTE
        or abs(structural_delta) > _MIN_IMPROVEMENT_FOR_PROMOTE
    )
    if grounding_unchanged and outputs_changed:
        gating_flags.append("grounding_not_sensitive")
        return _result("hold", "grounding_not_sensitive")

    # All gates passed → PROMOTE
    return _result("promote", "all_gates_passed")
