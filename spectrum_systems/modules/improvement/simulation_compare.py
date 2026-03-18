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
)
    -> str  # "promote" | "hold" | "reject"
"""
from __future__ import annotations

from typing import Any, Dict

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# A delta larger than this in the negative direction is a hard regression.
_HARD_REGRESSION_THRESHOLD: float = -0.10

# A delta between hard threshold and this is a warning.
_WARN_REGRESSION_THRESHOLD: float = -0.03

# Minimum targeted metric improvement to recommend promotion.
_MIN_IMPROVEMENT_FOR_PROMOTE: float = 0.01

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
) -> str:
    """Determine the promotion recommendation from simulation results.

    Promotion logic
    ---------------
    - ``promote`` if:
        - simulation_fidelity is "high" or "medium"
        - targeted metric improved (observed_direction matches expected_direction)
        - no hard regression failures
    - ``hold`` if:
        - mixed results or inconclusive evidence
        - targeted metric improved but warnings exist
        - fidelity is "low" but no regressions
    - ``reject`` if:
        - hard regression failures
        - targeted metric worsened (observed_direction opposite to expected)
        - simulation fidelity is "none"

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

    Returns
    -------
    str
        "promote", "hold", or "reject".
    """
    hard_failures = regression_check.get("hard_failures", 0)
    warnings = regression_check.get("warnings", 0)
    expected_direction = targeted_effect.get("expected_direction", "increase")
    observed_direction = targeted_effect.get("observed_direction", "none")

    # Reject conditions
    if simulation_fidelity == "none":
        return "reject"

    if hard_failures > 0:
        return "reject"

    # Check if observed direction is opposite to expected (regression in target)
    _opposites = {"increase": "decrease", "decrease": "increase"}
    if observed_direction == _opposites.get(expected_direction):
        return "reject"

    # Promote conditions
    if simulation_fidelity in ("high", "medium"):
        if observed_direction == expected_direction and hard_failures == 0:
            if warnings == 0:
                return "promote"
            else:
                # Improvements with warnings → hold for safety
                return "hold"

    # Low fidelity: hold even if target metric improved
    if simulation_fidelity == "low":
        if observed_direction == expected_direction:
            return "hold"
        return "hold"

    # Mixed/unclear results
    return "hold"
