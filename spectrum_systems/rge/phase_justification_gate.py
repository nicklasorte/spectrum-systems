"""RGE Phase Justification Gate - Principle 1: Kill Complexity Early.

Every proposed roadmap phase must declare:
  - failure_prevented: what specific failure this prevents
  - signal_improved: what measurable signal this improves (must have a metric)
  - loop_leg: which canonical loop leg this strengthens

Phases failing any check raise PhaseJustificationError (fail-closed).
Emits phase_justification_record for every gate decision.
Deletion phases are first-class citizens and must also justify themselves.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from spectrum_systems.contracts import validate_artifact

CANONICAL_LOOP_LEGS = frozenset({
    "AEX", "PQX", "EVL", "TPA", "CDE", "SEL",
    "REP", "LIN", "OBS", "SLO",
})

_VAGUE_TERMS = frozenset({
    "improve things", "make better", "help with", "address issues",
    "various", "misc", "other", "general", "some things", "generally",
})

_MEASURABLE_MARKERS = [
    "%", "rate", "count", "score", "latency", "time", "budget",
    "coverage", "threshold", "ms", "seconds", "per day", "per week",
    "per run", "/day", "/week", "points", "bps",
]


class PhaseJustificationError(ValueError):
    """Raised when a phase fails the justification gate. Always fail-closed."""


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"PJR-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def _is_vague(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in _VAGUE_TERMS)


def _is_measurable(text: str) -> bool:
    lower = text.lower()
    if any(ch.isdigit() for ch in text):
        return True
    return any(m in lower for m in _MEASURABLE_MARKERS)


def validate_phase_justification(
    phase: dict[str, Any],
    *,
    run_id: str,
    trace_id: str,
) -> dict[str, Any]:
    """Gate a proposed phase against Principle 1.

    Args:
        phase: must contain phase_id, name, failure_prevented,
               signal_improved, loop_leg
        run_id: run identifier for lineage
        trace_id: trace identifier for lineage

    Returns:
        phase_justification_record (schema-validated)

    Raises:
        PhaseJustificationError: on any justification failure (fail-closed)
    """
    phase_id = str(phase.get("phase_id", "")).strip()
    name = str(phase.get("name", "")).strip()
    failure_prevented = str(phase.get("failure_prevented", "")).strip()
    signal_improved = str(phase.get("signal_improved", "")).strip()
    loop_leg = str(phase.get("loop_leg", "")).strip().upper()

    errors: list[str] = []

    if not failure_prevented:
        errors.append(
            "failure_prevented: missing - every phase must declare what failure it prevents"
        )
    elif len(failure_prevented) < 15:
        errors.append(
            f"failure_prevented: too vague ('{failure_prevented}') - "
            "be specific about the failure mode"
        )
    elif _is_vague(failure_prevented):
        errors.append(
            f"failure_prevented: vague language ('{failure_prevented}') - "
            "name the specific failure mode"
        )

    if not signal_improved:
        errors.append(
            "signal_improved: missing - every phase must declare what measurable signal it improves"
        )
    elif not _is_measurable(signal_improved):
        errors.append(
            f"signal_improved: not measurable ('{signal_improved}') - "
            "must reference a rate, count, score, latency, budget, coverage, or threshold"
        )

    if not loop_leg:
        errors.append(
            "loop_leg: missing - declare which canonical loop leg this strengthens "
            f"(one of: {sorted(CANONICAL_LOOP_LEGS)})"
        )
    elif loop_leg not in CANONICAL_LOOP_LEGS:
        errors.append(
            f"loop_leg: '{loop_leg}' is not a canonical loop leg - "
            f"must be one of: {sorted(CANONICAL_LOOP_LEGS)}"
        )

    decision = "block" if errors else "allow"

    record = {
        "artifact_type": "phase_justification_record",
        "schema_version": "1.0.0",
        "record_id": _stable_id({"phase_id": phase_id, "run_id": run_id}),
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": _utc_now(),
        "phase_id": phase_id,
        "phase_name": name,
        "decision": decision,
        "failure_prevented": failure_prevented,
        "signal_improved": signal_improved,
        "loop_leg": loop_leg,
        "errors": errors,
        "principle": "kill_complexity_early",
    }

    validate_artifact(record, "phase_justification_record")

    if errors:
        bullets = "\n".join(f"  - {e}" for e in errors)
        raise PhaseJustificationError(
            f"Phase '{name}' ({phase_id}) blocked by Principle 1 - justification gate:\n{bullets}"
        )

    return record
