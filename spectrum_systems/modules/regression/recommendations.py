"""
Regression Recommendation Engine — spectrum_systems/modules/regression/recommendations.py

Rule-based recommendation generation from regression report data.

Design principles
-----------------
- Purely rule-based; no LLM calls.
- Recommendations are specific enough to guide debugging.
- Pass-level attribution is used when available.
- No external dependencies beyond the Python standard library.

Public API
----------
generate_recommendations(report_dict)
    Generate a list of recommendation strings from a RegressionReport dict.
"""
from __future__ import annotations

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Recommendation rules
# ---------------------------------------------------------------------------


def generate_recommendations(report_dict: Dict[str, Any]) -> List[str]:
    """Generate concise, actionable recommendations from a regression report.

    Parameters
    ----------
    report_dict:
        A dict matching the RegressionReport schema (as produced by
        ``RegressionHarness.generate_report``).

    Returns
    -------
    list of str
        Ordered from highest to lowest severity.
    """
    recommendations: List[str] = []
    dim_results = report_dict.get("dimension_results", {})
    worst = report_dict.get("worst_regressions", [])
    summary = report_dict.get("summary", {})

    # --- Hard-fail recommendations (highest priority) ---
    hard_dims = [
        k for k, v in dim_results.items()
        if v.get("severity") == "hard_fail" and not v.get("insufficient_data", False)
    ]
    for dim in hard_dims:
        result = dim_results[dim]
        delta = result.get("delta", 0.0)
        # Look for pass-type context in worst regressions
        matching_passes = [
            w for w in worst
            if w.get("dimension") == dim and w.get("pass_type")
        ]
        if matching_passes:
            pass_list = ", ".join(sorted({w["pass_type"] for w in matching_passes}))
            recommendations.append(
                f"HARD FAIL: {_dim_label(dim)} dropped by {abs(delta):.4f} "
                f"(threshold exceeded). Investigate pass(es): {pass_list}."
            )
        else:
            recommendations.append(
                f"HARD FAIL: {_dim_label(dim)} dropped by {abs(delta):.4f} "
                f"(threshold exceeded). Review recent changes to prompts or model adapter."
            )

    # --- Warning recommendations ---
    warn_dims = [
        k for k, v in dim_results.items()
        if v.get("severity") == "warning" and not v.get("insufficient_data", False)
    ]
    for dim in warn_dims:
        result = dim_results[dim]
        delta = result.get("delta", 0.0)
        matching_passes = [
            w for w in worst
            if w.get("dimension") == dim and w.get("pass_type")
        ]
        if matching_passes:
            pass_list = ", ".join(sorted({w["pass_type"] for w in matching_passes}))
            recommendations.append(
                f"WARNING: {_dim_label(dim)} degraded by {abs(delta):.4f}. "
                f"Monitor pass(es): {pass_list}."
            )
        else:
            recommendations.append(
                f"WARNING: {_dim_label(dim)} degraded by {abs(delta):.4f}. "
                f"Monitor for further degradation before next release."
            )

    # --- Grounding-specific guidance ---
    grounding = dim_results.get("grounding_score", {})
    if grounding.get("severity") in ("warning", "hard_fail") and not grounding.get("insufficient_data", False):
        recommendations.append(
            "Grounding failures increased; inspect upstream_pass_refs enforcement "
            "and verify that reference documents have not changed."
        )

    # --- Latency-specific guidance ---
    latency = dim_results.get("latency", {})
    if latency.get("severity") in ("warning", "hard_fail") and not latency.get("insufficient_data", False):
        lat_delta = latency.get("delta", 0.0)
        matching_passes = [w for w in worst if w.get("dimension") == "latency_ms" and w.get("pass_type")]
        if matching_passes:
            pass_list = ", ".join(sorted({w["pass_type"] for w in matching_passes}))
            recommendations.append(
                f"Latency increased by {lat_delta:.0f} ms. "
                f"Regression isolated to pass(es): {pass_list}; "
                f"compare model adapter/scoring pass behavior."
            )
        else:
            recommendations.append(
                f"Latency increased by {lat_delta:.0f} ms. "
                "Compare model adapter versions and scoring pass configuration."
            )

    # --- Human disagreement guidance ---
    hd = dim_results.get("human_disagreement", {})
    if (
        hd.get("severity") in ("warning", "hard_fail")
        and not hd.get("insufficient_data", False)
    ):
        recommendations.append(
            "Human disagreement rate increased. Review recent human feedback records "
            "to identify systematic failure patterns before next release."
        )

    # --- Insufficient data notices ---
    insufficient_dims = [
        k for k, v in dim_results.items()
        if v.get("insufficient_data", False)
    ]
    if insufficient_dims:
        dim_list = ", ".join(insufficient_dims)
        recommendations.append(
            f"Insufficient data to evaluate: {dim_list}. "
            "Increase sample size to meet policy minimum_sample_sizes requirements."
        )

    # --- Deterministic mode mismatch ---
    if report_dict.get("determinism_fail"):
        recommendations.insert(
            0,
            "HARD FAIL: Candidate run is non-deterministic but policy requires "
            "deterministic_required=true. Re-run with deterministic mode enabled."
        )

    # --- Fallback if no issues found ---
    if not recommendations:
        recommendations.append(
            "No regressions detected. All dimensions within policy thresholds."
        )

    return recommendations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_DIM_LABELS: Dict[str, str] = {
    "structural_score": "Structural score",
    "semantic_score": "Semantic score",
    "grounding_score": "Grounding score",
    "latency": "Latency",
    "latency_ms": "Latency",
    "human_disagreement": "Human disagreement rate",
}


def _dim_label(dim: str) -> str:
    return _DIM_LABELS.get(dim, dim.replace("_", " ").title())
