"""
Simulation Pipeline — spectrum_systems/modules/improvement/simulation_pipeline.py

Orchestrates the AW2 Fix Simulation Sandbox end-to-end pipeline:

  1. Accept remediation plans from AW1.
  2. Filter to only ``mapped`` plans (others are immediately rejected).
  3. Simulate each mapped plan via FixSimulator.
  4. Produce a structured summary of outcomes.

Public API
----------
run_simulation_for_plan(remediation_plan, golden_dataset, baseline_summary)
    -> SimulationResult

run_simulation_batch(remediation_plans, golden_dataset, baseline_summary)
    -> List[SimulationResult]

summarize_simulation_outcomes(results)
    -> Dict[str, Any]
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from spectrum_systems.modules.improvement.simulation import FixSimulator, SimulationResult

if TYPE_CHECKING:
    from spectrum_systems.modules.improvement.remediation_mapping import RemediationPlan


# ---------------------------------------------------------------------------
# Pipeline functions
# ---------------------------------------------------------------------------


def run_simulation_for_plan(
    remediation_plan: "RemediationPlan",
    golden_dataset: Optional[List[Dict[str, Any]]] = None,
    baseline_summary: Optional[Dict[str, Any]] = None,
) -> SimulationResult:
    """Simulate a single remediation plan.

    Parameters
    ----------
    remediation_plan:
        The ``RemediationPlan`` to simulate.
    golden_dataset:
        List of golden case dicts for case selection.
    baseline_summary:
        Optional baseline eval summary override.

    Returns
    -------
    SimulationResult
        The simulation result for this plan.
    """
    simulator = FixSimulator(
        golden_dataset=golden_dataset or [],
        baseline_summary=baseline_summary,
    )
    return simulator.simulate_plan(remediation_plan)


def run_simulation_batch(
    remediation_plans: List["RemediationPlan"],
    golden_dataset: Optional[List[Dict[str, Any]]] = None,
    baseline_summary: Optional[Dict[str, Any]] = None,
) -> List[SimulationResult]:
    """Simulate a batch of remediation plans.

    Parameters
    ----------
    remediation_plans:
        All ``RemediationPlan`` objects to simulate.
    golden_dataset:
        List of golden case dicts for case selection.
    baseline_summary:
        Optional baseline eval summary override.

    Returns
    -------
    List[SimulationResult]
        One result per input plan, in the same order.
    """
    simulator = FixSimulator(
        golden_dataset=golden_dataset or [],
        baseline_summary=baseline_summary,
    )
    return simulator.simulate_many(remediation_plans)


def summarize_simulation_outcomes(
    results: List[SimulationResult],
) -> Dict[str, Any]:
    """Produce a structured summary of simulation outcomes.

    Parameters
    ----------
    results:
        All SimulationResult objects to summarize.

    Returns
    -------
    Dict[str, Any]
        Summary dict with counts, promotable/held/rejected plans, top
        targeted improvements, and top regressions detected.
    """
    status_counter: Counter[str] = Counter(r.simulation_status for r in results)
    recommendation_counter: Counter[str] = Counter(
        r.promotion_recommendation for r in results
    )

    promotable: List[Dict[str, Any]] = []
    held: List[Dict[str, Any]] = []
    rejected_results: List[Dict[str, Any]] = []
    top_improvements: List[Dict[str, Any]] = []
    top_regressions: List[Dict[str, Any]] = []

    for result in results:
        entry = _result_summary_entry(result)
        rec = result.promotion_recommendation
        if rec == "promote":
            promotable.append(entry)
        elif rec == "hold":
            held.append(entry)
        else:
            rejected_results.append(entry)

        # Collect targeted improvements
        te = result.targeted_effect
        if te.get("observed_direction") == te.get("expected_direction"):
            top_improvements.append(
                {
                    "remediation_id": result.remediation_id,
                    "target_component": te.get("target_component"),
                    "target_metric": te.get("target_metric"),
                    "delta": result.deltas.get(f"{te.get('target_metric')}_delta", 0.0),
                }
            )

        # Collect regressions
        rc = result.regression_check
        if rc.get("hard_failures", 0) > 0 or rc.get("warnings", 0) > 0:
            top_regressions.append(
                {
                    "remediation_id": result.remediation_id,
                    "hard_failures": rc.get("hard_failures", 0),
                    "warnings": rc.get("warnings", 0),
                    "simulation_status": result.simulation_status,
                }
            )

    # Sort improvements by delta magnitude descending
    top_improvements.sort(key=lambda x: -abs(float(x.get("delta", 0.0))))

    # Sort regressions by hard_failures descending
    top_regressions.sort(key=lambda x: (-x.get("hard_failures", 0), -x.get("warnings", 0)))

    return {
        "total_results": len(results),
        "by_status": dict(status_counter),
        "by_recommendation": dict(recommendation_counter),
        "promotable_plans": promotable,
        "held_plans": held,
        "rejected_plans": rejected_results,
        "top_targeted_improvements": top_improvements[:10],
        "top_regressions_detected": top_regressions[:10],
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _result_summary_entry(result: SimulationResult) -> Dict[str, Any]:
    """Build a compact summary entry for a SimulationResult."""
    te = result.targeted_effect
    return {
        "simulation_id": result.simulation_id,
        "remediation_id": result.remediation_id,
        "cluster_id": result.cluster_id,
        "simulation_status": result.simulation_status,
        "promotion_recommendation": result.promotion_recommendation,
        "target_component": te.get("target_component"),
        "target_metric": te.get("target_metric"),
        "observed_direction": te.get("observed_direction"),
        "hard_failures": result.regression_check.get("hard_failures", 0),
        "warnings": result.regression_check.get("warnings", 0),
    }
