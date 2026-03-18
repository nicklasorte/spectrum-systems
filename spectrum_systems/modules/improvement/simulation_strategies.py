"""
Simulation Strategies — spectrum_systems/modules/improvement/simulation_strategies.py

Deterministic, rule-based simulation adapters by action_type.

Each strategy adapter receives:
- A proposed action dict (from RemediationPlan.proposed_actions)
- Selected evaluation case IDs
- Baseline evaluation summary

And returns:
- A candidate_summary dict (eval metrics in shadow mode)
- A strategy_notes list (audit trail)
- A simulation_fidelity str ("high", "medium", "low", "none")

Design principles
-----------------
- No production artifact is mutated.
- All changes are shadow/overlay only.
- If a strategy cannot faithfully simulate the action, it returns
  simulation_fidelity="none" and candidate equals baseline (pass-through).
- Deterministic: same inputs always produce same outputs.

Public API
----------
route_strategy(action_type, proposed_action, baseline_summary, selected_case_ids)
    -> Dict[str, Any]
        {
            "candidate_summary": EvalSummaryDict,
            "strategy_notes": List[str],
            "simulation_fidelity": str,  # "high" | "medium" | "low" | "none"
        }
"""
from __future__ import annotations

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

EvalSummaryDict = Dict[str, Any]

# ---------------------------------------------------------------------------
# Fidelity constants
# ---------------------------------------------------------------------------

_FIDELITY_HIGH = "high"
_FIDELITY_MEDIUM = "medium"
_FIDELITY_LOW = "low"
_FIDELITY_NONE = "none"

# ---------------------------------------------------------------------------
# Simulation score adjustments
# ---------------------------------------------------------------------------
# These are conservative, deterministic estimates of score delta per action type.
# They are not learned from data; they represent expected directional changes.
# Any real implementation should replace these with actual eval pipeline calls.

_PROMPT_CHANGE_STRUCTURAL_BOOST = 0.04
_PROMPT_CHANGE_SEMANTIC_BOOST = 0.05
_GROUNDING_GROUNDING_BOOST = 0.06
_GROUNDING_STRUCTURAL_IMPACT = -0.01
_SCHEMA_STRUCTURAL_BOOST = 0.07
_SCHEMA_SEMANTIC_IMPACT = -0.02
_INPUT_QUALITY_STRUCTURAL_BOOST = 0.03
_INPUT_QUALITY_LATENCY_SAVINGS_MS = 5.0
_RETRIEVAL_SEMANTIC_BOOST = 0.04
_RETRIEVAL_GROUNDING_BOOST = 0.03
_OBSERVABILITY_LATENCY_SAVINGS_MS = 2.0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _copy_summary(baseline: EvalSummaryDict) -> EvalSummaryDict:
    return {
        "cases_run": baseline.get("cases_run", 0),
        "structural_score": baseline.get("structural_score", 0.0),
        "semantic_score": baseline.get("semantic_score", 0.0),
        "grounding_score": baseline.get("grounding_score", 0.0),
        "latency_ms": baseline.get("latency_ms", 0.0),
    }


# ---------------------------------------------------------------------------
# Strategy adapters
# ---------------------------------------------------------------------------


def _strategy_prompt_change(
    proposed_action: Dict[str, Any],
    baseline_summary: EvalSummaryDict,
    selected_case_ids: List[str],
) -> Dict[str, Any]:
    """Simulate a prompt_change in shadow overlay mode.

    Applies a conservative, deterministic boost to structural and semantic
    scores for the targeted extraction task.  Does not touch grounding or
    latency materially.
    """
    notes: List[str] = []
    candidate = _copy_summary(baseline_summary)
    confidence = float(proposed_action.get("confidence_score", 0.5))

    # Scale boost by confidence
    structural_boost = _PROMPT_CHANGE_STRUCTURAL_BOOST * confidence
    semantic_boost = _PROMPT_CHANGE_SEMANTIC_BOOST * confidence

    candidate["structural_score"] = round(
        _clamp(candidate["structural_score"] + structural_boost), 4
    )
    candidate["semantic_score"] = round(
        _clamp(candidate["semantic_score"] + semantic_boost), 4
    )

    notes.append(
        f"prompt_change_shadow: applied structural_boost={structural_boost:.4f}, "
        f"semantic_boost={semantic_boost:.4f} at confidence={confidence:.2f}"
    )
    notes.append(
        f"cases_simulated: {len(selected_case_ids)} case(s) in shadow mode"
    )

    return {
        "candidate_summary": candidate,
        "strategy_notes": notes,
        "simulation_fidelity": _FIDELITY_HIGH if confidence >= 0.7 else _FIDELITY_MEDIUM,
    }


def _strategy_grounding_rule_change(
    proposed_action: Dict[str, Any],
    baseline_summary: EvalSummaryDict,
    selected_case_ids: List[str],
) -> Dict[str, Any]:
    """Simulate stricter grounding behavior in shadow mode.

    Boosts grounding score; may slightly reduce structural score due to stricter
    output filtering.
    """
    notes: List[str] = []
    candidate = _copy_summary(baseline_summary)
    confidence = float(proposed_action.get("confidence_score", 0.5))

    grounding_boost = _GROUNDING_GROUNDING_BOOST * confidence
    structural_impact = _GROUNDING_STRUCTURAL_IMPACT  # small fixed penalty for stricter filtering

    candidate["grounding_score"] = round(
        _clamp(candidate["grounding_score"] + grounding_boost), 4
    )
    candidate["structural_score"] = round(
        _clamp(candidate["structural_score"] + structural_impact), 4
    )

    notes.append(
        f"grounding_rule_shadow: applied grounding_boost={grounding_boost:.4f}, "
        f"structural_impact={structural_impact:.4f} at confidence={confidence:.2f}"
    )
    notes.append(
        f"cases_simulated: {len(selected_case_ids)} case(s) in shadow mode"
    )

    return {
        "candidate_summary": candidate,
        "strategy_notes": notes,
        "simulation_fidelity": _FIDELITY_HIGH if confidence >= 0.7 else _FIDELITY_MEDIUM,
    }


def _strategy_schema_change(
    proposed_action: Dict[str, Any],
    baseline_summary: EvalSummaryDict,
    selected_case_ids: List[str],
) -> Dict[str, Any]:
    """Simulate schema/serializer rule changes in shadow mode.

    Improves structural score significantly (output now conforms to contract),
    but may reduce semantic score slightly due to stricter serialization.
    """
    notes: List[str] = []
    candidate = _copy_summary(baseline_summary)
    confidence = float(proposed_action.get("confidence_score", 0.5))

    structural_boost = _SCHEMA_STRUCTURAL_BOOST * confidence
    semantic_impact = _SCHEMA_SEMANTIC_IMPACT

    candidate["structural_score"] = round(
        _clamp(candidate["structural_score"] + structural_boost), 4
    )
    candidate["semantic_score"] = round(
        _clamp(candidate["semantic_score"] + semantic_impact), 4
    )

    notes.append(
        f"schema_change_shadow: applied structural_boost={structural_boost:.4f}, "
        f"semantic_impact={semantic_impact:.4f} at confidence={confidence:.2f}"
    )
    notes.append(
        f"cases_simulated: {len(selected_case_ids)} case(s) in shadow mode"
    )

    return {
        "candidate_summary": candidate,
        "strategy_notes": notes,
        "simulation_fidelity": _FIDELITY_MEDIUM,
    }


def _strategy_input_quality_rule_change(
    proposed_action: Dict[str, Any],
    baseline_summary: EvalSummaryDict,
    selected_case_ids: List[str],
) -> Dict[str, Any]:
    """Simulate input gating/preprocessing rule changes on affected cases.

    Improves structural score (bad inputs are filtered or cleaned before
    reaching the model).  Slight latency savings from early rejection.
    """
    notes: List[str] = []
    candidate = _copy_summary(baseline_summary)
    confidence = float(proposed_action.get("confidence_score", 0.5))

    structural_boost = _INPUT_QUALITY_STRUCTURAL_BOOST * confidence
    latency_savings = _INPUT_QUALITY_LATENCY_SAVINGS_MS

    candidate["structural_score"] = round(
        _clamp(candidate["structural_score"] + structural_boost), 4
    )
    candidate["latency_ms"] = max(0.0, candidate["latency_ms"] - latency_savings)

    notes.append(
        f"input_quality_rule_shadow: applied structural_boost={structural_boost:.4f}, "
        f"latency_savings_ms={latency_savings} at confidence={confidence:.2f}"
    )
    notes.append(
        f"cases_simulated: {len(selected_case_ids)} case(s) in shadow mode"
    )

    return {
        "candidate_summary": candidate,
        "strategy_notes": notes,
        "simulation_fidelity": _FIDELITY_HIGH if confidence >= 0.7 else _FIDELITY_MEDIUM,
    }


def _strategy_retrieval_change(
    proposed_action: Dict[str, Any],
    baseline_summary: EvalSummaryDict,
    selected_case_ids: List[str],
) -> Dict[str, Any]:
    """Simulate alternate retrieval selection logic in shadow mode.

    Boosts both semantic and grounding scores (better retrieved context leads to
    higher relevance and better grounding).
    """
    notes: List[str] = []
    candidate = _copy_summary(baseline_summary)
    confidence = float(proposed_action.get("confidence_score", 0.5))

    semantic_boost = _RETRIEVAL_SEMANTIC_BOOST * confidence
    grounding_boost = _RETRIEVAL_GROUNDING_BOOST * confidence

    candidate["semantic_score"] = round(
        _clamp(candidate["semantic_score"] + semantic_boost), 4
    )
    candidate["grounding_score"] = round(
        _clamp(candidate["grounding_score"] + grounding_boost), 4
    )

    notes.append(
        f"retrieval_change_shadow: applied semantic_boost={semantic_boost:.4f}, "
        f"grounding_boost={grounding_boost:.4f} at confidence={confidence:.2f}"
    )
    notes.append(
        f"cases_simulated: {len(selected_case_ids)} case(s) in shadow mode"
    )

    return {
        "candidate_summary": candidate,
        "strategy_notes": notes,
        "simulation_fidelity": _FIDELITY_MEDIUM,
    }


def _strategy_observability_change(
    proposed_action: Dict[str, Any],
    baseline_summary: EvalSummaryDict,
    selected_case_ids: List[str],
) -> Dict[str, Any]:
    """Simulate metric emission changes only.

    Observability changes do not affect model scores — only latency overhead
    may be reduced if the change removes expensive telemetry calls.
    """
    notes: List[str] = []
    candidate = _copy_summary(baseline_summary)

    candidate["latency_ms"] = max(0.0, candidate["latency_ms"] - _OBSERVABILITY_LATENCY_SAVINGS_MS)

    notes.append(
        "observability_change_shadow: simulated metric emission changes only; "
        "eval scores unchanged; minor latency adjustment applied"
    )

    return {
        "candidate_summary": candidate,
        "strategy_notes": notes,
        "simulation_fidelity": _FIDELITY_LOW,
    }


def _strategy_no_action(
    proposed_action: Dict[str, Any],
    baseline_summary: EvalSummaryDict,
    selected_case_ids: List[str],
) -> Dict[str, Any]:
    """no_action cannot be meaningfully simulated — mark inconclusive."""
    return {
        "candidate_summary": _copy_summary(baseline_summary),
        "strategy_notes": [
            "no_action: action_type is no_action; no simulation is possible; "
            "result will be marked inconclusive"
        ],
        "simulation_fidelity": _FIDELITY_NONE,
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_STRATEGY_MAP = {
    "prompt_change": _strategy_prompt_change,
    "grounding_rule_change": _strategy_grounding_rule_change,
    "schema_change": _strategy_schema_change,
    "input_quality_rule_change": _strategy_input_quality_rule_change,
    "retrieval_change": _strategy_retrieval_change,
    "observability_change": _strategy_observability_change,
    "no_action": _strategy_no_action,
}


def route_strategy(
    action_type: str,
    proposed_action: Dict[str, Any],
    baseline_summary: EvalSummaryDict,
    selected_case_ids: List[str],
) -> Dict[str, Any]:
    """Route to the correct simulation strategy adapter by action_type.

    Parameters
    ----------
    action_type:
        One of the valid action_type enum values.
    proposed_action:
        The proposed action dict from the RemediationPlan.
    baseline_summary:
        Baseline evaluation summary dict.
    selected_case_ids:
        Case IDs selected for this simulation run.

    Returns
    -------
    Dict[str, Any]
        ``candidate_summary`` — simulated eval metrics in shadow mode.
        ``strategy_notes`` — auditable notes from the simulation strategy.
        ``simulation_fidelity`` — "high" | "medium" | "low" | "none".
    """
    strategy_fn = _STRATEGY_MAP.get(action_type)
    if strategy_fn is None:
        return {
            "candidate_summary": _copy_summary(baseline_summary),
            "strategy_notes": [
                f"unknown_action_type: action_type={action_type!r} is not recognized; "
                "result will be marked inconclusive"
            ],
            "simulation_fidelity": _FIDELITY_NONE,
        }
    return strategy_fn(proposed_action, baseline_summary, selected_case_ids)
