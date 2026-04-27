"""SLO/CDE: Control signal minimality audit (NT-16..18).

Audit SLO/CDE control inputs to confirm only hard trust signals can drive
``freeze`` / ``block``. Observation-only signals (dashboard freshness, count
metrics, report volume, non-critical trend notes, advisory recommendations,
cosmetic formatting) must not gate promotion unless explicitly promoted by
policy.

Hard trust signals are declared canonically in
``spectrum_systems/modules/runtime/slo_budget_gate.py::HARD_TRUST_SIGNALS``
and extended here with the additional NT-ALL-01 hard signals (artifact tier
validity, trust artifact freshness). This module reports a validation
result; canonical owners (CDE/SEL) consume it.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from spectrum_systems.modules.runtime.slo_budget_gate import HARD_TRUST_SIGNALS


# NT-16: extend the recognized hard-trust signal set with NT-ALL-01 inputs.
HARD_TRUST_SIGNALS_NT = tuple(HARD_TRUST_SIGNALS) + (
    "artifact_tier_validity_status",
    "trust_artifact_freshness_status",
)


# Signals that must NOT drive freeze/block. Adding to this list is a
# governance change — observations can warn/report only.
OBSERVATION_ONLY_SIGNALS = (
    "dashboard_freshness",
    "report_count",
    "report_volume",
    "non_critical_trend_note",
    "advisory_recommendation",
    "cosmetic_proof_formatting",
    "ui_render_time",
    "metric_count_drift",
)


CANONICAL_CONTROL_SIGNAL_MINIMALITY_REASON_CODES = (
    "CONTROL_SIGNAL_MINIMALITY_OK",
    "CONTROL_SIGNAL_OBSERVATION_USED_AS_HARD",
)


class ControlSignalMinimalityError(ValueError):
    """Raised when control signal minimality audit cannot be performed."""


def validate_control_signal_minimality(
    *,
    hard_signals_observed: Mapping[str, Any],
    observation_signals: Optional[Mapping[str, Any]] = None,
    blocking_signal_keys: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Validate that block/freeze inputs draw only from hard trust signals.

    Parameters
    ----------
    hard_signals_observed:
        The map of hard-trust signals observed by the caller. Keys MUST be
        in ``HARD_TRUST_SIGNALS_NT``. Any other key is rejected.
    observation_signals:
        Optional map of observation-only signals captured for reporting.
        These are tagged advisory and never block.
    blocking_signal_keys:
        Optional iterable naming signals that the caller proposes to use
        as block/freeze drivers. Used to detect observation hijack: if any
        named key is an observation-only signal, the audit blocks.

    Returns
    -------
    {"decision": "allow" | "block",
     "reason_code": canonical,
     "blocking_reasons": [str, ...],
     "hard_signals_admitted": [str, ...],
     "observations_admitted": [str, ...],
     "rejected_keys": [str, ...]}
    """
    if not isinstance(hard_signals_observed, Mapping):
        raise ControlSignalMinimalityError(
            "hard_signals_observed must be a mapping"
        )

    hard_set = set(HARD_TRUST_SIGNALS_NT)
    obs_set = set(OBSERVATION_ONLY_SIGNALS)

    rejected: List[str] = []
    admitted_hard: List[str] = []
    for key in hard_signals_observed:
        if key in hard_set:
            admitted_hard.append(key)
        else:
            rejected.append(key)

    blocking: List[str] = []
    if rejected:
        blocking.append(
            f"non-hard signals supplied to hard-signal slot: {sorted(rejected)}"
        )

    proposed_blockers = list(blocking_signal_keys or [])
    obs_used_as_hard = sorted(set(proposed_blockers) & obs_set)
    if obs_used_as_hard:
        blocking.append(
            f"observation-only signals used as block/freeze drivers: "
            f"{obs_used_as_hard}"
        )

    # Observation signals are recorded for reporting only.
    obs_admitted = sorted((observation_signals or {}).keys())

    decision = "block" if blocking else "allow"
    reason_code = (
        "CONTROL_SIGNAL_OBSERVATION_USED_AS_HARD"
        if blocking
        else "CONTROL_SIGNAL_MINIMALITY_OK"
    )

    return {
        "artifact_type": "control_signal_minimality_audit",
        "schema_version": "1.0.0",
        "decision": decision,
        "reason_code": reason_code,
        "blocking_reasons": blocking,
        "hard_signals_admitted": sorted(admitted_hard),
        "observations_admitted": obs_admitted,
        "rejected_keys": sorted(rejected),
    }


def list_hard_trust_signals() -> List[str]:
    """Read-only accessor for the hard-trust signal set used by NT-ALL-01."""
    return list(HARD_TRUST_SIGNALS_NT)


def list_observation_only_signals() -> List[str]:
    """Read-only accessor for observation-only signal names."""
    return list(OBSERVATION_ONLY_SIGNALS)


__all__ = [
    "CANONICAL_CONTROL_SIGNAL_MINIMALITY_REASON_CODES",
    "ControlSignalMinimalityError",
    "HARD_TRUST_SIGNALS_NT",
    "OBSERVATION_ONLY_SIGNALS",
    "list_hard_trust_signals",
    "list_observation_only_signals",
    "validate_control_signal_minimality",
]
