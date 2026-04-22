"""Phase 4.4: Signal Definitions & Clarity

All control signals defined with units, targets, acceptable ranges,
and unambiguous human-readable interpretations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class SignalDefinition:
    """Immutable definition of a system signal."""

    name: str
    unit: str
    target: float
    acceptable_range: Tuple[float, float]
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "target": self.target,
            "acceptable_range": list(self.acceptable_range),
            "interpretation": self.interpretation,
        }

    def is_in_range(self, value: float) -> bool:
        lo, hi = self.acceptable_range
        return lo <= value <= hi


SIGNAL_DEFINITIONS: Dict[str, SignalDefinition] = {
    "eval_pass_rate": SignalDefinition(
        name="Evaluation Pass Rate",
        unit="%",
        target=95.0,
        acceptable_range=(85.0, 100.0),
        interpretation=(
            "Percentage of evaluations passing the quality threshold. "
            "Below 85% triggers a control freeze."
        ),
    ),
    "signal_latency": SignalDefinition(
        name="Signal Latency",
        unit="ms",
        target=50.0,
        acceptable_range=(0.0, 200.0),
        interpretation=(
            "Time from event to control signal dispatch. "
            "Must stay below 200ms for real-time feedback guarantees."
        ),
    ),
    "drift_rate": SignalDefinition(
        name="Drift Rate",
        unit="divergences/1000 runs",
        target=0.0,
        acceptable_range=(0.0, 2.0),
        interpretation=(
            "Rate at which artifact outputs diverge across replays. "
            "Zero means fully deterministic; above 2 blocks promotion."
        ),
    ),
    "lineage_completeness": SignalDefinition(
        name="Lineage Completeness",
        unit="%",
        target=100.0,
        acceptable_range=(95.0, 100.0),
        interpretation=(
            "Percentage of artifacts whose full input→output lineage is recorded. "
            "Below 95% blocks promotion."
        ),
    ),
}


def get_signal_definition(signal_name: str) -> SignalDefinition:
    """Return the definition for a named signal. Raises ValueError if unknown."""
    if signal_name not in SIGNAL_DEFINITIONS:
        raise ValueError(
            f"Unknown signal '{signal_name}'. "
            f"Defined signals: {sorted(SIGNAL_DEFINITIONS)}"
        )
    return SIGNAL_DEFINITIONS[signal_name]


def get_signal_interpretation(signal_name: str) -> str:
    """Return human-readable interpretation for a named signal."""
    return get_signal_definition(signal_name).interpretation
