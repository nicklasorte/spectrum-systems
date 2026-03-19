"""
Simulation Engine — spectrum_systems/modules/improvement/simulation.py

Implements the AW2 Fix Simulation Sandbox.

This layer sits between:
  AW1 (proposed remediation plans)
  and
  AW  (actual improvement loop)

It takes remediation plans from AW1 and tests their proposed interventions
against controlled evaluation cases in shadow mode — without modifying any
production artifact.

Design principles
-----------------
- Simulation only.  No production artifact is mutated.
- Only ``mapped`` remediation plans may be simulated.
- ``ambiguous`` and ``rejected`` plans produce simulation_status="rejected".
- Results are deterministic: same inputs → same outputs.
- Fail closed: inconclusive results do not advance to AW.
- Full audit trail via simulation_reasons.

Public API
----------
SimulationResult
    In-memory, schema-validated output of one simulation run.

FixSimulator
    Simulates RemediationPlan objects in shadow mode.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import jsonschema

from spectrum_systems.modules.improvement.case_selection import select_cases_for_plan
from spectrum_systems.modules.improvement.simulation_compare import (
    check_regression,
    compare_baseline_candidate,
    determine_promotion_recommendation,
    summarize_targeted_effect,
)
from spectrum_systems.modules.improvement.simulation_strategies import route_strategy

if TYPE_CHECKING:
    from spectrum_systems.modules.improvement.remediation_mapping import RemediationPlan

# ---------------------------------------------------------------------------
# Schema path
# ---------------------------------------------------------------------------

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "schemas"
    / "simulation_result.schema.json"
)

# ---------------------------------------------------------------------------
# Default baseline
# ---------------------------------------------------------------------------

_DEFAULT_BASELINE: Dict[str, Any] = {
    "cases_run": 0,
    "structural_score": 0.70,
    "semantic_score": 0.70,
    "grounding_score": 0.65,
    "latency_ms": 250.0,
}

# ---------------------------------------------------------------------------
# SimulationResult
# ---------------------------------------------------------------------------


class SimulationResult:
    """In-memory representation of one AW2 simulation result.

    Parameters
    ----------
    simulation_id:
        Unique identifier for this simulation result.
    remediation_id:
        ID of the source RemediationPlan.
    cluster_id:
        ID of the source cluster.
    created_at:
        ISO-8601 timestamp.
    simulation_status:
        "passed", "failed", "inconclusive", or "rejected".
    simulation_reasons:
        Auditable reasons for every simulation decision.
    baseline_summary:
        Eval summary dict for the baseline.
    candidate_summary:
        Eval summary dict for the candidate.
    deltas:
        Score deltas (candidate − baseline).
    targeted_effect:
        Analysis of targeted metric effect.
    regression_check:
        Regression gate results.
    promotion_recommendation:
        "promote", "hold", or "reject".
    evidence:
        References to evaluation, observability, and regression artifacts.
    """

    def __init__(
        self,
        *,
        simulation_id: str,
        remediation_id: str,
        cluster_id: str,
        created_at: str,
        simulation_status: str,
        simulation_reasons: List[str],
        baseline_summary: Dict[str, Any],
        candidate_summary: Dict[str, Any],
        deltas: Dict[str, Any],
        targeted_effect: Dict[str, Any],
        regression_check: Dict[str, Any],
        promotion_recommendation: str,
        evidence: Dict[str, Any],
        gating_decision_reason: str = "",
        gating_flags: Optional[List[str]] = None,
    ) -> None:
        self.simulation_id = simulation_id
        self.remediation_id = remediation_id
        self.cluster_id = cluster_id
        self.created_at = created_at
        self.simulation_status = simulation_status
        self.simulation_reasons = simulation_reasons
        self.baseline_summary = baseline_summary
        self.candidate_summary = candidate_summary
        self.deltas = deltas
        self.targeted_effect = targeted_effect
        self.regression_check = regression_check
        self.promotion_recommendation = promotion_recommendation
        self.evidence = evidence
        self.gating_decision_reason = gating_decision_reason
        self.gating_flags: List[str] = gating_flags if gating_flags is not None else []

    # --- Serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "remediation_id": self.remediation_id,
            "cluster_id": self.cluster_id,
            "created_at": self.created_at,
            "simulation_status": self.simulation_status,
            "simulation_reasons": self.simulation_reasons,
            "baseline_summary": self.baseline_summary,
            "candidate_summary": self.candidate_summary,
            "deltas": self.deltas,
            "targeted_effect": self.targeted_effect,
            "regression_check": self.regression_check,
            "promotion_recommendation": self.promotion_recommendation,
            "evidence": self.evidence,
            "gating_decision_reason": self.gating_decision_reason,
            "gating_flags": self.gating_flags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationResult":
        return cls(
            simulation_id=data["simulation_id"],
            remediation_id=data["remediation_id"],
            cluster_id=data["cluster_id"],
            created_at=data["created_at"],
            simulation_status=data["simulation_status"],
            simulation_reasons=data["simulation_reasons"],
            baseline_summary=data["baseline_summary"],
            candidate_summary=data["candidate_summary"],
            deltas=data["deltas"],
            targeted_effect=data["targeted_effect"],
            regression_check=data["regression_check"],
            promotion_recommendation=data["promotion_recommendation"],
            evidence=data["evidence"],
            gating_decision_reason=data.get("gating_decision_reason", ""),
            gating_flags=data.get("gating_flags", []),
        )

    # --- Schema validation ---------------------------------------------------

    def validate_against_schema(self) -> List[str]:
        """Validate this object against the JSON Schema.

        Returns
        -------
        List[str]
            List of validation error messages.  Empty list means valid.
        """
        if not _SCHEMA_PATH.exists():
            return [f"Schema file not found: {_SCHEMA_PATH}"]
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        errors: List[str] = []
        for err in jsonschema.Draft202012Validator(schema).iter_errors(self.to_dict()):
            errors.append(err.message)
        return errors


# ---------------------------------------------------------------------------
# FixSimulator
# ---------------------------------------------------------------------------


class FixSimulator:
    """Simulates RemediationPlan objects against controlled evaluation cases.

    Parameters
    ----------
    golden_dataset:
        List of golden case dicts.  Each must include at least a ``case_id``
        key.
    baseline_summary:
        Optional override for the baseline eval summary.  Defaults to
        ``_DEFAULT_BASELINE``.
    """

    def __init__(
        self,
        golden_dataset: Optional[List[Dict[str, Any]]] = None,
        baseline_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._golden_dataset: List[Dict[str, Any]] = golden_dataset or []
        self._baseline: Dict[str, Any] = dict(baseline_summary or _DEFAULT_BASELINE)

    # --- Public API ----------------------------------------------------------

    def simulate_plan(
        self,
        remediation_plan: "RemediationPlan",
        *,
        cases: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = True,
    ) -> SimulationResult:
        """Simulate one remediation plan in shadow mode.

        Parameters
        ----------
        remediation_plan:
            The ``RemediationPlan`` to simulate.
        cases:
            Optional override for the golden dataset used in this simulation.
        deterministic:
            If True, uses fixed seed logic (currently always True; parameter
            reserved for future use).

        Returns
        -------
        SimulationResult
            A new SimulationResult.  The remediation plan and all production
            artifacts are not modified.
        """
        dataset = cases if cases is not None else self._golden_dataset

        # Gate: only mapped plans may be simulated
        if remediation_plan.mapping_status != "mapped":
            return self._build_rejected_result(
                remediation_plan,
                reason=(
                    f"plan_gate: mapping_status={remediation_plan.mapping_status!r}; "
                    "only 'mapped' plans may be simulated"
                ),
            )

        # Select evaluation cases for this plan
        case_selection = select_cases_for_plan(
            remediation_plan=remediation_plan,
            golden_dataset=dataset,
        )
        selected_case_ids: List[str] = case_selection["selected_case_ids"]
        reasons: List[str] = list(case_selection["selection_reasons"])

        # Identify primary proposed action
        if not remediation_plan.proposed_actions:
            return self._build_rejected_result(
                remediation_plan,
                reason="no_proposed_actions: remediation plan has no proposed actions",
            )

        primary_idx = min(
            remediation_plan.primary_proposal_index,
            len(remediation_plan.proposed_actions) - 1,
        )
        proposed_action = remediation_plan.proposed_actions[primary_idx]
        action_type = proposed_action.get("action_type", "")

        reasons.append(
            f"primary_action: index={primary_idx}, action_type={action_type!r}, "
            f"target_component={proposed_action.get('target_component', 'unknown')!r}"
        )

        # Run strategy
        baseline = dict(self._baseline)
        # Ensure cases_run reflects selection
        baseline["cases_run"] = len(selected_case_ids)

        strategy_result = route_strategy(
            action_type=action_type,
            proposed_action=proposed_action,
            baseline_summary=baseline,
            selected_case_ids=selected_case_ids,
        )

        candidate_summary: Dict[str, Any] = strategy_result["candidate_summary"]
        candidate_summary["cases_run"] = len(selected_case_ids)
        strategy_notes: List[str] = strategy_result["strategy_notes"]
        simulation_fidelity: str = strategy_result["simulation_fidelity"]

        reasons.extend(strategy_notes)
        reasons.append(f"simulation_fidelity: {simulation_fidelity!r}")

        # Compare baseline vs candidate
        deltas = compare_baseline_candidate(baseline, candidate_summary)
        targeted_effect = summarize_targeted_effect(proposed_action, deltas, action_type)
        regression_check = check_regression(baseline, candidate_summary)

        reasons.append(
            f"targeted_effect: metric={targeted_effect['target_metric']!r}, "
            f"expected={targeted_effect['expected_direction']!r}, "
            f"observed={targeted_effect['observed_direction']!r}"
        )
        reasons.append(
            f"regression_check: overall_pass={regression_check['overall_pass']}, "
            f"hard_failures={regression_check['hard_failures']}, "
            f"warnings={regression_check['warnings']}"
        )

        # Determine promotion recommendation
        gating_result = determine_promotion_recommendation(
            simulation_fidelity=simulation_fidelity,
            targeted_effect=targeted_effect,
            regression_check=regression_check,
            deltas=deltas,
            candidate_summary=candidate_summary,
        )
        promotion_recommendation = gating_result["recommendation"]
        gating_decision_reason = gating_result["gating_decision_reason"]
        gating_flags = gating_result["gating_flags"]
        reasons.append(f"promotion_recommendation: {promotion_recommendation!r}")
        reasons.append(f"gating_decision_reason: {gating_decision_reason!r}")

        # Determine simulation_status
        simulation_status = _derive_simulation_status(
            simulation_fidelity=simulation_fidelity,
            regression_check=regression_check,
            targeted_effect=targeted_effect,
            promotion_recommendation=promotion_recommendation,
        )
        reasons.append(f"simulation_status: {simulation_status!r}")

        evidence: Dict[str, Any] = {
            "eval_result_refs": [f"case:{cid}" for cid in selected_case_ids],
            "observability_refs": [],
        }

        return SimulationResult(
            simulation_id=str(uuid.uuid4()),
            remediation_id=remediation_plan.remediation_id,
            cluster_id=remediation_plan.cluster_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            simulation_status=simulation_status,
            simulation_reasons=reasons,
            baseline_summary=baseline,
            candidate_summary=candidate_summary,
            deltas=deltas,
            targeted_effect=targeted_effect,
            regression_check=regression_check,
            promotion_recommendation=promotion_recommendation,
            evidence=evidence,
            gating_decision_reason=gating_decision_reason,
            gating_flags=gating_flags,
        )

    def simulate_many(
        self,
        remediation_plans: List["RemediationPlan"],
        *,
        cases: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = True,
    ) -> List[SimulationResult]:
        """Simulate a list of remediation plans.

        Parameters
        ----------
        remediation_plans:
            All ``RemediationPlan`` objects to simulate.
        cases:
            Optional override for the golden dataset.
        deterministic:
            Reserved for future use.

        Returns
        -------
        List[SimulationResult]
            One result per input plan, in the same order.
        """
        return [
            self.simulate_plan(plan, cases=cases, deterministic=deterministic)
            for plan in remediation_plans
        ]

    # --- Private helpers -----------------------------------------------------

    def _build_rejected_result(
        self,
        remediation_plan: "RemediationPlan",
        reason: str,
    ) -> SimulationResult:
        """Build a rejected simulation result for a plan that cannot be simulated."""
        baseline = dict(self._baseline)
        baseline["cases_run"] = 0
        candidate = dict(baseline)

        return SimulationResult(
            simulation_id=str(uuid.uuid4()),
            remediation_id=remediation_plan.remediation_id,
            cluster_id=remediation_plan.cluster_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            simulation_status="rejected",
            simulation_reasons=[reason],
            baseline_summary=baseline,
            candidate_summary=candidate,
            deltas={
                "structural_score_delta": 0.0,
                "semantic_score_delta": 0.0,
                "grounding_score_delta": 0.0,
                "latency_ms_delta": 0.0,
            },
            targeted_effect={
                "target_component": "unknown",
                "target_metric": "structural_score",
                "expected_direction": "increase",
                "observed_direction": "none",
            },
            regression_check={
                "overall_pass": True,
                "hard_failures": 0,
                "warnings": 0,
            },
            promotion_recommendation="reject",
            evidence={"eval_result_refs": [], "observability_refs": []},
            gating_decision_reason="insufficient_signal",
            gating_flags=["insufficient_signal"],
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _derive_simulation_status(
    *,
    simulation_fidelity: str,
    regression_check: Dict[str, Any],
    targeted_effect: Dict[str, Any],
    promotion_recommendation: str,
) -> str:
    """Derive simulation_status from outcome components."""
    if simulation_fidelity == "none":
        return "rejected"

    hard_failures = regression_check.get("hard_failures", 0)
    if hard_failures > 0:
        return "failed"

    expected = targeted_effect.get("expected_direction", "increase")
    observed = targeted_effect.get("observed_direction", "none")
    _opposites = {"increase": "decrease", "decrease": "increase"}
    if observed == _opposites.get(expected):
        return "failed"

    if observed == "none" and simulation_fidelity == "low":
        return "inconclusive"

    if promotion_recommendation == "promote":
        return "passed"
    if promotion_recommendation == "hold":
        return "inconclusive"

    return "failed"
